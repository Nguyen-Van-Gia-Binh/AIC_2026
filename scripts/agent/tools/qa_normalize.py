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

# Answer dài hơn ngưỡng này (theo số từ) mới gọi LLM rút gọn — answer ngắn sẵn thì chỉ cần làm sạch
# bằng rule, không tốn thêm 1 lượt gọi API.
CANONICAL_MAX_WORDS = 5

# Văn phong giao tiếp cần cắt bỏ ở đầu answer (rule, không tốn LLM).
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

# Dấu hiệu VLM/OCR KHÔNG đọc được — không được biến thành 1 đáp án "có vẻ đúng" (chống ảo giác §4.2).
_NON_ANSWER_HINTS = re.compile(
    r"(cannot\s+(?:be\s+)?(?:determine|tell|read|see)|can't\s+(?:tell|read|see)|not\s+visible|"
    r"not\s+legible|unable\s+to|no\s+visible|unclear|not\s+(?:shown|displayed|clearly\s+visible)|"
    r"does\s+not\s+(?:show|display|contain|appear)|no\s+(?:number|digit|text|numbers)\b|"
    # "không/khong" + (động từ tri giác | 'hiển thị' | 'hiện') — bắt "không hiển thị (rõ) con số"
    r"kh(?:ô|o)ng\s+(?:nhìn|thấy|rõ|xác\s+định|đọc|hiển\s+thị|hiện)|"
    r"kh(?:ô|o)ng\s+có\s+(?:thông\s+tin|dữ\s+liệu|đủ\s+dữ\s+liệu)|"
    # "con số nào (được) viết/ghi/hiển thị..." — đuôi phủ định điển hình của VLM, bất kể cách "không" bao xa
    r"(?:con\s+số|chữ|ký\s+tự)\s+nào\s+(?:được\s+|có\s+thể\s+)?(?:viết|ghi|hiển\s+thị|thể\s+hiện|nhìn\s+thấy|đọc)|"
    r"(?:hoặc|hay)\s+(?:con\s+số|chữ|ký\s+tự)\s+nào|"
    # "không <tối đa 8 từ> con số/số nào/chữ nào/ký tự nào"
    r"kh(?:ô|o)ng\s+\S+(?:\s+\S+){0,8}?\s+(?:con\s+số|số\s+nào|chữ\s+nào|ký\s+tự\s+nào))",
    re.IGNORECASE,
)

def extract_visual_count(response: str) -> str | None:
    """Chỉ nhận một số nguyên độc lập, tránh coi khoảng số trên chú giải là đáp án."""
    matches = _STANDALONE_INTEGER.findall(response or "")
    return matches[0] if len(matches) == 1 else None

def is_non_answer(answer: str) -> bool:
    """True nếu answer thực chất là "không đọc/nhìn được" — cổng chống ảo giác (§4.2): không được
    đem chuỗi này đi nộp như 1 đáp án, và phải kéo confidence xuống."""
    return bool(_NON_ANSWER_HINTS.search(answer or "")) or not (answer or "").strip()

def canonicalize_answer(raw_answer: str, question: str = "", use_llm: bool = True) -> str:
    """
    Canonical Extractor (§4.2): đưa answer về 1-3 từ khoá trọng tâm, bỏ văn phong giao tiếp.

    Vì sao cần: chấm điểm BTC so khớp answer với đáp án mẫu; 1 câu trả lời đúng ý nhưng bọc trong
    cau van ("Trong hinh co mot chiec xe mau trang") de truot so voi dap an mau ("màu trắng").

    2 tầng, ưu tiên rẻ trước:
      1. Rule — bỏ tiền tố giao tiếp, bỏ dấu câu thừa. Chạy luôn, không gọi API.
      2. LLM — chỉ khi sau bước 1 answer VẪN dài hơn CANONICAL_MAX_WORDS từ. Lỗi LLM -> giữ kết quả
         bước 1 (không bao giờ crash, không bao giờ trả về rỗng).
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
        print(f"[qa_normalize] Canonical extractor lỗi ({type(error).__name__}: {error}) — giữ answer rule-based")
        return answer

    short = normalize_answer(short)
    short = _CONVERSATIONAL_PREFIX.sub("", short).strip(" \t\"'.,;:")
    # Chỉ nhận bản rút gọn nếu nó THỰC SỰ ngắn hơn và không rỗng — tránh LLM trả về lời giải thích.
    if short and len(short.split()) < len(answer.split()):
        print(f"[answer_qa] Canonical: {answer!r} -> {short!r}")
        return short
    return answer

def normalize_answer(raw_answer: str) -> str:
    """Giữ answer 1 dòng, ngắn gọn, và không vượt giới hạn BTC."""
    answer = " ".join(str(raw_answer).replace("\r", " ").replace("\n", " ").split())
    answer = re.sub(r"^(answer|final answer|câu trả lời)\s*:\s*", "", answer, flags=re.IGNORECASE)
    answer = answer.strip(" \t\"'")
    if len(answer) <= MAX_ANSWER_CHARS:
        return answer

    first_sentence = re.split(r"(?<=[.!?])\s+", answer, maxsplit=1)[0].strip()
    if first_sentence and len(first_sentence) <= MAX_ANSWER_CHARS:
        return first_sentence
    return answer[: MAX_ANSWER_CHARS - 3].rstrip() + "..."
