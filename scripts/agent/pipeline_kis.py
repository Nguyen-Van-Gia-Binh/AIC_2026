"""
pipeline_kis.py — Pipeline KIS tuyến tính (không LLM, không loop).

Workflow:
    query_text → SigLIP(top_k=500) → apply_risk_aware_ranking() → rerank_by_ocr() → top_k

Câu hỏi tiếng Việt: kết quả sẽ thấp hơn vì các model retrieval hiểu tiếng Anh tốt hơn.
Cố ý KHÔNG tự dịch VN→EN ở đây — quyết định kiến trúc đã chốt: KIS là workflow tuyến tính, không
LLM (xem ARCHITECTURE.md §3). Dịch VN→EN được đặt ở tầng UI (`scripts/app.py`, checkbox
auto-translate gọi `agent/tools/rewrite.py`), không phải trong pipeline này.

Bước cuối rerank_by_ocr() (nhánh feat/ocr-matching-keyframes) KHÔNG phải LLM — chỉ OCR that (PaddleOCR
Detection + VietOCR Recognition, xem agent/tools/ocr_read.py) trên top_n_ocr candidate ĐÃ matching sẵn
bằng CLIP, và CHỈ chạy khi query có dấu hiệu chứa chữ/số cụ thể (biển số, năm, tỷ số...) — CLIP/SigLIP
giỏi về ngữ nghĩa nhưng không đọc được text cụ thể trên khung hình. An toàn tuyệt đối: không match gì
thì trả về nguyên thứ tự CLIP, không có rủi ro regression.

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

from scripts.agent.tools.retrieve import fast_retrieve, fast_retrieve_multi_model
from scripts.agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE
from scripts.agent.tools.ocr_read import query_likely_has_readable_text, rerank_by_ocr


def run_kis(
    query_text: str,
    top_k: int = 100,
    use_ocr_rerank: bool = True,
    use_model_fusion: bool = False,
) -> list[dict]:
    """
    Chạy pipeline KIS tuyến tính.

    Args:
        query_text: Mô tả cảnh cần tìm (tiếng Anh cho kết quả tốt nhất).
        top_k: Số kết quả trả về, tối đa 100.
        use_ocr_rerank: Cho phép tắt bước rerank_by_ocr() (vd để benchmark/so sánh trước-sau —
            xem test_eval/) — mặc định bật, tự nhận biết query có cần OCR hay không, không cần set thủ công.
        use_model_fusion: Dùng RRF trên ViT-L/14, SigLIP2 và DFN trước khi rerank — mặc định tắt.

    Returns:
        list[dict] đã xếp hạng giảm dần theo score (đã qua risk-aware rerank — xem
        agent/tools/rerank.py — rồi qua rerank_by_ocr() nếu query có dấu hiệu cần đọc chữ/số cụ thể),
        mỗi item có: video_id, frame_id, frame_idx, pts_time, score, jpg_path
    """
    pool_size = max(top_k, RETRIEVAL_POOL_SIZE)
    if use_model_fusion:
        results = fast_retrieve_multi_model(query_text, top_k=pool_size)
        print(f"[kis] RRF fusion: {len(results)} ung vien tu 3 model")
    else:
        results = fast_retrieve(query_text, top_k=pool_size)
    print(f"[kis] Lay {len(results)} ung vien tho (pool={pool_size}), rerank cat ve top_k={top_k}")
    # Không trộn hit đào sâu từ một model đơn vào điểm RRF khác thang đo.
    rerank_query = None if use_model_fusion else query_text
    results = apply_risk_aware_ranking(results, top_k=top_k, query_text=rerank_query)

    if use_ocr_rerank and query_likely_has_readable_text(query_text):
        print(f"[kis] Query co dau hieu chua chu/so cu the -> chay rerank_by_ocr() tren top ung vien")
        results = rerank_by_ocr(results, query_text, top_n_ocr=min(20, len(results)))

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
