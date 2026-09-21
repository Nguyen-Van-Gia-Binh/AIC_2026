"""Test cho scripts/agent/tools/ocr_read.py — chuyển từ khối __main__ cũ, giữ nguyên mọi assert.

CHỈ giữ các test THUẦN (không cần ảnh thật, không nạp engine OCR). Phần "self-test 2" và "4b" của
khối cũ là kiểm tra bằng mắt trên ảnh thật, không có hard-assert — chúng ở lại khối __main__ của
ocr_read.py dưới dạng CLI demo.
"""
from __future__ import annotations

from scripts.agent.tools.ocr_read import (
    _OCR_JSONL_DIR, _OFFLINE_OCR_CACHE, _extract_literal_tokens, _load_offline_text_map,
    query_likely_has_readable_text, read_text_from_hits, rerank_by_ocr,
)


def _fake_hit(jpg_path: str | None, video_id: str = "", n: int = 0, score: float = 1.0) -> dict:
    return {"video_id": video_id, "n": n, "frame_idx": n, "frame_id": n + 1,
            "pts_time": 0.0, "score": score, "jpg_path": jpg_path}


def test_hits_rong_hoac_jpg_path_khong_ton_tai_khong_crash() -> None:
    assert read_text_from_hits([]) == {}
    assert read_text_from_hits([{"jpg_path": None}]) == {}
    assert read_text_from_hits([{"jpg_path": "khong_ton_tai.jpg"}]) == {}


def test_nhan_biet_query_co_chu_so_cu_the() -> None:
    assert query_likely_has_readable_text("a person walking on the street") is False
    assert query_likely_has_readable_text('biển số xe ghi "AG-09399"') is True
    assert query_likely_has_readable_text("năm 1997 trên tấm bia") is True


def test_trich_token_chu_so_nguyen_van() -> None:
    assert _extract_literal_tokens('biển số xe ghi "AG-09399"') == ["AG-09399"]
    assert _extract_literal_tokens("năm 1997 trên tấm bia") == ["1997"]
    assert _extract_literal_tokens("a person walking") == []


def test_rerank_khong_co_token_thi_giu_nguyen_thu_tu_va_bonus_0() -> None:
    hits = [_fake_hit(None, "L27_V001", 110, score=0.30),
            _fake_hit(None, "L22_V001", 120, score=0.29),
            _fake_hit(None, "L28_V003", 190, score=0.28)]
    out = rerank_by_ocr(hits, "a person walking on the street")
    assert out == hits, "Khong co token van ban -> phai giu nguyen thu tu"
    assert all(h.get("ocr_bonus", 0.0) == 0.0 for h in out)


def test_video_chua_co_file_offline_tra_none() -> None:
    assert _load_offline_text_map(
        "__video_khong_ton_tai__", _OCR_JSONL_DIR, _OFFLINE_OCR_CACHE, "ocr_text"
    ) is None


def test_rerank_khong_ghi_de_score_goc() -> None:
    """rerank_by_ocr chi doi THU TU list; truong `score` goc phai giu nguyen de cac buoc sau
    (va cot diem trong submission) khong bi lech thang do."""
    hits = [_fake_hit(None, "L27_V001", 110, score=0.30),
            _fake_hit(None, "L22_V001", 120, score=0.29),
            _fake_hit(None, "L28_V003", 190, score=0.28)]
    goc = {h["video_id"] + "/" + str(h["n"]): h["score"] for h in hits}
    out = rerank_by_ocr(hits, 'a plaque with the year "1997" on it', top_n_ocr=3)
    for h in out:
        key = h["video_id"] + "/" + str(h["n"])
        assert h["score"] == goc[key], f"score goc bi ghi de o {key}"


# ─── Đường query CHỈ đọc OCR offline, không bao giờ OCR realtime ────────────────
# Lý do: OCR realtime tốn ~37s/ảnh trên máy này (detection bị ép CPU vì xung đột DLL
# paddle/torch), khiến QA mất 400s+/câu trong khi LLM chỉ chiếm ~40s. Xem docstring ocr_read.py.

def _no_realtime_ocr(_path: str):
    raise AssertionError("Đường query đã gọi OCR realtime — phải chỉ đọc OCR offline")


def test_read_text_from_hits_khong_chay_ocr_realtime(monkeypatch, tmp_path) -> None:
    """Có jpg tồn tại thật nhưng video chưa có OCR offline -> trả rỗng, KHÔNG OCR ảnh."""
    monkeypatch.setattr("scripts.agent.tools.ocr_read._ocr_single_image", _no_realtime_ocr)
    jpg = tmp_path / "frame.jpg"
    jpg.write_bytes(b"khong-phai-anh-that")
    hits = [_fake_hit(str(jpg), "__video_khong_ton_tai__", 1)]
    assert read_text_from_hits(hits) == {}


def test_read_text_from_hits_doc_tu_ocr_offline(monkeypatch) -> None:
    """Video đã có OCR offline -> lấy text từ đó (không cần jpg_path)."""
    monkeypatch.setitem(_OFFLINE_OCR_CACHE, "L99_V001", {7: "AG-09399", 8: ""})
    hits = [_fake_hit(None, "L99_V001", 7), _fake_hit(None, "L99_V001", 8)]
    # n=8 có bản ghi nhưng text rỗng (ảnh không có chữ) -> không xuất hiện trong kết quả
    assert read_text_from_hits(hits) == {0: ["AG-09399"]}


def test_rerank_khong_chay_ocr_realtime(monkeypatch, tmp_path) -> None:
    """Query có token cụ thể + jpg tồn tại, nhưng không có OCR offline -> không OCR realtime."""
    monkeypatch.setattr("scripts.agent.tools.ocr_read._ocr_single_image", _no_realtime_ocr)
    jpg = tmp_path / "frame.jpg"
    jpg.write_bytes(b"khong-phai-anh-that")
    hits = [_fake_hit(str(jpg), "__video_khong_ton_tai__", 1, score=0.30),
            _fake_hit(str(jpg), "__video_khong_ton_tai__", 2, score=0.29)]
    out = rerank_by_ocr(hits, 'tấm bia ghi năm "1997"', top_n_ocr=2)
    assert len(out) == 2
    assert all(h.get("ocr_bonus", 0.0) == 0.0 for h in out)
