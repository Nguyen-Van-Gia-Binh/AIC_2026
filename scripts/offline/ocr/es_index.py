"""
es_index.py — Kết nối Elasticsearch, định nghĩa mapping và các hàm index/tìm kiếm cho dữ liệu
OCR + caption sinh bởi agent/tools/vlm_ocr_caption.py (Qwen2.5-VL).

Đây là thành phần HẠ TẦNG MỚI cho repo này — trước giờ "No database, no ORM, no message queue,
everything is files" (xem CLAUDE.md). Cần 1 cluster Elasticsearch đang chạy (local qua Docker, hoặc
Elastic Cloud) — không có sẵn trong repo, phải tự dựng. Cấu hình qua .env (xem .env.example):
    ES_URL       mặc định "http://localhost:9200"
    ES_INDEX     mặc định "aic_ocr_caption"
    ES_API_KEY   tuỳ chọn (ưu tiên nếu có)
    ES_USER / ES_PASSWORD  tuỳ chọn (dùng nếu không có ES_API_KEY)

Singleton pattern giống các tool khác trong thư mục này — client chỉ tạo 1 lần/process. KHÔNG tự
động connect lúc import module (lazy, giống _ensure_loaded() của retrieve.py/detect_objects.py) —
import module này ở đâu cũng không crash nếu ES chưa chạy, chỉ fail loud khi thực sự gọi hàm cần
kết nối (setup/data problem — đúng quy ước error handling trong CLAUDE.md).

QUY ƯỚC frame_id: module này CHỈ lưu "n" (số thứ tự keyframe trong map-keyframes) và "frame_idx"
(0-based) — KHÔNG tự tính frame_id = frame_idx + 1 (quy định CLAUDE.md: phép tính này chỉ làm ở
agent/tools/retrieve.py, không được suy ra lại ở nơi khác). Nơi nào cần frame_id từ kết quả
search_ocr() thì tự cộng thêm 1 tại đúng điểm dùng (vd lúc ghép vào submission), không làm sẵn ở đây.

Usage:
    from scripts.offline.ocr.es_index import ensure_index, index_frame, search_ocr
    ensure_index()
    index_frame(video_id="L21_V001", n=1, frame_idx=0, pts_time=0.5,
                ocr_text="EXIT", caption="A man walks through a doorway.")
    hits = search_ocr("exit sign", top_k=10)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
load_dotenv(_ROOT / ".env", override=False)

DEFAULT_ES_URL = "http://localhost:9200"
DEFAULT_ES_INDEX = "aic_ocr_caption"

_CLIENT = None
_INDEX_NAME = os.environ.get("ES_INDEX", "").strip() or DEFAULT_ES_INDEX

_MAPPINGS = {
    "properties": {
        "video_id":  {"type": "keyword"},
        "n":         {"type": "integer"},
        "frame_idx": {"type": "integer"},
        "pts_time":  {"type": "float"},
        "ocr_text":  {"type": "text"},
        "caption":   {"type": "text"},
    }
}


def _ensure_client():
    """Tạo Elasticsearch client 1 lần/process. Fail loud (ConnectionError) nếu không ping được —
    KHÔNG âm thầm trả về client "chết" rồi để lỗi mơ hồ ở lần gọi index_frame()/search_ocr() sau."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT
    from elasticsearch import Elasticsearch

    url = os.environ.get("ES_URL", "").strip() or DEFAULT_ES_URL
    api_key = os.environ.get("ES_API_KEY", "").strip() or None
    user = os.environ.get("ES_USER", "").strip() or None
    password = os.environ.get("ES_PASSWORD", "").strip() or None

    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    elif user and password:
        kwargs["basic_auth"] = (user, password)

    print(f"[es_index] Đang kết nối Elasticsearch: {url} (index={_INDEX_NAME})")
    client = Elasticsearch(url, **kwargs)
    if not client.ping():
        raise ConnectionError(
            f"[es_index] Không kết nối được Elasticsearch tại {url}. Kiểm tra ES đã chạy chưa "
            f"(vd 'docker run -p 9200:9200 docker.elastic.co/elasticsearch/elasticsearch:8.15.0') "
            f"và biến môi trường ES_URL/ES_API_KEY (hoặc ES_USER/ES_PASSWORD) trong .env."
        )
    _CLIENT = client
    return _CLIENT


def ensure_index() -> None:
    """Tạo index (với mapping ở trên) nếu chưa tồn tại. Gọi 1 lần trước khi index_frame()/bulk."""
    client = _ensure_client()
    if not client.indices.exists(index=_INDEX_NAME):
        print(f"[es_index] Tạo index mới: {_INDEX_NAME}")
        client.indices.create(index=_INDEX_NAME, mappings=_MAPPINGS)


def _doc_id(video_id: str, n: int) -> str:
    return f"{video_id}_{n}"


def frame_exists(video_id: str, n: int) -> bool:
    """Kiểm tra 1 frame đã được index chưa — dùng cho cơ chế resume ở scripts/index_ocr_es.py
    (tránh gọi lại Qwen2.5-VL cho frame đã xử lý, vì mỗi lần gọi model khá tốn thời gian)."""
    client = _ensure_client()
    return bool(client.exists(index=_INDEX_NAME, id=_doc_id(video_id, n)))


def index_frame(
    video_id: str,
    n: int,
    frame_idx: int,
    ocr_text: str,
    caption: str,
    pts_time: Optional[float] = None,
) -> None:
    """Index (hoặc ghi đè) 1 document cho 1 keyframe. Id xác định bởi video_id+n nên gọi lại với
    cùng tham số sẽ ghi đè (idempotent), không tạo doc trùng."""
    client = _ensure_client()
    doc = {
        "video_id": video_id,
        "n": n,
        "frame_idx": frame_idx,
        "pts_time": pts_time,
        "ocr_text": ocr_text,
        "caption": caption,
    }
    client.index(index=_INDEX_NAME, id=_doc_id(video_id, n), document=doc)


def search_ocr(
    query_text: str,
    video_id: Optional[str] = None,
    top_k: int = 20,
) -> list[dict]:
    """
    Tìm keyframe có ocr_text/caption khớp query_text (full-text search, KHÔNG phải vector search —
    dùng để lọc/cross-check kết quả của fast_retrieve() (CLIP), không thay thế nó).

    Args:
        query_text: câu hỏi/keyword tìm (tiếng Anh, khớp tốt nhất với caption do Qwen2.5-VL sinh)
        video_id:   lọc theo 1 video cụ thể (tuỳ chọn)
        top_k:      số kết quả tối đa

    Returns:
        list[dict]: {video_id, n, frame_idx, pts_time, ocr_text, caption, score}
                    KHÔNG có frame_id — xem "QUY ƯỚC frame_id" ở đầu file.
    """
    client = _ensure_client()
    must = [{
        "multi_match": {
            "query": query_text,
            "fields": ["ocr_text^1.5", "caption"],  # ưu tiên khớp OCR hơn caption
        }
    }]
    filters = [{"term": {"video_id": video_id}}] if video_id else []

    resp = client.search(
        index=_INDEX_NAME,
        query={"bool": {"must": must, "filter": filters}},
        size=top_k,
    )
    results = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        results.append({
            "video_id":  src["video_id"],
            "n":         src["n"],
            "frame_idx": src["frame_idx"],
            "pts_time":  src.get("pts_time"),
            "ocr_text":  src.get("ocr_text", ""),
            "caption":   src.get("caption", ""),
            "score":     float(hit["_score"]),
        })
    return results


# ─── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    ensure_index()
    print(f"[es_index] Index '{_INDEX_NAME}' sẵn sàng.")
    query = " ".join(sys.argv[1:]) or "exit"
    hits = search_ocr(query)
    print(f"[es_index] Test search {query!r}: {len(hits)} kết quả")
    for h in hits[:5]:
        print(f"  {h['video_id']} n={h['n']}  score={h['score']:.2f}  caption={h['caption']!r}")
