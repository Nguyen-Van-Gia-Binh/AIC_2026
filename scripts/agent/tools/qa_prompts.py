"""
qa_prompts.py — Toàn bộ prompt template của nhánh Q&A, tách khỏi answer_qa.py.

Để riêng vì đây là phần được đọc/sửa nhiều nhất khi tinh chỉnh chất lượng trả lời, trong khi logic
3 tầng ở answer_qa.py gần như không đổi. Sửa nội dung ở đây LÀ đổi hành vi hệ thống — phải đo lại
bằng tests/e2e/score_pipelines.py, không phải sửa xong là xong.

Prompt viết bằng tiếng Anh (mô hình bám tốt hơn); phần trả lời được yêu cầu dùng cùng ngôn ngữ với
câu hỏi. Đây là ngoại lệ có chủ đích với quy ước "tiếng Việt" của repo.
"""
from __future__ import annotations

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

CANONICAL_PROMPT = """\
Compress the following answer into the shortest possible form: 1-3 keywords that directly answer the \
question. Remove all conversational wording, full sentences and explanations. Keep numbers, names and \
colors exactly as written. Answer in the SAME language as the original answer.

Question: {question}
Long answer: {answer}

Short answer:"""
