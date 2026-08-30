"""
schemas.py — Pydantic request/response models cho scripts/api/.

Chi mo ta shape HTTP (JSON) — KHONG chua business logic. Cac field khop voi dict tra ve tu
scripts/agent/pipeline_kis.py / pipeline_qa.py / pipeline_trake.py / scripts/agent/tools/retrieve.py,
TRU jpg_path — khong lo duong dan file ra JSON. Frontend lay anh keyframe that qua endpoint rieng
GET /api/images/{video_id}/{frame_idx} (routers/images.py), chi can (video_id, frame_idx) co san
trong moi Hit / NeighborFrame.
"""
from __future__ import annotations

from pydantic import BaseModel


class RewriteRequest(BaseModel):
    query: str
    question: str | None = None
    max_n: int = 3


class RewriteResponse(BaseModel):
    candidates: list[str]


class TranslateRawRequest(BaseModel):
    query: str


class TranslateRawResponse(BaseModel):
    translation: str


class Hit(BaseModel):
    video_id: str
    frame_id: int
    frame_idx: int
    pts_time: float
    score: float


class NeighborFrame(BaseModel):
    video_id: str
    frame_id: int
    frame_idx: int
    pts_time: float


class VideoMeta(BaseModel):
    fps: float
    duration: float | None = None  # giay — tu media-info/{video_id}.json "length" neu co


class KisSearchRequest(BaseModel):
    query: str
    top_k: int = 20


class KisSearchResponse(BaseModel):
    hits: list[Hit]


class QaRunRequest(BaseModel):
    query: str
    question: str | None = None
    top_k: int = 20
    query_en: str | None = None


class QaHit(Hit):
    answer: str


class QaRunResponse(BaseModel):
    hits: list[QaHit]
    answer: str
    confidence: float
    n_loops: int


class TrakeRunRequest(BaseModel):
    query: str
    events: list[str]
    top_k_video: int = 5
    query_en: str | None = None


class TrakeCandidate(BaseModel):
    video_id: str
    frame_ids: list[int]
    score: float


class TrakeRunResponse(BaseModel):
    candidates: list[TrakeCandidate]
    n_events: int


class QueueRowIn(BaseModel):
    query_id: str
    query_type: str  # "kis" | "qa" | "trake"
    rows: list[dict]  # shape phu thuoc query_type — xem state.py
    answer: str | None = None  # chi dung khi query_type == "qa"


class QueueRowOut(QueueRowIn):
    pass


class ExportResponse(BaseModel):
    zip_path: str
    valid: bool
    csv_count: int
    errors: list[str]
