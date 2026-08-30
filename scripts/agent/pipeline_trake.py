"""
pipeline_trake.py — Pipeline TRAKE: Retrieve video + Windowed Alignment.

Workflow co dinh 2 giai doan (khong de LLM tu quyet dinh so buoc):

Giai doan 1 - Multi-Event Coverage Pooling (BAN DAC TA §5.1):
  rewrite global query VA ca N event query
  -> fast_retrieve(top_k=RETRIEVAL_POOL_SIZE) cho global query + cho TUNG event
  -> Video_Score(V) = Sim_global(V) + sum_i max_{f in V} Sim(e_i, f)
  -> xep theo (so moc video co mat trong pool, tong diem) -> top_k_video candidate (mac dinh 20)
  Y nghia: video "phu" du ca N moc thang video chi trung boi canh chung — dung dieu TRAKE can.

Giai doan 2 - Strict Monotonic DP (§5.2):
  For moi video candidate:
    For moi event_i: fast_retrieve_for_video(event_query_i, video_id, top_k=top_k_frame)
    -> DP tim chuoi 1 frame/event co frame_idx TANG NGHIEM NGAT (f_1 < ... < f_N), tong score max
    -> video khong ton tai chuoi hop le bi LOAI hoan toan
    -> trake_score = trung binh score cac event trong chuoi

Giai doan 3 - Gated Multi-Modal Verification (§5.3):
  Cong 1 (rule, mien phi, chay cho TAT CA candidate): do khop tu khoa Objects JSON tung frame trong
    chuoi vs mo ta event -> rule_score -> score = trake_score + RULE_GATE_WEIGHT * rule_score
  Cong 2 (LLM, dat): CHI mo khi chenh lech #1-#2 <= GATE_MARGIN (0.02) -> hoi LLM plausibility cho
    top GATE_MAX_VIDEOS video (objects + transcript tung frame) -> cong LLM_SCORE_WEIGHT * llm_score
  -> Sap xep lai theo final_score -> chon video tot nhat

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


# Trong so cua diem LLM crosscheck (0.0-1.0) khi cong vao trake_score (trung binh cosine similarity,
# cung thang do voi rerank.MARGIN_THRESHOLD ~0.012) de ra final_score dung de rank. Diem khoi dau, se
# tinh chinh o Phase 6 khi co benchmark rong hon (xem PLAN.md "Blockers").
LLM_SCORE_WEIGHT = 0.05

# Diem trung lap khi LLM crosscheck loi hoac khong parse duoc — khong lam lech ranking so voi trake_score.
DEFAULT_LLM_CROSSCHECK_SCORE = 0.5

# Trong so cua "cong nhanh" rule-based (do khop tu khoa giua Objects JSON tung frame trong chuoi va
# mo ta event) — chay cho TAT CA video candidate vi khong ton API call (BAN DAC TA §5.3).
RULE_GATE_WEIGHT = 0.03

# Chi kich hoat cong LLM/VLM (dat, cham) khi chenh lech diem giua video #1 va #2 nho hon nguong nay —
# khi 1 video da thang cach biet thi LLM gan nhu khong the doi thu tu, chi ton tien (§5.3).
GATE_MARGIN = 0.02

# So video duoc dua qua cong LLM khi cong duoc kich hoat (§5.3 "Top 2-3").
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
    strict_monotonic: bool = True,
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
                     khong doi (van tu dong nhu cu — xem docstring module).
        strict_monotonic: True (mac dinh, §5.2) = chuoi frame phai TANG NGHIEM NGAT. Dat False neu
                     can cho phep 2 moc lien tiep roi vao cung 1 keyframe (video keyframe rat thua).

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

    # Rewrite tung event query TRUOC giai doan 1 — can chung ngay de tinh do phu N moc khi loc video
    # (chi rewrite 1 lan, dung chung cho moi video o giai doan 2).
    event_queries_en = []
    for i, ev in enumerate(events):
        eq = rewrite_query(ev)
        event_queries_en.append(eq)
        print(f"[trake]   Event {i+1}: {ev!r} -> {eq!r}")

    # Multi-Event Coverage Pooling (§5.1): thay vi chi loc video bang 1 global query chung chung,
    # cham diem video = Sim_global(V) + tong cac max_{f in V} Sim(e_i, f). Video "phu" du ca N moc se
    # thang video chi trung boi canh chung — dung dieu TRAKE thuc su can.
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
            coverage_count[vid] += 1  # so moc ma video nay co mat trong pool -> do "phu"

    # Uu tien video phu duoc NHIEU moc nhat truoc, roi moi den tong diem — dung §5.1 "Top-20 video
    # co do phu day du N moc nhat".
    top_videos = sorted(
        coverage_score, key=lambda v: (coverage_count[v], coverage_score[v]), reverse=True
    )[:top_k_video]
    print(f"[trake]   Top {len(top_videos)} videos (phu {[coverage_count[v] for v in top_videos]}"
          f"/{n_events} moc): {top_videos}")

    # ─── Giai doan 2: Alignment cho tung video ─────────────────────────────────
    video_results = []

    for vid in top_videos:
        event_hits = [fast_retrieve_for_video(eq, vid, top_k=top_k_frame) for eq in event_queries_en]
        chain = find_best_increasing_chain(event_hits, strict=strict_monotonic)
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

    # ─── Giai doan 3: Gated Multi-Modal Verification (§5.3) ────────────────────
    # Cong 1 — loc nhanh rule-based (Objects JSON vs mo ta event): mien phi, chay cho TAT CA candidate.
    for vr in video_results:
        vr["rule_score"] = rule_plausibility(event_queries_en, vr["chain"])
        vr["llm_score"] = None
        vr["score"] = vr["trake_score"] + RULE_GATE_WEIGHT * vr["rule_score"]
    video_results.sort(key=lambda x: x["score"], reverse=True)
    for vr in video_results[:5]:
        print(f"[trake]   {vr['video_id']}: trake={vr['trake_score']:.4f} "
              f"rule={vr['rule_score']:.2f} -> {vr['score']:.4f}")

    # Cong 2 — LLM/VLM: CHI chay khi #1 va #2 sat nhau (<= GATE_MARGIN). Thay cho ban truoc goi LLM
    # cho MOI candidate (toi da 20 luot/lan chay TRAKE) — khi 1 video da thang cach biet thi LLM
    # khong the doi thu tu, luot goi do chi ton tien/thoi gian.
    if len(video_results) >= 2:
        margin = video_results[0]["score"] - video_results[1]["score"]
        if margin <= GATE_MARGIN:
            print(f"[trake]   margin #1-#2 = {margin:.4f} <= {GATE_MARGIN} -> mo cong LLM cho top "
                  f"{GATE_MAX_VIDEOS} video")
            for vr in video_results[:GATE_MAX_VIDEOS]:
                llm_score = _llm_crosscheck_chain(query_en, event_queries_en, vr["chain"])
                vr["llm_score"] = llm_score
                vr["score"] = (vr["trake_score"] + RULE_GATE_WEIGHT * vr["rule_score"]
                               + LLM_SCORE_WEIGHT * llm_score)
                print(f"[trake]   {vr['video_id']}: llm={llm_score:.2f} -> final={vr['score']:.4f}")
            video_results.sort(key=lambda x: x["score"], reverse=True)
        else:
            print(f"[trake]   margin #1-#2 = {margin:.4f} > {GATE_MARGIN} -> bo qua cong LLM "
                  f"(video dan dau da cach biet)")

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
    chain_1 = find_best_increasing_chain(event_hits_1)
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
    assert find_best_increasing_chain(event_hits_2) is None, "Khong co chuoi hop le phai tra None"
    print("[trake] Test khong co chuoi hop le: OK (tra None)")

    # Test 3: 1 event duy nhat -> chon frame diem cao nhat
    event_hits_3 = [[_fake_hit("V", 10, 0.5), _fake_hit("V", 20, 0.9)]]
    chain_3 = find_best_increasing_chain(event_hits_3)
    assert chain_3 is not None and chain_3[0]["frame_idx"] == 20, "1 event phai chon diem cao nhat"
    print("[trake] Test 1 event: OK")

    # Test 4: STRICT MONOTONIC (BAN DAC TA §5.2) — 2 event lien tiep KHONG duoc tro ve cung 1 frame
    # o che do mac dinh; che do noi long (strict=False, hanh vi cu tu Phase 4) van cho phep.
    event_hits_4 = [[_fake_hit("V", 10, 0.5)], [_fake_hit("V", 10, 0.6)]]
    assert find_best_increasing_chain(event_hits_4) is None, (
        "Mac dinh strict: 2 moc trung frame_idx phai bi loai"
    )
    assert find_best_increasing_chain(event_hits_4, strict=False) is not None, (
        "strict=False phai cho phep frame_idx bang nhau (hanh vi cu)"
    )
    # Co lua chon khac tang nghiem ngat thi strict phai tim ra, khong loai ca video.
    event_hits_4b = [[_fake_hit("V", 10, 0.5)], [_fake_hit("V", 10, 0.6), _fake_hit("V", 11, 0.4)]]
    chain_4b = find_best_increasing_chain(event_hits_4b)
    assert chain_4b is not None and chain_4b[1]["frame_idx"] == 11, (
        f"Strict phai chon phuong an tang nghiem ngat con lai: {chain_4b}"
    )
    print("[trake] Test strict monotonic: OK")

    # Test 4c: cong loc nhanh rule-based (§5.3) — objects khop mo ta event thi diem cao hon.
    global get_objects
    from scripts.agent.tools import trake_align   # rule_plausibility da chuyen sang day
    _orig_get_objects = get_objects
    _orig_align_get_objects = trake_align.get_objects
    try:
        get_objects = trake_align.get_objects = (
            lambda vid, n: {1: ["Bicycle", "Person"], 2: ["Car"]}.get(n, []))
        chain_rule = [_fake_hit("V", 1, 0.5), _fake_hit("V", 2, 0.5)]
        chain_rule[0]["n"], chain_rule[1]["n"] = 1, 2
        score_match = rule_plausibility(["a person riding a bicycle", "a car on the road"], chain_rule)
        score_miss = rule_plausibility(["an airplane taking off", "a boat on a river"], chain_rule)
        assert score_match > score_miss, f"Khop tu khoa phai cho diem cao hon: {score_match} vs {score_miss}"
        assert 0.0 <= score_match <= 1.0 and 0.0 <= score_miss <= 1.0, "rule_score phai nam trong [0,1]"
        assert rule_plausibility([], []) == 0.0, "Chuoi rong -> 0.0, khong crash"
        print(f"[trake] Test cong rule-based: OK (khop={score_match:.2f}, khong khop={score_miss:.2f})")
    finally:
        get_objects = _orig_get_objects
        trake_align.get_objects = _orig_align_get_objects

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
    if "--self-test" in sys.argv:
        # Thoat som: demo ben duoi chay run_trake THAT (ton luot LLM). Cung quy uoc voi pipeline_qa.py.
        sys.exit(0)
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
