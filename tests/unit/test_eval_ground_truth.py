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

from tests.eval.gt_loader import load_ground_truth, get_gt_path, GT_FILENAMES  # noqa: E402
from tests.eval.normalize_gt import TAG_CHUAN  # noqa: E402


def _load() -> list[dict]:
    data = load_ground_truth()
    if not data:
        pytest.skip("Khong tim thay du lieu ground truth trong tests/eval/")
    return data


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


def test_sub_files_co_cau_truc_hop_le_va_khong_trung_id():
    """Kiểm tra cả 3 file con KIS, QA, TRAKE đều hợp lệ và không trùng query_id."""
    for expected_type in GT_FILENAMES:
        path = get_gt_path(expected_type)
        if not path.exists():
            continue
        items = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(items, list), f"{path.name} phai chua mot JSON array"
        assert all(str(x.get("type", "")).upper() == expected_type for x in items), (
            f"Moi phan tu trong {path.name} phai co type la {expected_type}"
        )
        ids = [x.get("query_id") for x in items]
        trung = [k for k, v in collections.Counter(ids).items() if v > 1]
        assert not trung, f"File {path.name} co query_id bi trung: {trung}"


# ─── Regression Guard ──────────────────────────────────────────────────────────

def test_regression_guard_khong_bao_dong_gia_khi_chay_tung_phan(tmp_path, capsys):
    """Chạy --types qa rồi so ALL (5 câu QA) với ALL của baseline (38 câu cả 3 loại) sẽ luôn báo
    suy thoái giả. Đã xảy ra thật khi đo P2.1 ngày 2026-08-31."""
    import json as _json

    from tests.e2e.score_pipelines import check_regression

    baseline = tmp_path / "baseline.json"
    baseline.write_text(_json.dumps({
        "saved_at": "test",
        "finals": {"ALL": 0.456, "KIS": 0.643, "QA": 0.040, "TRAKE": 0.233},
    }), encoding="utf-8")

    # Chỉ chạy QA: QA tốt lên (0.040 -> 0.160), ALL thấp hơn baseline nhưng KHÔNG cùng đơn vị.
    regressed = check_regression({"ALL": 0.160, "QA": 0.160}, baseline)
    assert regressed is False, "so ALL cua lan chay tung phan voi ALL day du = bao dong gia"
    assert "BO QUA so sanh" in capsys.readouterr().out


def test_regression_guard_van_bao_khi_that_su_tut(tmp_path):
    import json as _json

    from tests.e2e.score_pipelines import check_regression

    baseline = tmp_path / "baseline.json"
    baseline.write_text(_json.dumps({
        "saved_at": "test", "finals": {"ALL": 0.456, "QA": 0.400},
    }), encoding="utf-8")
    assert check_regression({"ALL": 0.100, "QA": 0.100}, baseline) is True
