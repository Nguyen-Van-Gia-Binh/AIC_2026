"""
temporal_nms.py — Khử trùng lặp thời gian (Temporal Non-Maximum Suppression) cho danh sách keyframe.

Vấn đề: keyframe liên tiếp trong cùng 1 cảnh gần như giống hệt nhau về nội dung, nên SigLIP chấm
điểm chúng gần bằng nhau. Không lọc thì top-100 dòng nộp bài có thể bị 10-20 dòng của CÙNG 1 cảnh
chiếm chỗ — lãng phí dung lượng 100 dòng mà không tăng cơ hội trúng (R@k tính max trên k dòng đầu,
2 dòng sát nhau cùng sai thì vẫn sai).

Nguyên lý (BẢN ĐẶC TẢ §3.2): duyệt hits theo điểm giảm dần, giữ 1 keyframe làm "đỉnh cục bộ"
(local peak), loại mọi keyframe CÙNG VIDEO cách đỉnh đó dưới MIN_TIME_GAP giây; tối đa
MAX_PEAKS_PER_VIDEO đỉnh cho 1 video.

Module THUẦN (pure): không đọc index/model/file — dùng chung được cho cả đường production
(rerank.py) lẫn nhánh eval (tests/eval/run_eval.py), không kéo theo việc nạp SigLIP.

Usage:
    from scripts.agent.tools.temporal_nms import temporal_nms
    kept = temporal_nms(hits, min_gap=3.0, max_per_video=3)
"""
from __future__ import annotations

# Khoảng cách thời gian tối thiểu giữa 2 keyframe được giữ trong CÙNG 1 video (giây) — BẢN ĐẶC TẢ
# §3.2. 3.0s bám theo bước lấy keyframe thực tế của BTC (map-keyframes: pts_time cách nhau ~2.5-3s
# ở phần lớn video) nên thực chất loại "keyframe kế bên", không loại cảnh khác.
MIN_TIME_GAP = 3.0

# Số đỉnh cục bộ tối đa giữ lại cho 1 video — trùng với rerank.SPREAD_MAX_PER_VIDEO (chế độ trải
# rủi ro). None = không giới hạn (chỉ lọc theo khoảng cách thời gian).
MAX_PEAKS_PER_VIDEO = 3


def temporal_nms(
    hits: list,
    min_gap: float = MIN_TIME_GAP,
    max_per_video: int | None = None,
    score_key: str = "score",
) -> list:
    """
    Lọc hits: giữ đỉnh cục bộ, bỏ keyframe lân cận trong cùng video.

    Args:
        hits:          list[dict] từ fast_retrieve() — cần có 'video_id', 'pts_time', score_key.
                       KHÔNG bắt buộc đã sắp xếp: hàm tự sắp xếp giảm dần theo score trước khi duyệt.
        min_gap:       Khoảng cách thời gian tối thiểu (giây) giữa 2 keyframe được giữ trong 1 video.
        max_per_video: Số đỉnh tối đa mỗi video (None = không giới hạn).
        score_key:     Tên trường điểm dùng để sắp xếp (mặc định 'score'; dùng 'rrf_score' khi lọc
                       kết quả đã qua dung hợp RRF).

    Returns:
        list[dict] — các hit được giữ, sắp xếp giảm dần theo score_key. Không sửa đổi dict đầu vào.
        Hit thiếu 'pts_time' (None) được giữ nguyên, không bị lọc (không đủ thông tin để so sánh).
    """
    if not hits:
        return hits

    ordered = sorted(hits, key=lambda h: -float(h.get(score_key, 0.0)))
    kept_times: dict = {}   # video_id -> list[pts_time] của các đỉnh đã giữ
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
                continue  # sát 1 đỉnh đã giữ -> cùng cảnh, bỏ
            times.append(pts)
        kept.append(hit)

    return kept

# Bo test: tests/unit/test_temporal_nms.py
