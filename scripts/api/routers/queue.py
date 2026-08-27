"""
routers/queue.py — Hang doi submission trong RAM + export ZIP.

Export bridge sang scripts/submit/build_submission.py (noi DUY NHAT duoc phep ghi CSV/ZIP submission
— xem CLAUDE.md) va scripts/submit/validate_submission.py — khong tu ghi file o day.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from scripts.api import state
from scripts.api.schemas import QueueRowIn, QueueRowOut, ExportResponse
from scripts.submit.build_submission import (
    build_kis_csv, build_qa_csv, build_trake_csv, build_zip_submission,
)
from scripts.submit.validate_submission import validate_file

router = APIRouter(prefix="/api", tags=["queue"])


@router.get("/queue/{session_id}", response_model=list[QueueRowOut])
def get_queue(session_id: str) -> list[QueueRowOut]:
    return [QueueRowOut(**q) for q in state.get_queue(session_id)]


@router.post("/queue/{session_id}/add", response_model=list[QueueRowOut])
def add_to_queue(session_id: str, item: QueueRowIn) -> list[QueueRowOut]:
    state.add_to_queue(session_id, item.model_dump())
    return [QueueRowOut(**q) for q in state.get_queue(session_id)]


@router.delete("/queue/{session_id}/{query_id}", response_model=list[QueueRowOut])
def remove_from_queue(session_id: str, query_id: str) -> list[QueueRowOut]:
    if not state.remove_from_queue(session_id, query_id):
        raise HTTPException(404, f"khong tim thay query_id={query_id}")
    return [QueueRowOut(**q) for q in state.get_queue(session_id)]


@router.delete("/queue/{session_id}", response_model=list[QueueRowOut])
def clear_queue(session_id: str) -> list[QueueRowOut]:
    state.clear_queue(session_id)
    return []


@router.post("/export/{session_id}", response_model=ExportResponse)
def export_zip(session_id: str) -> ExportResponse:
    queue = state.get_queue(session_id)
    if not queue:
        raise HTTPException(400, "Hang doi rong")

    csv_files = []
    errors: list[str] = []
    for item in queue:
        qid, qtype, rows = item["query_id"], item["query_type"], item["rows"]
        try:
            if qtype == "kis":
                hits = [{"video_id": r["video_id"], "frame_id": r["frame_id"]} for r in rows]
                csv_files.append(build_kis_csv(qid, hits))
            elif qtype == "qa":
                hits = [{"video_id": r["video_id"], "frame_id": r["frame_id"],
                         "answer": r.get("answer", item.get("answer", ""))} for r in rows]
                csv_files.append(build_qa_csv(qid, hits))
            elif qtype == "trake":
                csv_files.append(build_trake_csv(qid, rows))
            else:
                errors.append(f"{qid}: query_type khong hop le '{qtype}'")
        except Exception as e:
            errors.append(f"{qid}: {e}")

    if not csv_files:
        raise HTTPException(500, "Khong tao duoc CSV nao:\n" + "\n".join(errors))

    zip_path = build_zip_submission(csv_files, tag="frontend")
    valid = validate_file(zip_path)
    return ExportResponse(zip_path=str(zip_path), valid=valid, csv_count=len(csv_files), errors=errors)
