"""
test_phase4_trake.py — Benchmark that cho pipeline_trake.py (Phase 4: DP tang dan + cross-check
tang 3) tren cac cau TRAKE that trong queries/eval_ground_truth.json.

Metric (khac KIS/QA — TRAKE la 1 phuong an tron ven cho ca chuoi N moc, khong phai 1 dong/moc):
  - video_rank:      video co gt_video_id dung nam o hang thu may trong results (None = khong xuat
                      hien trong top_k_video ung vien).
  - events_matched:  CHI tinh cho cac cau video #1 (best) DUNG — trong so do, bao nhieu event co
                      frame_id du doan nam trong [gt_frame_start, gt_frame_end] cua chinh event do,
                      DUNG THU TU (khop tung phan tu cua danh sach du doan voi danh sach that).

Usage:
    .venv\\Scripts\\python.exe scripts\\test_phase4_trake.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.pipeline_trake import run_trake

EVAL_SET_PATH = _ROOT / "queries" / "eval_ground_truth.json"


def _rank_of_video(results: list[dict], gt_video_id: str) -> int | None:
    for i, r in enumerate(results, start=1):
        if r["video_id"] == gt_video_id:
            return i
    return None


def main() -> None:
    eval_set = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    queries = [q for q in eval_set if q["type"] == "TRAKE"]
    print(f"[test_phase4] {len(queries)} cau TRAKE tu {EVAL_SET_PATH}")

    n_video_top1 = 0
    n_video_found_any_rank = 0
    total_events = 0
    total_events_matched = 0

    for q in queries:
        events_text = [ev["text_en"] for ev in q["events"]]
        out = run_trake(q["text_en"], events_text, top_k_video=20, top_k_frame=20)
        results = out["results"]

        rank = _rank_of_video(results, q["gt_video_id"])
        top1_ok = rank == 1
        n_video_top1 += int(top1_ok)
        n_video_found_any_rank += int(rank is not None)

        events_matched = 0
        if top1_ok:
            predicted = results[0]["frame_ids"]
            for fid, ev in zip(predicted, q["events"]):
                lo, hi = sorted((ev["gt_frame_start"], ev["gt_frame_end"]))
                if lo <= fid <= hi:
                    events_matched += 1
        total_events += len(q["events"])
        total_events_matched += events_matched

        print(f"  {q['query_id']}: video_rank={rank}  events_matched={events_matched}/{len(q['events'])}"
              f"  (gt_video={q['gt_video_id']})")

    n = len(queries)
    print("\n[test_phase4] === Tom tat ===")
    print(f"  Video dung hang #1:            {n_video_top1}/{n}")
    print(f"  Video xuat hien (bat ky hang): {n_video_found_any_rank}/{n}")
    print(f"  Event frame dung (trong cac cau video #1 dung): {total_events_matched}/{total_events}")


if __name__ == "__main__":
    main()
