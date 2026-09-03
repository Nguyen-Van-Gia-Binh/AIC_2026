"""
main.py — FastAPI app entrypoint cho backend AIC2026.

Chay:  .venv\\Scripts\\python.exe -m uvicorn scripts.api.main:app --reload --port 8000
Mo:    http://127.0.0.1:8000/api/health

Nạp sẵn index + model SigLIP lúc khởi động để request search đầu tiên không phải chờ load model.
(Trước đây việc này do scripts/app.py làm — Gradio đã retire vào docs/_archive/.)
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import time
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from scripts.agent.tools.index_store import preload
from scripts.api.logging_config import setup_logging, get_logger

# Khởi tạo hệ thống per-session logging
setup_logging()
_http_logger = get_logger("api.http")

app = FastAPI(title="AIC2026 Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chỉ ghi log request cho các đường pipeline. Các route phục vụ ảnh/video/keyframe cho UI
# (GET /api/images/..., /api/videos/..., /api/keyframes/..., /api/health) mỗi phiên gọi hàng
# trăm lần và không có giá trị phân tích — bỏ khỏi file log, TRỪ khi lỗi hoặc chậm bất thường.
_PIPELINE_PREFIXES = (
    "/api/kis", "/api/qa", "/api/trake", "/api/queue", "/api/rewrite", "/api/translate_raw",
)
_SLOW_REQUEST_MS = 1000.0


def _is_pipeline_path(path: str) -> bool:
    return path.startswith(_PIPELINE_PREFIXES)


@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    method = request.method
    path = request.url.path
    query = request.url.query
    query_str = f"?{query}" if query else ""
    client_ip = request.client.host if request.client else "unknown"

    log_this = _is_pipeline_path(path)
    if log_this:
        _http_logger.info(f"[REQ] {method} {path}{query_str} (client: {client_ip})")
    try:
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        if log_this or response.status_code >= 400 or duration_ms > _SLOW_REQUEST_MS:
            _http_logger.info(f"[RES] {method} {path} -> {response.status_code} ({duration_ms:.1f}ms)")
        return response
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        _http_logger.error(f"[ERR] {method} {path} -> 500 ({duration_ms:.1f}ms): {exc}", exc_info=True)
        raise exc


@app.on_event("startup")
def _on_startup() -> None:
    print("[api] Nạp index + SigLIP model (một lần)...")
    preload()
    print("[api] San sang.")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


from scripts.api.routers import kis  # noqa: E402

app.include_router(kis.router)

from scripts.api.routers import images  # noqa: E402

app.include_router(images.router)

from scripts.api.routers import qa  # noqa: E402

app.include_router(qa.router)

from scripts.api.routers import trake  # noqa: E402

app.include_router(trake.router)

from scripts.api.routers import videos  # noqa: E402

app.include_router(videos.router)

from scripts.api.routers import queue  # noqa: E402

app.include_router(queue.router)
