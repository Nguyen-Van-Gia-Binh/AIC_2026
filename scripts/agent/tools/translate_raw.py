"""
translate_raw.py — Dịch thô VN->EN, KHÔNG qua LLM (không gọi call_llm()).

Khác với rewrite.py (rewrite.py dịch + tối ưu lại câu cho CLIP qua LLM), module này chỉ dịch máy
thuần tuý (deep-translator, bọc Google Translate miễn phí, không cần API key). Dùng để người dùng
đối chiếu bản dịch "thô" (sát nghĩa gốc) với bản rewrite đã qua LLM tối ưu, tránh trường hợp LLM
rewrite làm lệch ý mà không nhận ra.

Usage:
    from scripts.agent.tools.translate_raw import translate_raw
    en = translate_raw("Một người đang đi xe đạp trên đường núi")
    # -> "A person is cycling on a mountain road"
"""
from __future__ import annotations

from deep_translator import GoogleTranslator


def translate_raw(text: str, source: str = "vi", target: str = "en") -> str:
    """
    Dịch thô 1 câu, không qua LLM — chỉ dịch máy thuần (không tối ưu lại cho CLIP).

    Args:
        text:   Câu cần dịch (mặc định coi là tiếng Việt).
        source: Ngôn ngữ gốc (mặc định "vi").
        target: Ngon ngu dich (mac dinh "en").

    Returns:
        Câu đã dịch. Nếu dịch lỗi (mất mạng, API đổi format...), fail loud —
        người gọi (API endpoint) chịu trách nhiệm bắt exception và trả về lỗi rõ ràng.
    """
    text = text.strip()
    if not text:
        return ""
    return GoogleTranslator(source=source, target=target).translate(text)
