"""
routers/qa.py — Bridge pipeline_qa sang HTTP.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from scripts.agent.pipeline_qa import run_qa
from scripts.agent.tools.run_trace import RunTrace
from scripts.api.schemas import QaRunRequest, QaRunResponse, QaHit

router = APIRouter(prefix="/api", tags=["qa"])

_QA_HIT_KEYS = {"video_id", "frame_id", "frame_idx", "pts_time", "score", "answer"}


@router.post("/qa/run", response_model=QaRunResponse)
def qa_run(req: QaRunRequest) -> QaRunResponse:
    if not req.query.strip():
        raise HTTPException(400, "query rong")
    with RunTrace("qa", req.query, {"top_k": req.top_k, "question": req.question}) as tr:
        out = run_qa(req.query, question=req.question, top_k=req.top_k,
                     query_en=req.query_en, trace=tr)
    hits = [QaHit(**{k: v for k, v in h.items() if k in _QA_HIT_KEYS}) for h in out["results"]]
    return QaRunResponse(
        hits=hits, answer=out["answer"], confidence=out["confidence"], n_loops=out["n_loops"],
        run_id=tr.run_id or None,
    )
