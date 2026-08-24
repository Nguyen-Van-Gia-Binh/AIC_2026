"""
test_phase3_rerank.py — So sanh R@k truoc/sau khi ap dung apply_risk_aware_ranking (Phase 3) tren
cac cau KIS/QA that trong queries/eval_ground_truth.json, dung DUNG duong dan production
(scripts/agent/tools/retrieve.py, model clip_vitb32) — khac voi scripts/eval/run_eval.py (chi so
sanh embedding baseline qua multi_index.py, khong dung retrieve.py).

Usage:
    .venv\\Scripts\\python.exe scripts\\test_phase3_rerank.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.tools.retrieve import fast_retrieve
from scripts.agent.tools.rerank import apply_risk_aware_ranking

K_VALUES = [1, 5, 20, 50, 100]
EVAL_SET_PATH = _ROOT / "queries" / "eval_ground_truth.json"


def _rank_of_gt(hits: list[dict], gt_video_id: str, gt_start: int, gt_end: int) -> int | None:
    for i, h in enumerate(hits, start=1):
        if h["video_id"] == gt_video_id and gt_start <= h["frame_id"] <= gt_end:
            return i
    return None


def _r_at_k(rank: int | None) -> dict[int, float]:
    return {k: (1.0 if rank is not None and rank <= k else 0.0) for k in K_VALUES}


def main() -> None:
    eval_set = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    queries = [q for q in eval_set if q["type"] in ("KIS", "QA")]
    print(f"[test_phase3] {len(queries)} cau KIS/QA tu {EVAL_SET_PATH}")

    before_scores, after_scores = [], []
    for q in queries:
        hits = fast_retrieve(q["text_en"], top_k=100)
        rank_before = _rank_of_gt(hits, q["gt_video_id"], q["gt_frame_start"], q["gt_frame_end"])
        before_scores.append(_r_at_k(rank_before))

        reranked = apply_risk_aware_ranking(hits, top_k=100, query_text=q["text_en"])
        rank_after = _rank_of_gt(reranked, q["gt_video_id"], q["gt_frame_start"], q["gt_frame_end"])
        after_scores.append(_r_at_k(rank_after))

        print(f"  {q['query_id']}: rank_before={rank_before}  rank_after={rank_after}")

    print("\n[test_phase3] === R@k TRUOC/SAU (trung binh tren", len(queries), "cau) ===")
    print("  k    | truoc  | sau")
    for k in K_VALUES:
        b = sum(s[k] for s in before_scores) / len(before_scores)
        a = sum(s[k] for s in after_scores) / len(after_scores)
        flag = "" if a >= b - 1e-9 else "  <-- TE DI"
        print(f"  R@{k:<4}| {b:.3f}  | {a:.3f}{flag}")


if __name__ == "__main__":
    main()
