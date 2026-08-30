"""
routers/images.py — Serve file anh keyframe that (.jpg) tu data/extracted/keyframes/ cho frontend.

Frontend chi biet (video_id, frame_idx) -> goi GET /api/images/{video_id}/{frame_idx}. Router tra
ve file .jpg tuong ung (FileResponse). Neu anh chua giai nen / khong co dong -> 404, frontend tu
thay bang o fallback.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from scripts.agent.tools.frames import get_keyframe_path

router = APIRouter(prefix="/api", tags=["images"])


@router.get("/images/{video_id}/{frame_idx}")
def keyframe_image(video_id: str, frame_idx: int) -> FileResponse:
    path = get_keyframe_path(video_id, frame_idx)
    if not path:
        raise HTTPException(404, f"khong co anh cho {video_id} frame_idx={frame_idx}")
    # Cache 1 ngay — anh keyframe la tinh, khong doi trong 1 phien thi.
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"}
    )
