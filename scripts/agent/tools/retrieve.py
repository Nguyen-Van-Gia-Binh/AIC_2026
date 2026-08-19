"""
Công cụ truy xuất keyframe dùng chung cho cả 3 pipeline (KIS / Q&A / TRAKE).

Bọc index.py với singleton pattern: build_index() chỉ chạy 1 lần per process.

Usage:
    from scripts.agent.tools.retrieve import fast_retrieve
    results = fast_retrieve("a person walking on the street", top_k=100)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from index import build_index  # noqa: E402

_MATRIX: Optional[np.ndarray] = None
_META = None
_MODEL = None


def _ensure_loaded() -> None:
    global _MATRIX, _META, _MODEL
    if _MATRIX is not None:
        return
    print("[retrieve] Building index...", flush=True)
    _MATRIX, _META = build_index()
    n_kf = len(_META)
    n_vid = _META["video_id"].nunique()
    print(f"[retrieve] Index ready: {n_kf} keyframes / {n_vid} videos")
    print("[retrieve] Loading CLIP model...", flush=True)
    from sentence_transformers import SentenceTransformer
    _MODEL = SentenceTransformer("clip-ViT-B-32")
    print("[retrieve] Ready.")


def fast_retrieve(query_text: str, top_k: int = 100) -> list[dict]:
    """
    Tìm top_k keyframe gần nhất với query_text bằng CLIP cosine similarity.

    Returns list of dict:
      video_id  (str):   "L21_V001" (không .mp4)
      frame_idx (int):   index gốc từ 0
      frame_id  (int):   frame_idx + 1  — dùng trong submission (BTC tính từ 1)
      pts_time  (float): timestamp giây
      score     (float): cosine similarity
      jpg_path  (str|None)
    """
    _ensure_loaded()
    top_k = min(top_k, 100)
    q_vec = _MODEL.encode([query_text], normalize_embeddings=True)[0].astype(np.float32)
    scores = _MATRIX @ q_vec
    top_idx = np.argsort(-scores)[:top_k]
    results = []
    for idx in top_idx:
        row = _META.iloc[idx]
        frame_idx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "n":         int(row["n"]),        # keyframe sequence no (for ocr_lookup)
            "frame_idx": frame_idx,
            "frame_id":  frame_idx + 1,
            "pts_time":  float(row["pts_time"]),
            "score":     float(scores[idx]),
            "jpg_path":  row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
        })
    return results


def fast_retrieve_for_video(query_text: str, video_id: str, top_k: int = 20) -> list[dict]:
    """Như fast_retrieve nhưng chỉ tìm trong 1 video — dùng cho bước Alignment TRAKE."""
    _ensure_loaded()
    mask = _META["video_id"] == video_id
    if not mask.any():
        return []
    q_vec = _MODEL.encode([query_text], normalize_embeddings=True)[0].astype(np.float32)
    local_matrix = _MATRIX[mask.values]
    local_meta   = _META[mask].reset_index(drop=True)
    scores  = local_matrix @ q_vec
    top_idx = np.argsort(-scores)[:top_k]
    results = []
    for idx in top_idx:
        row = local_meta.iloc[idx]
        frame_idx = int(row["frame_idx"])
        results.append({
            "video_id":  row["video_id"],
            "n":         int(row["n"]),        # keyframe sequence no (for ocr_lookup)
            "frame_idx": frame_idx,
            "frame_id":  frame_idx + 1,
            "pts_time":  float(row["pts_time"]),
            "score":     float(scores[idx]),
            "jpg_path":  row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
        })
    return results


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "a person walking on the street"
    print(f"\nQuery: {query!r}")
    hits = fast_retrieve(query, top_k=5)
    print(f"\nTop {len(hits)} results:")
    for i, h in enumerate(hits, 1):
        img = "  [img]" if h["jpg_path"] else ""
        print(f"  #{i}  {h['video_id']}  frame_id={h['frame_id']}  t={h['pts_time']:.1f}s  score={h['score']:.4f}{img}")
