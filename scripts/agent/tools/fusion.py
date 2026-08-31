"""
fusion.py — Reciprocal Rank Fusion (RRF) để dung hợp kết quả Dense (SigLIP cosine) và Sparse (BM25).

Vì sao KHÔNG cộng thẳng 2 điểm: cosine similarity nằm trong [-1, 1] (thực tế SigLIP ~0.05-0.15,
CLIP ~0.28-0.31 — xem ocr_read.py) còn BM25 nằm trong [0, +inf) và thay đổi theo độ hiếm của term.
Cộng/chuẩn hoá min-max đều bị lệch nặng theo từng query. RRF chỉ dùng THỨ HẠNG (rank), không dùng
giá trị điểm, nên miễn nhiễm hoàn toàn với chênh lệch thang đo:

    RRF(d) = w_dense / (k + rank_dense(d)) + w_sparse / (k + rank_sparse(d))

k = 60 là giá trị chuẩn trong bài gốc (Cormack et al. 2009) — đủ lớn để 1 vài vị trí đầu không áp
đảo toàn bộ, đủ nhỏ để rank 1-100 vẫn tách biệt rõ.

Module THUẦN (pure): không đọc index, không gọi model, không I/O — nên dùng được cả ở đường
production (scripts/agent/tools/hybrid.py) lẫn ở nhánh eval (tests/eval/run_eval.py) mà không
kéo theo việc nạp SigLIP/index (tests/eval/multi_index.py vẫn tự nạp index riêng như cũ).

Usage:
    from scripts.agent.tools.fusion import reciprocal_rank_fusion
    fused = reciprocal_rank_fusion(
        [(dense_keys, W_DENSE), (sparse_keys, W_SPARSE)]
    )  # -> [(key, rrf_score), ...] giam dan
"""
from __future__ import annotations

# Tham số chuẩn hoá — xem BẢN ĐẶC TẢ §2.2.
RRF_K = 60
W_DENSE = 0.75
W_SPARSE = 0.25


def reciprocal_rank_fusion(
    ranked_lists: list, k: int = RRF_K, top_k: int | None = None
) -> list:
    """
    Dung hợp nhiều danh sách đã xếp hạng thành 1 danh sách duy nhất bằng RRF.

    Args:
        ranked_lists: list các tuple (keys, weight) — `keys` là list key (bất kỳ kiểu hashable nào,
                      vd tuple (video_id, n)) ĐÃ sắp xếp giảm dần theo độ phù hợp của hệ thống đó;
                      `weight` là trọng số của hệ thống đó.
        k:            Hằng số làm mịn RRF (mặc định 60).
        top_k:        Cắt bớt kết quả trả về (None = trả hết).

    Returns:
        list[tuple[key, float]] sắp xếp giảm dần theo điểm RRF. Key chỉ xuất hiện ở 1 hệ thống vẫn
        được giữ (chỉ cộng 1 số hạng) — RRF không đòi hỏi giao nhau.
    """
    scores: dict = {}
    for keys, weight in ranked_lists:
        if not keys or weight == 0:
            continue
        for rank, key in enumerate(keys, start=1):
            scores[key] = scores.get(key, 0.0) + weight / (k + rank)

    fused = sorted(scores.items(), key=lambda kv: -kv[1])
    return fused[:top_k] if top_k else fused


def rrf_fuse_hits(
    model_hits: list, top_k: int = 500, rrf_k: int = 60
) -> list:
    """Gộp các hit (dict) cùng frame theo hạng, không cộng trực tiếp điểm model.

    Khác với reciprocal_rank_fusion() (làm việc trên key hashable + trọng số), hàm này nhận trực tiếp
    list[list[dict]] từ nhiều model và trả về list[dict] đã gộp — tiện cho fast_retrieve_multi_model()
    trong retrieve.py.

    Args:
        model_hits: list các danh sách hit (mỗi phần tử là list[dict] từ 1 model, đã sắp xếp giảm dần
                    theo điểm). Mỗi hit dict phải có 'video_id' và 'n'.
        top_k:      Số ứng viên trả về tối đa.
        rrf_k:      Hằng số làm mịn RRF (mặc định 60).

    Returns:
        list[dict] sắp xếp giảm dần theo điểm RRF tổng hợp. Trường 'score' trong dict được ghi đè
        bằng điểm RRF (không phải cosine gốc). Trường 'rrf_ranks' chứa danh sách hạng trong từng model.
    """
    if top_k <= 0 or rrf_k < 0:
        return []

    fused: dict = {}
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

# Bo test: tests/unit/test_fusion.py + tests/unit/test_rrf_fusion.py
