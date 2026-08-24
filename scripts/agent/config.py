"""Cau hinh LLM tap trung cho toan project AIC2026.

Moi loi goi LLM di qua LiteLLM. O AIC_MODE=test, uu tien goi thang Google AI
Studio (Gemini) bang cac key trong GEMINI_API_KEY, xoay vong qua nhieu model
Flash de tan dung free tier, roi moi fallback sang OpenRouter. O AIC_MODE=
contest, chi dung OpenRouter (OPENROUTER_MODEL_CONTEST) de on dinh. Cung mot
model duoc dung cho ca text va vision trong tung provider — xem PROVIDER_CHAIN.
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

# AIC_MODE chon model theo che do: "test" (re, dung khi dev) hoac "contest" (manh hon, dung luc nop
# that). Khong doi signature call_llm() — chi doi model nao duoc PROVIDER_CHAIN tro toi.
AIC_MODE = os.getenv("AIC_MODE", "test").strip().lower()
if AIC_MODE not in ("test", "contest"):
    print(f"[config] WARNING: AIC_MODE='{AIC_MODE}' khong hop le, dung 'test' hoac 'contest'. Mac dinh: 'test'")
    AIC_MODE = "test"

# Nhieu key Google AI Studio (goi thang Gemini, khong qua OpenRouter) — chi dung o AIC_MODE=test de
# tan dung free tier truoc khi ton tien OpenRouter. Cu phap nhieu key: xem _parse_key_list o tren
# (phay hoac xuong dong trong GEMINI_API_KEY).
# Luu y: Google phat hanh Gemini API key duoi nhieu dinh dang khac nhau (da xac nhan bang test that
# qua REST API — ca dang "AIzaSy..." lan dang "AQ.Ab8..." deu la key hop le, tra ve HTTP 200). Khong
# loc theo tien to o day — moi dong khong phai placeholder deu duoc coi la key that va dua vao vong xoay.
GEMINI_API_KEYS = _parse_key_list(os.getenv("GEMINI_API_KEY", ""))

# Danh sach model Gemini truc tiep, sap theo RPD (requests/ngay) giam dan roi RPM giam dan — de dung
# het quota cua cac model "Flash Lite" moi (RPD 500) truoc khi phai cham den nhom RPD 20, giup 1 key
# song duoc lau nhat trong 1 phien test. Rate limit free tier thuc te (1 key, ghi nhan 08/2026):
#   model                   RPM   TPM    RPD
#   gemini-3.5-flash-lite    15   250K   500
#   gemini-3.1-flash-lite    15   250K   500
#   gemini-2.5-flash-lite    10   250K    20
#   gemini-3.7-flash          5   250K    20
#   gemini-3.6-flash          5   250K    20
#   gemini-3.5-flash          5   250K    20
#   gemini-3-flash             5   250K    20
#   gemini-2.5-flash           5   250K    20
# Neu ten model tren Google AI Studio doi khac (vd them hau to phien ban), goi sai chi loi 400/404
# rat nhanh roi rot xuong model/key ke tiep — khong lam ket qua treo, khong can sua code.
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
    print("[config] WARNING: AIC_MODE=contest nhung OPENROUTER_MODEL_CONTEST trong .env trong rong. Dung OPENROUTER_MODEL thay the.")
    _SELECTED_MODEL = OPENROUTER_MODEL

MIN_OUTPUT_TOKENS = 2048
MAX_AGENT_LOOPS = 2

# LiteLLM dung tien to gemini/ de goi thang Google AI Studio, openrouter/ de chuyen den OpenRouter.
# O AIC_MODE=test: uu tien xoay vong GEMINI_DIRECT_MODELS x GEMINI_API_KEYS (free tier) truoc,
# OpenRouter la luoi an toan cuoi cung khi tat ca deu that bai (het quota/loi mang/sai ten model).
# O AIC_MODE=contest: chi dung OpenRouter — uu tien on dinh, khong phu thuoc free tier co the bi
# rate-limit giua luc thi that.
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

# Xoay diem bat dau trong danh sach key moi lan goi call_llm(), de cac lan goi lien tiep rai deu qua
# nhieu key thay vi lan nao cung dam vao key dau tien (de dinh RPM neu goi lien tuc trong 1 phut).
# Bien dem trong bo nho cua tien trinh — khong can luu lai giua cac lan chay script.
_call_counter = 0


def _rotate_keys(keys: list[str]) -> list[tuple[int, str]]:
    """Tra ve list (vi tri goc trong .env, key) da xoay, de log con tro ro vi tri that."""
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
        raise ValueError(f"{model} tra ve response rong")
    return content.strip()


def call_llm(
    prompt: str,
    image_paths: list[str] | None = None,
    model: str = "auto",
    temperature: float = 0.1,
    max_tokens: int = 512,
) -> str:
    """Goi LLM theo PROVIDER_CHAIN: uu tien Gemini truc tiep (AIC_MODE=test), fallback OpenRouter."""
    global _call_counter
    is_vision = model == "vision" or bool(image_paths)
    actual_max = max(max_tokens, MIN_OUTPUT_TOKENS)
    messages = _build_messages(prompt, image_paths)
    last_error: Exception | None = None
    _call_counter += 1

    for provider in PROVIDER_CHAIN:
        api_keys = provider["api_keys"]
        if not api_keys:
            print(f"[config] Bo qua {provider['name']} (chua co API key trong .env)")
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
        "Tat ca provider deu that bai — kiem tra GEMINI_API_KEY/OPENROUTER_API_KEY va model trong .env."
    ) from last_error


if __name__ == "__main__":
    print(f"[config] Testing PROVIDER_CHAIN (AIC_MODE={AIC_MODE}, {len(PROVIDER_CHAIN)} provider)...")
    result = call_llm("Reply with exactly: HELLO_AIC2026", model="text")
    print(f"[config] Response: {result!r}")
