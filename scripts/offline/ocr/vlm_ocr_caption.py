"""
vlm_ocr_caption.py — OCR (trích xuất văn bản) + captioning (mô tả ngữ cảnh) cho 1 keyframe,
dùng chung Qwen2.5-VL-3B-Instruct qua transformers (chạy local, không gọi API trả phí).

Bối cảnh: objects_lookup.py hiện có KHÔNG phải OCR thật — nó đọc Objects JSON (nhãn object closed-set
từ Faster R-CNN/OpenImages V4 do BTC cung cấp), không đọc được chữ trong ảnh (biển hiệu, phụ đề,
văn bản trên màn hình...). Module này là hệ thống OCR THẬT đầu tiên trong repo, dùng 1 model
Vision-Language để vừa đọc chữ (OCR) vừa sinh mô tả cảnh (caption) trong 1 lần gọi model — tách
riêng khỏi objects_lookup.py, KHÔNG thay thế nó (quyết định giữ nguyên objects_lookup.py, xem PLAN.md).

Singleton pattern giống agent/tools/retrieve.py và agent/tools/detect_objects.py — model chỉ load
1 lần/process. Đây là VLM chạy local qua transformers, KHÔNG đi qua agent/config.py:call_llm() —
không vi phạm quy tắc "chỉ gọi LLM qua config.py", vì quy tắc đó áp dụng cho các provider API trả
phí qua LiteLLM/OpenRouter, không phải model local.

CẢNH BÁO QUY MÔ: Qwen2.5-VL-3B trên CPU khá chậm (nhiều khả năng vài chục giây/ảnh trên máy không
có GPU — CHƯA đo thật, xem ghi chú "chưa kiểm chứng" bên dưới) — KHÔNG dùng để chạy hàng loạt
177K keyframe của toàn bộ dataset trên máy không có GPU. Dùng module này cho:
  (a) test/xem thử kết quả trên vài ảnh,
  (b) chạy trên máy có GPU CUDA (tự động dùng "cuda" nếu torch.cuda.is_available()),
  (c) làm nền cho batch job ở scripts/index_ocr_es.py (script đó tự cảnh báo lại quy mô).

CHƯA KIỂM CHỨNG: model chưa được chạy thử thật trong lần viết này (tải weight ~6-7GB, không tự ý
chạy) — chỉ mới compile-check cú pháp. Tên class (Qwen2_5_VLForConditionalGeneration) và cách gọi
processor/generate() theo đúng model card chính thức của Qwen2.5-VL-3B-Instruct trên HuggingFace,
nhưng có thể lệch nếu bản `transformers` thực tế cài (xem requirements.txt) đổi API — nếu lỗi khi
chạy thật, kiểm tra lại theo đúng tinh thần "dựa vào lỗi thật, không đoán tiếp" đã áp dụng ở
kaggle_jobs/README.md.

Usage:
    from scripts.offline.ocr.vlm_ocr_caption import describe_frame
    result = describe_frame("data/extracted/keyframes/L21/L21_V001/001.jpg")
    # {"ocr_text": "...", "caption": "..."}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DEFAULT_MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
DEFAULT_MAX_NEW_TOKENS = 256

_MODEL = None
_PROCESSOR = None

# Yêu cầu model trả về đúng 1 JSON object — dễ parse, tránh phải tách OCR/caption bằng 2 lần gọi
# model (tốn gấp đôi thời gian trên CPU).
_PROMPT = (
    "Look at this video keyframe carefully. Reply with ONLY a single JSON object, no other text, "
    "with exactly two keys:\n"
    '  "ocr_text": all readable text visible in the image (signs, subtitles, captions, UI text, '
    'labels...), transcribed as-is. Use an empty string "" if there is no readable text.\n'
    '  "caption": one concise English sentence describing what is happening in the scene (people, '
    "objects, action, setting).\n"
    'Example: {"ocr_text": "EXIT", "caption": "A man walks through a doorway marked EXIT."}'
)


def _ensure_loaded(model_id: str = DEFAULT_MODEL_ID) -> None:
    """Load Qwen2.5-VL 1 lần/process (singleton) — cùng cách tổ chức với
    agent/tools/retrieve.py:_ensure_loaded() và agent/tools/detect_objects.py:_ensure_loaded().
    device_map="auto" + torch_dtype="auto" (theo đúng model card chính thức) tự chọn GPU/CPU và
    dtype phù hợp — không tự quản lý .to(device) thủ công để tránh xung đột với device_map."""
    global _MODEL, _PROCESSOR
    if _MODEL is not None:
        return
    from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

    print(f"[vlm_ocr_caption] Đang tải model {model_id} (có thể mất vài phút lần đầu)...")
    _PROCESSOR = AutoProcessor.from_pretrained(model_id)
    _MODEL = Qwen2_5_VLForConditionalGeneration.from_pretrained(
        model_id, torch_dtype="auto", device_map="auto"
    )
    _MODEL.eval()
    print(f"[vlm_ocr_caption] Ready. device={_MODEL.device}")


def _parse_model_output(text: str) -> dict:
    """Parse output của model thành {"ocr_text": str, "caption": str}. Model được yêu cầu trả về
    JSON thuần, nhưng VLM đôi khi bọc thêm ```json ... ``` hoặc chèn text thừa quanh — tìm khối
    {...} đầu tiên thay vì json.loads() thẳng cả chuỗi. Fail loud nếu không parse được, thay vì
    âm thầm trả về ocr_text/caption rỗng (dữ liệu rác sẽ bị index vào Elasticsearch)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"[vlm_ocr_caption] Không tìm thấy JSON trong output model: {text!r}")
    data = json.loads(match.group(0))
    return {
        "ocr_text": str(data.get("ocr_text", "")).strip(),
        "caption": str(data.get("caption", "")).strip(),
    }


def describe_frame(
    image_path: str,
    model_id: str = DEFAULT_MODEL_ID,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
) -> dict:
    """
    Chạy Qwen2.5-VL trên 1 keyframe, trả về OCR text + caption trong 1 lần gọi model.

    Args:
        image_path:     Đường dẫn ảnh keyframe (vd "data/extracted/keyframes/L21/L21_V001/001.jpg")
        model_id:       HuggingFace model id, mặc định Qwen2.5-VL-3B-Instruct
        max_new_tokens: Giới hạn token sinh ra (JSON ngắn, 256 là đủ dư)

    Returns:
        dict: {"ocr_text": str, "caption": str}

    Raises:
        FileNotFoundError: nếu image_path không tồn tại
        ValueError:        nếu output model không parse được thành JSON hợp lệ
    """
    img_path = Path(image_path)
    if not img_path.exists():
        raise FileNotFoundError(f"[vlm_ocr_caption] Không thấy ảnh: {image_path}")

    _ensure_loaded(model_id)
    import torch

    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": str(img_path)},
            {"type": "text", "text": _PROMPT},
        ],
    }]
    chat_text = _PROCESSOR.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    try:
        # qwen_vl_utils là helper chính thức của Qwen team để resize/normalize ảnh đúng chuẩn
        # (min/max pixel theo model) — xem requirements.txt.
        from qwen_vl_utils import process_vision_info
        image_inputs, video_inputs = process_vision_info(messages)
    except ImportError:
        from PIL import Image
        image_inputs, video_inputs = [Image.open(img_path).convert("RGB")], None

    inputs = _PROCESSOR(
        text=[chat_text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    ).to(_MODEL.device)

    with torch.no_grad():
        generated_ids = _MODEL.generate(**inputs, max_new_tokens=max_new_tokens)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = _PROCESSOR.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]

    return _parse_model_output(output_text)


# ─── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "data/extracted/keyframes/L21/L21_V001/001.jpg"
    result = describe_frame(path)
    print(f"[vlm_ocr_caption] {path}")
    print(f"  ocr_text: {result['ocr_text']!r}")
    print(f"  caption:  {result['caption']!r}")
