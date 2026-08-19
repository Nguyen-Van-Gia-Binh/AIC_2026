"""
config.py - Cau hinh LLM tap trung cho toan project AIC2026.

Gemini 3.5 Flash la thinking model: token "thinking" tieu thu truoc,
phai dung max_tokens >= 2048 de dam bao co du token cho response.
"""
from __future__ import annotations

import base64
import os
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env", override=False)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_VISION   = "gemini/gemini-3.5-flash"
MODEL_TEXT     = "gemini/gemini-3.5-flash"
MIN_OUTPUT_TOKENS = 2048
MAX_AGENT_LOOPS   = 2


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_llm(
    prompt: str,
    image_paths: list[str] | None = None,
    model: str = "auto",
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    """
    Goi Gemini LLM.
    max_tokens tu dong nang len >= 2048 de tranh Gemini tra None (thinking budget).
    """
    import litellm

    actual_max = max(max_tokens, MIN_OUTPUT_TOKENS)
    chosen_model = MODEL_VISION if model == "vision" else MODEL_TEXT

    if image_paths:
        content = [{"type": "text", "text": prompt}]
        for img_path in image_paths[:3]:
            if os.path.exists(img_path):
                ext  = Path(img_path).suffix.lstrip(".").lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                b64  = _encode_image(img_path)
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
        messages = [{"role": "user", "content": content}]
    else:
        messages = [{"role": "user", "content": prompt}]

    response = litellm.completion(
        model=chosen_model,
        messages=messages,
        temperature=temperature,
        max_tokens=actual_max,
        api_key=GEMINI_API_KEY,
        stream=False,
    )

    content = response.choices[0].message.content
    if content is None:
        # Thinking model het budget: nang gap doi va thu lai
        response2 = litellm.completion(
            model=chosen_model,
            messages=messages,
            temperature=temperature,
            max_tokens=actual_max * 2,
            api_key=GEMINI_API_KEY,
            stream=False,
        )
        content = response2.choices[0].message.content
        if content is None:
            raise ValueError(f"Gemini van tra None voi {actual_max*2} tokens")

    return content.strip()


if __name__ == "__main__":
    print("[config] Testing Gemini...")
    result = call_llm("Reply with exactly: HELLO_AIC2026", model="text")
    print(f"[config] Response: {result!r}")
    print("[config] OK!")
