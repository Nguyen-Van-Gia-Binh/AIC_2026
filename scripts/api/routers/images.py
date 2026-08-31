"""
routers/images.py — Serve file ảnh keyframe thật (.jpg) từ data/extracted/keyframes/ cho frontend.

Frontend chỉ biết (video_id, frame_idx) -> gọi GET /api/images/{video_id}/{frame_idx}. Router trả
về file .jpg tương ứng (FileResponse). Nếu ảnh chưa giải nén / không có dòng -> 404, frontend tự
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
        raise HTTPException(404, f"không có ảnh cho {video_id} frame_idx={frame_idx}")
    # Cache 1 ngày — ảnh keyframe là tĩnh, không đổi trong 1 phiên thi.
    return FileResponse(
        path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"}
    )
