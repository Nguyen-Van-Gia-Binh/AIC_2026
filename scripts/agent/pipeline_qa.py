"""
pipeline_qa.py — Pipeline Q&A: Orchestrator + Tool-use, tối đa 2 vòng verify-rewrite.

Workflow (BẢN ĐẶC TẢ §4):
  query_vi
    -> rewrite_query()            -> query_en
    -> hybrid_retrieve(qa=True)   -> pool 500 (dense + BM25, dung hợp RRF — §2)
    -> apply_risk_aware_ranking() -> top-100 hits (xếp theo rrf_score)
    -> answer_by_video_cluster()  -> MỖI video trong top cụm có answer RIÊNG của nó (§4.1)
    -> nếu confidence cụm tốt nhất < 0.5:
         -> rewrite_query(feedback) -> query_en_v2 -> retrieve + trả lời lại, giữ kết quả tốt hơn
    -> build_qa_results: dòng nộp bài thuộc video nào mang answer CỦA CHÍNH video đó

Điểm khác quan trọng so với bản trước (§4.1): KHÔNG còn gán cùng 1 đáp án của video top-1 cho cả
100 dòng. Nếu video top-1 sai nhưng video đúng nằm ở hạng 7, dòng của video hạng 7 vẫn mang đáp án
đúng của chính nó -> R@20/R@50/R@100 không bị về 0 vì "answer sai".

Model embedding Q&A: xem index_store.py (env AIC_QA_MODEL). ⚠️ Mặc định trong code hiện là `siglip`,
trong khi bake-off 33 query (2026-08-28) cho QA-retrieval Final = 0.440 với `siglip2` so với 0.120
với `siglip` — chênh lệch x3.7. Sai lệch giữa code và tài liệu này CHƯA được xử lý: xem PLAN.md P2.1.

Output: list[dict] {video_id, frame_id, answer, score} đã sắp xếp
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent  # repo root — cho `import scripts.*`
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.config import MAX_AGENT_LOOPS
from scripts.agent.tools.hybrid import hybrid_retrieve
from scripts.agent.tools.rewrite import rewrite_query
from scripts.agent.tools.answer_qa import answer_from_hits
from scripts.agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE

CONFIDENCE_THRESHOLD = 0.5  # Dưới ngưỡng này: thử lại vòng 2

# Số cụm video (top theo điểm) được trích xuất answer RIÊNG (§4.1 "Top 3-5 cụm video"). Mỗi cụm tốn
# thêm 1-3 lượt gọi LLM (Tier 1/Tier 2 + crosscheck) nên đây là đánh đổi chi phí/độ phủ: 3 cụm bao
# phủ được phần lớn trường hợp video đúng không phải top-1, vẫn giữ chi phí ở mức chấp nhận được.
MAX_ANSWER_CLUSTERS = 3

# Số keyframe tốt nhất CỦA MỖI CỤM đưa vào answer_from_hits().
CLUSTER_TOP_FRAMES = 5


def _cluster_by_video(hits: list[dict], score_key: str = "rrf_score") -> list[tuple[str, list[dict]]]:
    """Gom hits thành cụm theo video_id, sắp xếp cụm theo điểm tốt nhất trong cụm (giảm dần).
    Hits trong mỗi cụm giữ nguyên thứ tự (đã sắp xếp sẵn từ bước rerank)."""
    by_video: dict[str, list[dict]] = {}
    best: dict[str, float] = {}
    for h in hits:
        vid = h["video_id"]
        by_video.setdefault(vid, []).append(h)
        val = float(h.get(score_key, h.get("score", 0.0)))
        if vid not in best or val > best[vid]:
            best[vid] = val
    return sorted(by_video.items(), key=lambda kv: -best[kv[0]])


def answer_by_video_cluster(
    question: str,
    hits: list[dict],
    max_clusters: int = MAX_ANSWER_CLUSTERS,
) -> tuple[dict, dict]:
    """
    Trích xuất answer ĐỘC LẬP cho từng video trong top cụm (§4.1).

    Returns:
        (answers, best): `answers` = {video_id: answer} cho các cụm đã chạy; `best` = kết quả
        answer_from_hits() của cụm có confidence cao nhất (dùng làm đáp án mặc định cho các dòng
        thuộc video ngoài top cụm, và làm tín hiệu confidence cho vòng lặp).
    """
    clusters = _cluster_by_video(hits)[:max_clusters]
    answers: dict[str, str] = {}
    best: dict = {"answer": "", "best_hit": {}, "confidence": 0.0, "method": "fallback"}

    for vid, cluster_hits in clusters:
        result = answer_from_hits(question, cluster_hits, top_n=CLUSTER_TOP_FRAMES)
        answers[vid] = result["answer"]
        print(f"[qa]   Cum {vid}: answer={result['answer']!r} conf={result['confidence']:.2f} "
              f"method={result['method']}")
        if result["confidence"] > best["confidence"]:
            best = result
    return answers, best


def run_qa(
    query_text: str,
    question: str | None = None,
    top_k: int = 100,
    query_en: str | None = None,
    use_hybrid: bool = True,
) -> dict:
    """
    Chạy pipeline Q&A đầy đủ.

    Args:
        query_text: Mô tả cảnh cần tìm (tiếng Việt hoặc Anh).
        question:   Câu hỏi cụ thể (nếu None, dùng query_text làm question).
        top_k:      Số kết quả retrieve tối đa (100 theo rule BTC).
        query_en:   Nếu có (vd. người dùng đã xem/sửa câu rewrite trong UI — xem
                    agent/tools/rewrite.py rewrite_query_candidates() + frontend/), bỏ qua rewrite
                    vòng 1 và dùng thẳng giá trị này để retrieve. Vòng 2 (confidence thấp) vẫn tự
                    rewrite lại bình thường từ query_text gốc — đây là auto-retry nội bộ, không phải
                    bước preview thủ công.
        use_hybrid: Bật nhánh Sparse BM25 + RRF (§2). Tắt = chỉ dense như trước.

    Returns:
        dict:
          results  (list[dict]): Top-100 {video_id, frame_id, answer, score} — answer THEO TỪNG VIDEO
          answer   (str):        Câu trả lời của cụm tốt nhất (dùng cho UI/tóm tắt)
          answers_by_video (dict): {video_id: answer} đã trích xuất theo cụm
          best_hit (dict):       Hit có confidence cao nhất
          n_loops  (int):        Số vòng loop đã chạy
    """
    if question is None:
        question = query_text

    pool_size = max(top_k, RETRIEVAL_POOL_SIZE)

    def _retrieve_and_rank(q_en: str) -> list[dict]:
        raw = hybrid_retrieve(q_en, top_k=pool_size, use_sparse=use_hybrid, qa=True)
        return apply_risk_aware_ranking(raw, top_k=top_k, query_text=q_en, score_key="rrf_score")

    # ─── Vòng 1 ────────────────────────────────────────────────────────────────
    if query_en:
        print(f"[qa] Vòng 1: dùng query_en có sẵn (bỏ qua rewrite): {query_en!r}", flush=True)
    else:
        print("[qa] Vòng 1: rewrite + retrieve...", flush=True)
        query_en = rewrite_query(query_text, question=question)
        print(f"[qa]   query_en: {query_en!r}")

    hits = _retrieve_and_rank(query_en)
    print(f"[qa]   Retrieved: {len(hits)} hits, top score={hits[0]['score']:.4f}" if hits
          else "[qa]   Retrieved: 0 hits")

    answers, qa_result = answer_by_video_cluster(question, hits)
    print(f"[qa]   Answer tốt nhất (vòng 1): {qa_result['answer']!r}  "
          f"conf={qa_result['confidence']:.2f}  method={qa_result['method']}")

    n_loops = 1

    # ─── Vòng 2 (nếu cần) ──────────────────────────────────────────────────────
    if qa_result["confidence"] < CONFIDENCE_THRESHOLD and n_loops < MAX_AGENT_LOOPS:
        feedback = f"Top results did not clearly answer: {question}. Objects found: {_summarize_top_objects(hits[:5])}"
        print(f"[qa] Confidence thấp ({qa_result['confidence']:.2f}), thử vòng 2...")

        query_en_v2 = rewrite_query(query_text, feedback=feedback, question=question)
        print(f"[qa]   query_en_v2: {query_en_v2!r}")

        hits_v2 = _retrieve_and_rank(query_en_v2)
        answers_v2, qa_result_v2 = answer_by_video_cluster(question, hits_v2)
        print(f"[qa]   Answer tốt nhất (vòng 2): {qa_result_v2['answer']!r}  "
              f"conf={qa_result_v2['confidence']:.2f}")

        # Chọn kết quả tốt hơn
        if qa_result_v2["confidence"] > qa_result["confidence"]:
            qa_result, hits, answers = qa_result_v2, hits_v2, answers_v2

        n_loops = 2

    # ─── Build submission results ───────────────────────────────────────────────
    # Dòng thuộc video nào mang answer CỦA CHÍNH video đó (§4.1); video ngoài top cụm (chưa chạy
    # trích xuất riêng) dùng answer của cụm tốt nhất làm mặc định — vẫn hơn là bỏ trống.
    best_answer = qa_result["answer"]
    results = []
    for h in hits:
        results.append({
            "video_id":  h["video_id"],
            "frame_id":  h["frame_id"],
            "frame_idx": h["frame_idx"],
            "pts_time":  h["pts_time"],
            "score":     h["score"],
            "answer":    answers.get(h["video_id"], best_answer),
            "jpg_path":  h.get("jpg_path"),
        })

    n_own = sum(1 for r in results if r["video_id"] in answers)
    print(f"[qa]   {n_own}/{len(results)} dòng mang answer riêng của video mình "
          f"({len(answers)} cum da trich xuat)")

    return {
        "results":  results,
        "answer":   best_answer,
        "answers_by_video": answers,
        "best_hit": qa_result["best_hit"],
        "n_loops":  n_loops,
        "confidence": qa_result["confidence"],
    }


def _summarize_top_objects(hits: list[dict]) -> str:
    """Tóm tắt objects của top hits thành chuỗi ngắn."""
    from scripts.agent.tools.objects_lookup import get_objects
    all_objs = []
    for h in hits:
        n = h.get("n")
        if n:
            all_objs.extend(get_objects(h["video_id"], int(n))[:5])
    return ", ".join(list(dict.fromkeys(all_objs))[:15]) or "none"

# Bo test: tests/unit/test_pipeline_qa.py

# ─── CLI Demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    query = "Một người đang phát biểu trước đám đông, mặc áo trắng"
    question = "What color is the speaker's shirt?"

    print(f"\n[QA Pipeline] Query: {query!r}")
    print(f"[QA Pipeline] Question: {question!r}\n")

    out = run_qa(query, question, top_k=20)

    print("\n=== KẾT QUẢ ===")
    print(f"  Answer:     {out['answer']!r}")
    print(f"  Confidence: {out['confidence']:.2f}")
    print(f"  N_loops:    {out['n_loops']}")
    print(f"  Answer/video: {out['answers_by_video']}")
    print(f"  Best hit:   {out['best_hit'].get('video_id')} frame_id={out['best_hit'].get('frame_id')}")
    print(f"\n  Top-5 submission rows:")
    for r in out["results"][:5]:
        print(f"    {r['video_id']}, {r['frame_id']}, {r['answer']!r}  (score={r['score']:.4f})")
