"""
test_gt_loader.py — Kiểm tra module nạp dữ liệu ground truth tập trung từ 3 file con.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from tests.eval.gt_loader import get_gt_path, load_ground_truth, save_ground_truth


def test_get_gt_path_returns_correct_sub_file_paths(tmp_path):
    assert get_gt_path("KIS", tmp_path) == tmp_path / "eval_ground_truth_kis.json"
    assert get_gt_path("qa", tmp_path) == tmp_path / "eval_ground_truth_qa.json"
    assert get_gt_path("TRAKE", tmp_path) == tmp_path / "eval_ground_truth_trake.json"

    with pytest.raises(ValueError, match="Không hỗ trợ type"):
        get_gt_path("INVALID", tmp_path)


def test_load_ground_truth_loads_single_type(tmp_path):
    kis_mock = [{"query_id": "k1", "type": "KIS"}]
    (tmp_path / "eval_ground_truth_kis.json").write_text(json.dumps(kis_mock), encoding="utf-8")

    loaded = load_ground_truth(types="KIS", eval_dir=tmp_path)
    assert loaded == kis_mock


def test_load_ground_truth_loads_and_combines_all_types(tmp_path):
    kis_mock = [{"query_id": "k1", "type": "KIS"}]
    qa_mock = [{"query_id": "q1", "type": "QA"}]
    trake_mock = [{"query_id": "t1", "type": "TRAKE"}]

    (tmp_path / "eval_ground_truth_kis.json").write_text(json.dumps(kis_mock), encoding="utf-8")
    (tmp_path / "eval_ground_truth_qa.json").write_text(json.dumps(qa_mock), encoding="utf-8")
    (tmp_path / "eval_ground_truth_trake.json").write_text(json.dumps(trake_mock), encoding="utf-8")

    loaded = load_ground_truth(eval_dir=tmp_path)
    assert len(loaded) == 3
    assert [d["query_id"] for d in loaded] == ["k1", "q1", "t1"]


def test_save_ground_truth_writes_to_correct_file(tmp_path):
    qa_data = [{"query_id": "q2", "type": "QA"}]
    saved_path = save_ground_truth(qa_data, "QA", eval_dir=tmp_path)
    assert saved_path == tmp_path / "eval_ground_truth_qa.json"
    assert json.loads(saved_path.read_text(encoding="utf-8")) == qa_data
