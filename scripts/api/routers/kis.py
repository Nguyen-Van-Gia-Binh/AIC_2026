"""
routers/kis.py — Bridge sang HTTP cho rewrite + KIS search + frame lan can (man chi tiet keyframe).
KHONG chua logic retrieval/rerank — chi goi thang cac ham co san.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from scripts.agent.pipeline_kis import run_kis
from scripts.agent.tools.rewrite import rewrite_query_candidates
from scripts.agent.tools.retrieve import get_neighbor_frames
from scripts.api.schemas import (
    RewriteRequest, RewriteResponse, KisSearchRequest, KisSearchResponse, Hit, NeighborFrame,
)

router = APIRouter(prefix="/api", tags=["kis"])

_HIT_KEYS = {"video_id", "frame_id", "frame_idx", "pts_time", "score"}


def _strip_extra(hits: list[dict]) -> list[dict]:
    """Bo cac key khong thuoc schema (vd. jpg_path, n) truoc khi ep kieu Pydantic."""
    return [{k: v for k, v in h.items() if k in _HIT_KEYS} for h in hits]


@router.post("/rewrite", response_model=RewriteResponse)
def rewrite(req: RewriteRequest) -> RewriteResponse:
    if not req.query.strip():
        raise HTTPException(400, "query rong")
    candidates = rewrite_query_candidates(req.query, max_n=req.max_n, question=req.question)
    return RewriteResponse(candidates=candidates)


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
