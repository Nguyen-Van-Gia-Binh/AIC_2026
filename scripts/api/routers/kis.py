"""
routers/kis.py — Bridge sang HTTP cho rewrite + KIS search + frame lân cận (màn chi tiết keyframe).
KHÔNG chứa logic retrieval/rerank — chỉ gọi thẳng các hàm có sẵn.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from scripts.agent.pipeline_kis import run_kis
from scripts.agent.tools.rewrite import rewrite_query_candidates
from scripts.agent.tools.translate_raw import translate_raw
from scripts.agent.tools.frames import get_neighbor_frames, get_all_frames
from scripts.api.schemas import (
    RewriteRequest, RewriteResponse, TranslateRawRequest, TranslateRawResponse,
    KisSearchRequest, KisSearchResponse, Hit, NeighborFrame,
)

router = APIRouter(prefix="/api", tags=["kis"])

_HIT_KEYS = {"video_id", "frame_id", "frame_idx", "pts_time", "score"}


def _strip_extra(hits: list[dict]) -> list[dict]:
    """Bỏ các key không thuộc schema (vd. jpg_path, n) trước khi ép kiểu Pydantic."""
    return [{k: v for k, v in h.items() if k in _HIT_KEYS} for h in hits]


@router.post("/rewrite", response_model=RewriteResponse)
def rewrite(req: RewriteRequest) -> RewriteResponse:
    if not req.query.strip():
        raise HTTPException(400, "query rong")
    candidates = rewrite_query_candidates(req.query, max_n=req.max_n, question=req.question)
    return RewriteResponse(candidates=candidates)


@router.post("/translate_raw", response_model=TranslateRawResponse)
def translate_raw_endpoint(req: TranslateRawRequest) -> TranslateRawResponse:
    """Dịch thô VN->EN, không qua LLM — để đối chiếu với bản rewrite đã qua LLM tối ưu."""
    if not req.query.strip():
        raise HTTPException(400, "query rong")
    try:
        translation = translate_raw(req.query)
    except Exception as e:
        raise HTTPException(502, f"Dich tho that bai: {type(e).__name__}: {e}")
    return TranslateRawResponse(translation=translation)


@router.post("/kis/search", response_model=KisSearchResponse)
def kis_search(req: KisSearchRequest) -> KisSearchResponse:
    if not req.query.strip():
        raise HTTPException(400, "query rong")
    hits = run_kis(req.query, top_k=req.top_k)
    return KisSearchResponse(hits=[Hit(**h) for h in _strip_extra(hits)])


@router.get("/keyframes/{video_id}/neighbors", response_model=list[NeighborFrame])
def keyframe_neighbors(video_id: str, frame_idx: int, window: int = 5) -> list[NeighborFrame]:
    frames = get_neighbor_frames(video_id, frame_idx, window=window)
    return [NeighborFrame(**f) for f in frames]


@router.get("/keyframes/{video_id}/all", response_model=list[NeighborFrame])
def keyframe_all(video_id: str) -> list[NeighborFrame]:
    """Toàn bộ keyframe của 1 video — dải lướt ngang ở màn chi tiết KIS."""
    frames = get_all_frames(video_id)
    if not frames:
        raise HTTPException(404, f"không có keyframe cho {video_id}")
    return [NeighborFrame(**f) for f in frames]
