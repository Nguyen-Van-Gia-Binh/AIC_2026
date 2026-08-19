"""
pipeline_qa.py — Pipeline Q&A: Orchestrator + Tool-use, max 2 vong verify-rewrite.

Workflow:
  query_vi
    -> rewrite_query()      -> query_en
    -> fast_retrieve(100)   -> top-100 hits
    -> answer_from_hits(5)  -> answer + best_hit + confidence
    -> neu confidence < 0.5:
         -> rewrite_query(feedback) -> query_en_v2
         -> fast_retrieve(100)      -> hits_v2
         -> answer_from_hits(5)     -> answer_v2
    -> build_qa_results(hits + answer)

Output: list[dict] {video_id, frame_id, answer, score} da sap xep
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.config import MAX_AGENT_LOOPS
from agent.tools.retrieve import fast_retrieve
from agent.tools.rewrite import rewrite_query
from agent.tools.answer_qa import answer_from_hits

CONFIDENCE_THRESHOLD = 0.5  # Duoi nguong nay: thu lai vong 2


def run_qa(
    query_text: str,
    question: str | None = None,
    top_k: int = 100,
) -> dict:
    """
    Chay pipeline Q&A day du.

    Args:
        query_text: Mo ta canh can tim (tieng Viet hoac Anh).
        question:   Cau hoi cu the (neu None, dung query_text lam question).
        top_k:      So ket qua retrieve toi da (100 theo rule BTC).

    Returns:
        dict:
          results  (list[dict]): Top-100 {video_id, frame_id, answer, score}
          answer   (str):        Cau tra loi tot nhat
          best_hit (dict):       Hit co score cao nhat co answer
          n_loops  (int):        So vong loop da chay
    """
    if question is None:
        question = query_text

    # ─── Vong 1 ────────────────────────────────────────────────────────────────
    print(f"[qa] Vong 1: rewrite + retrieve...", flush=True)
    query_en = rewrite_query(query_text)
    print(f"[qa]   query_en: {query_en!r}")

    hits = fast_retrieve(query_en, top_k=top_k)
    print(f"[qa]   Retrieved: {len(hits)} hits, top score={hits[0]['score']:.4f}")

    # Gan truong 'n' tu meta neu chua co (can cho ocr_lookup)
    _enrich_hits_with_n(hits)

    qa_result = answer_from_hits(question, hits, top_n=5)
    print(f"[qa]   Answer (vong 1): {qa_result['answer']!r}  conf={qa_result['confidence']:.2f}  method={qa_result['method']}")

    n_loops = 1

    # ─── Vong 2 (neu can) ──────────────────────────────────────────────────────
    if qa_result["confidence"] < CONFIDENCE_THRESHOLD and n_loops < MAX_AGENT_LOOPS:
        feedback = f"Top results did not clearly answer: {question}. Objects found: {_summarize_top_objects(hits[:5])}"
        print(f"[qa] Confidence thap ({qa_result['confidence']:.2f}), thu vong 2...")

        query_en_v2 = rewrite_query(query_text, feedback=feedback)
        print(f"[qa]   query_en_v2: {query_en_v2!r}")

        hits_v2 = fast_retrieve(query_en_v2, top_k=top_k)
        _enrich_hits_with_n(hits_v2)

        qa_result_v2 = answer_from_hits(question, hits_v2, top_n=5)
        print(f"[qa]   Answer (vong 2): {qa_result_v2['answer']!r}  conf={qa_result_v2['confidence']:.2f}")

        # Chon ket qua tot hon
        if qa_result_v2["confidence"] > qa_result["confidence"]:
            qa_result = qa_result_v2
            hits      = hits_v2

        n_loops = 2

    # ─── Build submission results ───────────────────────────────────────────────
    # Gan answer cho toan bo hits (submission cho phep 100 rows)
    best_answer = qa_result["answer"]
    results = []
    for h in hits:
        results.append({
            "video_id":  h["video_id"],
            "frame_id":  h["frame_id"],
            "frame_idx": h["frame_idx"],
            "pts_time":  h["pts_time"],
            "score":     h["score"],
            "answer":    best_answer,
            "jpg_path":  h.get("jpg_path"),
        })

    return {
        "results":  results,
        "answer":   best_answer,
        "best_hit": qa_result["best_hit"],
        "n_loops":  n_loops,
        "confidence": qa_result["confidence"],
    }


def _enrich_hits_with_n(hits: list[dict]) -> None:
    """
    Them truong 'n' vao moi hit tu global META (de ocr_lookup dung).
    Sua doi in-place.
    """
    try:
        from agent.tools.retrieve import _META
        if _META is None:
            return
        # Tao lookup: (video_id, frame_idx) -> n
        lookup = {(row["video_id"], int(row["frame_idx"])): int(row["n"])
                  for _, row in _META.iterrows()}
        for h in hits:
            key = (h["video_id"], h["frame_idx"])
            h["n"] = lookup.get(key)
    except Exception:
        pass  # Khong co n thi ocr_lookup se tra []


def _summarize_top_objects(hits: list[dict]) -> str:
    """Tom tat objects cua top hits thanh chuoi ngan."""
    from agent.tools.ocr_lookup import get_objects
    all_objs = []
    for h in hits:
        n = h.get("n")
        if n:
            all_objs.extend(get_objects(h["video_id"], int(n))[:5])
    return ", ".join(list(dict.fromkeys(all_objs))[:15]) or "none"


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
    print(f"  Best hit:   {out['best_hit'].get('video_id')} frame_id={out['best_hit'].get('frame_id')}")
    print(f"\n  Top-5 submission rows:")
    for r in out["results"][:5]:
        print(f"    {r['video_id']}, {r['frame_id']}, {r['answer']!r}  (score={r['score']:.4f})")
