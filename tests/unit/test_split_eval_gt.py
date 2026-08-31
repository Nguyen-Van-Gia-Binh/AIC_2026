"""
test_split_eval_gt.py — Kiểm tra tính toàn vẹn và phi huỷ diệt của công cụ tách ground truth.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from tests.eval.split_eval_gt import split_ground_truth


def test_split_ground_truth_preserves_all_records(tmp_path):
    mock_data = [
        {"query_id": "k1", "type": "KIS", "text_vi": "mèo", "text_en": "cat", "gt_video_id": "L21_V001", "gt_frame_start": 1, "gt_frame_end": 2},
        {"query_id": "q1", "type": "QA", "text_vi": "chó?", "text_en": "dog?", "gt_video_id": "L21_V002", "gt_frame_start": 5, "gt_frame_end": 6, "question": "dog?", "gt_answer": "1", "gt_answers": ["1"]},
        {"query_id": "t1", "type": "TRAKE", "text_vi": "chuỗi", "text_en": "seq", "gt_video_id": "L21_V003", "events": [{"text_en": "e1", "gt_frame_start": 10, "gt_frame_end": 20}]},
    ]
    src_file = tmp_path / "eval_ground_truth.json"
    src_file.write_text(json.dumps(mock_data, ensure_ascii=False, indent=2), encoding="utf-8")

    result = split_ground_truth(src_file, tmp_path)

    assert len(result["KIS"]) == 1
    assert len(result["QA"]) == 1
    assert len(result["TRAKE"]) == 1
    assert result["KIS"][0]["query_id"] == "k1"
    assert result["QA"][0]["query_id"] == "q1"
    assert result["TRAKE"][0]["query_id"] == "t1"

    # Kiểm tra file sinh ra trên đĩa
    kis_file = tmp_path / "eval_ground_truth_kis.json"
    qa_file = tmp_path / "eval_ground_truth_qa.json"
    trake_file = tmp_path / "eval_ground_truth_trake.json"

    assert kis_file.exists()
    assert qa_file.exists()
    assert trake_file.exists()

    loaded_kis = json.loads(kis_file.read_text(encoding="utf-8"))
    assert loaded_kis == [mock_data[0]]
