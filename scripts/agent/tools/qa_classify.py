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

# Cau hoi ve SO/CHU DUOC HIEN THI tren khung hinh (bien so, ty so, gia, dong ho, nam...) — nhom duy
# nhat duoc phep de OCR ghi de truc tiep ket qua VLM (§4.2 "OCR Direct Overwrite"). CO Y KHONG gom
# cau hoi dem so luong ("bao nhiêu người", "how many cars") — OCR khong dem duoc vat the, chi doc chu.
_DISPLAYED_NUMBER_RE = re.compile(
    r"(biển\s*số|số\s*áo|tỷ\s*số|giá(?:\s*tiền|\s*bao\s*nhiêu)?|đồng\s*hồ|nhiệt\s*độ|"
    r"số\s+(?:hiển\s*thị|ghi|trên|mấy)|con\s+số|năm\s+(?:nào|mấy|bao\s+nhiêu)|"
    r"license\s+plate|jersey\s+number|score(?:board)?|what\s+number|number\s+(?:shown|on|displayed))",
    re.IGNORECASE,
)

# Cau hoi doi hoi doc so/chu/dem tren man hinh (bien bao, dong ho, chu giai ban do, ten dia danh...).
# Objects JSON (Faster R-CNN/OpenImages) chi tra ve TEN OBJECT chung chung, khong doc duoc text/so, nen
# voi nhom cau hoi nay bo qua thang Tang 1 va di thang vao Tang 2 (vision doc anh truc tiep) de tranh
# doan bay tu danh sach object khong lien quan.
_TEXT_READING_HINTS = re.compile(
    r"(bao nhiêu|con số|số (?:mấy|hiển thị|ghi)|biển báo|biển số|giá(?:\s*tiền)?|"
    r"dòng chữ|chữ gì|tên (?:là gì|của|gọi)|ghi (?:là )?gì|cấp độ|number|how many|what number)",
    re.IGNORECASE,
)

def is_visual_count_question(question: str) -> bool:
    """Nhận biết câu hỏi yêu cầu đếm đối tượng hoặc ký hiệu trong ảnh."""
    return bool(question and _VISUAL_COUNT_HINTS.search(question))

def asks_displayed_number(question: str) -> bool:
    """True neu cau hoi hoi ve so/chu DUOC HIEN THI tren khung hinh (khac voi dem so luong vat the)."""
    return bool(_DISPLAYED_NUMBER_RE.search(question or ""))

def needs_text_reading(question: str) -> bool:
    """True neu cau hoi can doc so/chu/dem tren man hinh — nen bo qua Tang 1 (objects JSON)."""
    return bool(_TEXT_READING_HINTS.search(question))
