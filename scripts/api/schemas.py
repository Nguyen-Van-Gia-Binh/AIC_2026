"""
schemas.py — Pydantic request/response models cho scripts/api/.

Chỉ mô tả shape HTTP (JSON) — KHÔNG chứa business logic. Các field khớp với dict trả về từ
scripts/agent/pipeline_kis.py / pipeline_qa.py / pipeline_trake.py / scripts/agent/tools/retrieve.py,
TRỪ jpg_path — không lộ đường dẫn file ra JSON. Frontend lấy ảnh keyframe thật qua endpoint riêng
GET /api/images/{video_id}/{frame_idx} (routers/images.py), chỉ cần (video_id, frame_idx) có sẵn
trong mỗi Hit / NeighborFrame.
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
    duration: float | None = None  # giây — từ media-info/{video_id}.json "length" nếu có


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
    rows: list[dict]  # shape phụ thuộc query_type — xem state.py
    answer: str | None = None  # chỉ dùng khi query_type == "qa"


class QueueRowOut(QueueRowIn):
    pass


class ExportResponse(BaseModel):
    zip_path: str
    valid: bool
    csv_count: int
    errors: list[str]
