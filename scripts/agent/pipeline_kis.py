"""
pipeline_kis.py — Pipeline KIS tuyến tính (không LLM, không loop).

Workflow:
  query_text → fast_retrieve(top_k=100) → trả về list kết quả đã rank

Câu hỏi tiếng Việt: kết quả sẽ thấp hơn vì CLIP-ViT-B-32 hiểu tiếng Anh tốt hơn.
Cố ý KHÔNG tự dịch VN→EN ở đây — quyết định kiến trúc đã chốt: KIS là workflow tuyến tính, không
LLM (xem ARCHITECTURE.md §3). Dịch VN→EN được đặt ở tầng UI (`scripts/app.py`, checkbox
auto-translate gọi `agent/tools/rewrite.py`), không phải trong pipeline này.

Usage:
    from scripts.agent.pipeline_kis import run_kis
    results = run_kis("a cyclist racing on a mountain road")
    # → list[dict] đã rank, dùng trực tiếp cho build_submission.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.tools.retrieve import fast_retrieve
from agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE


def run_kis(query_text: str, top_k: int = 100) -> list[dict]:
    """
    Chạy pipeline KIS tuyến tính.

    Args:
        query_text: Mô tả cảnh cần tìm (tiếng Anh cho kết quả tốt nhất).
        top_k: Số kết quả trả về, tối đa 100.

    Returns:
        list[dict] đã xếp hạng giảm dần theo score (đã qua risk-aware rerank — xem
        agent/tools/rerank.py), mỗi item có: video_id, frame_id, frame_idx, pts_time, score, jpg_path
    """
    pool_size = max(top_k, RETRIEVAL_POOL_SIZE)
    results = fast_retrieve(query_text, top_k=pool_size)
    print(f"[kis] Lay {len(results)} ung vien tho (pool={pool_size}), rerank cat ve top_k={top_k}")
    results = apply_risk_aware_ranking(results, top_k=top_k, query_text=query_text)
    return results


# ─── CLI Demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "a red car parked on the street"
    print(f"\n[KIS Pipeline] Query: {query!r}")
    hits = run_kis(query, top_k=10)

    print(f"\nTop {len(hits)} results:")
    for i, h in enumerate(hits, 1):
        img = " [img]" if h["jpg_path"] else ""
        print(
            f"  #{i:3d}  {h['video_id']}  frame_id={h['frame_id']:6d}  "
            f"t={h['pts_time']:7.1f}s  score={h['score']:.4f}{img}"
        )

    print("\n[Submission rows — first 5]:")
    for h in hits[:5]:
        print(f"  {h['video_id']}, {h['frame_id']}")
