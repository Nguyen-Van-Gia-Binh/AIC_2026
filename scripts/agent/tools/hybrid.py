"""
hybrid.py — Truy xuất lai ghép: Dense (SigLIP) + Sparse (BM25), dung hợp bằng RRF.

Tách khỏi retrieve.py 2026-08-31. `retrieve.py` giữ phần truy vấn dense thuần; file này giữ phần
lai ghép nhiều nguồn — hai mối quan tâm khác nhau, thay đổi vì lý do khác nhau.

Dense và Sparse chạy độc lập trên CÙNG tập keyframe, kết quả dung hợp bằng Reciprocal Rank Fusion
(chỉ dùng THỨ HẠNG — xem fusion.py về lý do không cộng thẳng 2 thang điểm). Sparse chưa build cache
-> tự động chạy dense-only, không crash.

Usage:
    from scripts.agent.tools.hybrid import hybrid_retrieve
    hits = hybrid_retrieve("a red double decker bus", top_k=500)
"""
from __future__ import annotations

import numpy as np

from scripts.agent.tools import index_store

# Số ứng viên BM25 đưa vào dung hợp RRF. CÓ Ý nhỏ hơn nhiều so với pool dense (500): BM25 ở đây chạy
# trên tập từ khoá RẤT THÔ (tên object từ Faster R-CNN + caption, ~5.5K term, doc dài ~10 token) nên
# chỉ đáng tin ở phần ĐỈNH danh sách — càng xuống sâu càng nhiều frame chỉ trùng 1-2 từ chung chung
# ("person", "car"). Đo thật trên 18 câu KIS (2026-08-28): đưa cả 500 ứng viên BM25 vào làm Final tụt
# 0.667 -> 0.656; giới hạn ở đỉnh giữ được phần đóng góp thật mà không kéo rác lên.
SPARSE_TOP_K = 50


def hybrid_retrieve(
    query_text: str,
    top_k: int = 500,
    aspects: list[str] | None = None,
    use_sparse: bool = True,
    qa: bool = False,
    sparse_top_k: int | None = None,
) -> list[dict]:
    """
    Truy xuat lai ghep Dense + Sparse, tra ve pool ung vien da dung hop bang RRF (BAN DAC TA §2).

    Args:
        query_text: Query (tieng Anh cho ket qua tot nhat). Dung cho ca BM25 va (neu khong truyen
                    aspects) cho nhanh dense.
        top_k:      Kich thuoc pool tra ve (mac dinh 500 = RETRIEVAL_POOL_SIZE).
        aspects:    Cac cach dien dat cua cung query cho nhanh dense (query_expand.expand_aspects()).
                    None => chi dung query_text.
        use_sparse: False => chay dense-only (dung de do truoc/sau khi bat hybrid).
        sparse_top_k: So ung vien BM25 dua vao dung hop (None = SPARSE_TOP_K). Nho hon top_k co chu
                    dich — xem SPARSE_TOP_K.
        qa:         True => dung khong gian embedding siglip2 cua Q&A thay vi siglip cua KIS/TRAKE.

    Returns:
        list[dict] cung dinh dang fast_retrieve(), SAP XEP GIAM DAN THEO 'rrf_score', trong do:
          score      — cosine similarity dense GOC (giu nguyen thang do cu cho cac buoc sau)
          rrf_score  — diem dung hop RRF (thu tu list bam theo diem nay)
          rank_dense / rank_sparse — thu hang trong tung he thong (None neu he thong do khong tra ve)
    """
    from scripts.agent.tools.fusion import reciprocal_rank_fusion, RRF_K, W_DENSE, W_SPARSE

    matrix, meta, _ = index_store.get_index(qa=qa)

    texts = aspects if aspects else [query_text]
    dense_scores = matrix @ index_store.encode_mean(texts, qa=qa)
    dense_rows = np.argsort(-dense_scores)[: min(top_k, len(dense_scores))]

    key_of_row = {}
    dense_keys = []
    for r in dense_rows:
        row = meta.iloc[int(r)]
        key = (row["video_id"], int(row["n"]))
        key_of_row[key] = int(r)
        dense_keys.append(key)

    sparse_keys: list = []
    if use_sparse:
        from scripts.agent.tools.sparse_index import search_sparse
        key_index = index_store.key_index(qa=qa)
        n_sparse = SPARSE_TOP_K if sparse_top_k is None else sparse_top_k
        for h in search_sparse(query_text, top_k=n_sparse):
            key = (h["video_id"], int(h["n"]))
            row = key_index.get(key)
            if row is None:
                continue  # keyframe co objects/caption nhung khong co trong index dense -> bo qua
            key_of_row.setdefault(key, row)
            sparse_keys.append(key)

    if not sparse_keys:
        # Khong co tin hieu sparse (chua build cache / query khong co token khop) -> dense-only,
        # giu nguyen thu tu cosine de khong khac gi fast_retrieve().
        hits = [index_store.row_to_hit(meta, key_of_row[k], float(dense_scores[key_of_row[k]])) for k in dense_keys]
        for rank, h in enumerate(hits, start=1):
            h["rrf_score"] = W_DENSE / (RRF_K + rank)
            h["rank_dense"], h["rank_sparse"] = rank, None
        return hits

    dense_rank = {k: i for i, k in enumerate(dense_keys, start=1)}
    sparse_rank = {k: i for i, k in enumerate(sparse_keys, start=1)}
    fused = reciprocal_rank_fusion(
        [(dense_keys, W_DENSE), (sparse_keys, W_SPARSE)], top_k=top_k
    )

    hits = []
    for key, rrf in fused:
        row = key_of_row[key]
        hit = index_store.row_to_hit(meta, row, float(dense_scores[row]))
        hit["rrf_score"] = float(rrf)
        hit["rank_dense"] = dense_rank.get(key)
        hit["rank_sparse"] = sparse_rank.get(key)
        hits.append(hit)

    n_sparse_only = sum(1 for h in hits if h["rank_dense"] is None)
    print(f"[retrieve] hybrid: {len(dense_keys)} dense + {len(sparse_keys)} sparse -> {len(hits)} "
          f"ung vien sau RRF ({n_sparse_only} chi den tu BM25)")
    return hits


def fast_retrieve_multi_model(
    query_text: str,
    model_tags: tuple[str, ...] = ("vitl14", "siglip2", "dfn"),
    top_k: int = 500,
    rrf_k: int = 60,
) -> list[dict]:
    """Tim ung vien bang nhieu model roi gop o muc frame bang RRF.

    Khac voi hybrid_retrieve() (dense + sparse cung 1 model), ham nay chay doc lap nhieu model
    CLIP/SigLIP khac nhau va dung hop ket qua — phu hop cho nut 'use_model_fusion' trong
    pipeline_kis.run_kis(). Cac model phai da build index bang kaggle_jobs/.

    Args:
        query_text:   Query text (tieng Anh cho ket qua tot nhat).
        model_tags:   Tap model de thu nghiem — tag hop le xem MODEL_REGISTRY trong multi_index.py.
        top_k:        So ung vien tra ve sau fusion.
        rrf_k:        Hang so RRF (mac dinh 60, theo Cormack et al. 2009).

    Returns:
        list[dict] da sap xep giam dan theo diem RRF tong hop, cung dinh dang fast_retrieve().
    """
    from scripts.agent.tools.fusion import rrf_fuse_hits
    if not model_tags:
        return []

    stream_hits: list[list[dict]] = []
    per_model_top_k = min(max(top_k, 1), 1000)
    for tag in model_tags:
        matrix, meta, encode_fn = index_store.load_model(tag)
        q_vec = encode_fn(query_text)
        scores = matrix @ q_vec
        top_idx = np.argsort(-scores)[:per_model_top_k]
        hits = []
        for idx in top_idx:
            row = meta.iloc[idx]
            frame_idx = int(row["frame_idx"])
            hits.append({
                "video_id": row["video_id"],
                "n":        int(row["n"]),
                "frame_idx": frame_idx,
                "frame_id": frame_idx + 1,
                "pts_time": float(row["pts_time"]),
                "score":    float(scores[idx]),
                "jpg_path": row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
            })
        stream_hits.append(hits)

    fused = rrf_fuse_hits(stream_hits, top_k=top_k, rrf_k=rrf_k)
    print(f"[retrieve] RRF {list(model_tags)}: {len(fused)} fused frame candidates")
    return fused
