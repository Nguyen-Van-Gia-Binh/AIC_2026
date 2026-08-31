"""
test_eval_ground_truth.py — Kiểm tra tính toàn vẹn của bộ ground truth.

Vì sao cần: `tests/e2e/golden_kis_snapshot.py` gom kết quả vào dict khoá theo `query_id`. Nếu hai
câu trùng `query_id`, câu sau **ghi đè âm thầm** câu trước — bộ eval mất câu mà không báo gì, và
digest vẫn "khớp" vì các câu còn lại không đổi. Chuyện này đã thật sự xảy ra: 5 câu KIS thêm vào
2026-08-31 dùng lại 4 id đã có (`e-kis-ai-008` xuất hiện 3 lần), làm ảnh chụp vàng lặng lẽ bỏ qua
cả 5 câu mới. Xem docs/decisions-log.md.

Bộ test này không cần `data/` và không cần API key — file ground truth nằm trong git.
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

import pytest

_GT_PATH = Path(__file__).resolve().parents[1] / "eval" / "eval_ground_truth.json"

# TAG_CHUAN có nguồn sự thật duy nhất ở tests/eval/normalize_gt.py — import lại, đừng chép bản thứ
# hai (hai bản sẽ lệch nhau ngay lần đầu ai đó thêm tag mới).
from tests.eval.normalize_gt import TAG_CHUAN  # noqa: E402


def _load() -> list[dict]:
    if not _GT_PATH.exists():
        pytest.skip(f"khong tim thay {_GT_PATH}")
    return json.loads(_GT_PATH.read_text(encoding="utf-8"))


def test_query_id_khong_duoc_trung():
    """Trùng query_id = câu bị ghi đè âm thầm trong golden snapshot."""
    data = _load()
    ids = [q.get("query_id") for q in data]
    trung = [k for k, v in collections.Counter(ids).items() if v > 1]
    assert not trung, (
        f"query_id bi trung: {trung}. Moi cau phai co id duy nhat — "
        f"golden_kis_snapshot.py khoa ket qua theo query_id nen cau trung se bi ghi de am tham."
    )


def test_moi_cau_deu_co_query_id():
    data = _load()
    thieu = [i for i, q in enumerate(data) if not q.get("query_id")]
    assert not thieu, f"cac entry sau thieu query_id (theo chi so): {thieu}"


def test_type_hop_le():
    data = _load()
    xau = [(q.get("query_id"), q.get("type")) for q in data
           if str(q.get("type", "")).upper() not in ("KIS", "QA", "TRAKE")]
    assert not xau, f"type khong hop le: {xau}"


def test_difficulty_tags_nam_trong_danh_sach_chuan():
    """Tag tự do làm breakdown theo dạng khó mất ý nghĩa — xem TAG_CHUAN."""
    data = _load()
    la = sorted({t for q in data for t in q.get("difficulty_tags", []) if t not in TAG_CHUAN})
    assert not la, (
        f"tag ngoai danh sach chuan: {la}. Them vao TAG_CHUAN neu that su can dang moi, "
        f"dung dat tag tu do."
    )
