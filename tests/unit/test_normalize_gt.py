"""
test_normalize_gt.py — Bộ test cho tests/eval/normalize_gt.py.

Không cần `data/`, không cần mạng (dịch máy bị monkeypatch), không cần API key.

Điều quan trọng nhất được khoá ở đây: **script KHÔNG tự nới khoảng**. Một entry chỉ ghi
`gt_frame: 305` phải ra `[305, 305]`, không phải một khoảng rộng hơn. Nới rộng làm điểm dễ ăn
⇒ mọi model trông giỏi ⇒ mất khả năng phân biệt. Xem spec Pha 2 §5.2.
"""
from __future__ import annotations

import json

import pytest

from tests.eval.normalize_gt import (
    TAG_CHUAN,
    check_entries,
    convert_entry,
    load_entries,
)


# ─── Chuyển đổi ────────────────────────────────────────────────────────────────

def test_kis_mot_frame_ra_khoang_dung_mot_keyframe():
    """gt_frame duy nhất -> [gt_frame, gt_frame]. KHÔNG được tự nới."""
    out = convert_entry(
        {"query_id": "k1", "type": "KIS", "query_text": "một con mèo",
         "text_en": "a cat", "gt_video_id": "L21_V001", "gt_frame": 305},
        translate=False,
    )
    assert out["gt_frame_start"] == 305
    assert out["gt_frame_end"] == 305


def test_nguoi_ghi_tu_nhap_gt_frame_end_thi_khoang_moi_rong():
    out = convert_entry(
        {"query_id": "k2", "type": "KIS", "query_text": "x", "text_en": "x",
         "gt_video_id": "L21_V001", "gt_frame": 300, "gt_frame_end": 340},
        translate=False,
    )
    assert (out["gt_frame_start"], out["gt_frame_end"]) == (300, 340)


def test_trake_moi_moc_thanh_khoang_rieng():
    out = convert_entry(
        {"query_id": "t1", "type": "TRAKE", "query_text": "chuỗi động tác",
         "text_en": "a sequence", "gt_video_id": "L25_V003",
         "events": [{"text_en": "takes off", "gt_frame": 95},
                    {"text_en": "lands", "gt_frame": 195}]},
        translate=False,
    )
    assert [(e["gt_frame_start"], e["gt_frame_end"]) for e in out["events"]] == [(95, 95), (195, 195)]


def test_qa_giu_question_va_gt_answers():
    out = convert_entry(
        {"query_id": "q1", "type": "QA", "query_text": "cảnh cân cá", "text_en": "weighing fish",
         "question": "What number is shown?", "gt_answers": ["1204"],
         "gt_video_id": "L21_V009", "gt_frame": 21053},
        translate=False,
    )
    assert out["question"] == "What number is shown?"
    assert out["gt_answers"] == ["1204"]


def test_dich_may_duoc_goi_khi_thieu_text_en(monkeypatch):
    """text_en sinh bằng DỊCH MÁY (tất định), không phải LLM — xem docstring normalize_gt.py."""
    import scripts.agent.tools.translate_raw as tr
    monkeypatch.setattr(tr, "translate_raw", lambda text, **kw: "TRANSLATED")

    out = convert_entry(
        {"query_id": "k3", "type": "KIS", "query_text": "một con mèo",
         "gt_video_id": "L21_V001", "gt_frame": 10},
        translate=True,
    )
    assert out["text_en"] == "TRANSLATED"
    assert out["text_en_reviewed"] is False, "phai danh dau la chua co nguoi duyet"


def test_khong_dich_khi_da_co_text_en(monkeypatch):
    import scripts.agent.tools.translate_raw as tr
    monkeypatch.setattr(tr, "translate_raw", lambda text, **kw: pytest.fail("khong duoc goi dich"))

    out = convert_entry(
        {"query_id": "k4", "type": "KIS", "query_text": "x", "text_en": "already english",
         "gt_video_id": "L21_V001", "gt_frame": 10},
        translate=True,
    )
    assert out["text_en"] == "already english"
    assert "text_en_reviewed" not in out


# ─── Đọc file ──────────────────────────────────────────────────────────────────

def test_doc_duoc_ca_hai_format(tmp_path):
    v2 = tmp_path / "v2.json"
    v2.write_text(json.dumps({"entries": [{"query_id": "a"}]}), encoding="utf-8")
    v1 = tmp_path / "v1.json"
    v1.write_text(json.dumps([{"query_id": "a"}]), encoding="utf-8")
    assert load_entries(v2) == load_entries(v1) == [{"query_id": "a"}]


def test_dict_khong_co_entries_thi_bao_loi(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"queries": []}), encoding="utf-8")
    with pytest.raises(SystemExit):
        load_entries(bad)


# ─── Kiểm tra ──────────────────────────────────────────────────────────────────

def _entry_sach(**over):
    e = {"query_id": "k1", "type": "KIS", "query_text": "x", "text_en": "x",
         "gt_video_id": "L21_V001", "gt_frame": 10, "difficulty_tags": []}
    e.update(over)
    return e


def test_check_phat_hien_query_id_trung():
    issues = check_entries([_entry_sach(), _entry_sach()])
    assert any("TRUNG" in m for m in issues)


def test_check_phat_hien_video_id_co_duoi_mp4():
    issues = check_entries([_entry_sach(gt_video_id="L21_V001.mp4")])
    assert any(".mp4" in m for m in issues)


def test_check_phat_hien_tag_ngoai_danh_sach():
    issues = check_entries([_entry_sach(difficulty_tags=["tag_bia_ra"])])
    assert any("tag ngoai danh sach chuan" in m for m in issues)


def test_check_phat_hien_qa_thieu_gt_answers():
    issues = check_entries([_entry_sach(type="QA", question="How many?")])
    assert any("gt_answers" in m for m in issues)


def test_check_phat_hien_gt_answers_khong_phai_mang():
    issues = check_entries([_entry_sach(type="QA", question="How many?", gt_answers="3")])
    assert any("phai la MANG" in m for m in issues)


def test_check_bo_qua_entry_unresolved():
    """Câu chưa tìm được đáp án không bị tính là lỗi — xem EVAL_GUIDE.md."""
    issues = check_entries([{"query_id": "x", "status": "unresolved"}])
    assert issues == []


def test_check_phat_hien_thieu_gt_frame():
    e = _entry_sach()
    del e["gt_frame"]
    issues = check_entries([e])
    assert any("gt_frame" in m for m in issues)


def test_tag_chuan_phu_het_tag_dang_dung_trong_bo_eval():
    """TAG_CHUAN là nguồn sự thật duy nhất — bộ eval thật không được có tag ngoài nó."""
    from pathlib import Path
    gt = Path(__file__).resolve().parents[1] / "eval" / "eval_ground_truth.json"
    if not gt.exists():
        pytest.skip("khong tim thay eval_ground_truth.json")
    data = json.loads(gt.read_text(encoding="utf-8"))
    la = sorted({t for q in data for t in q.get("difficulty_tags", []) if t not in TAG_CHUAN})
    assert not la, f"tag ngoai TAG_CHUAN: {la}"
