"""
routers/videos.py — Serve file video gốc (.mp4) + metadata (fps, duration) cho màn kiểm chứng
keyframe ben frontend (VideoVerifier).

- GET /api/videos/{video_id}            -> FileResponse .mp4 (Starlette tu xu ly Range -> 206,
                                          <video> tua được). 404 nếu không tìm thấy file.
- GET /api/videos/{video_id}/meta       -> {fps, duration}. fps đọc từ map-keyframes/{video_id}.csv
                                          (cột fps, hằng số trong 1 video); duration lấy từ
                                          media-info/{video_id}.json "length" nếu có.

KHÔNG chứa logic retrieval — chỉ đọc file từ data/extracted/.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from scripts.api.schemas import VideoMeta

router = APIRouter(prefix="/api", tags=["videos"])

_ROOT = Path(__file__).resolve().parents[3]  # .../scripts/api/routers/videos.py -> repo root
_VIDEO_DIR = _ROOT / "data" / "extracted" / "video"
_MAPKF_DIR = _ROOT / "data" / "extracted" / "map-keyframes"
_MEDIAINFO_DIR = _ROOT / "data" / "extracted" / "media-info"

# Cache đường dẫn đã giải ra — glob thư mục video chỉ chạy 1 lần / video.
_VIDEO_PATH_CACHE: dict[str, Path | None] = {}


def get_video_path(video_id: str) -> Path | None:
    """Tìm file .mp4 của video_id. Cấu trúc: data/extracted/video/Videos_{batch}_*/{video_id}.mp4
    (vd Videos_L21_a/L21_V001.mp4). Trả về None nếu không có."""
    if video_id in _VIDEO_PATH_CACHE:
        return _VIDEO_PATH_CACHE[video_id]
    batch = video_id.split("_")[0]  # "L21_V001" -> "L21"
    match = next(_VIDEO_DIR.glob(f"Videos_{batch}_*/{video_id}.mp4"), None)
    if match is None:  # fallback: quét toàn bộ thư mục video (cấu trúc khác dự kiến)
        match = next(_VIDEO_DIR.glob(f"**/{video_id}.mp4"), None)
    _VIDEO_PATH_CACHE[video_id] = match
    return match


@router.get("/videos/{video_id}")
def video_file(video_id: str) -> FileResponse:
    path = get_video_path(video_id)
    if not path:
        raise HTTPException(404, f"không tìm thấy video {video_id}")
    return FileResponse(path, media_type="video/mp4")


@router.get("/videos/{video_id}/meta", response_model=VideoMeta)
def video_meta(video_id: str) -> VideoMeta:
    csv_path = _MAPKF_DIR / f"{video_id}.csv"
    if not csv_path.exists():
        raise HTTPException(404, f"không có map-keyframes cho {video_id}")

    # fps ở cột thứ 3, hằng số trong 1 video -> chỉ cần hàng đầu tiên (bỏ qua header).
    fps = 25.0
    with csv_path.open(encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        first = f.readline().strip().split(",")
    if "fps" in header and len(first) == len(header):
        try:
            fps = float(first[header.index("fps")])
        except (ValueError, IndexError):
            fps = 25.0

    duration: float | None = None
    info_path = _MEDIAINFO_DIR / f"{video_id}.json"
    if info_path.exists():
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
            if isinstance(info.get("length"), (int, float)):
                duration = float(info["length"])
        except (json.JSONDecodeError, OSError):
            duration = None

    return VideoMeta(fps=fps, duration=duration)
