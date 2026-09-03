"""Test cho scripts/agent/tools/asr_lookup.py — chuyển từ _run_self_tests() cũ, giữ nguyên assert.

Khác các file còn lại trong tests/unit/: bộ test này đọc file ASR THẬT trong data/extracted/ (đây
là cách duy nhất kiểm tra logic ghép segment theo cửa sổ thời gian mà không phải dựng lại dữ liệu
giả kém tin cậy hơn). Tự bỏ qua khi máy chưa giải nén data/ — để `pytest tests/unit` vẫn xanh trên
máy chỉ có source.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.agent.tools.asr_lookup import get_transcript, get_transcript_for_hits

_ASR_DIR = Path(__file__).resolve().parents[2] / "data" / "extracted" / "ASR_json_PhoWhisper_base"

pytestmark = pytest.mark.skipif(
    not _ASR_DIR.is_dir(),
    reason=f"Chua co du lieu ASR tai {_ASR_DIR} — bo qua (xem README: phai giai nen data/ truoc)",
)


def test_ghep_2_segment_khi_cua_so_thoi_gian_giao_ca_hai() -> None:
    """pts_time=20.0, window=7.5 -> [12.5, 27.5] giao segment 0 ([0, 15.1]) va segment 1
    ([15.1, 32.06]) cua L21_V001 -> phai noi ca 2."""
    text = get_transcript("L21_V001", pts_time=20.0, window=7.5)
    assert "chào mừng" in text, f"Phai chua text cua segment 0, duoc: {text!r}"
    assert "sông cửu long" in text, f"Phai chua text cua segment 1, duoc: {text!r}"


def test_ngoai_moi_segment_tra_rong() -> None:
    empty = get_transcript("L21_V001", pts_time=99999.0, window=7.5)
    assert empty == "", f"Ngoai moi segment phai tra rong, duoc: {empty!r}"


def test_video_khong_co_file_asr_tra_rong_khong_crash() -> None:
    missing = get_transcript("L99_V999", pts_time=10.0)
    assert missing == "", f"Video khong ton tai phai tra rong, duoc: {missing!r}"


def test_get_transcript_for_hits_xu_ly_nhieu_hit() -> None:
    hits = [{"video_id": "L21_V001", "pts_time": 20.0},
            {"video_id": "L21_V001", "pts_time": 99999.0}]
    batch = get_transcript_for_hits(hits, window=7.5)
    assert "chào mừng" in batch[0], f"Hit 0 phai co transcript, duoc: {batch[0]!r}"
    assert batch[1] == "", f"Hit 1 (ngoai khoang) phai rong, duoc: {batch[1]!r}"
