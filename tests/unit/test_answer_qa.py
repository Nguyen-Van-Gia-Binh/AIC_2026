"""Test cho answer_qa.py + qa_normalize.py + qa_classify.py — chuyển từ _run_self_tests() cũ.

Giữ nguyên mọi assert. Khối cũ gán đè biến global `call_llm`; ở đây dùng `monkeypatch` và patch
ĐÚNG module chứa hàm — sau khi tách file, canonicalize_answer đọc call_llm của qa_normalize chứ
không phải của answer_qa (patch nhầm thì test gọi LLM thật mà vẫn có vẻ "pass").
"""
from __future__ import annotations

from scripts.agent.tools import answer_qa, qa_normalize
from scripts.agent.tools.answer_qa import answer_from_hits, ocr_direct_answer
from scripts.agent.tools.qa_normalize import canonicalize_answer, is_non_answer

_HIT = {"video_id": "V", "n": 1, "frame_idx": 0, "frame_id": 1, "pts_time": 10.0,
        "score": 0.9, "jpg_path": None}


def test_tang_1_va_crosscheck_deu_nhan_duoc_transcript(monkeypatch) -> None:
    captured: list[str] = []

    def _fake_call_llm(prompt, **kwargs):
        captured.append(prompt)
        if "Detected objects in candidate frames" in prompt:
            return "a red car"
        if "Is this answer plausible" in prompt:
            return "YES"
        return "unexpected prompt"

    monkeypatch.setattr(answer_qa, "call_llm", _fake_call_llm)
    monkeypatch.setattr(answer_qa, "get_objects", lambda vid, n: ["car", "person"])
    monkeypatch.setattr(answer_qa, "get_transcript",
                        lambda vid, pts, window=7.5: "a red car passes by quickly")

    result = answer_from_hits("What color is the car?", [_HIT], top_n=1)
    assert result["method"] == "objects", f"Phai dung Tier 1 (objects), duoc {result['method']}"
    assert result["answer"] == "a red car", f"Answer sai: {result['answer']!r}"

    tier1 = next(p for p in captured if "Detected objects in candidate frames" in p)
    assert "a red car passes by quickly" in tier1, "Tier 1 prompt phai chua transcript hint"
    crosscheck = next(p for p in captured if "Is this answer plausible" in p)
    assert "a red car passes by quickly" in crosscheck, "Crosscheck prompt phai chua transcript"


def test_transcript_rong_khong_crash(monkeypatch) -> None:
    monkeypatch.setattr(answer_qa, "call_llm",
                        lambda prompt, **k: "a red car" if "Detected objects" in prompt else "YES")
    monkeypatch.setattr(answer_qa, "get_objects", lambda vid, n: ["car", "person"])
    monkeypatch.setattr(answer_qa, "get_transcript", lambda vid, pts, window=7.5: "")
    result = answer_from_hits("What color is the car?", [_HIT], top_n=1)
    assert result["method"] == "objects", f"Phai dung Tier 1 (objects), duoc {result['method']}"


def test_canonical_rule_based_khong_goi_llm() -> None:
    assert canonicalize_answer("The answer is: màu trắng") == "màu trắng"
    assert canonicalize_answer("Trong hình có một chiếc xe") == "một chiếc xe"
    assert canonicalize_answer("There are 15 people") == "15 people"
    assert canonicalize_answer("15") == "15", "Answer da chuan phai giu nguyen"


def test_canonical_qua_llm_va_tu_choi_ban_dai_hon(monkeypatch) -> None:
    long_answer = "Ngọn núi xuất hiện trong khung hình này chính là núi Phú Sĩ ở Nhật Bản"

    monkeypatch.setattr(qa_normalize, "call_llm", lambda prompt, **k: "Phú Sĩ")
    assert canonicalize_answer(long_answer, "Núi gì?") == "Phú Sĩ"

    monkeypatch.setattr(qa_normalize, "call_llm",
                        lambda *a, **k: "Đây là một lời giải thích rất dài hơn cả câu trả lời gốc ban đầu")
    assert canonicalize_answer(long_answer, "Núi gì?") == long_answer, (
        "LLM tra ve dai hon -> phai giu ban rule-based"
    )


def test_cong_chong_ao_giac() -> None:
    assert is_non_answer("The text is not legible in any frame") is True
    assert is_non_answer("Không nhìn rõ biển số") is True
    assert is_non_answer("") is True
    assert is_non_answer("màu trắng") is False


def test_ocr_direct_overwrite_rat_chat() -> None:
    assert ocr_direct_answer("Biển số xe là gì?", {0: ["AG 09399"], 1: ["AG 09399"]}) == "09399"
    assert ocr_direct_answer("Biển số xe là gì?", {0: ["09399"], 1: ["12627"]}) is None, (
        "Nhieu chuoi so khac nhau -> khong ghi de, de VLM quyet dinh"
    )
    assert ocr_direct_answer("Có bao nhiêu người trong hình?", {0: ["15"]}) is None, (
        "Cau hoi DEM vat the khong duoc de OCR ghi de"
    )
    assert ocr_direct_answer("Biển số xe là gì?", {}) is None
