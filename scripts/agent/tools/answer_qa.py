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

import json
import sys
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # repo root — cho `import scripts.*`
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.config import call_llm
from scripts.agent.tools.ocr_lookup import get_objects, objects_contain_keywords
from scripts.agent.tools.ocr_read import read_text_from_hits, format_ocr_hint
from scripts.agent.tools.asr_lookup import get_transcript

# ─── Prompts ───────────────────────────────────────────────────────────────────

ANSWER_FROM_OBJECTS_PROMPT = """\
You are answering a question about a video frame. You have:
- The original question (may be in Vietnamese or English)
- A list of objects detected in the top candidate frames (from object detection AI)

Note: this object list only contains generic OBJECT NAMES (person, car, fish, ...) detected by an
object detector — it does NOT contain any text, digits, prices, or signage content read from the image.
If the question asks for a specific NUMBER, PRICE, or TEXT shown on screen, reply with exactly:
CANNOT_ANSWER_FROM_OBJECTS — do not guess a number from the object list.

Based on the detected objects, answer the question concisely.
If you cannot answer from objects alone, reply with exactly: CANNOT_ANSWER_FROM_OBJECTS

Question: {question}

Detected objects in candidate frames:
{objects_text}
{transcript_hint}
Answer (concise, in the same language as the question):"""

ANSWER_FROM_IMAGES_PROMPT = """\
You are analyzing up to 10 candidate video keyframes retrieved for the same scene to answer a question.
They may show the same moment at slightly different times — one may be clearer than the others.

Question: {question}
Candidate evidence from OCR, captions, ASR, and object detection:
{evidence_bundle}

Look at the image(s) carefully and answer concisely:
- If the question asks for a NUMBER, COUNT, or TEXT visible on a display/gauge/sign/banner/scoreboard/
    price tag, read the digits/characters literally, one by one, and report EXACTLY what is shown across
    the clearest frame — do not round, estimate, or invent a "plausible" number.
- If the question asks to COUNT people/objects, count carefully what is visible in the frame(s).
- If the target detail is not visible/legible in ANY of the frames, say so briefly instead of guessing.
- If the question is in Vietnamese, answer in Vietnamese; if in English, answer in English.
- Keep the answer SHORT (1-5 words if possible) and factual, based only on what you can see.

Answer:"""

VISUAL_COUNT_PROMPT = """\
You are answering a visual counting question about a video frame.

Question: {question}
Candidate evidence from OCR, captions, ASR, and object detection:
{evidence_bundle}

Count only the requested visual markers or objects inside the main map/image area.
Ignore the entire legend, key, scale, labels, subtitles, and graphics outside the main map.
If the question says not to count the legend, do not count any symbol shown in the legend.
Return only the final integer count. Do not describe the scale, explain your reasoning, or quote text.

Answer:"""

VISUAL_COUNT_REPAIR_PROMPT = """\
Extract the answer to this visual counting question from the response below.
Return only one integer: the number of requested markers inside the main map/image area.
Ignore the legend and ignore any scale ranges such as 4.0-4.5.
Do not return an explanation.

Question: {question}
Previous response: {response}

Integer:"""

OCR_HINT_TEMPLATE = """\
Automated OCR hint (from a text-reading model on the candidate frame(s) — may contain errors; treat \
as a hint, verify every digit/word against what you actually see in the image before trusting it):
{ocr_lines}
"""

TRANSCRIPT_HINT_TEMPLATE = """\
Spoken transcript near this moment (automatic speech-to-text, may contain errors/no punctuation — \
treat as a hint, not a certain fact):
{transcript}
"""

CROSSCHECK_PROMPT = """\
You are verifying if an answer is consistent with the evidence found in a video frame.

Question: {question}
Proposed answer: {answer}
Detected objects: {objects}
Spoken transcript near this moment: {transcript}

Is this answer plausible given this evidence? Reply with:
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
QA_EVIDENCE_TOP_N = 10

_VISUAL_COUNT_HINTS = re.compile(
    r"(bao nhiêu|số lượng|đếm|how many|number of|count)",
    re.IGNORECASE,
)
_STANDALONE_INTEGER = re.compile(r"(?<![\d.,])\d+(?![\d.,])")
_CAPTION_JSONL_DIR = _ROOT / "data" / "extracted" / "caption_vintern1b"
_CAPTION_CACHE: dict[str, dict[int, str] | None] = {}


def is_visual_count_question(question: str) -> bool:
    """Nhận biết câu hỏi yêu cầu đếm đối tượng hoặc ký hiệu trong ảnh."""
    return bool(question and _VISUAL_COUNT_HINTS.search(question))


def extract_visual_count(response: str) -> str | None:
    """Chỉ nhận một số nguyên độc lập, tránh coi khoảng số trên chú giải là đáp án."""
    matches = _STANDALONE_INTEGER.findall(response or "")
    return matches[0] if len(matches) == 1 else None


def _trace_evidence(stage: str, candidates: list[dict], objects: list[str] | None = None,
                    ocr_hint: str = "", transcript: str = "") -> None:
    """In ra cac bang chung va nguon du lieu da duoc dung de tra loi."""
    candidate_ids = [
        f"{hit.get('video_id', '?')}/n={hit.get('n', '?')}/frame={hit.get('frame_id', '?')}"
        for hit in candidates
    ]
    print(f"[qa] Evidence ({stage}): candidates={candidate_ids}")
    print(f"[qa] Evidence ({stage}): objects={objects or 'not used'}")
    print(f"[qa] Evidence ({stage}): ocr={ocr_hint or 'not used'}")
    print(f"[qa] Evidence ({stage}): asr={transcript or 'not used'}")
    print(f"[qa] Evidence ({stage}): caption: not used")


def _load_captions(video_id: str) -> dict[int, str] | None:
    """Đọc caption Vintern theo video và cache trong tiến trình."""
    if video_id in _CAPTION_CACHE:
        return _CAPTION_CACHE[video_id]
    path = _CAPTION_JSONL_DIR / f"{video_id}.jsonl"
    if not path.exists():
        _CAPTION_CACHE[video_id] = None
        return None
    captions: dict[int, str] = {}
    try:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                try:
                    record = json.loads(line)
                    captions[int(record["n"])] = str(record.get("caption", "")).strip()
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
    except OSError:
        _CAPTION_CACHE[video_id] = None
        return None
    _CAPTION_CACHE[video_id] = captions
    return captions


def _build_evidence_bundle(candidates: list[dict]) -> tuple[str, list[str]]:
    """Gom moi bang chung cua top candidate va danh sach anh gui cho vision."""
    ocr_results = read_text_from_hits(candidates, top_n=len(candidates))
    image_paths: list[str] = []
    blocks: list[str] = []
    for index, hit in enumerate(candidates, start=1):
        video_id = hit.get("video_id", "")
        frame_n = hit.get("n")
        image_path = hit.get("jpg_path")
        if image_path and Path(image_path).exists():
            image_paths.append(image_path)
        objects = get_objects(video_id, int(frame_n)) if video_id and frame_n is not None else []
        transcript = get_transcript(video_id, float(hit["pts_time"])) if video_id and hit.get("pts_time") is not None else ""
        ocr_lines = ocr_results.get(index - 1, [])
        captions = _load_captions(video_id) if video_id else None
        caption = captions.get(int(frame_n), "") if captions is not None and frame_n is not None else ""
        blocks.append(
            f"Candidate {index}: video={video_id}, frame_id={hit.get('frame_id')}, "
            f"n={frame_n}, retrieval_score={hit.get('score')}\n"
            f"  Objects: {', '.join(objects) or 'none'}\n"
            f"  OCR: {' | '.join(ocr_lines) or 'none'}\n"
            f"  Vintern caption: {caption or 'none'}\n"
            f"  ASR near frame: {transcript or 'none'}"
        )
    return "\n\n".join(blocks), image_paths


def _trace_prompt(stage: str, prompt: str) -> None:
    """In ra nguyen prompt da gui qua call_llm()."""
    print(f"[qa] Prompt ({stage}):")
    print(prompt)

# Cau hoi doi hoi doc so/chu/dem tren man hinh (bien bao, dong ho, chu giai ban do, ten dia danh...).
# Objects JSON (Faster R-CNN/OpenImages) chi tra ve TEN OBJECT chung chung, khong doc duoc text/so, nen
# voi nhom cau hoi nay bo qua thang Tang 1 va di thang vao Tang 2 (vision doc anh truc tiep) de tranh
# doan bay tu danh sach object khong lien quan.
_TEXT_READING_HINTS = re.compile(
    r"(bao nhiêu|con số|số (?:mấy|hiển thị|ghi)|biển báo|biển số|giá(?:\s*tiền)?|"
    r"dòng chữ|chữ gì|tên (?:là gì|của|gọi)|ghi (?:là )?gì|cấp độ|number|how many|what number)",
    re.IGNORECASE,
)


def _needs_text_reading(question: str) -> bool:
    """True neu cau hoi can doc so/chu/dem tren man hinh — nen bo qua Tang 1 (objects JSON)."""
    return bool(_TEXT_READING_HINTS.search(question))


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
    skip_objects_tier = _needs_text_reading(question)
    visual_count = is_visual_count_question(question)

    # --- Tang 1: Objects JSON (bo qua neu cau hoi can doc so/chu — xem _needs_text_reading) ---
    if not skip_objects_tier:
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
            top_vid, top_pts = candidates[0].get("video_id", ""), candidates[0].get("pts_time")
            transcript1 = get_transcript(top_vid, top_pts) if top_vid and top_pts is not None else ""
            transcript_hint1 = TRANSCRIPT_HINT_TEMPLATE.format(transcript=transcript1) if transcript1 else ""

            obj_text = ", ".join(unique_objects[:30])  # cap 30 objects
            prompt1  = ANSWER_FROM_OBJECTS_PROMPT.format(
                question=question,
                objects_text=obj_text,
                transcript_hint=transcript_hint1,
            )
            _trace_evidence("objects", candidates, unique_objects[:30], transcript=transcript1)
            _trace_prompt("objects", prompt1)
            ans1 = call_llm(prompt1, model="text", temperature=0.1, max_tokens=80)
            print(f"[qa] LLM response (objects): {ans1!r}")

            if "CANNOT_ANSWER_FROM_OBJECTS" not in ans1:
                # Cross-check
                crosscheck = _crosscheck_answer(question, ans1, unique_objects[:15], transcript1)
                conf = 0.75 if crosscheck else 0.45
                return {
                    "answer":     _normalize_answer(ans1),
                    "best_hit":   candidates[0],
                    "confidence": conf,
                    "method":     "objects",
                }

    # --- Tang 2: Vision (chi khi co anh) ---
    # --- Tang 2: Vision voi evidence bundle ---
    # Gui top-10 candidate va moi nguon bang chung de LLM tu danh gia muc do lien quan.
    vision_hits = [h for h in candidates if h.get("jpg_path") and Path(h["jpg_path"]).exists()][:QA_EVIDENCE_TOP_N]
    if vision_hits:
        evidence_bundle, image_paths = _build_evidence_bundle(vision_hits)

        if visual_count:
            prompt2 = VISUAL_COUNT_PROMPT.format(
                question=question, evidence_bundle=evidence_bundle,
            )
        else:
            prompt2 = ANSWER_FROM_IMAGES_PROMPT.format(
                question=question, evidence_bundle=evidence_bundle,
            )
        _trace_evidence("vision", vision_hits, ocr_hint=evidence_bundle)
        _trace_prompt("vision", prompt2)
        ans2 = call_llm(
            prompt2,
            image_paths=image_paths,
            model="vision",
            temperature=0.1,
            max_tokens=80,
        )
        print(f"[qa] LLM response (vision): {ans2!r}")
        if visual_count:
            visual_count_answer = extract_visual_count(ans2)
            if visual_count_answer is None:
                repair_prompt = VISUAL_COUNT_REPAIR_PROMPT.format(
                    question=question, response=ans2,
                )
                repaired = call_llm(
                    repair_prompt, model="text", temperature=0.0, max_tokens=10,
                )
                _trace_prompt("visual-count-repair", repair_prompt)
                print(f"[qa] LLM response (visual-count-repair): {repaired!r}")
                visual_count_answer = extract_visual_count(repaired)
            if visual_count_answer is None:
                visual_count_answer = "N/A"
        else:
            visual_count_answer = _normalize_answer(ans2)
        # Cross-check voi objects gom tu tat ca anh da gui cho vision
        combined_objs = []
        for h in vision_hits:
            hit_n, hit_vid = h.get("n"), h.get("video_id", "")
            if hit_n:
                combined_objs.extend(get_objects(hit_vid, int(hit_n)))
        crosscheck = False if visual_count else _crosscheck_answer(
            question, ans2, list(dict.fromkeys(combined_objs)), "",
        )
        conf = 0.7 if visual_count else (0.85 if crosscheck else 0.6)
        return {
            "answer":     visual_count_answer,
            "best_hit":   vision_hits[0],
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


def _crosscheck_answer(question: str, answer: str, objects: list[str], transcript: str = "") -> bool:
    """Kiem tra answer nhat quan voi objects + transcript. Tra True neu qua duoc cross-check."""
    if (not objects and not transcript) or not answer or answer == "N/A":
        return False
    prompt = CROSSCHECK_PROMPT.format(
        question=question,
        answer=answer,
        objects=", ".join(objects[:15]) or "none",
        transcript=transcript or "none",
    )
    result = call_llm(prompt, model="text", temperature=0.0, max_tokens=20)
    return result.strip().upper().startswith("YES")


# ─── CLI self-test (repo khong dung pytest — xem CLAUDE.md) ────────────────────
def _run_self_tests() -> None:
    """Monkeypatch call_llm/get_objects/get_transcript de test transcript duoc bom vao Tier 1
    va crosscheck ma khong can goi API that."""
    global call_llm, get_objects, get_transcript
    _orig_call_llm, _orig_get_objects, _orig_get_transcript = call_llm, get_objects, get_transcript
    captured_prompts: list[str] = []

    def _fake_call_llm(prompt, **kwargs):
        captured_prompts.append(prompt)
        if "Detected objects in candidate frames" in prompt:
            return "a red car"
        if "Is this answer plausible" in prompt:
            return "YES"
        return "unexpected prompt"

    hit = {"video_id": "V", "n": 1, "frame_idx": 0, "frame_id": 1, "pts_time": 10.0,
           "score": 0.9, "jpg_path": None}

    try:
        # Test A: transcript co noi dung -> phai xuat hien trong ca prompt Tier 1 va crosscheck
        call_llm = _fake_call_llm
        get_objects = lambda vid, n: ["car", "person"]
        get_transcript = lambda vid, pts, window=7.5: "a red car passes by quickly"
        captured_prompts.clear()

        result = answer_from_hits("What color is the car?", [hit], top_n=1)
        assert result["method"] == "objects", f"Phai dung Tier 1 (objects), duoc {result['method']}"
        assert result["answer"] == "a red car", f"Answer sai: {result['answer']!r}"

        tier1_prompt = next(p for p in captured_prompts if "Detected objects in candidate frames" in p)
        assert "a red car passes by quickly" in tier1_prompt, "Tier 1 prompt phai chua transcript hint"

        crosscheck_prompt = next(p for p in captured_prompts if "Is this answer plausible" in p)
        assert "a red car passes by quickly" in crosscheck_prompt, "Crosscheck prompt phai chua transcript"
        print("[answer_qa] Test Tier 1 + crosscheck co transcript: OK")

        # Test B: transcript rong -> khong crash, template van render binh thuong
        get_transcript = lambda vid, pts, window=7.5: ""
        captured_prompts.clear()
        result_b = answer_from_hits("What color is the car?", [hit], top_n=1)
        assert result_b["method"] == "objects", f"Phai dung Tier 1 (objects), duoc {result_b['method']}"
        print("[answer_qa] Test transcript rong khong crash: OK")

        print("[answer_qa] Tat ca self-test PASS")
    finally:
        call_llm, get_objects, get_transcript = _orig_call_llm, _orig_get_objects, _orig_get_transcript


# ─── CLI demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _run_self_tests()
    print()

    from scripts.agent.tools.retrieve import fast_retrieve

    question = "What objects can be seen in the background of this scene?"
    print(f"[answer_qa] Testing with: {question!r}")

    hits = fast_retrieve("outdoor press conference with trees", top_k=5)
    result = answer_from_hits(question, hits, top_n=3)
    print(f"  answer:     {result['answer']!r}")
    print(f"  confidence: {result['confidence']:.2f}")
    print(f"  method:     {result['method']}")
    print(f"  best_hit:   {result['best_hit'].get('video_id')} frame_id={result['best_hit'].get('frame_id')}")
