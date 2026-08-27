"""
pipeline_trake.py — Pipeline TRAKE: Retrieve video + Windowed Alignment.

Workflow co dinh 2 giai doan (khong de LLM tu quyet dinh so buoc):

Giai doan 1 - Retrieval:
  query tong quat -> rewrite -> fast_retrieve(top_k=RETRIEVAL_POOL_SIZE)  # =500, xem rerank.py
  -> group by video_id -> rank video theo diem trung binh (video_avg)
  -> chon top_k_video video candidates (mac dinh 20, xem run_trake())

Giai doan 2 - Alignment (N lan, 1 lan / khoang khac):
  For moi video candidate:
    For moi event_i in events[]:
      -> rewrite(event_description_i)
      -> fast_retrieve_for_video(query_i, video_id, top_k=10)
      -> chon frame tot nhat, CO THOI GIAN sau frame[i-1] (world model nhe)
    -> tinh trake_score = trung binh score cac event
    -> LLM crosscheck 1 lan/video: doc objects (ocr_lookup) + transcript (asr_lookup) tung frame
       trong chain, hoi LLM 1 diem plausibility 0.0-1.0 (_llm_crosscheck_chain) -> final_score =
       trake_score + LLM_SCORE_WEIGHT * llm_score
  -> Sap xep theo final_score -> chon video tot nhat

Output: list[dict] {video_id, frame_id_1, ..., frame_id_N}
"""
from __future__ import annotations

import sys
import re
from pathlib import Path
from collections import defaultdict
from typing import Optional

_ROOT = Path(__file__).resolve().parent.parent.parent  # repo root — cho `import scripts.*`
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.config import call_llm
from scripts.agent.tools.retrieve import fast_retrieve, fast_retrieve_for_video
from scripts.agent.tools.rewrite import rewrite_query
from scripts.agent.tools.rerank import RETRIEVAL_POOL_SIZE
from scripts.agent.tools.ocr_lookup import get_objects
from scripts.agent.tools.asr_lookup import get_transcript


def _find_best_increasing_chain(event_hits: list[list[dict]]) -> list[dict] | None:
    """Tim chuoi 1 frame/event sao cho frame_idx KHONG GIAM qua tung event (event sau >= event
    truoc — cho phep bang nhau vi du lieu that co truong hop 2 event lien tiep trung 1 frame, xem
    docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md) va TONG score la lon nhat, bang
    quy hoach dong — thay vi greedy cu (chon diem cao nhat cho event dau tien roi khoa cung, co the
    chan mat lua chon tot hon o cac event sau, xem "Ly do thiet ke" trong plan).

    Args:
        event_hits: event_hits[i] = list ung vien (tu fast_retrieve_for_video, da sap xep giam dan
                    theo score) cho event thu i.

    Returns:
        list[dict] do dai == len(event_hits), 1 hit/event, frame_idx khong giam dan, tong score lon
        nhat co the; None neu KHONG TON TAI chuoi hop le nao (video nay bi loai hoan toan).
    """
    n = len(event_hits)
    if n == 0 or any(not candidates for candidates in event_hits):
        return None

    NEG_INF = float("-inf")
    # dp[i][j] = tong score lon nhat cua chuoi ket thuc bang ung vien j cua event i
    dp: list[list[float]] = [[NEG_INF] * len(candidates) for candidates in event_hits]
    back: list[list[Optional[int]]] = [[None] * len(candidates) for candidates in event_hits]

    for j, hit in enumerate(event_hits[0]):
        dp[0][j] = hit["score"]

    for i in range(1, n):
        for j, hit in enumerate(event_hits[i]):
            for k, prev_hit in enumerate(event_hits[i - 1]):
                if prev_hit["frame_idx"] > hit["frame_idx"]:
                    continue  # phai khong giam (>=), khong duoc lui ve truoc
                if dp[i - 1][k] == NEG_INF:
                    continue
                candidate_score = dp[i - 1][k] + hit["score"]
                if candidate_score > dp[i][j]:
                    dp[i][j] = candidate_score
                    back[i][j] = k

    last = n - 1
    best_j, best_score = None, NEG_INF
    for j, s in enumerate(dp[last]):
        if s > best_score:
            best_score, best_j = s, j
    if best_j is None or best_score == NEG_INF:
        return None

    chain: list[Optional[dict]] = [None] * n
    j = best_j
    for i in range(last, -1, -1):
        chain[i] = event_hits[i][j]
        j = back[i][j]
    return chain  # type: ignore[return-value]


# Trong so cua diem LLM crosscheck (0.0-1.0) khi cong vao trake_score (trung binh cosine similarity,
# cung thang do voi rerank.MARGIN_THRESHOLD ~0.012) de ra final_score dung de rank. Diem khoi dau, se
# tinh chinh o Phase 6 khi co benchmark rong hon (xem PLAN.md "Blockers").
LLM_SCORE_WEIGHT = 0.05

# Diem trung lap khi LLM crosscheck loi hoac khong parse duoc — khong lam lech ranking so voi trake_score.
DEFAULT_LLM_CROSSCHECK_SCORE = 0.5

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
    """Goi LLM 1 lan de danh gia plausibility cua ca chain (object + transcript moi frame) so voi
    chuoi event mo ta — thay cho crosscheck rule-based (keyword-matching) truoc day (xem
    DECISION.md/EXPERIMENT.md neu can boi canh doi huong). Loi/parse fail -> tra ve
    DEFAULT_LLM_CROSSCHECK_SCORE (trung lap, khong lam lech ranking)."""
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
        response = call_llm(prompt, model="text", temperature=0.0, max_tokens=20)
    except Exception as error:
        print(f"[trake]   LLM crosscheck loi ({type(error).__name__}: {error}), dung diem trung lap {DEFAULT_LLM_CROSSCHECK_SCORE}")
        return DEFAULT_LLM_CROSSCHECK_SCORE

    match = _SCORE_RE.search(response)
    if not match:
        print(f"[trake]   LLM crosscheck khong parse duoc score tu: {response!r}, dung diem trung lap")
        return DEFAULT_LLM_CROSSCHECK_SCORE

    return max(0.0, min(1.0, float(match.group(1))))


def run_trake(
    query_text: str,
    events: list[str],
    top_k_video: int = 20,
    top_k_frame: int = 20,
    query_en: str | None = None,
) -> dict:
    """
    Chay pipeline TRAKE day du.

    Args:
        query_text:  Mo ta tong quat chuoi su kien (de tim video).
        events:      Danh sach mo ta tung khoang khac theo thu tu thoi gian.
                     Vi du: ["athlete takes off", "athlete clears bar", "athlete lands"]
        top_k_video: So video candidate de thu alignment (default 20).
        top_k_frame: So frame candidate moi event khi alignment (default 20).
        query_en:    Neu co (vd. nguoi dung da xem/sua cau rewrite global query trong UI — xem
                     agent/tools/rewrite.py rewrite_query_candidates() + scripts/app.py), bo qua
                     rewrite global query o Giai doan 1 va dung thang gia tri nay. Rewrite tung event
                     o Giai doan 2 khong doi (van tu dong nhu cu — xem docstring module).

    Returns:
        dict:
          results   (list[dict]): Top submissions, moi item {video_id, frame_ids, score}
          best      (dict):       Ket qua tot nhat.
          n_events  (int):        So khoang khac.
    """
    n_events = len(events)
    print(f"[trake] {n_events} events, finding video candidates...", flush=True)

    # ─── Giai doan 1: Tim video ────────────────────────────────────────────────
    if query_en:
        print(f"[trake]   Global query co san (bo qua rewrite): {query_en!r}")
    else:
        query_en = rewrite_query(query_text)
        print(f"[trake]   Global query: {query_en!r}")

    all_hits = fast_retrieve(query_en, top_k=RETRIEVAL_POOL_SIZE)

    # Group by video, tinh trung binh score TAT CA frame cua video do trong pool (khong gioi han top-3)
    video_scores: dict[str, float] = defaultdict(float)
    video_frame_count: dict[str, int] = defaultdict(int)

    for h in all_hits:
        vid = h["video_id"]
        video_scores[vid] += h["score"]
        video_frame_count[vid] += 1

    # Normalize theo so frame (lay trung binh) roi rank
    video_avg = {v: s / video_frame_count[v] for v, s in video_scores.items()}
    top_videos = sorted(video_avg, key=lambda v: video_avg[v], reverse=True)[:top_k_video]
    print(f"[trake]   Top {len(top_videos)} videos: {top_videos}")

    # ─── Giai doan 2: Alignment cho tung video ─────────────────────────────────
    # Rewrite tung event query (chi lam 1 lan, dung chung cho moi video)
    event_queries_en = []
    for i, ev in enumerate(events):
        eq = rewrite_query(ev)
        event_queries_en.append(eq)
        print(f"[trake]   Event {i+1}: {ev!r} -> {eq!r}")

    video_results = []

    for vid in top_videos:
        event_hits = [fast_retrieve_for_video(eq, vid, top_k=top_k_frame) for eq in event_queries_en]
        chain = _find_best_increasing_chain(event_hits)
        if chain is None:
            print(f"[trake]   {vid}: khong tim duoc chuoi moc tang dan hop le -> loai")
            continue

        trake_score = sum(h["score"] for h in chain) / len(chain)
        video_results.append({
            "video_id":    vid,
            "frame_ids":   [h["frame_id"] for h in chain],
            "trake_score": trake_score,
            "chain":       chain,  # giu hit day du (co "n") de cross-check tang 3 dung — khong vao CSV
        })

    # ─── LLM crosscheck (objects + transcript) cho MOI video candidate ─────────
    # Thay cho crosscheck rule-based (keyword-matching, chi chay khi margin top-2 sat) truoc day —
    # xem scripts/agent/tools/asr_lookup.py va _llm_crosscheck_chain(). Danh doi: cham hon (toi da
    # len(video_results) LLM call / lan chay TRAKE) doi lay danh gia ngu nghia thay vi khop tu tho.
    for vr in video_results:
        llm_score = _llm_crosscheck_chain(query_en, event_queries_en, vr["chain"])
        vr["llm_score"] = llm_score
        vr["score"] = vr["trake_score"] + LLM_SCORE_WEIGHT * llm_score
        print(f"[trake]   {vr['video_id']}: trake_score={vr['trake_score']:.4f} "
              f"llm_score={llm_score:.2f} -> final_score={vr['score']:.4f}")

    # Sap xep theo final_score (trake_score + LLM_SCORE_WEIGHT * llm_score)
    video_results.sort(key=lambda x: x["score"], reverse=True)

    # Moi video la 1 phuong an; giu tran 100 dong theo rule BTC.
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

    return {
        "results":  results,
        "best":     best,
        "n_events": n_events,
    }


# ─── CLI self-test (repo khong dung pytest — xem CLAUDE.md) ────────────────────
def _fake_hit(video_id: str, frame_idx: int, score: float) -> dict:
    return {
        "video_id": video_id, "n": frame_idx, "frame_idx": frame_idx, "frame_id": frame_idx + 1,
        "pts_time": 0.0, "score": score, "jpg_path": None,
    }


def _run_self_tests() -> None:
    # Test 1: DP phai thang greedy — event 0 co frame diem cao nhat (100, 0.9) nam MUON, chan mat
    # event 1 co frame diem cao (10, 0.95) nam SOM hon. Greedy se khoa X1 (0.9) ngay lap tuc, chi con
    # Y2 (0.3) hop le cho event 1 -> tong 1.2. DP phai chon X2+Y1 = 0.8+0.95 = 1.75 (tot hon).
    event_hits_1 = [
        [_fake_hit("V", 100, 0.9), _fake_hit("V", 5, 0.8)],
        [_fake_hit("V", 10, 0.95), _fake_hit("V", 200, 0.3)],
    ]
    chain_1 = _find_best_increasing_chain(event_hits_1)
    assert chain_1 is not None, "Phai tim duoc chuoi hop le"
    total_1 = sum(h["score"] for h in chain_1)
    assert abs(total_1 - 1.75) < 1e-9, f"DP phai chon X2+Y1 (0.8+0.95=1.75), duoc {total_1}"
    assert chain_1[0]["frame_idx"] == 5 and chain_1[1]["frame_idx"] == 10, (
        f"DP phai chon frame_idx=5 roi 10, duoc {[h['frame_idx'] for h in chain_1]}"
    )
    print("[trake] Test DP thang greedy: OK (tong=1.75, tot hon greedy=1.2)")

    # Test 2: khong co chuoi hop le -> None (video bi loai)
    event_hits_2 = [
        [_fake_hit("V", 100, 0.9)],
        [_fake_hit("V", 50, 0.8)],  # frame_idx < event truoc -> khong the tang dan
    ]
    assert _find_best_increasing_chain(event_hits_2) is None, "Khong co chuoi hop le phai tra None"
    print("[trake] Test khong co chuoi hop le: OK (tra None)")

    # Test 3: 1 event duy nhat -> chon frame diem cao nhat
    event_hits_3 = [[_fake_hit("V", 10, 0.5), _fake_hit("V", 20, 0.9)]]
    chain_3 = _find_best_increasing_chain(event_hits_3)
    assert chain_3 is not None and chain_3[0]["frame_idx"] == 20, "1 event phai chon diem cao nhat"
    print("[trake] Test 1 event: OK")

    # Test 4: cho phep frame_idx BANG NHAU giua 2 event lien tiep (du lieu that co truong hop nay —
    # xem docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md)
    event_hits_4 = [[_fake_hit("V", 10, 0.5)], [_fake_hit("V", 10, 0.6)]]
    chain_4 = _find_best_increasing_chain(event_hits_4)
    assert chain_4 is not None, "Frame_idx bang nhau giua 2 event phai HOP LE (khong giam)"
    print("[trake] Test frame_idx bang nhau: OK")

    # Test 5-8: _llm_crosscheck_chain — monkeypatch call_llm (module-level, import truc tiep nen
    # gan lai bien global de "thay the ham that").
    global call_llm
    _orig_call_llm = call_llm
    fake_chain = [_fake_hit("V", 1, 0.5), _fake_hit("V", 2, 0.6)]
    fake_events = ["athlete takes off", "athlete lands"]

    try:
        # Test 5: parse dung score tu response chuan
        call_llm = lambda *a, **k: "SCORE: 0.82"
        score5 = _llm_crosscheck_chain("high jump", fake_events, fake_chain)
        assert abs(score5 - 0.82) < 1e-9, f"Phai parse dung 0.82, duoc {score5}"
        print("[trake] Test LLM crosscheck parse dung: OK")

        # Test 6: call_llm loi -> tra ve diem trung lap, khong crash
        def _raise(*a, **k):
            raise RuntimeError("simulated failure")
        call_llm = _raise
        score6 = _llm_crosscheck_chain("high jump", fake_events, fake_chain)
        assert score6 == DEFAULT_LLM_CROSSCHECK_SCORE, f"Loi call_llm phai tra diem trung lap, duoc {score6}"
        print("[trake] Test LLM crosscheck loi -> diem trung lap: OK")

        # Test 7: response khong parse duoc -> diem trung lap
        call_llm = lambda *a, **k: "I cannot determine this."
        score7 = _llm_crosscheck_chain("high jump", fake_events, fake_chain)
        assert score7 == DEFAULT_LLM_CROSSCHECK_SCORE, f"Response khong hop le phai tra diem trung lap, duoc {score7}"
        print("[trake] Test LLM crosscheck khong parse duoc -> diem trung lap: OK")

        # Test 8: clamp ve [0, 1] khi LLM tra so ngoai khoang
        call_llm = lambda *a, **k: "SCORE: 1.50"
        assert _llm_crosscheck_chain("q", fake_events, fake_chain) == 1.0, "Phai clamp ve 1.0"
        call_llm = lambda *a, **k: "SCORE: -0.20"
        assert _llm_crosscheck_chain("q", fake_events, fake_chain) == 0.0, "Phai clamp ve 0.0"
        print("[trake] Test LLM crosscheck clamp [0,1]: OK")
    finally:
        call_llm = _orig_call_llm

    print("[trake] Tat ca self-test PASS")


# ─── CLI Demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _run_self_tests()
    print()

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

    out = run_trake(query, events, top_k_video=3, top_k_frame=5)

    print(f"\n=== KET QUA ===")
    print(f"  N events:  {out['n_events']}")
    print(f"  Best video: {out['best'].get('video_id')}")
    print(f"  Frame IDs:  {out['best'].get('frame_ids')}")
    print(f"  Score:      {out['best'].get('score', 0):.4f}")

    print(f"\n  Submission rows ({len(out['results'])}):")
    for r in out["results"]:
        fids = ", ".join(str(f) for f in r["frame_ids"])
        print(f"    {r['video_id']}, {fids}  (score={r['score']:.4f})")
