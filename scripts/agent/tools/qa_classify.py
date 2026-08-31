"""
qa_classify.py — Nhận dạng LOẠI câu hỏi Q&A bằng regex (thuần, không gọi LLM, không đọc file).

Ba nhóm cần phân biệt vì mỗi nhóm đi một đường khác nhau trong answer_from_hits():
  - đếm vật thể       → prompt đếm riêng, bỏ qua cross-check
  - cần đọc chữ/số    → bỏ qua Tầng 1 (Objects JSON không đọc được chữ), bật gợi ý OCR
  - hỏi SỐ HIỂN THỊ   → nhóm DUY NHẤT được phép để OCR ghi đè thẳng kết quả VLM

Lưu ý ranh giới: "đếm vật thể" KHÔNG thuộc "số hiển thị" — OCR đọc được chữ chứ không đếm được vật.
"""
from __future__ import annotations

import re

_VISUAL_COUNT_HINTS = re.compile(
    r"(bao nhiêu|số lượng|đếm|how many|number of|count)",
    re.IGNORECASE,
)

# Câu hỏi về SỐ/CHỮ ĐƯỢC HIỂN THỊ trên khung hình (biển số, tỷ số, giá, đồng hồ, năm...) — nhóm duy
# nhất được phép để OCR ghi đè trực tiếp kết quả VLM (§4.2 "OCR Direct Overwrite"). CÓ Ý KHÔNG gộp
# cau hoi dem so luong ("bao nhiêu người", "how many cars") — OCR khong dem duoc vat the, chi doc chu.
_DISPLAYED_NUMBER_RE = re.compile(
    r"(biển\s*số|số\s*áo|tỷ\s*số|giá(?:\s*tiền|\s*bao\s*nhiêu)?|đồng\s*hồ|nhiệt\s*độ|"
    r"số\s+(?:hiển\s*thị|ghi|trên|mấy)|con\s+số|năm\s+(?:nào|mấy|bao\s+nhiêu)|"
    r"license\s+plate|jersey\s+number|score(?:board)?|what\s+number|number\s+(?:shown|on|displayed))",
    re.IGNORECASE,
)

# Câu hỏi đòi hỏi đọc số/chữ/đếm trên màn hình (biển báo, đồng hồ, chú giải bản đồ, tên địa danh...).
# Objects JSON (Faster R-CNN/OpenImages) chỉ trả về TÊN OBJECT chung chung, không đọc được text/số, nên
# với nhóm câu hỏi này bỏ qua thẳng Tầng 1 và đi thẳng vào Tầng 2 (vision đọc ảnh trực tiếp) để tránh
# đoán bậy từ danh sách object không liên quan.
_TEXT_READING_HINTS = re.compile(
    r"(bao nhiêu|con số|số (?:mấy|hiển thị|ghi)|biển báo|biển số|giá(?:\s*tiền)?|"
    r"dòng chữ|chữ gì|tên (?:là gì|của|gọi)|ghi (?:là )?gì|cấp độ|number|how many|what number)",
    re.IGNORECASE,
)

def is_visual_count_question(question: str) -> bool:
    """Nhận biết câu hỏi yêu cầu đếm đối tượng hoặc ký hiệu trong ảnh."""
    return bool(question and _VISUAL_COUNT_HINTS.search(question))

def asks_displayed_number(question: str) -> bool:
    """True nếu câu hỏi hỏi về số/chữ ĐƯỢC HIỂN THỊ trên khung hình (khác với đếm số lượng vật thể)."""
    return bool(_DISPLAYED_NUMBER_RE.search(question or ""))

def needs_text_reading(question: str) -> bool:
    """True nếu câu hỏi cần đọc số/chữ/đếm trên màn hình — nên bỏ qua Tầng 1 (objects JSON)."""
    return bool(_TEXT_READING_HINTS.search(question))
