"""
pipeline_qa.py — Pipeline Q&A: Orchestrator + Tool-use, max 2 vong verify-rewrite.

Workflow (BAN DAC TA §4):
  query_vi
    -> rewrite_query()            -> query_en
    -> hybrid_retrieve(qa=True)   -> pool 500 (dense siglip2 + BM25, dung hop RRF — §2)
    -> apply_risk_aware_ranking() -> top-100 hits (xep theo rrf_score)
    -> answer_by_video_cluster()  -> MOI video trong top cum co answer RIENG cua no (§4.1)
    -> neu confidence cum tot nhat < 0.5:
         -> rewrite_query(feedback) -> query_en_v2 -> retrieve + tra loi lai, giu ket qua tot hon
    -> build_qa_results: dong nop bai thuoc video nao mang answer CUA CHINH video do

Diem khac quan trong so voi ban truoc (§4.1): KHONG con gan cung 1 dap an cua video top-1 cho ca
100 dong. Neu video top-1 sai nhung video dung nam o hang 7, dong cua video hang 7 van mang dap an
dung cua chinh no -> R@20/R@50/R@100 khong bi ve 0 vi "answer sai".

Model embedding Q&A: siglip2 (google/siglip2-so400m-patch14-384) — chon vi QA-retrieval Final=0.440
(x3.7 so siglip) trong benchmark 33 query 2026-08-28.

Output: list[dict] {video_id, frame_id, answer, score} da sap xep
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

CONFIDENCE_THRESHOLD = 0.5  # Duoi nguong nay: thu lai vong 2

# So cum video (top theo diem) duoc trich xuat answer RIENG (§4.1 "Top 3-5 cum video"). Moi cum ton
# them 1-3 luot goi LLM (Tier 1/Tier 2 + crosscheck) nen day la danh doi chi phi/do phu: 3 cum bao
# phu duoc phan lon truong hop video dung khong phai top-1, van giu chi phi o muc chap nhan duoc.
MAX_ANSWER_CLUSTERS = 3

# So keyframe tot nhat CUA MOI CUM dua vao answer_from_hits().
CLUSTER_TOP_FRAMES = 5


def _cluster_by_video(hits: list[dict], score_key: str = "rrf_score") -> list[tuple[str, list[dict]]]:
    """Gom hits thanh cum theo video_id, sap xep cum theo diem tot nhat trong cum (giam dan).
    Hits trong moi cum giu nguyen thu tu (da sap xep san tu buoc rerank)."""
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
    Trich xuat answer DOC LAP cho tung video trong top cum (§4.1).

    Returns:
        (answers, best): `answers` = {video_id: answer} cho cac cum da chay; `best` = ket qua
        answer_from_hits() cua cum co confidence cao nhat (dung lam dap an mac dinh cho cac dong
        thuoc video ngoai top cum, va lam tin hieu confidence cho vong lap).
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
    Chay pipeline Q&A day du.

    Args:
        query_text: Mo ta canh can tim (tieng Viet hoac Anh).
        question:   Cau hoi cu the (neu None, dung query_text lam question).
        top_k:      So ket qua retrieve toi da (100 theo rule BTC).
        query_en:   Neu co (vd. nguoi dung da xem/sua cau rewrite trong UI — xem
                    agent/tools/rewrite.py rewrite_query_candidates() + scripts/app.py), bo qua rewrite
                    vong 1 va dung thang gia tri nay de retrieve. Vong 2 (confidence thap) van tu
                    rewrite lai binh thuong tu query_text goc — day la auto-retry noi bo, khong phai
                    buoc preview thu cong.
        use_hybrid: Bat nhanh Sparse BM25 + RRF (§2). Tat = chi dense siglip2 nhu truoc.

    Returns:
        dict:
          results  (list[dict]): Top-100 {video_id, frame_id, answer, score} — answer THEO TUNG VIDEO
          answer   (str):        Cau tra loi cua cum tot nhat (dung cho UI/tom tat)
          answers_by_video (dict): {video_id: answer} da trich xuat theo cum
          best_hit (dict):       Hit co confidence cao nhat
          n_loops  (int):        So vong loop da chay
    """
    if question is None:
        question = query_text

    pool_size = max(top_k, RETRIEVAL_POOL_SIZE)

    def _retrieve_and_rank(q_en: str) -> list[dict]:
        raw = hybrid_retrieve(q_en, top_k=pool_size, use_sparse=use_hybrid, qa=True)
        return apply_risk_aware_ranking(raw, top_k=top_k, query_text=q_en, score_key="rrf_score")

    # ─── Vong 1 ────────────────────────────────────────────────────────────────
    if query_en:
        print(f"[qa] Vong 1: dung query_en co san (bo qua rewrite): {query_en!r}", flush=True)
    else:
        print(f"[qa] Vong 1: rewrite + retrieve...", flush=True)
        query_en = rewrite_query(query_text, question=question)
        print(f"[qa]   query_en: {query_en!r}")

    hits = _retrieve_and_rank(query_en)
    print(f"[qa]   Retrieved: {len(hits)} hits, top score={hits[0]['score']:.4f}" if hits
          else "[qa]   Retrieved: 0 hits")

    answers, qa_result = answer_by_video_cluster(question, hits)
    print(f"[qa]   Answer tot nhat (vong 1): {qa_result['answer']!r}  "
          f"conf={qa_result['confidence']:.2f}  method={qa_result['method']}")

    n_loops = 1

    # ─── Vong 2 (neu can) ──────────────────────────────────────────────────────
    if qa_result["confidence"] < CONFIDENCE_THRESHOLD and n_loops < MAX_AGENT_LOOPS:
        feedback = f"Top results did not clearly answer: {question}. Objects found: {_summarize_top_objects(hits[:5])}"
        print(f"[qa] Confidence thap ({qa_result['confidence']:.2f}), thu vong 2...")

        query_en_v2 = rewrite_query(query_text, feedback=feedback, question=question)
        print(f"[qa]   query_en_v2: {query_en_v2!r}")

        hits_v2 = _retrieve_and_rank(query_en_v2)
        answers_v2, qa_result_v2 = answer_by_video_cluster(question, hits_v2)
        print(f"[qa]   Answer tot nhat (vong 2): {qa_result_v2['answer']!r}  "
              f"conf={qa_result_v2['confidence']:.2f}")

        # Chon ket qua tot hon
        if qa_result_v2["confidence"] > qa_result["confidence"]:
            qa_result, hits, answers = qa_result_v2, hits_v2, answers_v2

        n_loops = 2

    # ─── Build submission results ───────────────────────────────────────────────
    # Dong thuoc video nao mang answer CUA CHINH video do (§4.1); video ngoai top cum (chua chay
    # trich xuat rieng) dung answer cua cum tot nhat lam mac dinh — van hon la bo trong.
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
    print(f"[qa]   {n_own}/{len(results)} dong mang answer rieng cua video minh "
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
    """Tom tat objects cua top hits thanh chuoi ngan."""
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
    query = "Mot nguoi dang phat bieu truoc dam dong, mac ao trang"
    question = "What color is the speaker's shirt?"

    print(f"\n[QA Pipeline] Query: {query!r}")
    print(f"[QA Pipeline] Question: {question!r}\n")

    out = run_qa(query, question, top_k=20)

    print(f"\n=== KET QUA ===")
    print(f"  Answer:     {out['answer']!r}")
    print(f"  Confidence: {out['confidence']:.2f}")
    print(f"  N_loops:    {out['n_loops']}")
    print(f"  Answer/video: {out['answers_by_video']}")
    print(f"  Best hit:   {out['best_hit'].get('video_id')} frame_id={out['best_hit'].get('frame_id')}")
    print(f"\n  Top-5 submission rows:")
    for r in out["results"][:5]:
        print(f"    {r['video_id']}, {r['frame_id']}, {r['answer']!r}  (score={r['score']:.4f})")
