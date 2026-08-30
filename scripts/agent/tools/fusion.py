"""
fusion.py — Reciprocal Rank Fusion (RRF) de dung hop ket qua Dense (SigLIP cosine) va Sparse (BM25).

Vi sao KHONG cong thang 2 diem: cosine similarity nam trong [-1, 1] (thuc te SigLIP ~0.05-0.15,
CLIP ~0.28-0.31 — xem ocr_read.py) con BM25 nam trong [0, +inf) va thay doi theo do hiem cua term.
Cong/chuan hoa min-max deu bi lech nang theo tung query. RRF chi dung THU HANG (rank), khong dung
gia tri diem, nen mien nhiem hoan toan voi chenh lech thang do:

    RRF(d) = w_dense / (k + rank_dense(d)) + w_sparse / (k + rank_sparse(d))

k = 60 la gia tri chuan trong bai goc (Cormack et al. 2009) — du lon de 1 vai vi tri dau khong ap
dao toan bo, du nho de rank 1-100 van tach biet ro.

Module THUAN (pure): khong doc index, khong goi model, khong I/O — nen dung duoc ca o duong
production (scripts/agent/tools/retrieve.py) lan o nhanh eval (tests/eval/run_eval.py) ma khong
keo theo viec nap SigLIP/index (tests/eval/multi_index.py van tu nap index rieng nhu cu).

Usage:
    from scripts.agent.tools.fusion import reciprocal_rank_fusion
    fused = reciprocal_rank_fusion(
        [(dense_keys, W_DENSE), (sparse_keys, W_SPARSE)]
    )  # -> [(key, rrf_score), ...] giam dan
"""
from __future__ import annotations

# Tham so chuan hoa — xem BAN DAC TA §2.2.
RRF_K = 60
W_DENSE = 0.75
W_SPARSE = 0.25


def reciprocal_rank_fusion(
    ranked_lists: list, k: int = RRF_K, top_k: int | None = None
) -> list:
    """
    Dung hop nhieu danh sach da xep hang thanh 1 danh sach duy nhat bang RRF.

    Args:
        ranked_lists: list cac tuple (keys, weight) — `keys` la list key (bat ky kieu hashable nao,
                      vd tuple (video_id, n)) DA sap xep giam dan theo do phu hop cua he thong do;
                      `weight` la trong so cua he thong do.
        k:            Hang so lam min RRF (mac dinh 60).
        top_k:        Cat bot ket qua tra ve (None = tra het).

    Returns:
        list[tuple[key, float]] sap xep giam dan theo diem RRF. Key chi xuat hien o 1 he thong van
        duoc giu (chi cong 1 so hang) — RRF khong doi hoi giao nhau.
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
    """Gop cac hit (dict) cung frame theo hang, khong cong truc tiep diem model.

    Khac voi reciprocal_rank_fusion() (lam viec tren key hashable + trong so), ham nay nhan truc tiep
    list[list[dict]] tu nhieu model va tra ve list[dict] da gop — tien cho fast_retrieve_multi_model()
    trong retrieve.py.

    Args:
        model_hits: list cac danh sach hit (moi phan tu la list[dict] tu 1 model, da sap xep giam dan
                    theo diem). Moi hit dict phai co 'video_id' va 'n'.
        top_k:      So ung vien tra ve toi da.
        rrf_k:      Hang so lam min RRF (mac dinh 60).

    Returns:
        list[dict] sap xep giam dan theo diem RRF tong hop. Truong 'score' trong dict duoc ghi de
        bang diem RRF (khong phai cosine goc). Truong 'rrf_ranks' chua danh sach hang trong tung model.
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
