"""
pipeline_kis.py — Pipeline KIS tuyến tính (không LLM, không loop).

Workflow (BẢN ĐẶC TẢ §3):
  query_text
    → expand_aspects()          # Multi-Aspect Prompt Expansion, template tất định (§3.1) — mặc định TẮT, xem run_kis()
    → hybrid_retrieve(pool=500) # Dense SigLIP + Sparse BM25, dung hợp bằng RRF (§2)
    → apply_risk_aware_ranking(score_key="rrf_score", apply_nms=True)  # đặt cược / trải rủi ro + Temporal NMS (§3.2)
    → rerank_by_ocr()           # cộng bonus khi OCR/caption khớp chữ-số cụ thể trong query (§3.3)
    → top_k

Câu hỏi tiếng Việt: kết quả sẽ thấp hơn vì SigLIP hiểu tiếng Anh tốt hơn.
Cố ý KHÔNG tự dịch VN→EN ở đây — quyết định kiến trúc đã chốt: KIS là workflow tuyến tính, không
LLM (xem ARCHITECTURE.md §3). Dịch VN→EN được đặt ở tầng UI (`scripts/app.py`, checkbox
auto-translate gọi `agent/tools/rewrite.py`), không phải trong pipeline này. Vì lý do đó,
Multi-Aspect Expansion ở đây dùng template tất định (`query_expand.expand_aspects`), KHÔNG gọi
`expand_aspects_llm()`.

Bước cuối rerank_by_ocr() KHÔNG phải LLM — chỉ OCR that (PaddleOCR Detection + VietOCR Recognition,
xem agent/tools/ocr_read.py) hoặc tra OCR/caption offline trên top_n_ocr candidate ĐÃ matching sẵn,
và CHỈ chạy khi query có dấu hiệu chứa chữ/số cụ thể (biển số, năm, tỷ số...) — CLIP/SigLIP giỏi về
ngữ nghĩa nhưng không đọc được text cụ thể trên khung hình. An toàn tuyệt đối: không match gì thì trả
về nguyên thứ tự cũ, không có rủi ro regression.

Mọi bước mới đều có công tắc riêng (`use_hybrid`/`use_expansion`/`use_nms`) để đo trước-sau bằng
tests/e2e/score_pipelines.py — xem Regression Guard trong BẢN ĐẶC TẢ §6.

Usage:
    from scripts.agent.pipeline_kis import run_kis
    results = run_kis("a cyclist racing on a mountain road")
    # → list[dict] đã rank, dùng trực tiếp cho build_submission.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent  # repo root — cho `import scripts.*`
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.tools.hybrid import hybrid_retrieve
from scripts.agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE
from scripts.agent.tools.query_expand import expand_aspects
from scripts.agent.tools.ocr_read import query_likely_has_readable_text, rerank_by_ocr


def run_kis(
    query_text: str,
    top_k: int = 100,
    use_ocr_rerank: bool = True,
    use_hybrid: bool = True,
    use_expansion: bool = False,
    use_nms: bool = True,
) -> list[dict]:
    """
    Chạy pipeline KIS tuyến tính.

    Args:
        query_text: Mô tả cảnh cần tìm (tiếng Anh cho kết quả tốt nhất).
        top_k: Số kết quả trả về, tối đa 100.
        use_ocr_rerank: Cho phép tắt bước rerank_by_ocr() (vd để benchmark/so sánh trước-sau —
            xem tests/) — mặc định bật, tự nhận biết query có cần OCR hay không, không cần set thủ công.
        use_hybrid: Bật nhánh Sparse BM25 + dung hợp RRF (§2). Tắt = chỉ dense như trước.
            Chưa build cache BM25 thì tự động chạy dense-only (xem agent/tools/sparse_index.py).
        use_expansion: Bật Multi-Aspect Prompt Expansion (§3.1). Tắt = encode đúng 1 câu query gốc.
            **Mặc định TẮT** vì đo thật trên 18 câu KIS của tests (2026-08-28) cho thấy nó làm
            Final tụt 0.667 → 0.644: SigLIP đã được huấn luyện trên caption ảnh thật nên câu query
            gốc thường đã là "caption tốt", còn 2 biến thể template thêm vào chỉ kéo vector truy vấn
            về phía trung bình. Cơ chế vẫn giữ nguyên và bật được bằng cờ này (hoặc
            `run_eval.py --expand`) để đo lại khi có bộ eval lớn hơn / query thật của BTC.
        use_nms: Bật Temporal NMS trong bước xếp hạng (§3.2).

    Returns:
        list[dict] đã xếp hạng, mỗi item có: video_id, frame_id, frame_idx, pts_time, score
        (cosine gốc), rrf_score (điểm dung hợp — thứ tự list bám theo điểm này), jpg_path.
    """
    pool_size = max(top_k, RETRIEVAL_POOL_SIZE)
    aspects = expand_aspects(query_text) if use_expansion else [query_text]
    if len(aspects) > 1:
        print(f"[kis] Multi-aspect: {len(aspects)} góc nhìn cho cùng 1 truy vấn")

    results = hybrid_retrieve(
        query_text, top_k=pool_size, aspects=aspects, use_sparse=use_hybrid
    )
    print(f"[kis] Lấy {len(results)} ứng viên thô (pool={pool_size}), rerank cắt về top_k={top_k}")

    results = apply_risk_aware_ranking(
        results, top_k=top_k, query_text=query_text,
        score_key="rrf_score", apply_nms=use_nms,
    )

    if use_ocr_rerank and query_likely_has_readable_text(query_text):
        print("[kis] Query có dấu hiệu chứa chữ/số cụ thể -> chạy rerank_by_ocr() trên top ứng viên")
        results = rerank_by_ocr(
            results, query_text, top_n_ocr=min(20, len(results)), score_key="rrf_score",
        )

    return results


# ─── CLI Demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "a red car parked on the street"
    print(f"\n[KIS Pipeline] Query: {query!r}")
    hits = run_kis(query, top_k=10)

    print(f"\nTop {len(hits)} results:")
    for i, h in enumerate(hits, 1):
        img = " [img]" if h["jpg_path"] else ""
        src = ""
        if h.get("rank_dense") is None and h.get("rank_sparse") is not None:
            src = "  [chi BM25]"
        print(
            f"  #{i:3d}  {h['video_id']}  frame_id={h['frame_id']:6d}  "
            f"t={h['pts_time']:7.1f}s  cos={h['score']:.4f}  rrf={h.get('rrf_score', 0):.5f}{img}{src}"
        )

    print("\n[Submission rows — first 5]:")
    for h in hits[:5]:
        print(f"  {h['video_id']}, {h['frame_id']}")
