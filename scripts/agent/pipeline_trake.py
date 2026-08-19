"""
pipeline_trake.py — Pipeline TRAKE: Retrieve video + Windowed Alignment.

Workflow co dinh 2 giai doan (khong de LLM tu quyet dinh so buoc):

Giai doan 1 - Retrieval:
  query tong quat -> rewrite -> fast_retrieve(100)
  -> group by video_id -> rank video theo tong score
  -> chon top-5 video candidates

Giai doan 2 - Alignment (N lan, 1 lan / khoang khac):
  For moi video candidate:
    For moi event_i in events[]:
      -> rewrite(event_description_i)
      -> fast_retrieve_for_video(query_i, video_id, top_k=10)
      -> chon frame tot nhat, CO THOI GIAN sau frame[i-1] (world model nhe)
    -> tinh trake_score = trung binh score cac event
  -> Sap xep theo trake_score -> chon video tot nhat

Output: list[dict] {video_id, frame_id_1, ..., frame_id_N}
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import defaultdict

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.tools.retrieve import fast_retrieve, fast_retrieve_for_video
from agent.tools.rewrite import rewrite_query


def run_trake(
    query_text: str,
    events: list[str],
    top_k_video: int = 5,
    top_k_frame: int = 10,
) -> dict:
    """
    Chay pipeline TRAKE day du.

    Args:
        query_text:  Mo ta tong quat chuoi su kien (de tim video).
        events:      Danh sach mo ta tung khoang khac theo thu tu thoi gian.
                     Vi du: ["athlete takes off", "athlete clears bar", "athlete lands"]
        top_k_video: So video candidate de thu alignment (default 5).
        top_k_frame: So frame candidate moi event khi alignment (default 10).

    Returns:
        dict:
          results   (list[dict]): Top submissions, moi item {video_id, frame_ids, score}
          best      (dict):       Ket qua tot nhat.
          n_events  (int):        So khoang khac.
    """
    n_events = len(events)
    print(f"[trake] {n_events} events, finding video candidates...", flush=True)

    # ─── Giai doan 1: Tim video ────────────────────────────────────────────────
    query_en = rewrite_query(query_text)
    print(f"[trake]   Global query: {query_en!r}")

    all_hits = fast_retrieve(query_en, top_k=100)

    # Group by video, tinh tong score top-3 frame moi video
    video_scores: dict[str, float] = defaultdict(float)
    video_frame_count: dict[str, int] = defaultdict(int)

    for h in all_hits:
        vid = h["video_id"]
        video_scores[vid] += h["score"]
        video_frame_count[vid] += 1

    # Normalize theo so frame (lay trung binh) roi rank
    video_avg = {v: s / video_frame_count[v] for v, s in video_scores.items()}
    top_videos = sorted(video_avg, key=lambda v: video_avg[v], reverse=True)[:top_k_video]
    print(f"[trake]   Top {len(top_videos)} videos: {top_videos}")

    # ─── Giai doan 2: Alignment cho tung video ─────────────────────────────────
    # Rewrite tung event query (chi lam 1 lan, dung chung cho moi video)
    event_queries_en = []
    for i, ev in enumerate(events):
        eq = rewrite_query(ev)
        event_queries_en.append(eq)
        print(f"[trake]   Event {i+1}: {ev!r} -> {eq!r}")

    video_results = []

    for vid in top_videos:
        frame_ids = []
        event_scores = []
        prev_frame_idx = -1  # World model: frame sau phai > frame truoc

        for i, eq in enumerate(event_queries_en):
            frame_hits = fast_retrieve_for_video(eq, vid, top_k=top_k_frame)

            if not frame_hits:
                # Fallback: dung frame giua video
                frame_ids.append(1)
                event_scores.append(0.0)
                continue

            # Uu tien frame CO frame_idx > prev_frame_idx (thu tu thoi gian)
            valid = [h for h in frame_hits if h["frame_idx"] > prev_frame_idx]
            chosen = (valid[0] if valid else frame_hits[0])

            frame_ids.append(chosen["frame_id"])
            event_scores.append(chosen["score"])
            prev_frame_idx = chosen["frame_idx"]

        avg_score = sum(event_scores) / len(event_scores) if event_scores else 0.0
        video_results.append({
            "video_id":  vid,
            "frame_ids": frame_ids,
            "score":     avg_score,
            "event_scores": event_scores,
        })

    # Sap xep theo score
    video_results.sort(key=lambda x: x["score"], reverse=True)

    # Build submission format (top-100 rows: moi video la 1 row)
    results = []
    for vr in video_results:
        results.append({
            "video_id":  vr["video_id"],
            "frame_ids": vr["frame_ids"],
            "score":     vr["score"],
        })

    best = results[0] if results else {}
    print(f"[trake]   Best video: {best.get('video_id')}  score={best.get('score', 0):.4f}")
    print(f"[trake]   Frame IDs: {best.get('frame_ids')}")

    return {
        "results":  results,
        "best":     best,
        "n_events": n_events,
    }


# ─── CLI Demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    query = "An athlete performing a high jump: approach, takeoff, clearance, landing"
    events = [
        "athlete running toward the bar during approach run",
        "athlete pushing off the ground at takeoff moment",
        "athlete arching back over the high jump bar at peak",
        "athlete falling onto the mat after clearing the bar",
    ]

    print(f"\n[TRAKE Pipeline]")
    print(f"Query: {query!r}")
    print(f"Events ({len(events)}): {events}\n")

    out = run_trake(query, events, top_k_video=3, top_k_frame=5)

    print(f"\n=== KET QUA ===")
    print(f"  N events:  {out['n_events']}")
    print(f"  Best video: {out['best'].get('video_id')}")
    print(f"  Frame IDs:  {out['best'].get('frame_ids')}")
    print(f"  Score:      {out['best'].get('score', 0):.4f}")

    print(f"\n  Submission rows ({len(out['results'])}):")
    for r in out["results"]:
        fids = ", ".join(str(f) for f in r["frame_ids"])
        print(f"    {r['video_id']}, {fids}  (score={r['score']:.4f})")
