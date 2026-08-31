"""Cấu hình LLM tập trung cho toàn project AIC2026.

Mọi lời gọi LLM đi qua LiteLLM. Ở AIC_MODE=test, ưu tiên gọi thẳng Google AI
Studio (Gemini) bằng các key trong GEMINI_API_KEY, xoay vòng qua nhiều model
Flash để tận dụng free tier, rồi mới fallback sang OpenRouter. Ở AIC_MODE=
contest, chỉ dùng OpenRouter (OPENROUTER_MODEL_CONTEST) để ổn định. Cùng một
model được dùng cho cả text và vision trong từng provider — xem PROVIDER_CHAIN.
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path

import litellm
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env", override=False)


def _parse_key_list(raw: str) -> list[str]:
    """Tách một hoặc nhiều API key ngăn cách bằng dấu phẩy/xuống dòng."""
    if not raw:
        return []
    seen: set[str] = set()
    keys: list[str] = []
    for part in re.split(r"[,\r\n]+", raw):
        part = part.strip()
        if part and not part.lower().startswith("your_") and part not in seen:
            seen.add(part)
            keys.append(part)
    return keys


OPENROUTER_API_KEYS = _parse_key_list(os.getenv("OPENROUTER_API_KEY", ""))
OPENROUTER_API_KEY = OPENROUTER_API_KEYS[0] if OPENROUTER_API_KEYS else ""
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash").strip()
if OPENROUTER_MODEL.startswith("openrouter/"):
    OPENROUTER_MODEL = OPENROUTER_MODEL[len("openrouter/"):]

# AIC_MODE chọn model theo chế độ: "test" (rẻ, dùng khi dev) hoặc "contest" (mạnh hơn, dùng lúc nộp
# thật). Không đổi signature call_llm() — chỉ đổi model nào được PROVIDER_CHAIN trỏ tới.
AIC_MODE = os.getenv("AIC_MODE", "test").strip().lower()
if AIC_MODE not in ("test", "contest"):
    print(f"[config] WARNING: AIC_MODE='{AIC_MODE}' không hợp lệ, dùng 'test' hoặc 'contest'. Mặc định: 'test'")
    AIC_MODE = "test"

# Nhiều key Google AI Studio (gọi thẳng Gemini, không qua OpenRouter) — chỉ dùng ở AIC_MODE=test để
# tận dụng free tier trước khi tốn tiền OpenRouter. Cú pháp nhiều key: xem _parse_key_list ở trên
# (phẩy hoặc xuống dòng trong GEMINI_API_KEY).
# Lưu ý: Google phát hành Gemini API key dưới nhiều định dạng khác nhau (đã xác nhận bằng test thật
# qua REST API — cả dạng "AIzaSy..." lẫn dạng "AQ.Ab8..." đều là key hợp lệ, trả về HTTP 200). Không
# lọc theo tiền tố ở đây — mỗi dòng không phải placeholder đều được coi là key thật và đưa vào vòng xoay.
GEMINI_API_KEYS = _parse_key_list(os.getenv("GEMINI_API_KEY", ""))

# Danh sách model Gemini trực tiếp, sắp theo RPD (requests/ngày) giảm dần rồi RPM giảm dần — để dùng
# hết quota của các model "Flash Lite" mới (RPD 500) trước khi phải chạm đến nhóm RPD 20, giúp 1 key
# sống được lâu nhất trong 1 phiên test. Rate limit free tier thực tế (1 key, ghi nhận 08/2026):
#   model                   RPM   TPM    RPD
#   gemini-3.5-flash-lite    15   250K   500
#   gemini-3.1-flash-lite    15   250K   500
#   gemini-2.5-flash-lite    10   250K    20
#   gemini-3.7-flash          5   250K    20
#   gemini-3.6-flash          5   250K    20
#   gemini-3.5-flash          5   250K    20
#   gemini-3-flash             5   250K    20
#   gemini-2.5-flash           5   250K    20
# Nếu tên model trên Google AI Studio đổi khác (vd thêm hậu tố phiên bản), gọi sai chỉ lỗi 400/404
# rất nhanh rồi rớt xuống model/key kế tiếp — không làm kết quả treo, không cần sửa code.
GEMINI_DIRECT_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3-flash",
    "gemini-2.5-flash",
]

OPENROUTER_MODEL_CONTEST = os.getenv("OPENROUTER_MODEL_CONTEST", "").strip()
if OPENROUTER_MODEL_CONTEST.startswith("openrouter/"):
    OPENROUTER_MODEL_CONTEST = OPENROUTER_MODEL_CONTEST[len("openrouter/"):]

_SELECTED_MODEL = OPENROUTER_MODEL_CONTEST if AIC_MODE == "contest" else OPENROUTER_MODEL
if AIC_MODE == "contest" and not OPENROUTER_MODEL_CONTEST:
    print("[config] WARNING: AIC_MODE=contest nhưng OPENROUTER_MODEL_CONTEST trong .env trống rỗng. Dùng OPENROUTER_MODEL thay thế.")
    _SELECTED_MODEL = OPENROUTER_MODEL

MIN_OUTPUT_TOKENS = 2048
MAX_AGENT_LOOPS = 2

# LiteLLM dùng tiền tố gemini/ để gọi thẳng Google AI Studio, openrouter/ để chuyển đến OpenRouter.
# Ở AIC_MODE=test: ưu tiên xoay vòng GEMINI_DIRECT_MODELS x GEMINI_API_KEYS (free tier) trước,
# OpenRouter là lưới an toàn cuối cùng khi tất cả đều thất bại (hết quota/lỗi mạng/sai tên model).
# Ở AIC_MODE=contest: chỉ dùng OpenRouter — ưu tiên ổn định, không phụ thuộc free tier có thể bị
# rate-limit giữa lúc thi thật.
PROVIDER_CHAIN = []
if AIC_MODE == "test" and GEMINI_API_KEYS:
    PROVIDER_CHAIN.extend(
        {
            "name": f"gemini_direct:{model_id}",
            "model_text": f"gemini/{model_id}",
            "model_vision": f"gemini/{model_id}",
            "api_keys": GEMINI_API_KEYS,
        }
        for model_id in GEMINI_DIRECT_MODELS
    )
PROVIDER_CHAIN.append({
    "name": "openrouter",
    "model_text": f"openrouter/{_SELECTED_MODEL}",
    "model_vision": f"openrouter/{_SELECTED_MODEL}",
    "api_keys": OPENROUTER_API_KEYS,
})

MODEL_TEXT = PROVIDER_CHAIN[0]["model_text"]
MODEL_VISION = PROVIDER_CHAIN[0]["model_vision"]

# Xoay điểm bắt đầu trong danh sách key mỗi lần gọi call_llm(), để các lần gọi liên tiếp rải đều qua
# nhiều key thay vì lần nào cũng đâm vào key đầu tiên (dễ dính RPM nếu gọi liên tục trong 1 phút).
# Biến đếm trong bộ nhớ của tiến trình — không cần lưu lại giữa các lần chạy script.
_call_counter = 0


def _rotate_keys(keys: list[str]) -> list[tuple[int, str]]:
    """Trả về list (vị trí gốc trong .env, key) đã xoay, để log con trỏ rõ vị trí thật."""
    if len(keys) <= 1:
        return list(enumerate(keys, start=1))
    offset = _call_counter % len(keys)
    indexed = list(enumerate(keys, start=1))
    return indexed[offset:] + indexed[:offset]


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_messages(prompt: str, image_paths: list[str] | None):
    if not image_paths:
        return [{"role": "user", "content": prompt}]
    content = [{"type": "text", "text": prompt}]
    for image_path in image_paths[:3]:
        if os.path.exists(image_path):
            ext = Path(image_path).suffix.lstrip(".").lower()
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{_encode_image(image_path)}"},
            })
    return [{"role": "user", "content": content}]


def _call_one(model: str, api_key: str, messages, temperature: float, max_tokens: int) -> str:
    response = litellm.completion(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        stream=False,
    )
    content = response.choices[0].message.content
    if content is None:
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens * 2,
            api_key=api_key,
            stream=False,
        )
        content = response.choices[0].message.content
    if content is None:
        raise ValueError(f"{model} trả về response rỗng")
    return content.strip()


def call_llm(
    prompt: str,
    image_paths: list[str] | None = None,
    model: str = "auto",
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    """Gọi LLM theo PROVIDER_CHAIN: ưu tiên Gemini trực tiếp (AIC_MODE=test), fallback OpenRouter."""
    global _call_counter
    is_vision = model == "vision" or bool(image_paths)
    actual_max = max(max_tokens, MIN_OUTPUT_TOKENS)
    messages = _build_messages(prompt, image_paths)
    last_error: Exception | None = None
    _call_counter += 1

    for provider in PROVIDER_CHAIN:
        api_keys = provider["api_keys"]
        if not api_keys:
            print(f"[config] Bỏ qua {provider['name']} (chưa có API key trong .env)")
            continue
        chosen_model = provider["model_vision"] if is_vision else provider["model_text"]
        for key_index, api_key in _rotate_keys(api_keys):
            try:
                print(f"[config] {provider['name']} model={chosen_model} key {key_index}/{len(api_keys)} ({'vision' if is_vision else 'text'})")
                return _call_one(chosen_model, api_key, messages, temperature, actual_max)
            except Exception as error:
                print(f"[config] {provider['name']} key {key_index}/{len(api_keys)} loi {type(error).__name__}: {error}")
                last_error = error

    raise RuntimeError(
        "Tất cả provider đều thất bại — kiểm tra GEMINI_API_KEY/OPENROUTER_API_KEY và model trong .env."
    ) from last_error


if __name__ == "__main__":
    print(f"[config] Testing PROVIDER_CHAIN (AIC_MODE={AIC_MODE}, {len(PROVIDER_CHAIN)} provider)...")
    result = call_llm("Reply with exactly: HELLO_AIC2026", model="text")
    print(f"[config] Response: {result!r}")
