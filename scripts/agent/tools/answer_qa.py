"""
answer_qa.py — Trich xuat answer cho query dang Q&A.

Workflow 2 tang (theo khuyen nghi tieu lieu BTC):
  Tang 1: Doc objects JSON (offline, mien phi) -> tra loi neu du
  Tang 2: Goi Gemini VLM doc anh (chi khi can, chi khi co jpg)

Cross-check: answer phai nhat quan voi objects detect duoc.
Vi "sai answer = R-Score ve 0 du dung frame/video".

Usage:
    from scripts.agent.tools.answer_qa import answer_from_hits
    result = answer_from_hits(question, hits)
    # result: {answer, best_hit, confidence, method}
"""
from __future__ import annotations

import sys
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.config import call_llm
from agent.tools.ocr_lookup import get_objects, objects_contain_keywords

# ─── Prompts ───────────────────────────────────────────────────────────────────

ANSWER_FROM_OBJECTS_PROMPT = """\
You are answering a question about a video frame. You have:
- The original question (may be in Vietnamese or English)
- A list of objects detected in the top candidate frames (from object detection AI)

Based on the detected objects, answer the question concisely.
If you cannot answer from objects alone, reply with exactly: CANNOT_ANSWER_FROM_OBJECTS

Question: {question}

Detected objects in candidate frames:
{objects_text}

Answer (concise, in the same language as the question):"""

ANSWER_FROM_IMAGE_PROMPT = """\
You are analyzing a video keyframe to answer a question.

Question: {question}

Look at the image carefully and answer concisely.
- If the question is in Vietnamese, answer in Vietnamese
- If in English, answer in English
- Keep the answer SHORT (1-5 words if possible)
- Be factual, based only on what you can see

Answer:"""

CROSSCHECK_PROMPT = """\
You are verifying if an answer is consistent with detected objects in an image.

Question: {question}
Proposed answer: {answer}
Detected objects: {objects}

Is this answer plausible given the detected objects? Reply with:
- "YES" if consistent
- "NO: <brief reason>" if inconsistent

Response:"""

KNOWLEDGE_FALLBACK_PROMPT = """\
Answer this question using general knowledge only because no usable video evidence was found.
If the answer cannot be inferred reliably from the question, reply exactly: CANNOT_ANSWER.
Return only the shortest answer, with no explanation, no sentence prefix, and no uncertainty.
Use the same language as the question and keep the answer under 100 characters.

Question: {question}

Answer:"""

MAX_ANSWER_CHARS = 100


def _normalize_answer(raw_answer: str) -> str:
    """Giu answer 1 dong, ngan gon, va khong vuot gioi han BTC."""
    answer = " ".join(str(raw_answer).replace("\r", " ").replace("\n", " ").split())
    answer = re.sub(r"^(answer|final answer|câu trả lời)\s*:\s*", "", answer, flags=re.IGNORECASE)
    answer = answer.strip(" \t\"'")
    if len(answer) <= MAX_ANSWER_CHARS:
        return answer

    first_sentence = re.split(r"(?<=[.!?])\s+", answer, maxsplit=1)[0].strip()
    if first_sentence and len(first_sentence) <= MAX_ANSWER_CHARS:
        return first_sentence
    return answer[: MAX_ANSWER_CHARS - 3].rstrip() + "..."


# ─── Main Function ─────────────────────────────────────────────────────────────

def answer_from_hits(
    question: str,
    hits: list[dict],
    top_n: int = 5,
) -> dict:
    """
    Trich xuat answer tu danh sach candidate hits.

    Args:
        question: Cau hoi (tieng Viet hoac Anh).
        hits:     list[dict] tu fast_retrieve(), da co truong 'n' tu map-keyframes.
        top_n:    So hit dau can xem xet.

    Returns:
        dict:
          answer     (str):   Cau tra loi.
          best_hit   (dict):  Hit tot nhat de nop submission.
          confidence (float): 0.0-1.0.
          method     (str):   "objects" | "vision" | "fallback".
    """
    if not hits:
        return {"answer": "", "best_hit": {}, "confidence": 0.0, "method": "fallback"}

    candidates = hits[:top_n]

    # --- Tang 1: Objects JSON ---
    all_objects = []
    objects_by_hit = {}
    for i, hit in enumerate(candidates):
        vid = hit.get("video_id", "")
        n   = hit.get("n")
        if vid and n is not None:
            objs = get_objects(vid, int(n))
            objects_by_hit[i] = objs
            all_objects.extend(objs)
        else:
            objects_by_hit[i] = []

    unique_objects = list(dict.fromkeys(all_objects))  # preserve order, deduplicate

    if unique_objects:
        obj_text = ", ".join(unique_objects[:30])  # cap 30 objects
        prompt1  = ANSWER_FROM_OBJECTS_PROMPT.format(
            question=question,
            objects_text=obj_text,
        )
        ans1 = call_llm(prompt1, model="text", temperature=0.1, max_tokens=80)

        if "CANNOT_ANSWER_FROM_OBJECTS" not in ans1:
            # Cross-check
            crosscheck = _crosscheck_answer(question, ans1, unique_objects[:15])
            conf = 0.75 if crosscheck else 0.45
            return {
                "answer":     _normalize_answer(ans1),
                "best_hit":   candidates[0],
                "confidence": conf,
                "method":     "objects",
            }

    # --- Tang 2: Gemini Vision (chi khi co anh) ---
    for hit in candidates:
        jpg = hit.get("jpg_path")
        if jpg and Path(jpg).exists():
            prompt2 = ANSWER_FROM_IMAGE_PROMPT.format(question=question)
            ans2 = call_llm(
                prompt2,
                image_paths=[jpg],
                model="vision",
                temperature=0.1,
                max_tokens=80,
            )
            # Cross-check voi objects
            hit_n = hit.get("n")
            hit_vid = hit.get("video_id", "")
            hit_objs = get_objects(hit_vid, int(hit_n)) if hit_n else []
            crosscheck = _crosscheck_answer(question, ans2, hit_objs)
            conf = 0.85 if crosscheck else 0.6
            return {
                "answer":     _normalize_answer(ans2),
                "best_hit":   hit,
                "confidence": conf,
                "method":     "vision",
            }

    # --- Fallback: chi dung kien thuc nen khi khong con bang chung tu video ---
    knowledge_prompt = KNOWLEDGE_FALLBACK_PROMPT.format(question=question)
    knowledge_answer = _normalize_answer(
        call_llm(knowledge_prompt, model="text", temperature=0.0, max_tokens=80)
    )
    if knowledge_answer.upper() == "CANNOT_ANSWER":
        knowledge_answer = "N/A"
    return {
        "answer":     knowledge_answer,
        "best_hit":   candidates[0] if candidates else {},
        "confidence": 0.1,
        "method":     "knowledge_fallback",
    }


def _crosscheck_answer(question: str, answer: str, objects: list[str]) -> bool:
    """Kiem tra answer nhat quan voi objects. Tra True neu qua duoc cross-check."""
    if not objects or not answer or answer == "N/A":
        return False
    prompt = CROSSCHECK_PROMPT.format(
        question=question,
        answer=answer,
        objects=", ".join(objects[:15]),
    )
    result = call_llm(prompt, model="text", temperature=0.0, max_tokens=20)
    return result.strip().upper().startswith("YES")


# ─── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from agent.tools.retrieve import fast_retrieve

    question = "What objects can be seen in the background of this scene?"
    print(f"[answer_qa] Testing with: {question!r}")

    hits = fast_retrieve("outdoor press conference with trees", top_k=5)
    result = answer_from_hits(question, hits, top_n=3)
    print(f"  answer:     {result['answer']!r}")
    print(f"  confidence: {result['confidence']:.2f}")
    print(f"  method:     {result['method']}")
    print(f"  best_hit:   {result['best_hit'].get('video_id')} frame_id={result['best_hit'].get('frame_id')}")
