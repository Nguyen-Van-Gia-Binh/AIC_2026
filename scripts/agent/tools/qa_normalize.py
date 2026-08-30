"""
qa_normalize.py — Làm sạch và rút gọn answer trước khi nộp (chống văn phong giao tiếp, chống ảo giác).

Vì sao cần: chấm điểm BTC so khớp answer với đáp án mẫu. Một câu trả lời ĐÚNG Ý nhưng bọc trong câu
văn ("Trong hình có một chiếc xe màu trắng") vẫn trượt so với đáp án mẫu ("màu trắng").

is_non_answer() là cổng chống ảo giác: khi VLM tự nói "không đọc được", chuỗi đó KHÔNG được đem đi
nộp như một đáp án — nó phải kéo confidence xuống để pipeline thử vòng 2.
"""
from __future__ import annotations

import re

from scripts.agent.config import call_llm
from scripts.agent.tools.qa_prompts import CANONICAL_PROMPT

MAX_ANSWER_CHARS = 100

_STANDALONE_INTEGER = re.compile(r"(?<![\d.,])\d+(?![\d.,])")

# Answer dai hon nguong nay (theo so tu) moi goi LLM rut gon — answer ngan san thi chi can lam sach
# bang rule, khong ton them 1 luot goi API.
CANONICAL_MAX_WORDS = 5

# Van phong giao tiep can cat bo o dau answer (rule, khong ton LLM).
_CONVERSATIONAL_PREFIX = re.compile(
    r"^\s*(?:"
    r"(?:the\s+)?(?:answer|color|number|name)\s+(?:is|shown\s+is)|"
    r"(?:in\s+)?(?:the\s+)?(?:image|frame|photo|video)\s+(?:shows?|there\s+(?:is|are))|"
    r"i\s+(?:can\s+)?see|there\s+(?:is|are)|it\s+is|this\s+is|"
    r"trong\s+(?:hình|ảnh|khung\s+hình|video)\s*(?:có|là)?|"
    r"(?:câu\s+trả\s+lời|đáp\s+án)\s*(?:là|:)|(?:có|là)\s+"
    r")\s*[:,]?\s*",
    re.IGNORECASE,
)

# Dau hieu VLM/OCR KHONG doc duoc — khong duoc bien thanh 1 dap an "co ve dung" (chong ao giac §4.2).
_NON_ANSWER_HINTS = re.compile(
    r"(cannot\s+(?:be\s+)?(?:determine|tell|read|see)|can't\s+(?:tell|read|see)|not\s+visible|"
    r"not\s+legible|unable\s+to|no\s+visible|unclear|khong\s+(?:nhìn|thấy|rõ|xác\s+định|đọc)|"
    r"không\s+(?:nhìn|thấy|rõ|xác\s+định|đọc)|không\s+có\s+thông\s+tin)",
    re.IGNORECASE,
)

def extract_visual_count(response: str) -> str | None:
    """Chỉ nhận một số nguyên độc lập, tránh coi khoảng số trên chú giải là đáp án."""
    matches = _STANDALONE_INTEGER.findall(response or "")
    return matches[0] if len(matches) == 1 else None

def is_non_answer(answer: str) -> bool:
    """True neu answer thuc chat la "khong doc/nhin duoc" — cong chong ao giac (§4.2): khong duoc
    dem chuoi nay di nop nhu 1 dap an, va phai keo confidence xuong."""
    return bool(_NON_ANSWER_HINTS.search(answer or "")) or not (answer or "").strip()

def canonicalize_answer(raw_answer: str, question: str = "", use_llm: bool = True) -> str:
    """
    Canonical Extractor (§4.2): dua answer ve 1-3 tu khoa trong tam, bo van phong giao tiep.

    Vi sao can: cham diem BTC so khop answer voi dap an mau; 1 cau tra loi dung y nhung boc trong
    cau van ("Trong hinh co mot chiec xe mau trang") de truot so voi dap an mau ("màu trắng").

    2 tang, uu tien re truoc:
      1. Rule — bo tien to giao tiep, bo dau cau thua. Chay luon, khong goi API.
      2. LLM — chi khi sau buoc 1 answer VAN dai hon CANONICAL_MAX_WORDS tu. Loi LLM -> giu ket qua
         buoc 1 (khong bao gio crash, khong bao gio tra ve rong).
    """
    answer = normalize_answer(raw_answer)
    if not answer or is_non_answer(answer):
        return answer

    stripped = _CONVERSATIONAL_PREFIX.sub("", answer).strip(" \t\"'.,;:")
    if stripped:
        answer = stripped

    if len(answer.split()) <= CANONICAL_MAX_WORDS or not use_llm:
        return answer

    try:
        short = call_llm(
            CANONICAL_PROMPT.format(question=question or "(none)", answer=answer),
            model="text", temperature=0.0, max_tokens=40,
        )
    except Exception as error:
        print(f"[answer_qa] Canonical extractor loi ({type(error).__name__}: {error}) — giu answer rule-based")
        return answer

    short = normalize_answer(short)
    short = _CONVERSATIONAL_PREFIX.sub("", short).strip(" \t\"'.,;:")
    # Chi nhan ban rut gon neu no THUC SU ngan hon va khong rong — tranh LLM tra ve loi giai thich.
    if short and len(short.split()) < len(answer.split()):
        print(f"[answer_qa] Canonical: {answer!r} -> {short!r}")
        return short
    return answer

def normalize_answer(raw_answer: str) -> str:
    """Giu answer 1 dong, ngan gon, va khong vuot gioi han BTC."""
    answer = " ".join(str(raw_answer).replace("\r", " ").replace("\n", " ").split())
    answer = re.sub(r"^(answer|final answer|câu trả lời)\s*:\s*", "", answer, flags=re.IGNORECASE)
    answer = answer.strip(" \t\"'")
    if len(answer) <= MAX_ANSWER_CHARS:
        return answer

    first_sentence = re.split(r"(?<=[.!?])\s+", answer, maxsplit=1)[0].strip()
    if first_sentence and len(first_sentence) <= MAX_ANSWER_CHARS:
        return first_sentence
    return answer[: MAX_ANSWER_CHARS - 3].rstrip() + "..."
