"""Cau hinh LLM tap trung cho toan project AIC2026.

Moi loi goi LLM di qua OpenRouter, su dung API tuong thich OpenAI thong qua
LiteLLM. Cung mot model duoc dung cho nhanh text va vision; model co the doi
qua bien OPENROUTER_MODEL trong .env.
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
    """Tach mot hoac nhieu API key ngan cach bang dau phay/xuong dong."""
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

MIN_OUTPUT_TOKENS = 2048
MAX_AGENT_LOOPS = 2

# LiteLLM dung tien to openrouter/ de chuyen request den OpenRouter.
PROVIDER_CHAIN = [
    {
        "name": "openrouter",
        "model_text": f"openrouter/{OPENROUTER_MODEL}",
        "model_vision": f"openrouter/{OPENROUTER_MODEL}",
        "api_keys": OPENROUTER_API_KEYS,
    },
]

MODEL_TEXT = PROVIDER_CHAIN[0]["model_text"]
MODEL_VISION = PROVIDER_CHAIN[0]["model_vision"]


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
        raise ValueError(f"{model} tra ve response rong")
    return content.strip()


def call_llm(
    prompt: str,
    image_paths: list[str] | None = None,
    model: str = "auto",
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    """Goi model text/vision qua OpenRouter, giu nguyen interface hien tai."""
    is_vision = model == "vision" or bool(image_paths)
    actual_max = max(max_tokens, MIN_OUTPUT_TOKENS)
    messages = _build_messages(prompt, image_paths)
    last_error: Exception | None = None

    for provider in PROVIDER_CHAIN:
        api_keys = provider["api_keys"]
        if not api_keys:
            print("[config] Bo qua OpenRouter (chua co OPENROUTER_API_KEY trong .env)")
            continue
        chosen_model = provider["model_vision"] if is_vision else provider["model_text"]
        for key_index, api_key in enumerate(api_keys, start=1):
            try:
                print(f"[config] OpenRouter model={OPENROUTER_MODEL} ({'vision' if is_vision else 'text'})")
                return _call_one(chosen_model, api_key, messages, temperature, actual_max)
            except Exception as error:
                print(f"[config] OpenRouter key {key_index}/{len(api_keys)} loi {type(error).__name__}: {error}")
                last_error = error

    raise RuntimeError(
        "OpenRouter call that bai — kiem tra OPENROUTER_API_KEY va OPENROUTER_MODEL trong .env."
    ) from last_error


if __name__ == "__main__":
    print("[config] Testing OpenRouter...")
    result = call_llm("Reply with exactly: HELLO_AIC2026", model="text")
    print(f"[config] Response: {result!r}")
