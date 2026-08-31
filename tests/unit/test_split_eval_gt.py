"""
test_split_eval_gt.py — Kiểm tra tính toàn vẹn và phi huỷ diệt của công cụ tách ground truth.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from tests.eval.split_eval_gt import split_ground_truth

_EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
_KIS_GT = _EVAL_DIR / "eval_ground_truth_kis.json"
_QA_GT = _EVAL_DIR / "eval_ground_truth_qa.json"
_TRAKE_GT = _EVAL_DIR / "eval_ground_truth_trake.json"


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

    kis_file = tmp_path / "eval_ground_truth_kis.json"
    qa_file = tmp_path / "eval_ground_truth_qa.json"
    trake_file = tmp_path / "eval_ground_truth_trake.json"

    assert kis_file.exists()
    assert qa_file.exists()
    assert trake_file.exists()

    loaded_kis = json.loads(kis_file.read_text(encoding="utf-8"))
    assert loaded_kis == [mock_data[0]]


def test_split_files_on_disk_match_expected_counts_and_types():
    """Kiểm tra 3 file con trên đĩa đầy đủ 91 câu với đúng type tương ứng."""
    assert _KIS_GT.exists(), f"Thiếu file {_KIS_GT}"
    assert _QA_GT.exists(), f"Thiếu file {_QA_GT}"
    assert _TRAKE_GT.exists(), f"Thiếu file {_TRAKE_GT}"

    kis = json.loads(_KIS_GT.read_text(encoding="utf-8"))
    qa = json.loads(_QA_GT.read_text(encoding="utf-8"))
    trake = json.loads(_TRAKE_GT.read_text(encoding="utf-8"))

    # 1. Số lượng
    assert len(kis) == 59
    assert len(qa) == 17
    assert len(trake) == 15
    assert len(kis) + len(qa) + len(trake) == 91

    # 2. Type từng file
    assert all(d.get("type") == "KIS" for d in kis)
    assert all(d.get("type") == "QA" for d in qa)
    assert all(d.get("type") == "TRAKE" for d in trake)


def test_split_ground_truth_invalid_inputs(tmp_path):
    """Kiểm tra bắt lỗi đầu vào không hợp lệ."""
    # 1. File không tồn tại
    with pytest.raises(FileNotFoundError):
        split_ground_truth(tmp_path / "non_existent.json")

    # 2. Format không phải list
    bad_json = tmp_path / "bad.json"
    bad_json.write_text(json.dumps({"key": "val"}), encoding="utf-8")
    with pytest.raises(ValueError, match="list"):
        split_ground_truth(bad_json)

    # 3. Type lạ
    bad_type = tmp_path / "bad_type.json"
    bad_type.write_text(json.dumps([{"query_id": "x", "type": "UNKNOWN"}]), encoding="utf-8")
    with pytest.raises(ValueError, match="type không hợp lệ"):
        split_ground_truth(bad_type)
