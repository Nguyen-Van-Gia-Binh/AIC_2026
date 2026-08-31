"""
retrieve.py — Truy vấn dense (cosine similarity) trên ma trận embedding, dùng chung cho 3 pipeline.

State (ma trận, metadata, text encoder) KHÔNG nằm ở đây mà ở index_store.py — file này chỉ là
tầng truy vấn thuần. Xem thêm:
    index_store.py  — sở hữu index/model, và là điểm duy nhất quy đổi frame_id = frame_idx + 1
    hybrid.py       — lai ghép Dense + BM25 bằng RRF
    frames.py       — tra cứu keyframe cho tầng UI

Hai không gian embedding:
    KIS / TRAKE → fast_retrieve() / fast_retrieve_for_video()
    Q&A         → fast_retrieve_qa()

Lý do chọn model: benchmark 33 query (2026-08-28), xem docs/reports/eval_baseline_comparison.md.

Escape-hatch (dùng khi thử nghiệm, không phải production):
    AIC_RETRIEVE_MODEL=<tag>  đổi model cho KIS/TRAKE
    AIC_QA_MODEL=<tag>        đổi model cho Q&A
  Tag hợp lệ: xem MODEL_REGISTRY trong scripts/agent/tools/multi_index.py

Usage:
    from scripts.agent.tools.retrieve import fast_retrieve, fast_retrieve_qa
    results = fast_retrieve("a cyclist on a mountain road", top_k=100)

PowerShell — thử model khác cho KIS/TRAKE:
    $env:AIC_RETRIEVE_MODEL = "dfn"; .venv\\Scripts\\python.exe scripts\\agent\\tools\\retrieve.py "a red car"
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:      # file này chạy được trực tiếp từ CLI (xem __main__ cuối file)
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.agent.tools import index_store


def fast_retrieve(query_text: str, top_k: int = 100) -> list[dict]:
    """
    Tìm top_k keyframe gần nhất với query_text bằng cosine similarity. Dùng cho KIS và TRAKE.

    Returns list of dict:
      video_id  (str):   "L21_V001" (không .mp4)
      n         (int):   keyframe sequence no trong map-keyframes (dùng cho objects_lookup)
      frame_idx (int):   index gốc từ 0
      frame_id  (int):   frame_idx + 1  — dùng trong submission (BTC tính từ 1)
      pts_time  (float): timestamp giây
      score     (float): cosine similarity
      jpg_path  (str|None)
    """
    matrix, meta, encode_fn = index_store.get_index(qa=False)
    top_k = min(top_k, 1000)  # trần an toàn, KHÔNG phải giá trị mặc định — xem rerank.RETRIEVAL_POOL_SIZE
    scores = matrix @ encode_fn(query_text)
    top_idx = np.argsort(-scores)[:top_k]
    return [index_store.row_to_hit(meta, int(i), float(scores[i])) for i in top_idx]


def fast_retrieve_for_video(query_text: str, video_id: str, top_k: int = 20) -> list[dict]:
    """Như fast_retrieve nhưng chỉ tìm trong 1 video — dùng cho bước Alignment của TRAKE."""
    matrix, meta, encode_fn = index_store.get_index(qa=False)
    mask = meta["video_id"] == video_id
    if not mask.any():
        return []
    local_matrix = matrix[mask.values]
    local_meta = meta[mask].reset_index(drop=True)
    scores = local_matrix @ encode_fn(query_text)
    top_idx = np.argsort(-scores)[:top_k]
    return [index_store.row_to_hit(local_meta, int(i), float(scores[i])) for i in top_idx]


def fast_retrieve_qa(query_text: str, top_k: int = 100) -> list[dict]:
    """
    Tìm top_k keyframe trong không gian embedding của Q&A (khác KIS/TRAKE — xem index_store).

    Returns: cùng định dạng với fast_retrieve().
    """
    matrix, meta, encode_fn = index_store.get_index(qa=True)
    top_k = min(top_k, 1000)
    scores = matrix @ encode_fn(query_text)
    top_idx = np.argsort(-scores)[:top_k]
    return [index_store.row_to_hit(meta, int(i), float(scores[i])) for i in top_idx]


def fast_retrieve_multi(texts: list[str], top_k: int = 100, qa: bool = False) -> list[dict]:
    """Như fast_retrieve() nhưng nhận NHIỀU cách diễn đạt của cùng 1 truy vấn (Multi-Aspect Prompt
    Expansion — xem query_expand.py). texts độ dài 1 => y hệt fast_retrieve()."""
    matrix, meta, _ = index_store.get_index(qa=qa)
    top_k = min(top_k, 1000)
    scores = matrix @ index_store.encode_mean(texts, qa=qa)
    top_idx = np.argsort(-scores)[:top_k]
    return [index_store.row_to_hit(meta, int(i), float(scores[i])) for i in top_idx]


# ─── CLI demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "a person walking on the street"
    print(f"\nQuery: {query!r}")
    hits = fast_retrieve(query, top_k=5)
    kis_tag, _qa_tag = index_store.model_tags()
    print(f"\nTop {len(hits)} results (KIS/TRAKE model = {kis_tag}):")
    for i, h in enumerate(hits, 1):
        img = "  [img]" if h["jpg_path"] else ""
        print(f"  #{i}  {h['video_id']}  frame_id={h['frame_id']}  t={h['pts_time']:.1f}s  score={h['score']:.4f}{img}")
