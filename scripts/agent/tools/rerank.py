"""
rerank.py — Risk-aware re-ranking hau xu ly cho KIS/QA, chay sau khi fast_retrieve tra ve top-K.

Y tuong (PLAN.md Phase 3): quan sat "margin" giua video ung vien manh nhat va video ung vien manh
nhi trong danh sach hits (so sanh best score moi video).
  - Margin lon (1 video noi bat han so voi phan con lai) -> che do "dat cuoc": danh nhieu dong ket
    qua hon cho dung video do (dao sau hon trong video do bang fast_retrieve_for_video neu can), tang
    co hoi trung R@1/R@5.
  - Margin nho (khong video nao noi bat ro) -> che do "trai rui ro": gioi han so dong toi da tren 1
    video trong danh sach, ep ket qua trai rong hon nhieu video, tang co hoi trung R@50/R@100.

Khong goi LLM (PLAN.md Phase 3: "khong can LLM"). Chi phu thuoc fast_retrieve_for_video khi can dao
sau them trong video dang "dat cuoc" — khong tu doc/ghi index, khong doi retrieve.py.

MARGIN_THRESHOLD / BET_VIDEO_SHARE / SPREAD_MAX_PER_VIDEO la gia tri khoi diem, da can chinh so bo
bang du lieu that (xem docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md) —
se tinh chinh tiep o Phase 6 checkpoint bang benchmark that (test_eval/Test/test_phase3_rerank.py),
khong phai doan mo hinh.

Usage:
    from scripts.agent.tools.rerank import apply_risk_aware_ranking
    ranked = apply_risk_aware_ranking(hits, top_k=100, query_text="a red car parked on the street")
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Nguong chenh lech score (cosine similarity CLIP, thuong ~0.28-0.31 cho query that) de coi video #1
# la "noi bat ro rang" so voi video #2.
MARGIN_THRESHOLD = 0.012

# Che do "dat cuoc": ti le toi da so dong (tren top_k) danh cho video noi bat nhat.
BET_VIDEO_SHARE = 0.5

# Che do "trai rui ro": so dong toi da cho 1 video khi khong co video nao noi bat.
SPREAD_MAX_PER_VIDEO = 3

# So ung vien tho can lay tu fast_retrieve TRUOC KHI rerank/cat ve top_k submission. Lon hon han so voi
# top_k thuc te (thuong 100) vi chan doan thuc te tren eval_ground_truth.json cho thay GT frame chi nam
# trong top-100 o 12/23 cau nhung nam trong top-500 o 20/23 cau (xem
# docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md) — trong khi chi phi tinh gan nhu mien
# phi (fast_retrieve da nhan full ma tran 177K keyframe, chi argsort cat nhieu hon).
RETRIEVAL_POOL_SIZE = 500


def apply_risk_aware_ranking(
    hits: list[dict], top_k: int = 100, query_text: str | None = None
) -> list[dict]:
    """Sap xep lai hits theo chien luoc "dat cuoc" hoac "trai rui ro" tuy margin giua cac video.

    Args:
        hits: Ket qua da co tu fast_retrieve/fast_retrieve_for_video, da sap xep giam dan theo score.
        top_k: So dong toi da tra ve (gioi han submission — xem build_submission.py).
        query_text: Query da rewrite (tieng Anh) dung de dao sau them trong video "dat cuoc" khi can.
                    None = chi sap xep lai hits san co, khong goi them fast_retrieve_for_video.

    Returns:
        list[dict] cung dinh dang voi hits dau vao, do dai <= top_k.
    """
    if not hits:
        return hits

    best_score_by_video: dict[str, float] = {}
    for h in hits:
        vid = h["video_id"]
        if vid not in best_score_by_video or h["score"] > best_score_by_video[vid]:
            best_score_by_video[vid] = h["score"]

    ranked_videos = sorted(best_score_by_video.items(), key=lambda kv: -kv[1])

    if len(ranked_videos) == 1:
        margin = float("inf")
    else:
        margin = ranked_videos[0][1] - ranked_videos[1][1]

    if margin >= MARGIN_THRESHOLD:
        print(f"[rerank] margin={margin:.4f} >= {MARGIN_THRESHOLD} -> che do DAT CUOC (video={ranked_videos[0][0]})")
        return _bet_mode(hits, ranked_videos[0][0], top_k, query_text)

    print(f"[rerank] margin={margin:.4f} < {MARGIN_THRESHOLD} -> che do TRAI RUI RO")
    return _spread_mode(hits, top_k)


def _bet_mode(hits: list[dict], top_video_id: str, top_k: int, query_text: str | None) -> list[dict]:
    """"Dat cuoc" = ADD them ung vien dao sau tu video dang thang, de chung canh tranh cong bang
    theo score that voi phan con lai — KHONG ep chung len dau danh sach bat ke score (lam vay se
    day cac hit dung tu video khac xuong duoi mot cach vo ly, gay regression R@20/R@50 — xem
    docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md).
    """
    n_target = max(1, int(top_k * BET_VIDEO_SHARE))
    top_video_hits = [h for h in hits if h["video_id"] == top_video_id]

    if query_text and len(top_video_hits) < n_target:
        from agent.tools.retrieve import fast_retrieve_for_video
        deeper = fast_retrieve_for_video(query_text, top_video_id, top_k=n_target)
        # Chi loai trung voi frame_idx CUA CHINH top_video_id — frame_idx la index cuc bo trong tung
        # video (khong globally unique, xem index.py), so voi ca "hits" (nhieu video) se xoa nham cac
        # ung vien dao sau hop le chi vi trung frame_idx voi 1 video khac hoan toan.
        seen_frame_idx = {h["frame_idx"] for h in top_video_hits}
        extra = [d for d in deeper if d["frame_idx"] not in seen_frame_idx]
        hits = hits + extra

    result = sorted(hits, key=lambda h: -h["score"])
    return result[:top_k]


def _spread_mode(hits: list[dict], top_k: int) -> list[dict]:
    """"Trai rui ro" = uu tien theo THU HANG CUA VIDEO (best score/video), lay het dan (den
    SPREAD_MAX_PER_VIDEO) cho tung video truoc khi chuyen sang video ke — KHONG round-robin dan deu.

    Da thu round-robin (1 hit/video/vong) truoc — bi loi: khi pool rong (vd 250+ video khac nhau,
    xem docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md), vong 0 mot minh da chiem het
    top_k cho MOI video 1 hit, nen video dung (dang o hang tot, vd #44/255) chi duoc 1 hit dau (co the
    khong phai frame dung) ma khong con luot vong 1/2 de lay frame dung sau do — mat han ket qua da co
    truoc khi rerank (regression). Fix: xu ly video theo thu tu diem tot nhat, MOI video duoc lay du
    (toi da SPREAD_MAX_PER_VIDEO) hit CUA CHINH NO truoc khi xet video ke tiep — video dung thuong nam
    trong nhom diem kha tot (khong can toan bo hang dau), duoc dam bao co du kien de frame dung (khong
    nhat thiet la frame diem cao nhat cua video) van lot vao top_k.
    """
    by_video: dict[str, list[dict]] = {}
    video_best_score: dict[str, float] = {}
    for h in hits:
        vid = h["video_id"]
        by_video.setdefault(vid, []).append(h)  # hits() da sort giam dan -> list nay cung giam dan
        if vid not in video_best_score or h["score"] > video_best_score[vid]:
            video_best_score[vid] = h["score"]

    videos_by_score = sorted(by_video.keys(), key=lambda v: -video_best_score[v])

    result: list[dict] = []
    for vid in videos_by_score:
        result.extend(by_video[vid][:SPREAD_MAX_PER_VIDEO])
        if len(result) >= top_k:
            break
    return result[:top_k]


# ─── CLI self-test (repo khong dung pytest — xem CLAUDE.md) ────────────────────
if __name__ == "__main__":
    from collections import Counter

    def _fake_hit(video_id: str, i: int, score: float) -> dict:
        return {
            "video_id": video_id, "n": i, "frame_idx": i, "frame_id": i + 1,
            "pts_time": 0.0, "score": score, "jpg_path": None,
        }

    # Test 1: bet mode - video A noi bat ro rang (margin lon)
    hits_bet = (
        [_fake_hit("A", i, 0.9 - i * 0.001) for i in range(5)]
        + [_fake_hit(f"V{i}", i, 0.5 - i * 0.001) for i in range(20)]
    )
    out_bet = apply_risk_aware_ranking(hits_bet, top_k=10)
    n_a = sum(1 for h in out_bet if h["video_id"] == "A")
    assert n_a >= 5, f"Bet mode phai uu tien video A, chi thay {n_a}/10"
    print(f"[rerank] Test bet mode: OK ({n_a}/10 dong la video A)")

    # Test 2: spread mode - khong video nao noi bat (diem gan bang nhau), du nhieu video khac nhau
    # (20 video x 5 hit = 100 hit) de cap 3/video co the thoa man top_k=30 (can >=10 video de dat 30).
    hits_spread = [
        _fake_hit(f"V{i // 5}", i, 0.5 - i * 0.0001) for i in range(100)
    ]
    out_spread = apply_risk_aware_ranking(hits_spread, top_k=30)
    counts = Counter(h["video_id"] for h in out_spread)
    assert max(counts.values()) <= SPREAD_MAX_PER_VIDEO, f"Spread mode vuot qua {SPREAD_MAX_PER_VIDEO} dong/video: {counts}"
    print(f"[rerank] Test spread mode: OK ({len(counts)} video khac nhau / {len(out_spread)} dong, max/video={max(counts.values())})")

    # Test 3: hits rong khong crash
    assert apply_risk_aware_ranking([], top_k=10) == []
    print("[rerank] Test empty input: OK")

    # Test 4: bet mode KHONG duoc loai ung vien dao sau chi vi trung frame_idx voi 1 VIDEO KHAC —
    # frame_idx la index cuc bo tung video (khong globally unique), dedup sai o ban truoc chi kiem tra
    # "hits" (ca pool nhieu video) thay vi chi rieng top_video_hits (code review Phase 6).
    import agent.tools.retrieve as _retrieve_module

    def _fake_fetch_deeper(query_text, video_id, top_k):
        # Video A dat cuoc co 1 ung vien dao sau moi (frame_idx=99) chua tung xuat hien trong hits cua
        # rieng A, nhung video KHAC (V0) trong pool da co san frame_idx=99 — dedup sai se loai nham.
        return [_fake_hit("A", 99, 0.85)]

    _orig_fetch = _retrieve_module.fast_retrieve_for_video
    _retrieve_module.fast_retrieve_for_video = _fake_fetch_deeper
    try:
        hits_collision = (
            [_fake_hit("A", i, 0.9 - i * 0.001) for i in range(3)]          # video A: chi 3 hit co san
            + [_fake_hit("V0", 99, 0.5)]                                     # video khac trung frame_idx=99
            + [_fake_hit(f"V{i}", i, 0.4 - i * 0.001) for i in range(1, 20)]
        )
        out_collision = apply_risk_aware_ranking(hits_collision, top_k=10, query_text="fake query")
        frame_idxs_a = {h["frame_idx"] for h in out_collision if h["video_id"] == "A"}
        assert 99 in frame_idxs_a, (
            f"Ung vien dao sau (frame_idx=99) cua video A bi loai nham do trung voi video khac: {frame_idxs_a}"
        )
    finally:
        _retrieve_module.fast_retrieve_for_video = _orig_fetch
    print("[rerank] Test bet mode khong loai nham ung vien trung frame_idx voi video khac: OK")

    print("[rerank] Tat ca self-test PASS")
