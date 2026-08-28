"""Hợp nhất các danh sách ứng viên theo Reciprocal Rank Fusion (RRF)."""
from __future__ import annotations


def rrf_fuse_hits(
    model_hits: list[list[dict]], top_k: int = 500, rrf_k: int = 60
) -> list[dict]:
    """Gộp các hit cùng frame theo hạng, không cộng trực tiếp điểm model."""
    if top_k <= 0 or rrf_k < 0:
        return []

    fused: dict[tuple[str, int], dict] = {}
    for hits in model_hits:
        for rank, hit in enumerate(hits, start=1):
            key = (str(hit["video_id"]), int(hit["n"]))
            if key not in fused:
                fused[key] = dict(hit)
                fused[key]["score"] = 0.0
                fused[key]["rrf_ranks"] = []
            fused[key]["score"] += 1.0 / (rrf_k + rank)
            fused[key]["rrf_ranks"].append(rank)

    return sorted(fused.values(), key=lambda hit: -hit["score"])[:top_k]