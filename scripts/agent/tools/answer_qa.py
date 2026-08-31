"""
answer_qa.py — Trích xuất answer cho query dạng Q&A.

Workflow 3 tầng:
  Tầng 1: Đọc objects JSON (offline, miễn phí) -> trả lời nếu đủ
  Tầng 2: Gọi LLM Vision đọc ảnh (chỉ khi cần, chỉ khi có jpg)

Cross-check: answer phải nhất quán với objects detect được.
Vì "sai answer = R-Score về 0 dù đúng frame/video".

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
from scripts.agent.tools.objects_lookup import get_objects, objects_contain_keywords
from scripts.agent.tools.ocr_read import read_text_from_hits, format_ocr_hint
from scripts.agent.tools.qa_prompts import (
    ANSWER_FROM_OBJECTS_PROMPT, ANSWER_FROM_IMAGES_PROMPT, VISUAL_COUNT_PROMPT,
    VISUAL_COUNT_REPAIR_PROMPT, OCR_HINT_TEMPLATE, TRANSCRIPT_HINT_TEMPLATE,
    CROSSCHECK_PROMPT, KNOWLEDGE_FALLBACK_PROMPT,
)
from scripts.agent.tools.qa_classify import (
    is_visual_count_question, needs_text_reading, asks_displayed_number,
)
from scripts.agent.tools.qa_normalize import (
    canonicalize_answer, is_non_answer, normalize_answer, extract_visual_count,
)
from scripts.agent.tools.asr_lookup import get_transcript

QA_EVIDENCE_TOP_N = 10

_CAPTION_JSONL_DIR = _ROOT / "data" / "extracted" / "caption_vintern1b"
_CAPTION_CACHE: dict[str, dict[int, str] | None] = {}


def _trace_evidence(stage: str, candidates: list[dict], objects: list[str] | None = None,
                    ocr_hint: str = "", transcript: str = "") -> None:
    """In ra các bằng chứng và nguồn dữ liệu đã được dùng để trả lời."""
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
    """Gom mọi bằng chứng của top candidate và danh sách ảnh gửi cho vision."""
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
    """In ra nguyên prompt đã gửi qua call_llm()."""
    print(f"[qa] Prompt ({stage}):")
    print(prompt)

_DIGIT_TOKEN_RE = re.compile(r"\d[\d.,:/-]*\d|\d")


def ocr_direct_answer(question: str, ocr_results: dict) -> str | None:
    """
    OCR Direct Overwrite (§4.2): nếu câu hỏi hỏi về SỐ ĐƯỢC HIỂN THỊ trên khung hình và OCR đọc được
    DUY NHẤT 1 chuỗi số trên các frame candidate, trả thẳng chuỗi số đó — không để VLM tự phỏng đoán
    con số.

    Có ý RẤT chặt: chỉ kích hoạt khi (a) câu hỏi thuộc nhóm "số hiển thị" (không phải đếm vật thể),
    và (b) tất cả frame candidate đọc ra CÙNG 1 chuỗi số duy nhất. Nhiều chuỗi số khác nhau -> trả
    None (để VLM nhìn ảnh quyết định), vì lúc đó không biết số nào thuộc "vùng quan tâm".
    """
    if not asks_displayed_number(question) or not ocr_results:
        return None
    tokens: set = set()
    for lines in ocr_results.values():
        for line in lines or []:
            tokens.update(m.group(0) for m in _DIGIT_TOKEN_RE.finditer(line))
    if len(tokens) != 1:
        return None
    token = tokens.pop()
    print(f"[answer_qa] OCR direct overwrite: câu hỏi về số hiển thị, OCR đọc duy nhất {token!r}")
    return token

# ─── Main Function ─────────────────────────────────────────────────────────────

def answer_from_hits(
    question: str,
    hits: list[dict],
    top_n: int = 5,
) -> dict:
    """
    Trích xuất answer từ danh sách candidate hits.

    Args:
        question: Câu hỏi (tiếng Việt hoặc Anh).
        hits:     list[dict] từ fast_retrieve(), đã có trường 'n' từ map-keyframes.
        top_n:    So hit dau can xem xet.

    Returns:
        dict:
          answer     (str):   Câu trả lời.
          best_hit   (dict):  Hit tot nhat de nop submission.
          confidence (float): 0.0-1.0.
          method     (str):   "objects" | "vision" | "fallback".
    """
    if not hits:
        return {"answer": "", "best_hit": {}, "confidence": 0.0, "method": "fallback"}

    candidates = hits[:top_n]
    skip_objects_tier = needs_text_reading(question)
    visual_count = is_visual_count_question(question)

    # --- Tầng 1: Objects JSON (bỏ qua nếu câu hỏi cần đọc số/chữ — xem needs_text_reading) ---
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

            if "CANNOT_ANSWER_FROM_OBJECTS" not in ans1 and not is_non_answer(ans1):
                # Cross-check
                crosscheck = _crosscheck_answer(question, ans1, unique_objects[:15], transcript1)
                conf = 0.75 if crosscheck else 0.45
                return {
                    "answer":     canonicalize_answer(ans1, question),
                    "best_hit":   candidates[0],
                    "confidence": conf,
                    "method":     "objects",
                }

    # --- Tầng 2: Vision (chỉ khi có ảnh) ---
    # --- Tầng 2: Vision với evidence bundle ---
    # Gửi top-10 candidate và mọi nguồn bằng chứng để LLM tự đánh giá mức độ liên quan.
    vision_hits = [h for h in candidates if h.get("jpg_path") and Path(h["jpg_path"]).exists()][:QA_EVIDENCE_TOP_N]
    if vision_hits:
        evidence_bundle, image_paths = _build_evidence_bundle(vision_hits)

        # OCR thật — chỉ chạy khi câu hỏi thực sự cần đọc chữ/số (điều kiện tái sử dụng từ
        # skip_objects_tier ở trên), chỉ làm gợi ý phụ cho Vision, không thay thế nó.
        ocr_hint = ""
        if skip_objects_tier:
            ocr_results = read_text_from_hits(vision_hits, top_n=3)
            formatted = format_ocr_hint(ocr_results)
            if formatted:
                ocr_hint = OCR_HINT_TEMPLATE.format(ocr_lines=formatted)

            # OCR Direct Overwrite (§4.2) — câu hỏi về số HIỂN THỊ trên khung hình + OCR đọc được
            # duy nhất 1 chuỗi số => lấy thẳng chuỗi đó, không để VLM phỏng đoán con số.
            direct = ocr_direct_answer(question, ocr_results)
            if direct:
                return {
                    "answer":     direct,
                    "best_hit":   vision_hits[0],
                    "confidence": 0.8,
                    "method":     "ocr_direct",
                }

        if visual_count:
            prompt2 = VISUAL_COUNT_PROMPT.format(
                question=question, evidence_bundle=evidence_bundle,
            )
        else:
            top_vid2, top_pts2 = vision_hits[0].get("video_id", ""), vision_hits[0].get("pts_time")
            transcript2 = get_transcript(top_vid2, top_pts2) if top_vid2 and top_pts2 is not None else ""
            transcript_hint2 = TRANSCRIPT_HINT_TEMPLATE.format(transcript=transcript2) if transcript2 else ""
            prompt2 = ANSWER_FROM_IMAGES_PROMPT.format(
                question=question, evidence_bundle=evidence_bundle,
            )
        _trace_evidence("vision", vision_hits, ocr_hint=ocr_hint or evidence_bundle)
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
            visual_count_answer = normalize_answer(ans2)
        # Cross-check với objects gom từ tất cả ảnh đã gửi cho vision
        combined_objs = []
        for h in vision_hits:
            hit_n, hit_vid = h.get("n"), h.get("video_id", "")
            if hit_n:
                combined_objs.extend(get_objects(hit_vid, int(hit_n)))
        crosscheck = False if visual_count else _crosscheck_answer(
            question, ans2, list(dict.fromkeys(combined_objs)),
            transcript2 if not visual_count else "",
        )
        conf = 0.7 if visual_count else (0.85 if crosscheck else 0.6)
        if not visual_count and is_non_answer(ans2):
            # Cổng chống ảo giác: VLM tự nói không đọc/nhìn được -> KHÔNG nâng lên thành đáp án,
            # hạ confidence để pipeline_qa thử vòng 2 (rewrite + retrieve lại) thay vì nộp chuỗi này.
            print(f"[answer_qa] Vision trả lời không xác định ({ans2!r}) -> hạ confidence")
            conf = min(conf, 0.3)
        return {
            "answer":     visual_count_answer if visual_count else canonicalize_answer(ans2, question),

            "best_hit":   vision_hits[0],
            "confidence": conf,
            "method":     "vision",
        }

    # --- Fallback: chỉ dùng kiến thức nền khi không còn bằng chứng từ video ---
    knowledge_prompt = KNOWLEDGE_FALLBACK_PROMPT.format(question=question)
    knowledge_answer = normalize_answer(
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
    """Kiểm tra answer nhất quán với objects + transcript. Trả True nếu qua được cross-check."""
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

# Bo test: tests/unit/test_answer_qa.py (+ test_qa_answer_contract.py)

# ─── CLI demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from scripts.agent.tools.retrieve import fast_retrieve

    question = "What objects can be seen in the background of this scene?"
    print(f"[answer_qa] Testing with: {question!r}")

    hits = fast_retrieve("outdoor press conference with trees", top_k=5)
    result = answer_from_hits(question, hits, top_n=3)
    print(f"  answer:     {result['answer']!r}")
    print(f"  confidence: {result['confidence']:.2f}")
    print(f"  method:     {result['method']}")
    print(f"  best_hit:   {result['best_hit'].get('video_id')} frame_id={result['best_hit'].get('frame_id')}")
