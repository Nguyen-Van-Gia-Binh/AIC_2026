"""
sweep_rerank.py — Parameter sweep harness cho Risk-Aware Re-ranking (P2.4 + P2.7).

Chạy grid search trên các tham số của rerank (MARGIN_THRESHOLD, head_n, preserve_recall_tail, bet/spread)
để hỗ trợ phân tích khi có tập Ground Truth lớn (>= 100 câu).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.agent.tools.retrieve import fast_retrieve
from scripts.agent.tools.hybrid import hybrid_retrieve
from scripts.agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE
from scripts.agent.tools.temporal_nms import temporal_nms
from tests.e2e.score_pipelines import _final

_DEFAULT_GT = _ROOT / "tests" / "eval" / "eval_ground_truth_kis.json"
if not _DEFAULT_GT.exists():
    _DEFAULT_GT = _ROOT / "data" / "extracted" / "THUNGHIEM-bo-de-thi" / "eval_ground_truth_kis.json"



def evaluate_hits(hits: list[dict], q: dict) -> dict[int, float]:
    """Tính R@1, R@5, R@20, R@50, R@100 cho một query KIS."""
    ranks = [1, 5, 20, 50, 100]
    out = {k: 0.0 for k in ranks}

    gt_windows = q.get("ground_truth_windows", [])
    if not gt_windows and "gt_video_id" in q:
        gt_windows = [{
            "video_id": q["gt_video_id"],
            "start_frame": int(q.get("gt_frame_start", 0)),
            "end_frame": int(q.get("gt_frame_end", float("inf"))),
        }]

    for rank_idx, h in enumerate(hits, start=1):
        vid = h["video_id"]
        fid = int(h["frame_id"])
        for w in gt_windows:
            if w.get("video_id") == vid:
                start = int(w.get("start_frame", 0))
                end = int(w.get("end_frame", float("inf")))
                lo, hi = (start, end) if start <= end else (end, start)
                if lo <= fid <= hi:
                    for k in ranks:
                        if rank_idx <= k:
                            out[k] = 1.0
                    return out
    return out


def run_sweep(
    eval_set_path: Path,
    margin_thresholds: list[float] | None = None,
    head_n_values: list[int] | None = None,
    use_hybrid: bool = True,
) -> list[dict[str, Any]]:
    """Thực hiện sweep trên tập KIS queries."""
    if margin_thresholds is None:
        margin_thresholds = [0.005, 0.008, 0.010, 0.012, 0.015, 0.020, 0.025, 0.050]
    if head_n_values is None:
        head_n_values = [0, 10, 20, 30]

    with open(eval_set_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Lọc câu KIS có GT
    kis_queries = [
        q for q in data
        if q.get("type", "").upper() == "KIS" and (q.get("ground_truth_windows") or q.get("gt_video_id"))
    ]

    if not kis_queries:
        print(f"[sweep_rerank] Không tìm thấy câu KIS nào có ground_truth_windows trong {eval_set_path}")
        return []

    print(f"[sweep_rerank] Chuẩn bị pool retrieval cho {len(kis_queries)} câu KIS (pool={RETRIEVAL_POOL_SIZE})...")
    precomputed_pools: list[tuple[dict, list[dict]]] = []
    for q in kis_queries:
        text = q.get("text_en", q.get("text", ""))
        if use_hybrid:
            pool = hybrid_retrieve(text, top_k=RETRIEVAL_POOL_SIZE)
        else:
            pool = fast_retrieve(text, top_k=RETRIEVAL_POOL_SIZE)
        precomputed_pools.append((q, pool))

    results = []

    # 1. Baseline thuần (không rerank, chỉ temporal_nms)
    base_scores = []
    for q, pool in precomputed_pools:
        base_hits = temporal_nms(pool, score_key="score" if not use_hybrid else "rrf_score")[:100]
        base_scores.append(evaluate_hits(base_hits, q))
    avg_base = {k: sum(s[k] for s in base_scores) / len(base_scores) for k in [1, 5, 20, 50, 100]}
    results.append({
        "config": "No rerank (Retrieval + NMS only)",
        "margin_threshold": None,
        "head_n": None,
        "preserve_tail": None,
        "R@1": avg_base[1],
        "R@5": avg_base[5],
        "R@20": avg_base[20],
        "R@50": avg_base[50],
        "R@100": avg_base[100],
        "Final": _final(avg_base),
    })

    # 2. Sweep Grid
    for m_th in margin_thresholds:
        for hn in head_n_values:
            for tail in [True, False]:
                if not tail and hn != head_n_values[0]:
                    # Nếu tail=False thì head_n không có ý nghĩa -> bỏ qua duplicate
                    continue
                q_scores = []
                for q, pool in precomputed_pools:
                    text = q.get("text_en", q.get("text", ""))
                    ranked = apply_risk_aware_ranking(
                        pool,
                        top_k=100,
                        query_text=text,
                        score_key="rrf_score" if use_hybrid else "score",
                        margin_key="score",
                        margin_threshold=m_th,
                        apply_nms=True,
                        preserve_recall_tail=tail,
                        head_n=hn,
                    )
                    q_scores.append(evaluate_hits(ranked, q))

                avg = {k: sum(s[k] for s in q_scores) / len(q_scores) for k in [1, 5, 20, 50, 100]}
                cfg_name = f"m_th={m_th:.4f} | head_n={hn:02d} | tail={tail}"
                results.append({
                    "config": cfg_name,
                    "margin_threshold": m_th,
                    "head_n": hn,
                    "preserve_tail": tail,
                    "R@1": avg[1],
                    "R@5": avg[5],
                    "R@20": avg[20],
                    "R@50": avg[50],
                    "R@100": avg[100],
                    "Final": _final(avg),
                })

    return results


def format_table(results: list[dict[str, Any]]) -> str:
    """Format kết quả sweep thành markdown table sắp xếp giảm dần theo Final Score."""
    sorted_res = sorted(results, key=lambda x: x["Final"], reverse=True)
    lines = [
        "| Cấu hình | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted_res:
        lines.append(
            f"| {r['config']} | {r['R@1']:.3f} | {r['R@5']:.3f} | {r['R@20']:.3f} | "
            f"{r['R@50']:.3f} | {r['R@100']:.3f} | **{r['Final']:.3f}** |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep Rerank Parameters Harness")
    parser.add_argument("--eval-set", type=Path, default=_DEFAULT_GT, help="Đường dẫn file ground truth")
    parser.add_argument("--out-json", type=Path, default=None, help="Ghi kết quả ra file JSON")
    args = parser.parse_args()

    results = run_sweep(args.eval_set)
    table = format_table(results)
    print("\n# KẾT QUẢ PARAMETER SWEEP RERANK\n")
    print(table)

    if args.out_json and results:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_json, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n[sweep_rerank] Đã lưu {args.out_json}")


if __name__ == "__main__":
    main()
