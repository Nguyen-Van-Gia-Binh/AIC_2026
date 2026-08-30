"""
translate_raw.py — Dich tho VN->EN, KHONG qua LLM (khong goi call_llm()).

Khac voi rewrite.py (rewrite.py dich + toi uu lai cau cho CLIP qua LLM), module nay chi dich may
thuan tuy (deep-translator, boc Google Translate mien phi, khong can API key). Dung de nguoi dung
doi chieu ban dich "tho" (sat nghia goc) voi ban rewrite da qua LLM toi uu, tranh truong hop LLM
rewrite lam lech y ma khong nhan ra.

Usage:
    from scripts.agent.tools.translate_raw import translate_raw
    en = translate_raw("Mot nguoi dang di xe dap tren duong nui")
    # -> "A person is cycling on a mountain road"
"""
from __future__ import annotations

from deep_translator import GoogleTranslator


def translate_raw(text: str, source: str = "vi", target: str = "en") -> str:
    """
    Dich tho 1 cau, khong qua LLM — chi dich may thuan (khong toi uu lai cho CLIP).

    Args:
        text:   Cau can dich (mac dinh coi la tieng Viet).
        source: Ngon ngu goc (mac dinh "vi").
        target: Ngon ngu dich (mac dinh "en").

    Returns:
        Cau da dich. Neu dich loi (mat mang, API doi format...), fail loud —
        nguoi goi (API endpoint) chiu trach nhiem bat exception va tra ve loi ro rang.
    """
    text = text.strip()
    if not text:
        return ""
    return GoogleTranslator(source=source, target=target).translate(text)
