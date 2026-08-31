"""
test_phase4_trake.py — Benchmark that cho pipeline_trake.py (Phase 4: DP tang dan + cross-check
tang 3) tren cac cau TRAKE that trong tests/eval/eval_ground_truth.json.

Metric (khac KIS/QA — TRAKE la 1 phuong an tron ven cho ca chuoi N moc, khong phai 1 dong/moc):
  - video_rank:      video co gt_video_id dung nam o hang thu may trong results (None = khong xuat
                      hien trong top_k_video ung vien).
  - events_matched:  CHI tinh cho cac cau video #1 (best) DUNG — trong so do, bao nhieu event co
                      frame_id du doan nam trong [gt_frame_start, gt_frame_end] cua chinh event do,
                      DUNG THU TU (khop tung phan tu cua danh sach du doan voi danh sach that).

Chay 2 lan (2-pass) trong cung 1 process, tren cung dau vao da rewrite-bypass (xem comment ngay duoi
day) — Pass 1 tat cross-check (TRAKE_CROSSCHECK_MARGIN=-1.0, gia lap hanh vi "chi co Task 1/DP"),
Pass 2 bat cross-check that (margin=0.012, "Task 1 + Task 2"). Vi ca 2 pass dung chung 1 lan retrieval
deterministic, phan chenh lech giua 2 pass co the quy thang cho cross-check, khong con lan voi bien
thien cua LLM rewrite.

Usage:
    .venv\\Scripts\\python.exe tests\\Test\\test_phase4_trake.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # tests/e2e/ -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.pipeline_trake import run_trake
import scripts.agent.pipeline_trake as _trake_module

# Benchmark-only: rewrite_query() goi LLM (temperature=0.2, khong cache) ngay ca khi text da la tieng
# Anh san (dung text_en tu eval_ground_truth.json) — gay bien thien ket qua retrieval giua cac lan
# chay, lam so sanh "truoc/sau" khong con dang tin cay. Thay bang identity function CHI trong benchmark
# nay (khong dung production code) — giong cach tests/e2e/test_phase3_rerank.py da tranh van de nay bang
# cach goi fast_retrieve(text_en) truc tiep thay vi qua pipeline co rewrite.
_trake_module.rewrite_query = lambda text: text

EVAL_SET_PATH = _ROOT / "tests" / "eval" / "eval_ground_truth.json"


def _rank_of_video(results: list[dict], gt_video_id: str) -> int | None:
    for i, r in enumerate(results, start=1):
        if r["video_id"] == gt_video_id:
            return i
    return None


def _run_pass(queries: list[dict], label: str) -> dict:
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

        print(f"  [{label}] {q['query_id']}: video_rank={rank}  "
              f"events_matched={events_matched}/{len(q['events'])}  (gt_video={q['gt_video_id']})")

    n = len(queries)
    return {
        "n": n,
        "video_top1": n_video_top1,
        "video_any_rank": n_video_found_any_rank,
        "events_matched": total_events_matched,
        "events_total": total_events,
    }


def main() -> None:
    eval_set = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    queries = [q for q in eval_set if q["type"] == "TRAKE"]
    print(f"[test_phase4] {len(queries)} cau TRAKE tu {EVAL_SET_PATH}")
    print(f"[test_phase4] rewrite_query() da bi thay bang identity (chi trong benchmark nay) de ket qua"
          f" on dinh giua cac lan chay — xem comment o dau file.")

    real_margin = _trake_module.TRAKE_CROSSCHECK_MARGIN
    print(f"\n[test_phase4] === Pass 1: DP only (cross-check TAT, margin=-1.0) ===")
    _trake_module.TRAKE_CROSSCHECK_MARGIN = -1.0
    before = _run_pass(queries, "before")

    print(f"\n[test_phase4] === Pass 2: DP + cross-check (margin={real_margin}) ===")
    _trake_module.TRAKE_CROSSCHECK_MARGIN = real_margin
    after = _run_pass(queries, "after")

    print("\n[test_phase4] === Tom tat truoc/sau (cung 1 lan chay, deterministic) ===")
    print(f"  Video dung hang #1:            {before['video_top1']}/{before['n']}  ->  "
          f"{after['video_top1']}/{after['n']}")
    print(f"  Video xuat hien (bat ky hang): {before['video_any_rank']}/{before['n']}  ->  "
          f"{after['video_any_rank']}/{after['n']}")
    print(f"  Event frame dung (video #1 dung): {before['events_matched']}/{before['events_total']}  ->  "
          f"{after['events_matched']}/{after['events_total']}")


if __name__ == "__main__":
    main()
