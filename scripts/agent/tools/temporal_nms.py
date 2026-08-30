"""
temporal_nms.py — Khu trung lap thoi gian (Temporal Non-Maximum Suppression) cho danh sach keyframe.

Van de: keyframe lien tiep trong cung 1 canh gan nhu giong het nhau ve noi dung, nen SigLIP cham
diem chung gan bang nhau. Khong loc thi top-100 dong nop bai co the bi 10-20 dong cua CUNG 1 canh
chiem cho — lang phi dung luong 100 dong ma khong tang co hoi trung (R@k tinh max tren k dong dau,
2 dong sat nhau cung sai thi van sai).

Nguyen ly (BAN DAC TA §3.2): duyet hits theo diem giam dan, giu 1 keyframe lam "dinh cuc bo"
(local peak), loai moi keyframe CUNG VIDEO cach dinh do duoi MIN_TIME_GAP giay; toi da
MAX_PEAKS_PER_VIDEO dinh cho 1 video.

Module THUAN (pure): khong doc index/model/file — dung chung duoc cho ca duong production
(rerank.py) lan nhanh eval (tests/eval/run_eval.py), khong keo theo viec nap SigLIP.

Usage:
    from scripts.agent.tools.temporal_nms import temporal_nms
    kept = temporal_nms(hits, min_gap=3.0, max_per_video=3)
"""
from __future__ import annotations

# Khoang cach thoi gian toi thieu giua 2 keyframe duoc giu trong CUNG 1 video (giay) — BAN DAC TA
# §3.2. 3.0s bam theo buoc lay keyframe thuc te cua BTC (map-keyframes: pts_time cach nhau ~2.5-3s
# o phan lon video) nen thuc chat loai "keyframe ke ben", khong loai canh khac.
MIN_TIME_GAP = 3.0

# So dinh cuc bo toi da giu lai cho 1 video — trung voi rerank.SPREAD_MAX_PER_VIDEO (che do trai
# rui ro). None = khong gioi han (chi loc theo khoang cach thoi gian).
MAX_PEAKS_PER_VIDEO = 3


def temporal_nms(
    hits: list,
    min_gap: float = MIN_TIME_GAP,
    max_per_video: int | None = None,
    score_key: str = "score",
) -> list:
    """
    Loc hits: giu dinh cuc bo, bo keyframe lan can trong cung video.

    Args:
        hits:          list[dict] tu fast_retrieve() — can co 'video_id', 'pts_time', score_key.
                       KHONG bat buoc da sap xep: ham tu sap xep giam dan theo score truoc khi duyet.
        min_gap:       Khoang cach thoi gian toi thieu (giay) giua 2 keyframe duoc giu trong 1 video.
        max_per_video: So dinh toi da moi video (None = khong gioi han).
        score_key:     Ten truong diem dung de sap xep (mac dinh 'score'; dung 'rrf_score' khi loc
                       ket qua da qua dung hop RRF).

    Returns:
        list[dict] — cac hit duoc giu, sap xep giam dan theo score_key. Khong sua doi dict dau vao.
        Hit thieu 'pts_time' (None) duoc giu nguyen, khong bi loc (khong du thong tin de so sanh).
    """
    if not hits:
        return hits

    ordered = sorted(hits, key=lambda h: -float(h.get(score_key, 0.0)))
    kept_times: dict = {}   # video_id -> list[pts_time] cua cac dinh da giu
    kept: list = []

    for hit in ordered:
        vid = hit.get("video_id", "")
        times = kept_times.setdefault(vid, [])
        if max_per_video is not None and len(times) >= max_per_video:
            continue
        pts = hit.get("pts_time")
        if pts is not None:
            pts = float(pts)
            if any(abs(pts - t) < min_gap for t in times):
                continue  # sat 1 dinh da giu -> cung canh, bo
            times.append(pts)
        kept.append(hit)

    return kept

# Bo test: tests/unit/test_temporal_nms.py
