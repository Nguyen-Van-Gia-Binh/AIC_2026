"""
rewrite_eval.py — Đo tác động của bước CHUẨN BỊ query_en trong pipeline_qa (Phần 1 + 2):

  - <= 64 token  -> encode thẳng 1 câu (verbatim).
  - > 64 token   -> tách câu con theo dấu chấm (subquery.split_subqueries) + retrieve riêng
                    từng câu rồi dung hợp THỨ HẠNG bằng RRF (hybrid_retrieve aspects).

So A/B trên bộ eval ground-truth (KIS + QA), retrieval-only, KHÔNG LLM, tất định:

  BASELINE : hybrid_retrieve(text_en)                      -> câu dài bị SigLIP cắt còn 64 token
  ROUTED   : như pipeline_qa hiện tại (verbatim nếu <=64, split+RRF nếu >64)

Chấm R@k đúng công thức BTC §2.1 (video khớp ∧ frame ∈ [gt_start, gt_end]); Final = (1/5)·Σ R@k
trên K = {1,5,20,50,100}. Chỉ các câu > 64 token mới khác nhau giữa 2 cột — phần còn lại BASELINE
== ROUTED theo thiết kế.

Chạy:
    .venv\\Scripts\\python.exe tests\\eval\\rewrite_eval.py
    .venv\\Scripts\\python.exe tests\\eval\\rewrite_eval.py --types qa        # chỉ QA
    .venv\\Scripts\\python.exe tests\\eval\\rewrite_eval.py --no-sparse       # tắt BM25 (dense-only)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.agent.tools.hybrid import hybrid_retrieve  # noqa: E402
from scripts.agent.tools.fusion import rrf_fuse_hits  # noqa: E402
from scripts.agent.tools.subquery import (  # noqa: E402
    count_tokens, split_subqueries, MAX_ENCODER_TOKENS,
)
from tests.eval.gt_loader import load_ground_truth  # noqa: E402

K_VALUES = (1, 5, 10, 20, 50, 100)
FINAL_K = (1, 5, 20, 50, 100)  # BTC §2.1: Final = (1/5)·Σ R@k
TOP_K = 100


def _first_hit_rank(hits: list[dict], gt_video_id: str, gt_start: int, gt_end: int) -> int | None:
    """Hạng (1-based) của hit ĐẦU TIÊN khớp video + frame ∈ [gt_start, gt_end]; None nếu không có."""
    for rank, h in enumerate(hits, start=1):
        if h["video_id"] == gt_video_id and gt_start <= h["frame_id"] <= gt_end:
            return rank
    return None


def _r_at_k(rank: int | None) -> dict[int, float]:
    return {k: (1.0 if rank is not None and rank <= k else 0.0) for k in K_VALUES}


def _final(r: dict[int, float]) -> float:
    return sum(r[k] for k in FINAL_K) / len(FINAL_K)


def _retrieve(text: str, use_sparse: bool) -> list[dict]:
    """BASELINE: 1 câu, encoder tự cắt nếu > 64 token."""
    return hybrid_retrieve(text, top_k=TOP_K, use_sparse=use_sparse, qa=True)


def _retrieve_split(subs: list[str], use_sparse: bool) -> list[dict]:
    """ROUTED (>64 token): retrieve riêng từng câu con rồi dung hợp THỨ HẠNG bằng RRF — mirror
    pipeline_qa._retrieve_and_rank_multi (không qua apply_risk_aware_ranking, giữ eval thuần retrieval)."""
    streams = [hybrid_retrieve(s, top_k=TOP_K, use_sparse=use_sparse, qa=True) for s in subs]
    return rrf_fuse_hits(streams, top_k=TOP_K)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--types", default="kis,qa", help="Loại GT cần nạp (mặc định 'kis,qa')")
    ap.add_argument("--no-sparse", action="store_true", help="Tắt BM25, chạy dense-only")
    args = ap.parse_args()
    use_sparse = not args.no_sparse

    gt = [q for q in load_ground_truth(types=args.types)
          if q.get("type") in ("KIS", "QA") and q.get("text_en") and "gt_frame_start" in q]
    if not gt:
        raise SystemExit("[rewrite_eval] Không có câu KIS/QA nào hợp lệ trong GT")

    agg = {"base": {k: 0.0 for k in K_VALUES}, "routed": {k: 0.0 for k in K_VALUES}}
    agg_long = {"base": {k: 0.0 for k in K_VALUES}, "routed": {k: 0.0 for k in K_VALUES}}
    n_long = 0
    rows_long: list[tuple] = []

    for q in gt:
        text = q["text_en"]
        vid, s, e = q["gt_video_id"], int(q["gt_frame_start"]), int(q["gt_frame_end"])
        n_tok = count_tokens(text)

        base_hits = _retrieve(text, use_sparse)
        r_base = _r_at_k(_first_hit_rank(base_hits, vid, s, e))

        subs = split_subqueries(text) if n_tok > MAX_ENCODER_TOKENS else []
        if len(subs) >= 2:
            routed_hits = _retrieve_split(subs, use_sparse)
        else:
            routed_hits = base_hits  # <=64 token (hoặc không tách được): routed y hệt baseline
        r_routed = _r_at_k(_first_hit_rank(routed_hits, vid, s, e))

        for k in K_VALUES:
            agg["base"][k] += r_base[k]
            agg["routed"][k] += r_routed[k]
        if n_tok > MAX_ENCODER_TOKENS:
            n_long += 1
            for k in K_VALUES:
                agg_long["base"][k] += r_base[k]
                agg_long["routed"][k] += r_routed[k]
            rows_long.append((
                q["query_id"], q["type"], n_tok, len(split_subqueries(text)),
                _final(r_base), _final(r_routed),
            ))

    n = len(gt)
    print(f"\n[rewrite_eval] {n} câu KIS/QA  |  BM25={'on' if use_sparse else 'off'}  |  "
          f"{n_long} câu > {MAX_ENCODER_TOKENS} token (chỉ nhóm này BASELINE ≠ ROUTED)\n")

    # Bảng per-query cho các câu dài
    if rows_long:
        print(f"  {'query_id':22} {'type':4} {'tok':>4} {'sub':>3} {'Final base':>11} {'Final routed':>13}  Δ")
        print("  " + "-" * 66)
        for qid, ty, tok, nsub, fb, fr in sorted(rows_long, key=lambda r: r[4] - r[5]):
            d = fr - fb
            mark = "  " if abs(d) < 1e-9 else (" +" if d > 0 else " -")
            print(f"  {qid:22} {ty:4} {tok:4d} {nsub:3d} {fb:11.3f} {fr:13.3f} {mark}{d:+.3f}")
        print()

    print(f"ALL ({n} câu — phần lớn trùng nhau vì <=64 token):")
    for tag, a in (("BASELINE", agg["base"]), ("ROUTED", agg["routed"])):
        cells = "  ".join(f"R@{k}={a[k] / n:.3f}" for k in K_VALUES)
        print(f"  {tag:10} {cells}   Final={sum(a[k] for k in FINAL_K) / len(FINAL_K) / n:.4f}")

    if n_long:
        print(f"\nCHỈ {n_long} câu > {MAX_ENCODER_TOKENS} token (nhóm bị ảnh hưởng):")
        for tag, a in (("BASELINE", agg_long["base"]), ("ROUTED", agg_long["routed"])):
            cells = "  ".join(f"R@{k}={a[k] / n_long:.3f}" for k in K_VALUES)
            print(f"  {tag:10} {cells}   Final={sum(a[k] for k in FINAL_K) / len(FINAL_K) / n_long:.4f}")

    fb_all = sum(agg["base"][k] for k in FINAL_K) / len(FINAL_K) / n
    fr_all = sum(agg["routed"][k] for k in FINAL_K) / len(FINAL_K) / n
    print(f"\n[rewrite_eval] Δ Final (ALL)   = {fr_all - fb_all:+.4f}")
    if n_long:
        fbl = sum(agg_long["base"][k] for k in FINAL_K) / len(FINAL_K) / n_long
        frl = sum(agg_long["routed"][k] for k in FINAL_K) / len(FINAL_K) / n_long
        print(f"[rewrite_eval] Δ Final (>64)   = {frl - fbl:+.4f}   "
              f"({'ROUTED tốt hơn' if frl > fbl else 'ROUTED tệ hơn' if frl < fbl else 'hoà'})")


if __name__ == "__main__":
    main()
