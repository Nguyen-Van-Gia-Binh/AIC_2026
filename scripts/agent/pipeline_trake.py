"""
pipeline_trake.py — Pipeline TRAKE: Retrieve video + Windowed Alignment.

Workflow cố định 2 giai đoạn (không để LLM tự quyết định số bước):

Giai doan 1 - Multi-Event Coverage Pooling (BAN DAC TA §5.1):
  rewrite global query VA ca N event query
  -> fast_retrieve(top_k=RETRIEVAL_POOL_SIZE) cho global query + cho TỪNG event
  -> Video_Score(V) = Sim_global(V) + sum_i max_{f in V} Sim(e_i, f)
  -> xếp theo (số mốc video có mặt trong pool, tổng điểm) -> top_k_video candidate (mặc định 100)
  Ý nghĩa: video "phủ" đủ cả N mốc thắng video chỉ trùng bối cảnh chung — đúng điều TRAKE cần.

Giai doan 2 - Strict Monotonic DP (§5.2):
  For mỗi video candidate:
    For mỗi event_i: fast_retrieve_for_video(event_query_i, video_id, top_k=top_k_frame)
    -> DP tìm chuỗi 1 frame/event có frame_idx TĂNG NGHIÊM NGẶT (f_1 < ... < f_N), tổng score max
    -> video không tồn tại chuỗi hợp lệ bị LOẠI hoàn toàn
    -> trake_score = trung bình score các event trong chuỗi

Giai doan 3 - Gated Multi-Modal Verification (§5.3):
  Cổng 1 (rule, miễn phí, chạy cho TẤT CẢ candidate): độ khớp từ khoá Objects JSON từng frame trong
    chuỗi vs mô tả event -> rule_score -> score = trake_score + RULE_GATE_WEIGHT * rule_score
  Cổng 2 (LLM, đắt): CHỈ mở khi chênh lệch #1-#2 <= GATE_MARGIN (0.02) -> hỏi LLM plausibility cho
    top GATE_MAX_VIDEOS video (objects + transcript từng frame) -> cộng LLM_SCORE_WEIGHT * llm_score
  -> Sắp xếp lại theo final_score -> chọn video tốt nhất

Output: list[dict] {video_id, frame_id_1, ..., frame_id_N}
"""
from __future__ import annotations

import sys
import re
from pathlib import Path
from collections import defaultdict


_ROOT = Path(__file__).resolve().parent.parent.parent  # repo root — cho `import scripts.*`
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.config import call_llm
from scripts.agent.tools.retrieve import fast_retrieve, fast_retrieve_for_video
from scripts.agent.tools.rewrite import rewrite_query
from scripts.agent.tools.rerank import RETRIEVAL_POOL_SIZE
from scripts.agent.tools.objects_lookup import get_objects
from scripts.agent.tools.trake_align import find_best_increasing_chain, rule_plausibility
from scripts.agent.tools.asr_lookup import get_transcript
from scripts.agent.tools.run_trace import NULL_TRACE, RunTrace


# Trọng số của điểm LLM crosscheck (0.0-1.0) khi cộng vào trake_score (trung bình cosine similarity,
# cùng thang đo với rerank.MARGIN_THRESHOLD ~0.012) để ra final_score dùng để rank. Điểm khởi đầu, sẽ
# tinh chỉnh khi có benchmark rộng hơn (xem PLAN.md "Blockers").
LLM_SCORE_WEIGHT = 0.05

# Điểm trung lập khi LLM crosscheck lỗi hoặc không parse được — không làm lệch ranking so với trake_score.
DEFAULT_LLM_CROSSCHECK_SCORE = 0.5

# Trọng số của "cổng nhanh" rule-based (độ khớp từ khoá giữa Objects JSON từng frame trong chuỗi và
# mô tả event) — chạy cho TẤT CẢ video candidate vì không tốn API call (BẢN ĐẶC TẢ §5.3).
RULE_GATE_WEIGHT = 0.03

# Chỉ kích hoạt cổng LLM/VLM (đắt, chậm) khi chênh lệch điểm giữa video #1 và #2 nhỏ hơn ngưỡng này —
# khi 1 video đã thắng cách biệt thì LLM gần như không thể đổi thứ tự, chỉ tốn tiền (§5.3).
GATE_MARGIN = 0.02

# Số video được đưa qua cổng LLM khi cổng được kích hoạt (§5.3 "Top 2-3").
GATE_MAX_VIDEOS = 3

_SCORE_RE = re.compile(r"SCORE:\s*(-?\d+(?:\.\d+)?)", re.IGNORECASE)

TRAKE_CROSSCHECK_PROMPT = """\
You are verifying whether a candidate sequence of video frames matches a described sequence of events.

Overall scene: {query}

Events in order, with evidence found in each candidate frame:
{events_block}

Rate how well this evidence (detected objects + spoken transcript) supports that the frames truly show \
this sequence of events, in order. Detected objects and transcript may be incomplete or noisy — judge \
based on overall plausibility, not on requiring every event to have full evidence.

Reply with exactly one line in the form: SCORE: <a number between 0.00 and 1.00>"""


def _llm_crosscheck_chain(query_en: str, event_queries_en: list[str], chain: list[dict]) -> float:
    """Gọi LLM 1 lần để đánh giá plausibility của cả chain (object + transcript mỗi frame) so với
    chuỗi event mô tả — thay cho crosscheck rule-based (keyword-matching) trước đây (xem
    docs/decisions-log.md nếu cần bối cảnh đổi hướng). Lỗi/parse fail -> trả về
    DEFAULT_LLM_CROSSCHECK_SCORE (trung lập, không làm lệch ranking)."""
    lines = []
    for i, (eq, hit) in enumerate(zip(event_queries_en, chain)):
        vid, n, pts = hit.get("video_id", ""), hit.get("n"), hit.get("pts_time")
        objs = get_objects(vid, int(n)) if vid and n is not None else []
        transcript = get_transcript(vid, float(pts)) if vid and pts is not None else ""
        lines.append(
            f"Event {i + 1}: {eq}\n"
            f"  Objects: {', '.join(objs[:10]) or 'none'}\n"
            f"  Transcript: {transcript or 'none'}"
        )
    prompt = TRAKE_CROSSCHECK_PROMPT.format(query=query_en, events_block="\n".join(lines))

    try:
        response = call_llm(prompt, model="text", temperature=0.0, max_tokens=20,
                            purpose="trake_crosscheck")
    except Exception as error:
        print(f"[trake]   LLM crosscheck lỗi ({type(error).__name__}: {error}), dùng điểm trung lập {DEFAULT_LLM_CROSSCHECK_SCORE}")
        return DEFAULT_LLM_CROSSCHECK_SCORE

    match = _SCORE_RE.search(response)
    if not match:
        print(f"[trake]   LLM crosscheck không parse được score từ: {response!r}, dùng điểm trung lập")
        return DEFAULT_LLM_CROSSCHECK_SCORE

    return max(0.0, min(1.0, float(match.group(1))))


def run_trake(
    query_text: str,
    events: list[str],
    top_k_video: int = 100,
    top_k_frame: int = 20,
    query_en: str | None = None,
    strict_monotonic: bool = True,
    trace: "RunTrace | None" = None,
) -> dict:
    """
    Chạy pipeline TRAKE đầy đủ.

    Args:
        query_text:  Mô tả tổng quát chuỗi sự kiện (để tìm video).
        events:      Danh sách mô tả từng khoảnh khắc theo thứ tự thời gian.
                     Ví dụ: ["athlete takes off", "athlete clears bar", "athlete lands"]
        top_k_video: Số video candidate để thử alignment (default 100).
        top_k_frame: Số frame candidate mỗi event khi alignment (default 20).
        query_en:    Nếu có (vd. người dùng đã xem/sửa câu rewrite global query trong UI — xem
                     agent/tools/rewrite.py rewrite_query_candidates() + frontend/), bỏ qua
                     rewrite global query ở Giai đoạn 1 và dùng thẳng giá trị này. Rewrite từng event
                     không đổi (vẫn tự động như cũ — xem docstring module).
        strict_monotonic: True (mặc định, §5.2) = chuỗi frame phải TĂNG NGHIÊM NGẶT. Đặt False nếu
                     cần cho phép 2 mốc liên tiếp rơi vào cùng 1 keyframe (video keyframe rất thưa).

    Returns:
        dict:
          results   (list[dict]): Top submissions, mỗi item {video_id, frame_ids, score}
          best      (dict):       Kết quả tốt nhất.
          n_events  (int):        Số khoảnh khắc.
    """
    tr = trace if trace is not None else NULL_TRACE
    n_events = len(events)
    print(f"[trake] {n_events} events, finding video candidates...", flush=True)

    # ─── Giai doan 1: Tim video ────────────────────────────────────────────────
    if query_en:
        print(f"[trake]   Global query có sẵn (bỏ qua rewrite): {query_en!r}")
    else:
        with tr.stage("global_query"):
            query_en = rewrite_query(query_text)
        print(f"[trake]   Global query: {query_en!r}")

    # Rewrite từng event query TRƯỚC giai đoạn 1 — cần chúng ngay để tính độ phủ N mốc khi lọc video
    # (chỉ rewrite 1 lần, dùng chung cho mọi video ở giai đoạn 2).
    event_queries_en = []
    with tr.stage("per_event_query"):
        for i, ev in enumerate(events):
            eq = rewrite_query(ev)
            event_queries_en.append(eq)
            print(f"[trake]   Event {i+1}: {ev!r} -> {eq!r}")

    # Multi-Event Coverage Pooling (§5.1): thay vì chỉ lọc video bằng 1 global query chung chung,
    # chấm điểm video = Sim_global(V) + tổng các max_{f in V} Sim(e_i, f). Video "phủ" đủ cả N mốc sẽ
    # thắng video chỉ trùng bối cảnh chung — đúng điều TRAKE thực sự cần.
    def _video_best(hits: list[dict]) -> dict[str, float]:
        best: dict[str, float] = {}
        for h in hits:
            vid = h["video_id"]
            if vid not in best or h["score"] > best[vid]:
                best[vid] = h["score"]
        return best

    global_best = _video_best(fast_retrieve(query_en, top_k=RETRIEVAL_POOL_SIZE))
    coverage_score: dict[str, float] = defaultdict(float)
    coverage_count: dict[str, int] = defaultdict(int)
    for vid, s in global_best.items():
        coverage_score[vid] += s

    for eq in event_queries_en:
        for vid, s in _video_best(fast_retrieve(eq, top_k=RETRIEVAL_POOL_SIZE)).items():
            coverage_score[vid] += s
            coverage_count[vid] += 1  # số mốc mà video này có mặt trong pool -> độ "phủ"

    # Ưu tiên video phủ được NHIỀU mốc nhất trước, rồi mới đến tổng điểm — đúng §5.1 "Top-20 video
    # có độ phủ đầy đủ N mốc nhất".
    top_videos = sorted(
        coverage_score, key=lambda v: (coverage_count[v], coverage_score[v]), reverse=True
    )[:top_k_video]
    print(f"[trake]   Top {len(top_videos)} videos (phu {[coverage_count[v] for v in top_videos]}"
          f"/{n_events} moc): {top_videos}")
    tr.record("retrieval", {
        "method": "multi_event_coverage_pooling",
        "candidates": [
            {"rank": i, "video_id": v, "coverage": coverage_count[v],
             "coverage_score": round(coverage_score[v], 4)}
            for i, v in enumerate(top_videos[:20], 1)
        ],
    })
    tr.record("trake", {
        "events": list(events),
        "global_query": query_en,
        "event_queries": event_queries_en,
        "video_candidates": top_videos[:10],
        "alignment": None,
    })

    # ─── Giai đoạn 2: Alignment cho từng video ─────────────────────────────────
    video_results = []

    with tr.stage("align"):
        for vid in top_videos:
            event_hits = [fast_retrieve_for_video(eq, vid, top_k=top_k_frame) for eq in event_queries_en]
            chain = find_best_increasing_chain(event_hits, strict=strict_monotonic)
            is_strict = True
            if chain is None and strict_monotonic:
                # Thử nới lỏng strict=False để cứu video (vd keyframe thưa, 2 mốc rơi cùng 1 keyframe)
                chain = find_best_increasing_chain(event_hits, strict=False)
                is_strict = False
                if chain is not None:
                    print(f"[trake]   {vid}: cứu video bằng chuỗi nới lỏng (strict=False)")

            if chain is None:
                print(f"[trake]   {vid}: không tìm được chuỗi mốc hợp lệ -> loại")
                continue

            trake_score = sum(h["score"] for h in chain) / len(chain)
            video_results.append({
                "video_id":    vid,
                "frame_ids":   [h["frame_id"] for h in chain],
                "trake_score": trake_score,
                "strict_chain": is_strict,
                "chain":       chain,  # giữ hit đầy đủ (có "n") để cross-check tầng 3 đúng — không vào CSV
            })

    # ─── Giai doan 3: Gated Multi-Modal Verification (§5.3) ────────────────────
    # Cổng 1 — lọc nhanh rule-based (Objects JSON vs mô tả event): miễn phí, chạy cho TẤT CẢ candidate.
    for vr in video_results:
        vr["rule_score"] = rule_plausibility(event_queries_en, vr["chain"])
        vr["llm_score"] = None
        vr["score"] = vr["trake_score"] + RULE_GATE_WEIGHT * vr["rule_score"]
    video_results.sort(
        key=lambda x: (1 if x.get("strict_chain", True) else 0, x["score"]),
        reverse=True,
    )
    for vr in video_results[:5]:
        strict_tag = "" if vr.get("strict_chain", True) else " [relaxed]"
        print(f"[trake]   {vr['video_id']}{strict_tag}: trake={vr['trake_score']:.4f} "
              f"rule={vr['rule_score']:.2f} -> {vr['score']:.4f}")

    # Cổng 2 — LLM/VLM: CHỈ chạy khi #1 và #2 sát nhau (<= GATE_MARGIN). Thay cho bản trước gọi LLM
    # cho MỌI candidate (tối đa 20 lượt/lần chạy TRAKE) — khi 1 video đã thắng cách biệt thì LLM
    # không thể đổi thứ tự, lượt gọi đó chỉ tốn tiền/thời gian.
    gate_opened = False
    if len(video_results) >= 2:
        margin = video_results[0]["score"] - video_results[1]["score"]
        if margin <= GATE_MARGIN:
            gate_opened = True
            print(f"[trake]   margin #1-#2 = {margin:.4f} <= {GATE_MARGIN} -> mở cổng LLM cho top "
                  f"{GATE_MAX_VIDEOS} video")
            with tr.stage("llm_gate"):
                for vr in video_results[:GATE_MAX_VIDEOS]:
                    llm_score = _llm_crosscheck_chain(query_en, event_queries_en, vr["chain"])
                    vr["llm_score"] = llm_score
                    vr["score"] = (vr["trake_score"] + RULE_GATE_WEIGHT * vr["rule_score"]
                                   + LLM_SCORE_WEIGHT * llm_score)
                    print(f"[trake]   {vr['video_id']}: llm={llm_score:.2f} -> final={vr['score']:.4f}")
            video_results.sort(
                key=lambda x: (1 if x.get("strict_chain", True) else 0, x["score"]),
                reverse=True,
            )
        else:
            print(f"[trake]   margin #1-#2 = {margin:.4f} > {GATE_MARGIN} -> bỏ qua cổng LLM "
                  f"(video dan dau da cach biet)")

    tr.record("rerank", {
        "gate_opened": gate_opened,
        "margin_top2": round(video_results[0]["score"] - video_results[1]["score"], 4)
        if len(video_results) >= 2 else None,
        "final": [
            {"rank": i, "video_id": vr["video_id"], "frame_ids": vr["frame_ids"],
             "trake_score": round(vr["trake_score"], 4), "rule_score": round(vr["rule_score"], 3),
             "llm_score": vr["llm_score"], "score": round(vr["score"], 4)}
            for i, vr in enumerate(video_results[:10], 1)
        ],
    })

    # Mỗi video là 1 phương án; giữ trần 100 dòng theo rule BTC.
    results = []
    for vr in video_results[:100]:
        results.append({
            "video_id":  vr["video_id"],
            "frame_ids": vr["frame_ids"],
            "score":     vr["score"],
        })

    best = results[0] if results else {}
    print(f"[trake]   Best video: {best.get('video_id')}  score={best.get('score', 0):.4f}")
    print(f"[trake]   Frame IDs: {best.get('frame_ids')}")

    tr.record("trake", {
        "events": list(events),
        "global_query": query_en,
        "event_queries": event_queries_en,
        "video_candidates": top_videos[:10],
        "gate_opened": gate_opened,
        "alignment": {
            "video_id": best.get("video_id"),
            "frame_ids": best.get("frame_ids"),
            "score": round(float(best.get("score", 0.0)), 4),
        } if best else None,
    })
    tr.set_result(video_id=best.get("video_id"), frame_ids=best.get("frame_ids"))

    return {
        "results":  results,
        "best":     best,
        "n_events": n_events,
    }

# Bo test: tests/unit/test_trake_align.py + tests/unit/test_pipeline_trake.py

# ─── CLI Demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    query = "An athlete performing a high jump: approach, takeoff, clearance, landing"
    events = [
        "athlete running toward the bar during approach run",
        "athlete pushing off the ground at takeoff moment",
        "athlete arching back over the high jump bar at peak",
        "athlete falling onto the mat after clearing the bar",
    ]

    print(f"\n[TRAKE Pipeline]")
    print(f"Query: {query!r}")
    print(f"Events ({len(events)}): {events}\n")

    with RunTrace("trake", query, {"events": events, "top_k_video": 3, "top_k_frame": 5}) as _tr:
        out = run_trake(query, events, top_k_video=3, top_k_frame=5, trace=_tr)
    print(f"[TRAKE Pipeline] run_id={_tr.run_id}  (xem logs/runs/{_tr.run_id[:8]}/{_tr.run_id}.txt)")

    print("\n=== KẾT QUẢ ===")
    print(f"  N events:  {out['n_events']}")
    print(f"  Best video: {out['best'].get('video_id')}")
    print(f"  Frame IDs:  {out['best'].get('frame_ids')}")
    print(f"  Score:      {out['best'].get('score', 0):.4f}")

    print(f"\n  Submission rows ({len(out['results'])}):")
    for r in out["results"]:
        fids = ", ".join(str(f) for f in r["frame_ids"])
        print(f"    {r['video_id']}, {fids}  (score={r['score']:.4f})")
