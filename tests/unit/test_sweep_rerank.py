"""
test_sweep_rerank.py — Unit test cho tests/eval/sweep_rerank.py
"""
from __future__ import annotations

from tests.eval.sweep_rerank import evaluate_hits, format_table


def test_evaluate_hits_ranks() -> None:
    hits = [
        {"video_id": "V1", "frame_id": 10},
        {"video_id": "V2", "frame_id": 20},
        {"video_id": "V3", "frame_id": 30},
    ]
    q = {"gt_video_id": "V2", "gt_frame_start": 15, "gt_frame_end": 25}
    scores = evaluate_hits(hits, q)
    assert scores[1] == 0.0
    assert scores[5] == 1.0
    assert scores[20] == 1.0
    assert scores[50] == 1.0
    assert scores[100] == 1.0



def test_format_table() -> None:
    results = [
        {"config": "A", "R@1": 0.2, "R@5": 0.4, "R@20": 0.6, "R@50": 0.8, "R@100": 1.0, "Final": 0.6},
        {"config": "B", "R@1": 0.3, "R@5": 0.5, "R@20": 0.7, "R@50": 0.9, "R@100": 1.0, "Final": 0.68},
    ]
    table = format_table(results)
    assert "Cấu hình" in table
    assert "Final" in table
    # Phải sắp xếp giảm dần theo Final (B trước A)
    assert table.index("config B" if "config B" in table else "B") < table.index("config A" if "config A" in table else "A")
