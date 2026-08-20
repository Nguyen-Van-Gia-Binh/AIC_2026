"""
config.py - Cau hinh LLM tap trung cho toan project AIC2026.

Gemini 3.5 Flash la thinking model: token "thinking" tieu thu truoc,
phai dung max_tokens >= 2048 de dam bao co du token cho response.

Multi-provider fallback (Phase 5): moi loi goi LLM di qua PROVIDER_CHAIN theo
dung thu tu uu tien Gemini -> Groq -> NVIDIA NIM, cho ca nhanh text lan nhanh
vision. Neu provider dang thu bi rate-limit/quota (429) hoac bat ky loi nao
khac, tu dong chuyen sang provider ke tiep trong chuoi thay vi lam sap ca
pipeline giua luc thi; chi nem loi khi ca 3 provider deu that bai. Provider
chua dien API key trong .env se tu dong bi bo qua (khong crash).

Key rotation trong 1 provider: moi bien *_API_KEY trong .env co the chua
NHIEU key (ngan cach bang dau phay hoac xuong dong, xem .env.example) — vi du
nhieu Gemini key tu nhieu du an/tai khoan de ne rate-limit theo tung key rieng
le. call_llm() thu lan luot tung key trong provider truoc khi rot sang
provider ke tiep. Key sai dinh dang/khong hop le se tu bi bo qua (loi auth)
va chuyen sang key ke tiep, khong lam crash toan bo chuoi.
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
    """
    1 bien .env co the chua 1 hoac nhieu key, ngan cach bang dau phay hoac
    xuong dong (dung khi can xoay vong nhieu key cung provider). Tra ve danh
    sach key da loc placeholder ("your_..."), bo dong trong, giu nguyen thu
    tu va bo trung.
    """
    if not raw:
        return []
    seen, keys = set(), []
    for part in re.split(r"[,\r\n]+", raw):
        part = part.strip()
        if part and not part.lower().startswith("your_") and part not in seen:
            seen.add(part)
            keys.append(part)
    return keys


GEMINI_API_KEYS = _parse_key_list(os.getenv("GEMINI_API_KEY", ""))
GROQ_API_KEYS = _parse_key_list(os.getenv("GROQ_API_KEY", ""))
NVIDIA_NIM_API_KEYS = _parse_key_list(os.getenv("NVIDIA_NIM_API_KEY", ""))
OMNIROUTE_API_KEYS = _parse_key_list(os.getenv("OMNIROUTE_API_KEY", ""))
OMNIROUTE_BASE_URL = os.getenv("OMNIROUTE_BASE_URL", "http://localhost:20128/v1")

# Tuong thich nguoc: bien key don cho cho nao con doc truc tiep (key dau tien
# trong danh sach, hoac "" neu chua dien).
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""
GROQ_API_KEY = GROQ_API_KEYS[0] if GROQ_API_KEYS else ""
NVIDIA_NIM_API_KEY = NVIDIA_NIM_API_KEYS[0] if NVIDIA_NIM_API_KEYS else ""
OMNIROUTE_API_KEY = OMNIROUTE_API_KEYS[0] if OMNIROUTE_API_KEYS else ""

MIN_OUTPUT_TOKENS = 2048
MAX_AGENT_LOOPS = 2

# Chuoi fallback provider, thu theo dung thu tu liet ke. Moi phan tu la 1
# provider voi model string dang LiteLLM ("provider/model") va danh sach
# api_keys (co the rong neu chua dien trong .env — provider do se tu dong bi
# bo qua trong call_llm(), khong can xoa tay khoi danh sach nay).
PROVIDER_CHAIN = [
    {
        "name": "omniroute",
        "model_text": "openai/combo-text",
        "model_vision": "openai/auto",
        "api_keys": OMNIROUTE_API_KEYS,
        "api_base": OMNIROUTE_BASE_URL,
    },
    {
        "name": "gemini",
        "model_text": "gemini/gemini-3.5-flash",
        "model_vision": "gemini/gemini-3.5-flash",
        "api_keys": GEMINI_API_KEYS,
    },
    {
        "name": "groq",
        "model_text": "groq/llama-3.3-70b-versatile",
        "model_vision": "groq/llama-3.2-11b-vision-preview",
        "api_keys": GROQ_API_KEYS,
    },
    {
        "name": "nvidia_nim",
        "model_text": "nvidia_nim/meta/llama-3.3-70b-instruct",
        "model_vision": "nvidia_nim/meta/llama-3.2-90b-vision-instruct",
        "api_keys": NVIDIA_NIM_API_KEYS,
    },
]

# Giu lai 2 hang so nay (tro vao provider dau chuoi) de tuong thich nguoc
# phong khi co cho nao con import truc tiep MODEL_TEXT/MODEL_VISION.
MODEL_TEXT = PROVIDER_CHAIN[0]["model_text"]
MODEL_VISION = PROVIDER_CHAIN[0]["model_vision"]


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _build_messages(prompt: str, image_paths: list[str] | None):
    if not image_paths:
        return [{"role": "user", "content": prompt}]
    content = [{"type": "text", "text": prompt}]
    for img_path in image_paths[:3]:
        if os.path.exists(img_path):
            ext = Path(img_path).suffix.lstrip(".").lower()
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
            b64 = _encode_image(img_path)
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })
    return [{"role": "user", "content": content}]


def _call_one(
    model: str,
    api_key: str,
    messages,
    temperature: float,
    max_tokens: int,
    api_base: str | None = None,
) -> str:
    """Goi 1 model cu the; tu nang gap doi max_tokens neu thinking model tra None."""
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "api_key": api_key,
        "stream": False,
    }
    if api_base:
        kwargs["api_base"] = api_base

    response = litellm.completion(**kwargs)
    content = response.choices[0].message.content
    if content is None:
        kwargs["max_tokens"] = max_tokens * 2
        response2 = litellm.completion(**kwargs)
        content = response2.choices[0].message.content
        if content is None:
            raise ValueError(f"{model} van tra None sau khi nang max_tokens")
    return content.strip()


def call_llm(
    prompt: str,
    image_paths: list[str] | None = None,
    model: str = "auto",
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    """
    Goi LLM qua chuoi fallback PROVIDER_CHAIN (OmniRoute -> Gemini -> Groq -> NVIDIA NIM).
    model="vision" (hoac co image_paths) dung nhanh multimodal cua provider,
    con lai dung nhanh text. max_tokens tu dong nang len >= 2048 de tranh
    Gemini tra None (thinking budget).

    Provider/key dang thu neu loi (429/rate-limit/quota, timeout, 5xx, sai key,
    hay bat ky loi nao khac) se tu dong chuyen sang key ke tiep trong cung
    provider, roi sang provider ke tiep trong chuoi khi het key; chi nem loi
    (RuntimeError) khi tat ca provider/key deu that bai.
    """
    is_vision = model == "vision" or bool(image_paths)
    actual_max = max(max_tokens, MIN_OUTPUT_TOKENS)
    messages = _build_messages(prompt, image_paths)

    last_error: Exception | None = None
    for provider in PROVIDER_CHAIN:
        api_keys = provider["api_keys"]
        if not api_keys:
            print(f"[config] Bo qua provider '{provider['name']}' (chua co API key trong .env)")
            continue

        chosen_model = provider["model_vision"] if is_vision else provider["model_text"]
        api_base = provider.get("api_base")
        for key_idx, api_key in enumerate(api_keys, start=1):
            key_label = f"key {key_idx}/{len(api_keys)}" if len(api_keys) > 1 else "key"
            try:
                return _call_one(chosen_model, api_key, messages, temperature, actual_max, api_base=api_base)
            except Exception as e:
                print(
                    f"[config] Provider '{provider['name']}' ({chosen_model}, {key_label}) loi "
                    f"{type(e).__name__}: {e} -> thu key/provider ke tiep"
                )
                last_error = e
                continue

    raise RuntimeError(
        "Tat ca provider/key trong PROVIDER_CHAIN deu that bai — kiem tra lai API key trong .env "
        "(GEMINI_API_KEY / GROQ_API_KEY / NVIDIA_NIM_API_KEY)."
    ) from last_error


if __name__ == "__main__":
    print("[config] Testing multi-provider fallback chain (Gemini -> Groq -> NVIDIA NIM)...")
    result = call_llm("Reply with exactly: HELLO_AIC2026", model="text")
    print(f"[config] Response: {result!r}")
    print("[config] OK!")
