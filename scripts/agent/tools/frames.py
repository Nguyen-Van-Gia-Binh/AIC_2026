"""
frames.py — Tra cứu keyframe theo video cho tầng UI (dải frame lân cận, đường dẫn ảnh).

Tách khỏi retrieve.py 2026-08-31: ba hàm này phục vụ màn chi tiết của frontend, không phải kết quả
truy vấn — chúng không tính score và không nhận query. Để lẫn trong retrieve.py khiến file đó vừa là
động cơ tìm kiếm vừa là tiện ích hiển thị.

Ba hàm dưới trả "tham chiếu frame" (không có score) nên không đi qua index_store.row_to_hit(),
nhưng phép +1 vẫn phải khớp đúng quy ước ở đó: frame_id = frame_idx + 1.

Usage:
    from scripts.agent.tools.frames import get_all_frames, get_keyframe_path
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from scripts.agent.tools import index_store


def get_neighbor_frames(video_id: str, frame_idx: int, window: int = 5) -> list[dict]:
    """Trả về tối đa 2*window+1 keyframe LIÊN TIẾP (theo frame_idx) trong CÙNG 1 video, xung quanh
    frame_idx được chỉ định — dùng cho màn chi tiết keyframe (dải frame lân cận).
    Không tính score (không phải kết quả truy vấn) — chỉ trả về video_id/frame_id/frame_idx/pts_time.
    """
    _, _META, _ = index_store.get_index()
    mask = _META["video_id"] == video_id
    if not mask.any():
        return []
    local_meta = _META[mask].sort_values("frame_idx").reset_index(drop=True)
    pos = local_meta.index[local_meta["frame_idx"] == frame_idx]
    if len(pos) == 0:
        return []
    center = int(pos[0])
    lo = max(0, center - window)
    hi = min(len(local_meta), center + window + 1)
    results = []
    for _, row in local_meta.iloc[lo:hi].iterrows():
        fidx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "frame_idx": fidx,
            "frame_id":  fidx + 1,   # BTC đếm frame từ 1 — cùng quy ước index_store.row_to_hit()
            "pts_time":  float(row["pts_time"]),
        })
    return results

def get_all_frames(video_id: str) -> list[dict]:
    """Trả về TOÀN BỘ keyframe của 1 video (sắp theo frame_idx tăng dần) — dùng cho dải lướt
    keyframe đầy đủ ở màn chi tiết KIS (cuộn ngang từ frame đầu đến frame cuối, thay cho
    get_neighbor_frames chỉ lấy +/- vài frame). Không tính score (không phải kết quả truy vấn).
    Mỗi phần tử: {video_id, frame_idx, frame_id, pts_time}.
    """
    _, _META, _ = index_store.get_index()
    mask = _META["video_id"] == video_id
    if not mask.any():
        return []
    local_meta = _META[mask].sort_values("frame_idx")
    results = []
    for _, row in local_meta.iterrows():
        fidx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "frame_idx": fidx,
            "frame_id":  fidx + 1,   # BTC đếm frame từ 1 — cùng quy ước index_store.row_to_hit()
            "pts_time":  float(row["pts_time"]),
        })
    return results

def get_keyframe_path(video_id: str, frame_idx: int) -> Optional[str]:
    """Trả về đường dẫn file .jpg của keyframe (video_id, frame_idx) — hoặc None nếu không có dòng
    tương ứng / ảnh chưa giải nén. jpg_path đã được tính sẵn lúc nạp index (xem index_store.py),
    ở đây chỉ tra cứu lại. Dùng cho router serve ảnh (scripts/api/routers/images.py)."""
    _, _META, _ = index_store.get_index()
    mask = (_META["video_id"] == video_id) & (_META["frame_idx"] == frame_idx)
    if not mask.any():
        return None
    jpg_path = _META.loc[mask, "jpg_path"].iloc[0]
    if not isinstance(jpg_path, str) or not Path(jpg_path).exists():
        return None
    return jpg_path
