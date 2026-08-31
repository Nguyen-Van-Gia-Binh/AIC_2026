"""
query_expand.py — Multi-Aspect Prompt Expansion cho KIS (BẢN ĐẶC TẢ §3.1).

Ý tưởng: 1 câu mô tả cảnh được chiếu thành 2-3 "góc nhìn thị giác" khác nhau, mỗi góc nhìn encode
thành 1 vector riêng, rồi lấy trung bình + chuẩn hoá:

    q_final = Normalize((q_1 + q_2 + q_3) / 3)

  v1 — Bối cảnh tổng thể (global environment)
  v2 — Đối tượng trọng tâm + vị trí tương đối (anchor object & spatial position)
  v3 — Màu sắc, hành động, trạng thái động (color attributes & actions)

Đây là kỹ thuật "prompt ensembling" quen thuộc của họ CLIP/SigLIP: text encoder rất nhạy với cách
diễn đạt, trung bình nhiều cách diễn đạt của CÙNG 1 ý làm vector truy vấn ổn định hơn, bớt phụ thuộc
vao 1 cach dat cau duy nhat.

QUAN TRỌNG — KIS KHÔNG gọi LLM trong runtime (ARCHITECTURE.md §3, BẢN ĐẶC TẢ §3 "Tuyến tính, Không
LLM"): mặc định ở đây là template TẤT ĐỊNH (deterministic), không tốn API call, không biến thiên
giữa các lần chạy. Nhánh LLM (expand_aspects_llm) có sẵn nhưng PHẢI bật tường minh, và pipeline_kis
không bao giờ tự bật.

Module thuần text (không đọc index/model) — dùng được cả ở eval lẫn production.

Usage:
    from scripts.agent.tools.query_expand import expand_aspects
    aspects = expand_aspects("a cyclist racing on a mountain road")
    # -> [<goc nhin 1>, <goc nhin 2>, <goc nhin 3>]
"""
from __future__ import annotations

import re

# 3 góc nhìn theo BẢN ĐẶC TẢ §3.1. Giữ câu ngắn và tự nhiên — SigLIP được huấn luyện trên caption
# ảnh thật, câu càng giống caption càng tốt; tránh nhồi từ khoá làm loãng vector.
ASPECT_TEMPLATES = [
    "{q}",                                                    # v1 — bối cảnh tổng thể, giữ nguyên văn
    "a close-up view of {q}, the main subject in the center of the frame",  # v2 — đối tượng trọng tâm
    "{q}, showing the colors, clothing and the action taking place",         # v3 — màu sắc + hành động
]

# Query đã dài sẵn (nhiều mệnh đề) thì template v2/v3 chỉ làm loãng thêm — với query dài hơn ngưỡng
# này chỉ giữ v1 + v3. Ngưỡng đếm theo từ, chọn 25 (~2 câu mô tả đầy đủ).
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
    Sinh 2-3 biến thể góc nhìn của query bằng template tất định (KHÔNG gọi LLM).

    Args:
        query_text:   Mô tả cảnh (tiếng Anh cho kết quả tốt nhất — SigLIP mạnh nhất ở tiếng Anh).
        max_aspects:  Trần số góc nhìn (1 = tắt expansion, trả về đúng query gốc).

    Returns:
        list[str] độ dài 1..max_aspects, PHẦN TỬ ĐẦU LUÔN là query gốc — để nếu ai đó chỉ lấy
        aspects[0] thì hành vi y hệt trước khi có module này.
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
    # Bỏ trùng (vd query đã chứa sẵn cụm từ trong template) nhưng giữ thứ tự.
    return list(dict.fromkeys(aspects))


def expand_aspects_llm(query_text: str, max_aspects: int = 3) -> list:
    """
    Nhánh LLM của expand_aspects() — CHỈ dùng khi gọi tường minh (Q&A/TRAKE, hoặc thử nghiệm KIS).
    pipeline_kis.py KHÔNG gọi hàm này (KIS phải tất định, không LLM — xem docstring đầu file).

    Lỗi LLM/parse thất bại -> rớt về expand_aspects() (template tất định), không bao giờ crash.
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
        print(f"[query_expand] LLM lỗi ({type(error).__name__}: {error}) -> dùng template tất định")
        return expand_aspects(q, max_aspects)

    lines = [re.sub(r"^\s*\d+[.)]\s*", "", ln).strip(" -*\t") for ln in raw.splitlines()]
    lines = [ln for ln in lines if len(ln.split()) >= 3]
    if not lines:
        print(f"[query_expand] Không parse được góc nhìn từ LLM ({raw!r}) -> dùng template tất định")
        return expand_aspects(q, max_aspects)
    return [q] + lines[: max_aspects - 1]

# Bo test: tests/unit/test_query_expand.py
