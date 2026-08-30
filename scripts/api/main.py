"""
main.py — FastAPI app entrypoint cho backend AIC2026 (Phase 1 skeleton).

Chay:  .venv\\Scripts\\python.exe -m uvicorn scripts.api.main:app --reload --port 8000
Mo:    http://127.0.0.1:8000/api/health

Nap san index + model CLIP luc khoi dong (giong scripts/app.py) de request search dau tien khong
phai cho load model.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from scripts.agent.tools.index_store import preload

app = FastAPI(title="AIC2026 Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _on_startup() -> None:
    print("[api] Nap index + CLIP model (mot lan)...")
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
