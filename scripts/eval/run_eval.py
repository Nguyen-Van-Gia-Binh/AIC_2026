"""
So sánh baseline embedding (clip_vitb32 hiện tại vs vitl14/siglip/dfn/...) bằng ĐÚNG công thức thi
R@{1,5,20,50,100} (docs/Thong tin vong So tuyen AIC2026.md §2.1), chạy trên bộ eval ground-truth tự
ghi (queries/eval_ground_truth.json — xem queries/EVAL_GUIDE.md để biết cách ghi tay).

Phạm vi (đã chốt trong PLAN.md Phase 6 — xem đó để biết đầy đủ lý do, không lặp lại ở đây):
  - Chỉ đo chất lượng RETRIEVAL: video_id khớp + frame_id nằm trong [gt_frame_start, gt_frame_end].
    KHÔNG chấm lại answer text QA, KHÔNG chạy full pipeline_qa/pipeline_trake, KHÔNG gọi LLM.
  - TRAKE: chấm từng event độc lập như 1 query KIS riêng (retrieve full-corpus bằng text sự kiện
    đó), R@k của cả câu = trung bình R@k của N event — bám cấu trúc 1/N Σ của công thức thật.
  - Không đụng scripts/index.py / scripts/agent/tools/retrieve.py — xem scripts/eval/multi_index.py.

Usage:
    .venv\\Scripts\\python.exe scripts\\eval\\run_eval.py
    .venv\\Scripts\\python.exe scripts\\eval\\run_eval.py --models clip_vitb32,vitl14
    .venv\\Scripts\\python.exe scripts\\eval\\run_eval.py --eval-set queries\\eval_ground_truth.json --out docs\\eval_baseline_comparison.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from multi_index import MODEL_REGISTRY, retrieve  # noqa: E402

_REPO_ROOT = _THIS_DIR.parent.parent
_DEFAULT_EVAL_SET = _REPO_ROOT / "queries" / "eval_ground_truth.json"
_DEFAULT_OUT = _REPO_ROOT / "docs" / "eval_baseline_comparison.md"

K_VALUES = [1, 5, 20, 50, 100]
MAX_K = max(K_VALUES)

_REQUIRED_FIELDS = {
    "KIS": ["text_en", "gt_video_id", "gt_frame_start", "gt_frame_end"],
    "QA": ["text_en", "gt_video_id", "gt_frame_start", "gt_frame_end"],
    "TRAKE": ["gt_video_id", "events"],
}


def load_eval_set(path: Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit(f"[run_eval] {path} phải là 1 mảng JSON ở top-level")
    return data


def _validate_query(q: dict) -> None:
    """Fail loud với thông báo rõ ràng nếu thiếu field — đúng quy ước lỗi setup/data trong CLAUDE.md."""
    qid = q.get("query_id", "?")
    qtype = q.get("type")
    if qtype not in _REQUIRED_FIELDS:
        raise SystemExit(
            f"[run_eval] query_id={qid}: type='{qtype}' không hợp lệ (chỉ nhận KIS/QA/TRAKE)"
        )
    missing = [f for f in _REQUIRED_FIELDS[qtype] if f not in q]
    if missing:
        raise SystemExit(
            f"[run_eval] query_id={qid} ({qtype}): thiếu field {missing} — xem queries/EVAL_GUIDE.md"
        )
    if qtype == "TRAKE":
        if not q["events"]:
            raise SystemExit(f"[run_eval] query_id={qid}: 'events' rỗng")
        for i, ev in enumerate(q["events"]):
            ev_missing = [f for f in ("text_en", "gt_frame_start", "gt_frame_end") if f not in ev]
            if ev_missing:
                raise SystemExit(f"[run_eval] query_id={qid}: events[{i}] thiếu field {ev_missing}")


def _first_hit_rank(hits: pd.DataFrame, gt_video_id: str, gt_start: int, gt_end: int) -> Optional[int]:
    match = hits[
        (hits["video_id"] == gt_video_id)
        & (hits["frame_id"] >= gt_start)
        & (hits["frame_id"] <= gt_end)
    ]
    if match.empty:
        return None
    return int(match["rank"].min())


def _r_at_k_from_rank(rank: Optional[int]) -> dict[int, float]:
    return {k: (1.0 if rank is not None and rank <= k else 0.0) for k in K_VALUES}


def score_kis_like(tag: str, text: str, gt_video_id: str, gt_start: int, gt_end: int) -> dict[int, float]:
    """Dùng chung cho KIS và QA (QA chỉ chấm phần retrieval — xem docstring module)."""
    hits = retrieve(tag, text, top_k=MAX_K)
    rank = _first_hit_rank(hits, gt_video_id, int(gt_start), int(gt_end))
    return _r_at_k_from_rank(rank)


def score_trake(tag: str, gt_video_id: str, events: list[dict]) -> dict[int, float]:
    per_event = []
    for ev in events:
        hits = retrieve(tag, ev["text_en"], top_k=MAX_K)
        rank = _first_hit_rank(hits, gt_video_id, int(ev["gt_frame_start"]), int(ev["gt_frame_end"]))
        per_event.append(_r_at_k_from_rank(rank))
    return {k: float(np.mean([pe[k] for pe in per_event])) for k in K_VALUES}


def run_for_model(tag: str, eval_set: list[dict]) -> dict[str, list[dict[int, float]]]:
    grouped: dict[str, list[dict[int, float]]] = {"ALL": [], "KIS": [], "QA": [], "TRAKE": []}
    for q in eval_set:
        qtype = q["type"]
        if qtype in ("KIS", "QA"):
            scores = score_kis_like(tag, q["text_en"], q["gt_video_id"], q["gt_frame_start"], q["gt_frame_end"])
        else:  # TRAKE (đã validate ở trên)
            scores = score_trake(tag, q["gt_video_id"], q["events"])
        grouped["ALL"].append(scores)
        grouped[qtype].append(scores)
    return grouped


def aggregate(grouped: dict[str, list[dict[int, float]]]) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for group, scores_list in grouped.items():
        if not scores_list:
            out[group] = {k: float("nan") for k in K_VALUES}
            continue
        out[group] = {k: float(np.mean([s[k] for s in scores_list])) for k in K_VALUES}
    return out


def format_markdown_table(results: dict[str, dict[str, dict[int, float]]], eval_set: list[dict]) -> str:
    n_by_type = {"ALL": len(eval_set), "KIS": 0, "QA": 0, "TRAKE": 0}
    for q in eval_set:
        n_by_type[q["type"]] += 1

    lines = [
        "# So sánh baseline embedding — Phase 6\n",
        f"Bộ eval: {len(eval_set)} query (KIS={n_by_type['KIS']}, QA={n_by_type['QA']}, "
        f"TRAKE={n_by_type['TRAKE']}). Điểm = R@k đúng công thức thi "
        "(docs/Thong tin vong So tuyen AIC2026.md §2.1), CHỈ đo chất lượng retrieval — QA không "
        "chấm answer text, TRAKE chấm từng event độc lập rồi lấy trung bình (xem PLAN.md Phase 6 "
        "và docstring scripts/eval/run_eval.py để biết đầy đủ phạm vi/lý do).\n",
    ]
    for group in ("ALL", "KIS", "QA", "TRAKE"):
        if n_by_type[group] == 0:
            continue
        lines.append(f"\n## {group} (n={n_by_type[group]})\n")
        lines.append("| model | " + " | ".join(f"R@{k}" for k in K_VALUES) + " |")
        lines.append("|---" * (len(K_VALUES) + 1) + "|")
        for tag, groups in results.items():
            row = groups[group]
            cells = " | ".join(f"{row[k]:.3f}" for k in K_VALUES)
            lines.append(f"| {tag} | {cells} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--eval-set", type=Path, default=_DEFAULT_EVAL_SET)
    parser.add_argument("--models", type=str, default=",".join(MODEL_REGISTRY.keys()),
                         help="Danh sách tag cách nhau bởi dấu phẩy, ví dụ clip_vitb32,vitl14")
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    args = parser.parse_args()

    eval_set = load_eval_set(args.eval_set)
    if not eval_set:
        raise SystemExit(
            f"[run_eval] {args.eval_set} đang rỗng — chưa có ground truth để chấm. "
            "Xem queries/EVAL_GUIDE.md."
        )
    for q in eval_set:
        _validate_query(q)
    print(f"[run_eval] Đọc {len(eval_set)} query hợp lệ từ {args.eval_set}")

    tags = [t.strip() for t in args.models.split(",") if t.strip()]
    for t in tags:
        if t not in MODEL_REGISTRY:
            raise SystemExit(f"[run_eval] Model tag lạ: '{t}' — có sẵn: {list(MODEL_REGISTRY.keys())}")

    results: dict[str, dict[str, dict[int, float]]] = {}
    for tag in tags:
        print(f"\n[run_eval] === Model: {tag} ===")
        grouped = run_for_model(tag, eval_set)
        results[tag] = aggregate(grouped)

    table = format_markdown_table(results, eval_set)
    print("\n" + table)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(table, encoding="utf-8")
    print(f"[run_eval] Đã ghi {args.out}")


if __name__ == "__main__":
    main()
