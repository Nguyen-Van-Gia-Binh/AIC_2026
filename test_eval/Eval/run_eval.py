"""
So sánh baseline embedding (clip_vitb32 hiện tại vs vitl14/siglip/dfn/...) bằng công thức thi
R@{1,5,20,50,100} (docs/Thong tin vong So tuyen AIC2026.md §2.1), chạy trên bộ eval ground-truth tự
ghi (test_eval/Eval/eval_ground_truth.json — xem test_eval/Eval/EVAL_GUIDE.md để biết cách ghi tay).

Phạm vi (đã chốt trong PLAN.md Phase 6/7 — xem đó để biết đầy đủ lý do, không lặp lại ở đây):
  - CHỈ đo chất lượng RETRIEVAL, KHÔNG gọi LLM, deterministic (bake-off backbone embedding).
  - KIS: đúng công thức §2.1.1 — R@k = max_{i≤k} I(video khớp ∧ frame ∈ [s,e]).
  - QA: dùng lại đúng cách chấm KIS — KHÔNG chấm answer text (a_i = GT_a của §2.1.2). Cột QA ở đây
    là "trần retrieval", KHÔNG phải R-Score QA. Muốn Final Score QA thật (có chấm answer) → chạy
    test_eval/Test/score_pipelines.py.
  - TRAKE: proxy retrieval-only bám §2.1.3 — dựng danh sách ỨNG VIÊN có xếp hạng (mỗi ứng viên = 1
    video_id + N frame_id, chuỗi frame_idx không giảm bằng DP), áp CỔNG VIDEO (video sai → R-Score
    0), rồi R@k = max trên k ứng viên đầu. KHÔNG có LLM crosscheck (không phụ thuộc backbone).
  - Không đụng scripts/index.py / scripts/agent/tools/retrieve.py — xem test_eval/Eval/multi_index.py.

Usage:
    .venv\\Scripts\\python.exe test_eval\\Eval\\run_eval.py
    .venv\\Scripts\\python.exe test_eval\\Eval\\run_eval.py --models clip_vitb32,vitl14
    .venv\\Scripts\\python.exe test_eval\\Eval\\run_eval.py --eval-set test_eval\\Eval\\eval_ground_truth.json --out docs\\eval_baseline_comparison.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Console Windows mặc định cp1252 không encode được ký tự tiếng Việt trong log bên dưới — ép UTF-8
# tại điểm import (giống lookup_frame.py / retrieve.py). Bọc try/except cho môi trường không hỗ trợ.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))
from multi_index import MODEL_REGISTRY, retrieve, get_index, get_encoder  # noqa: E402

_REPO_ROOT = _THIS_DIR.parent.parent  # test_eval/Eval/ -> repo root
_DEFAULT_EVAL_SET = _THIS_DIR / "eval_ground_truth.json"
_DEFAULT_OUT = _REPO_ROOT / "docs" / "eval_baseline_comparison.md"

K_VALUES = [1, 5, 20, 50, 100]
MAX_K = max(K_VALUES)

_REQUIRED_FIELDS = {
    "KIS": ["text_en", "gt_video_id", "gt_frame_start", "gt_frame_end"],
    "QA": ["text_en", "gt_video_id", "gt_frame_start", "gt_frame_end"],
    "TRAKE": ["text_en", "gt_video_id", "events"],
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
            f"[run_eval] query_id={qid} ({qtype}): thiếu field {missing} — xem test_eval/Eval/EVAL_GUIDE.md"
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


# Hằng số TRAKE — mirror pipeline_trake.run_trake() (không import module đó, giữ eval độc lập với
# đường production — xem docstring multi_index.py).
_TRAKE_POOL = 500                    # ~ RETRIEVAL_POOL_SIZE: pool global query để rank video
_TRAKE_VIDEO_CANDIDATES = MAX_K      # 100 ứng viên video → R@100 có nghĩa
_TRAKE_FRAMES_PER_EVENT = 20         # ~ top_k_frame: số keyframe/event đưa vào DP


def _best_increasing_chain(event_cands: list[list[tuple[int, int, float]]]) -> Optional[list[int]]:
    """Chọn 1 keyframe/event sao cho frame_idx KHÔNG GIẢM qua từng event và tổng score lớn nhất
    (quy hoạch động) — sao thuật toán từ pipeline_trake._find_best_increasing_chain, KHÔNG import.

    event_cands[i] = list (frame_idx, frame_id, score) của event i (thứ tự bất kỳ).
    Trả về list frame_id (dài N), hoặc None nếu không tồn tại chuỗi hợp lệ.
    """
    n = len(event_cands)
    if n == 0 or any(len(c) == 0 for c in event_cands):
        return None
    NEG = float("-inf")
    dp = [[NEG] * len(c) for c in event_cands]
    back: list[list[Optional[int]]] = [[None] * len(c) for c in event_cands]
    for j, (_, _, s) in enumerate(event_cands[0]):
        dp[0][j] = s
    for i in range(1, n):
        for j, (fidx, _, s) in enumerate(event_cands[i]):
            for k, (pfidx, _, _) in enumerate(event_cands[i - 1]):
                if pfidx > fidx or dp[i - 1][k] == NEG:
                    continue
                cand = dp[i - 1][k] + s
                if cand > dp[i][j]:
                    dp[i][j] = cand
                    back[i][j] = k
    last = n - 1
    best_j = max(range(len(dp[last])), key=lambda j: dp[last][j])
    if dp[last][best_j] == NEG:
        return None
    chain_fid = [0] * n
    chain_score = [0.0] * n
    j: Optional[int] = best_j
    for i in range(last, -1, -1):
        assert j is not None
        chain_fid[i] = event_cands[i][j][1]
        chain_score[i] = event_cands[i][j][2]
        j = back[i][j]
    _best_increasing_chain.last_mean_score = float(np.mean(chain_score))  # type: ignore[attr-defined]
    return chain_fid


def score_trake(tag: str, gt_video_id: str, events: list[dict], global_text_en: str) -> dict[int, float]:
    """Proxy retrieval-only bám §2.1.3: dựng danh sách ứng viên (video + N frame) có xếp hạng, áp
    cổng video, R@k = max trên k ứng viên đầu. Xem docstring module."""
    matrix, meta = get_index(tag)
    encoder = get_encoder(tag)

    # Giai đoạn 1: rank video theo mean score của global query trong pool.
    pool = retrieve(tag, global_text_en, top_k=_TRAKE_POOL)
    video_mean = pool.groupby("video_id")["score"].mean().sort_values(ascending=False)
    cand_videos = list(video_mean.index[:_TRAKE_VIDEO_CANDIDATES])

    ev_vecs = np.asarray(encoder([ev["text_en"] for ev in events]), dtype=np.float32)  # (N, dim)
    vid_col = meta["video_id"].to_numpy()
    fidx_col = meta["frame_idx"].to_numpy()
    fid_col = meta["frame_id"].to_numpy()

    candidates: list[tuple[float, str, list[int]]] = []
    for vid in cand_videos:
        rows = np.nonzero(vid_col == vid)[0]
        if rows.size == 0:
            continue
        scores = matrix[rows] @ ev_vecs.T  # (n_kf, N) — cosine (matrix + ev_vecs đều đã chuẩn hoá)
        event_cands = []
        for j in range(len(events)):
            order = np.argsort(-scores[:, j])[:_TRAKE_FRAMES_PER_EVENT]
            event_cands.append([
                (int(fidx_col[rows[r]]), int(fid_col[rows[r]]), float(scores[r, j])) for r in order
            ])
        chain = _best_increasing_chain(event_cands)
        if chain is None:
            continue
        mean_s = getattr(_best_increasing_chain, "last_mean_score", 0.0)
        candidates.append((mean_s, vid, chain))

    candidates.sort(key=lambda c: -c[0])  # thứ tự "bài nộp"

    def _rscore(vid: str, frame_ids: list[int]) -> float:
        if vid != gt_video_id:
            return 0.0
        hit = sum(
            1 for j, fid in enumerate(frame_ids)
            if int(events[j]["gt_frame_start"]) <= fid <= int(events[j]["gt_frame_end"])
        )
        return hit / len(events)

    rscores = [_rscore(vid, fids) for _, vid, fids in candidates]
    return {k: (max(rscores[:k]) if rscores[:k] else 0.0) for k in K_VALUES}


def run_for_model(tag: str, eval_set: list[dict]) -> dict[str, list[dict[int, float]]]:
    grouped: dict[str, list[dict[int, float]]] = {"ALL": [], "KIS": [], "QA": [], "TRAKE": []}
    for q in eval_set:
        qtype = q["type"]
        if qtype in ("KIS", "QA"):
            scores = score_kis_like(tag, q["text_en"], q["gt_video_id"], q["gt_frame_start"], q["gt_frame_end"])
        else:  # TRAKE (đã validate ở trên)
            scores = score_trake(tag, q["gt_video_id"], q["events"], q["text_en"])
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
        "# So sánh baseline embedding — Phase 6/7\n",
        f"Bộ eval: {len(eval_set)} query (KIS={n_by_type['KIS']}, QA={n_by_type['QA']}, "
        f"TRAKE={n_by_type['TRAKE']}). `Final` = (1/5)·Σ R@k (con số BTC xếp hạng, "
        "docs/Thong tin vong So tuyen AIC2026.md §2.2). **Bake-off retrieval-only, KHÔNG LLM:**\n"
        "- **KIS** — đúng công thức §2.1.1.\n"
        "- **QA** — CHỈ retrieval, KHÔNG chấm answer (a_i = GT_a của §2.1.2); cột QA là trần "
        "retrieval, không phải R-Score QA. Final Score QA thật → test_eval/Test/score_pipelines.py.\n"
        "- **TRAKE** — proxy §2.1.3: ứng viên (video + N frame, chuỗi tăng dần) có xếp hạng + cổng "
        "video + max-trên-ứng-viên; KHÔNG có LLM crosscheck.\n"
        "\n(Xem PLAN.md Phase 6/7 + docstring test_eval/Eval/run_eval.py để biết đầy đủ phạm vi/lý do.)\n",
    ]
    header_cols = [f"R@{k}" for k in K_VALUES] + ["**Final**"]
    for group in ("ALL", "KIS", "QA", "TRAKE"):
        if n_by_type[group] == 0:
            continue
        lines.append(f"\n## {group} (n={n_by_type[group]})\n")
        lines.append("| model | " + " | ".join(header_cols) + " |")
        lines.append("|---" * (len(header_cols) + 1) + "|")
        for tag, groups in results.items():
            row = groups[group]
            final = float(np.mean([row[k] for k in K_VALUES]))
            cells = " | ".join(f"{row[k]:.3f}" for k in K_VALUES) + f" | **{final:.3f}**"
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
            "Xem test_eval/Eval/EVAL_GUIDE.md."
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
