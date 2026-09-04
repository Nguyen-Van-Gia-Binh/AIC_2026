"""
subquery.py — Chuẩn bị câu truy vấn tiếng Anh cho nhánh dense TRƯỚC khi encode.

Hai việc nhỏ, thuần xử lý chuỗi (riêng count_tokens phải nạp 1 tokenizer nhẹ):

- count_tokens(text): đếm token theo đúng tokenizer của model Q&A (siglip2). Text encoder
  SigLIP/SigLIP2 pad/cắt CỨNG ở 64 token (`text_config.max_position_embeddings = 64` — nướng
  vào checkpoint của Google, KHÔNG phải cấu hình chỉnh được). Câu dài hơn 64 token bị cắt mất
  đuôi ngay lúc embed -> cần biết trước để định tuyến (embed thẳng hay tách câu con).

- split_subqueries(text): tách 1 mô tả dài thành nhiều câu con ngắn theo DẤU CHẤM. pipeline_qa
  encode riêng từng câu con rồi dung hợp THỨ HẠNG bằng RRF (xem hybrid.hybrid_retrieve) —
  không gộp trung bình vector nên không làm nhoè tín hiệu từng khía cạnh.

Vì sao tách riêng khỏi rewrite.py: rewrite.py gọi LLM; ở đây không có LLM. Hai mối quan tâm
thay đổi vì lý do khác nhau.
"""
from __future__ import annotations

import re

# Trần token của text encoder SigLIP/SigLIP2 (google/*-so400m-patch14-384).
# max_position_embeddings = 64 — xem docs/decisions-log.md.
MAX_ENCODER_TOKENS = 64

# Trần số câu con: tách quá nhiều mảnh (4-5) làm retrieval TỆ HƠN cả cắt-64 — mảnh ngắn/generic
# kéo lệch RRF (đo trên tests/eval/rewrite_eval.py). Gộp câu liền nhau để còn tối đa ngần này.
MAX_SUBQUERIES = 3

# Tokenizer để đếm token phải khớp model encode Q&A. index_store mặc định siglip2; nếu ai đó
# ghi đè AIC_QA_MODEL sang model khác thì con số đếm chỉ còn xấp xỉ (chấp nhận được — chỉ dùng
# để định tuyến ≤64 / >64).
_SIGLIP2_MODEL_ID = "google/siglip2-so400m-patch14-384"

_tokenizer = None
_tokenizer_failed = False


def count_tokens(text: str) -> int:
    """Số token của `text` theo tokenizer siglip2 (KHÔNG pad, KHÔNG cắt — đếm độ dài thật).

    So với MAX_ENCODER_TOKENS để biết câu có bị text encoder cắt đuôi hay không.

    Không nạp được tokenizer (thiếu file model / CI offline) -> ước lượng theo số từ, hơi nống
    lên để câu ở ranh giới thiên về HƯỚNG tách câu con hơn là bị cắt âm thầm.
    """
    global _tokenizer, _tokenizer_failed
    t = (text or "").strip()
    if not t:
        return 0
    if _tokenizer is None and not _tokenizer_failed:
        try:
            from transformers import AutoTokenizer
            _tokenizer = AutoTokenizer.from_pretrained(_SIGLIP2_MODEL_ID)
        except Exception:
            _tokenizer_failed = True
    if _tokenizer is not None:
        return len(_tokenizer(t, padding=False, truncation=False)["input_ids"])
    return int(len(t.split()) * 1.6 + 0.999)  # ~1.6 token/từ, làm tròn lên


def split_subqueries(text: str) -> list[str]:
    """Tách `text` thành các câu con theo DẤU CHẤM, gộp lại còn tối đa MAX_SUBQUERIES mảnh.

    - Bỏ khoảng trắng thừa; bỏ mảnh rỗng hoặc không có ký tự chữ/số.
    - Ra 0-1 câu -> trả [text] (caller coi như truy vấn đơn, không tách).
    - > MAX_SUBQUERIES câu -> gộp câu LIỀN NHAU sao cho mỗi mảnh vẫn ≤ MAX_ENCODER_TOKENS, chốt ở
      MAX_SUBQUERIES mảnh (mảnh cuối gánh phần dư). Tách vụn 4-5 mảnh hại retrieval hơn cắt-64.
    """
    if not text or not text.strip():
        return []
    parts = [p.strip() for p in text.split(".")]
    sents = [p for p in parts if re.search(r"[0-9A-Za-zÀ-ỹ]", p)]
    if len(sents) < 2:
        return [text.strip()]
    if len(sents) <= MAX_SUBQUERIES:
        return sents

    chunks: list[str] = []
    cur = ""
    for s in sents:
        cand = f"{cur}. {s}" if cur else s
        if cur and len(chunks) < MAX_SUBQUERIES - 1 and count_tokens(cand) > MAX_ENCODER_TOKENS:
            chunks.append(cur)
            cur = s
        else:
            cur = cand
    if cur:
        chunks.append(cur)
    return chunks[:MAX_SUBQUERIES]

# Bo test: tests/unit/test_subquery.py
