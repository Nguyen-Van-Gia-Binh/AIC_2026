"""
state.py — Session state trong RAM cho backend API.

KHÔNG dùng database (xem CLAUDE.md / docs/superpowers/specs/2026-08-27-...-design.md §3) — mọi
session (session_id do frontend tự sinh, xem frontend/src/session.ts) có 1 danh sách các query đã
"Thêm vào hàng đợi", giữ trong dict toàn cục trong tiến trình backend. Mất khi restart backend —
chấp nhận được ở giai đoạn này (chưa cần persist qua nhiều lần chạy).

Thread-safety: uvicorn dev (1 worker) chạy các route FastAPI đồng bộ (không có await xen giữa lúc
sửa dict trong file này) -> không có race điều kiện thực sự. Nếu sau này chạy nhiều worker/process,
phải đổi sang store khác.
"""
from __future__ import annotations

from typing import Any

_QUEUES: dict[str, list[dict[str, Any]]] = {}


def get_queue(session_id: str) -> list[dict[str, Any]]:
    return _QUEUES.setdefault(session_id, [])


def add_to_queue(session_id: str, item: dict[str, Any]) -> None:
    """Thêm 1 query vào hàng đợi — nếu query_id đã tồn tại thì THAY THẾ."""
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
