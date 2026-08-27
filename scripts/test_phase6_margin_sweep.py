"""
test_phase6_margin_sweep.py — Do TRAKE_CROSSCHECK_MARGIN o nhieu gia tri khac nhau tren cung 1 lan
retrieval (PLAN.md Phase 6: "Tinh chinh TRAKE_CROSSCHECK_MARGIN").

CHI IN BANG SO LIEU — khong tu chon nguong "tot nhat". Nguoi dung tu doc bang ket qua va quyet dinh
gia tri cuoi cung cho TRAKE_CROSSCHECK_MARGIN trong scripts/agent/pipeline_trake.py, roi tu chinh tay
neu muon doi.

Tai dung dung logic tinh diem (_run_pass/_rank_of_video) va cach khu nhieu rewrite_query (monkeypatch
thanh identity) da co san o scripts/test_phase4_trake.py — khong viet lai (DRY).

Usage (chay that, can data/extracted/ + LLM key hop le vi run_trake() con goi rewrite_query cho tung
event — da bi patch thanh identity o day, nhung fast_retrieve van can index/model that):
    .venv\\Scripts\\python.exe scripts\\test_phase6_margin_sweep.py
    .venv\\Scripts\\python.exe scripts\\test_phase6_margin_sweep.py --margins -1.0,0.006,0.012,0.018,0.024,0.030

Self-test (khong can data/extracted/, khong goi model that):
    .venv\\Scripts\\python.exe scripts\\test_phase6_margin_sweep.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEFAULT_MARGINS = [-1.0, 0.006, 0.012, 0.018, 0.024, 0.030]


def _sweep(margins: list[float]) -> list[dict]:
    """Chay _run_pass() 1 lan cho moi gia tri margin, tra ve list dict (1 dict/margin)."""
    import scripts.test_phase4_trake as t4

    eval_set = json.loads(t4.EVAL_SET_PATH.read_text(encoding="utf-8"))
    queries = [q for q in eval_set if q["type"] == "TRAKE"]
    print(f"[margin_sweep] {len(queries)} cau TRAKE tu {t4.EVAL_SET_PATH}")
    if not queries:
        raise SystemExit("[margin_sweep] Khong co cau TRAKE nao trong eval set - xem EVAL_GUIDE.md")

    rows = []
    for m in margins:
        t4._trake_module.TRAKE_CROSSCHECK_MARGIN = m
        label = f"margin={m}"
        print(f"\n[margin_sweep] === {label} ===")
        result = t4._run_pass(queries, label)
        result["margin"] = m
        rows.append(result)
    return rows


def _print_table(rows: list[dict]) -> None:
    print("\n[margin_sweep] === Bang tong hop (nguoi dung tu doc, KHONG tu ket luan) ===")
    print(f"  {'margin':>8} | {'video_top1':>12} | {'video_any_rank':>15} | {'events_matched':>15}")
    for r in rows:
        print(
            f"  {r['margin']:>8} | {r['video_top1']:>3}/{r['n']:<8} | "
            f"{r['video_any_rank']:>3}/{r['n']:<11} | {r['events_matched']:>3}/{r['events_total']:<11}"
        )


def _self_test() -> None:
    """Khong goi model/index that - fake run_trake() tra ve ket qua co dinh, chi kiem tra vong lap
    sweep + bang tong hop chay dung, khong crash. KHONG danh gia do chinh xac that (viec do la cua
    nguoi dung tren du lieu that - xem docstring dau file)."""
    import scripts.test_phase4_trake as t4

    fake_eval_set = [
        {
            "query_id": "fake-trake-001",
            "type": "TRAKE",
            "text_en": "fake global query",
            "gt_video_id": "L99_V001",
            "events": [
                {"text_en": "event A", "gt_frame_start": 10, "gt_frame_end": 12},
                {"text_en": "event B", "gt_frame_start": 20, "gt_frame_end": 22},
            ],
        }
    ]

    def _fake_run_trake(query_text, events, top_k_video=20, top_k_frame=20):
        return {
            "results": [{"video_id": "L99_V001", "frame_ids": [11, 21], "score": 0.5}],
            "best": {"video_id": "L99_V001", "frame_ids": [11, 21]},
            "n_events": len(events),
        }

    eval_path = _ROOT / "queries" / "_fake_eval_for_selftest.json"
    eval_path.write_text(json.dumps(fake_eval_set), encoding="utf-8")
    try:
        with patch.object(t4, "EVAL_SET_PATH", eval_path), patch.object(t4, "run_trake", _fake_run_trake):
            rows = _sweep([-1.0, 0.012])
    finally:
        eval_path.unlink(missing_ok=True)

    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
    for r in rows:
        assert r["video_top1"] == 1, f"Fake video luon dung hang 1, got {r}"
        assert r["events_matched"] == 2, f"Fake ca 2 event deu dung khoang, got {r}"
    _print_table(rows)
    print("\n[margin_sweep] Self-test PASS (du lieu gia lap, khong phai ket qua that)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--margins", type=str, default=",".join(str(m) for m in DEFAULT_MARGINS))
    parser.add_argument("--self-test", action="store_true", help="Chay self-test bang du lieu gia, khong dung index/model that")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return

    margins = [float(m.strip()) for m in args.margins.split(",") if m.strip()]
    rows = _sweep(margins)
    _print_table(rows)


if __name__ == "__main__":
    main()
