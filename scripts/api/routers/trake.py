"""
routers/trake.py — Bridge pipeline_trake sang HTTP.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from scripts.agent.pipeline_trake import run_trake
from scripts.agent.tools.run_trace import RunTrace
from scripts.api.schemas import TrakeRunRequest, TrakeRunResponse, TrakeCandidate

router = APIRouter(prefix="/api", tags=["trake"])


@router.post("/trake/run", response_model=TrakeRunResponse)
def trake_run(req: TrakeRunRequest) -> TrakeRunResponse:
    if not req.query.strip():
        raise HTTPException(400, "query rong")
    if not req.events:
        raise HTTPException(400, "can it nhat 1 event")
    with RunTrace("trake", req.query, {"events": req.events, "top_k_video": req.top_k_video}) as tr:
        out = run_trake(req.query, req.events, top_k_video=req.top_k_video,
                        query_en=req.query_en, trace=tr)
    candidates = [TrakeCandidate(**c) for c in out["results"]]
    return TrakeRunResponse(candidates=candidates, n_events=out["n_events"], run_id=tr.run_id or None)
