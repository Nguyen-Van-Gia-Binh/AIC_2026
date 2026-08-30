"""
query_expand.py — Multi-Aspect Prompt Expansion cho KIS (BAN DAC TA §3.1).

Y tuong: 1 cau mo ta canh duoc chieu thanh 2-3 "goc nhin thi giac" khac nhau, moi goc nhin encode
thanh 1 vector rieng, roi lay trung binh + chuan hoa:

    q_final = Normalize((q_1 + q_2 + q_3) / 3)

  v1 — Boi canh tong the (global environment)
  v2 — Doi tuong trong tam + vi tri tuong doi (anchor object & spatial position)
  v3 — Mau sac, hanh dong, trang thai dong (color attributes & actions)

Day la ky thuat "prompt ensembling" quen thuoc cua ho CLIP/SigLIP: text encoder rat nhay voi cach
dien dat, trung binh nhieu cach dien dat cua CUNG 1 y lam vector truy van on dinh hon, bot phu thuoc
vao 1 cach dat cau duy nhat.

QUAN TRONG — KIS KHONG goi LLM trong runtime (ARCHITECTURE.md §3, BAN DAC TA §3 "Tuyen tinh, Khong
LLM"): mac dinh o day la template TAT DINH (deterministic), khong ton API call, khong bien thien
giua cac lan chay. Nhanh LLM (expand_aspects_llm) co san nhung PHAI bat tuong minh, va pipeline_kis
khong bao gio tu bat.

Module thuan text (khong doc index/model) — dung duoc ca o eval lan production.

Usage:
    from scripts.agent.tools.query_expand import expand_aspects
    aspects = expand_aspects("a cyclist racing on a mountain road")
    # -> [<goc nhin 1>, <goc nhin 2>, <goc nhin 3>]
"""
from __future__ import annotations

import re

# 3 goc nhin theo BAN DAC TA §3.1. Giu cau ngan va tu nhien — SigLIP duoc huan luyen tren caption
# anh that, cau cang giong caption cang tot; tranh nhoi tu khoa lam loang vector.
ASPECT_TEMPLATES = [
    "{q}",                                                    # v1 — boi canh tong the, giu nguyen van
    "a close-up view of {q}, the main subject in the center of the frame",  # v2 — doi tuong trong tam
    "{q}, showing the colors, clothing and the action taking place",         # v3 — mau sac + hanh dong
]

# Query da dai san (nhieu menh de) thi template v2/v3 chi lam loang them — voi query dai hon nguong
# nay chi giu v1 + v3. Nguong dem theo tu, chon 25 (~2 cau mo ta day du).
LONG_QUERY_WORDS = 25

EXPAND_ASPECTS_PROMPT = """\
Rewrite the following video scene description into exactly 3 short English search captions, each \
describing the SAME scene from a different angle:
1. the overall environment and setting
2. the main subject/object and its position in the frame
3. the colors, clothing and the action taking place

Scene: {query}

Reply with exactly 3 lines, one caption per line, no numbering, no extra text."""


def expand_aspects(query_text: str, max_aspects: int = 3) -> list:
    """
    Sinh 2-3 bien the goc nhin cua query bang template tat dinh (KHONG goi LLM).

    Args:
        query_text:   Mo ta canh (tieng Anh cho ket qua tot nhat — SigLIP manh nhat o tieng Anh).
        max_aspects:  Tran so goc nhin (1 = tat expansion, tra ve dung query goc).

    Returns:
        list[str] do dai 1..max_aspects, PHAN TU DAU LUON la query goc — de neu ai do chi lay
        aspects[0] thi hanh vi y het truoc khi co module nay.
    """
    q = (query_text or "").strip()
    if not q:
        return []
    if max_aspects <= 1:
        return [q]

    templates = ASPECT_TEMPLATES
    if len(q.split()) > LONG_QUERY_WORDS:
        templates = [ASPECT_TEMPLATES[0], ASPECT_TEMPLATES[2]]

    aspects = [t.format(q=q) for t in templates[:max_aspects]]
    # Bo trung (vd query da chua san cum tu trong template) nhung giu thu tu.
    return list(dict.fromkeys(aspects))


def expand_aspects_llm(query_text: str, max_aspects: int = 3) -> list:
    """
    Nhanh LLM cua expand_aspects() — CHI dung khi goi tuong minh (Q&A/TRAKE, hoac thu nghiem KIS).
    pipeline_kis.py KHONG goi ham nay (KIS phai tat dinh, khong LLM — xem docstring dau file).

    Loi LLM/parse that bai -> rot ve expand_aspects() (template tat dinh), khong bao gio crash.
    """
    q = (query_text or "").strip()
    if not q:
        return []
    try:
        from scripts.agent.config import call_llm
        raw = call_llm(
            EXPAND_ASPECTS_PROMPT.format(query=q), model="text", temperature=0.2, max_tokens=200
        )
    except Exception as error:
        print(f"[query_expand] LLM loi ({type(error).__name__}: {error}) -> dung template tat dinh")
        return expand_aspects(q, max_aspects)

    lines = [re.sub(r"^\s*\d+[.)]\s*", "", ln).strip(" -*\t") for ln in raw.splitlines()]
    lines = [ln for ln in lines if len(ln.split()) >= 3]
    if not lines:
        print(f"[query_expand] Khong parse duoc goc nhin tu LLM ({raw!r}) -> dung template tat dinh")
        return expand_aspects(q, max_aspects)
    return [q] + lines[: max_aspects - 1]

# Bo test: tests/unit/test_query_expand.py
