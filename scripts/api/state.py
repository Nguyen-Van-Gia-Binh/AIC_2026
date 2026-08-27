"""
state.py — Session state trong RAM cho backend API (Phase 1 skeleton).

KHONG dung database (xem CLAUDE.md / docs/superpowers/specs/2026-08-27-...-design.md §3) — moi
session (session_id do frontend tu sinh, xem frontend/src/session.ts) co 1 danh sach cac query da
"Them vao hang doi", giu trong dict toan cuc trong tien trinh backend. Mat khi restart backend —
chap nhan duoc o Phase 1 (chua can persist qua nhieu lan chay).

Thread-safety: uvicorn dev (1 worker) chay cac route FastAPI dong bo (khong co await xen giua luc
sua dict trong file nay) -> khong co race dieu kien thuc su. Neu sau nay chay nhieu worker/process,
phai doi sang store khac.
"""
from __future__ import annotations

from typing import Any

_QUEUES: dict[str, list[dict[str, Any]]] = {}


def get_queue(session_id: str) -> list[dict[str, Any]]:
    return _QUEUES.setdefault(session_id, [])


def add_to_queue(session_id: str, item: dict[str, Any]) -> None:
    """Them 1 query vao hang doi — neu query_id da ton tai thi THAY THE (giong scripts/app.py cu)."""
    queue = get_queue(session_id)
    queue[:] = [q for q in queue if q["query_id"] != item["query_id"]]
    queue.append(item)


def remove_from_queue(session_id: str, query_id: str) -> bool:
    queue = get_queue(session_id)
    before = len(queue)
    queue[:] = [q for q in queue if q["query_id"] != query_id]
    return len(queue) < before


def clear_queue(session_id: str) -> None:
    _QUEUES[session_id] = []
