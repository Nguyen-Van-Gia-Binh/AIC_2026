"""
rewrite.py — Dịch query tiếng Việt sang tiếng Anh + làm rõ mô tả visual.

CLIP-family hiểu tiếng Anh tốt hơn nhiều. Mô tả visual-centric (vật thể neo,
màu sắc, hành động, bối cảnh) sẽ cho kết quả retrieval tốt hơn.

Usage:
    from scripts.agent.tools.rewrite import rewrite_query
    en = rewrite_query("Một người đang đi xe đạp trên đường núi")
    # -> "a person cycling on a mountain road, outdoor scenery"
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent  # repo root — cho `import scripts.*`
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.config import call_llm  # noqa: E402

# Phần "rules" dùng chung cho cả chế độ rewrite 1 câu (REWRITE_PROMPT) và nhiều câu
# (REWRITE_CANDIDATES_PROMPT) — tách riêng để không lặp lại/lệch nhau giữa 2 prompt.
REWRITE_INTRO = """\
You are a visual search query optimizer for a video retrieval system using CLIP (image-text matching)
on Vietnamese TV/news-style footage (cooking, wildlife, sports, education, disaster coverage, festivals).

Task: Translate and rewrite the following query into {n_desc} concise English sentence(s) describing a
SINGLE video frame, optimized for CLIP image search.

Rules:
- Output ONLY the rewritten query (no explanations, no quotes)
- Keep it concise (max 40 words), plain visual language (no camera/editing jargon like "shot", "cut")
- If the query describes MULTIPLE sequential moments ("starts with X, then Y, ends with Z" /
    "bắt đầu bằng... sau đó... kết thúc bằng..."), do NOT blend everything into one vague sentence —
    but also do NOT silently drop a rare/specific object just because it was mentioned in an earlier
    moment. Keep a short mention (a few words) of EVERY moment that contains a rare or specific visual
    detail (an unusual object, a measuring instrument, a display/gauge/sign/number board, a close-up
    action); only drop moments that are generic/common (plain establishing shots, ordinary people
    standing/walking with no distinguishing detail). If you must pick just ONE moment as the primary
    target because of the length limit, pick the one with the rarest, most specific object — NOT
    automatically the first or the last one described; ordering in the query is not a reliable signal
    of which moment is the target.
- A measuring/display object mentioned anywhere in the query (a scale, gauge, meter, sign, scoreboard,
    price/number board) is almost always more distinctive than a generic action (a hand holding
    something, someone walking) — when choosing what to keep, this kind of object outranks a generic
    action even if the generic action is described later in the query.
- Preserve EXACT counts and colors mentioned for people/objects (e.g. "5 people", "one person wearing
    glasses", "three red hats", "yellow car") — these are strong CLIP-matchable attributes, keep them
    verbatim rather than summarizing them away
- If the query says something is ABSENT or NEGATED (Vietnamese "không có", "không đeo", "không mặc",
    English "without", "no X", "not wearing X"), do NOT keep the negation as-is in the rewritten query —
    CLIP matches positive visual descriptions and cannot understand logical negation, so a literal "a
    person without glasses" is often still matched by CLIP toward frames that DO show glasses. Instead
    rewrite the negated clause into what IS visibly present: either describe the actually-visible
    attribute in its place (e.g. "không đeo kính" -> "bare face" / "plain face, no eyewear" as part of a
    positive description, not as a "no X" clause), or if the object is simply not relevant to
    disambiguate the scene, drop it from the description entirely rather than negate it. Never output
    the words "no"/"without"/"không" immediately before an object name.
- Preserve distinctive proper nouns or on-screen signage/text mentioned in the query (e.g. place/brand
    names like "London Zoo", a price/number board, a scoreboard) — CLIP cannot read text reliably, but
    naming it tells CLIP what KIND of shot to match (a sign, a gauge, a display)
- FIRST identify and preserve the single most distinctive visual anchor object or landmark for the
    chosen moment (for example: helicopter, wind turbine, red octopus toy, sand sculpture, a scale/gauge
    display, a lion-dance head)
- Put that anchor object near the START of the rewritten query; never omit it even
    when the query also describes people or an action
- Then include the main action and the important people/clothing/colors, followed by location
    or background context if useful
- Prefer concrete visual nouns and verbs; remove vague filler and factual details
    that cannot be seen in a single still frame (sounds, durations, "sau đó", "tiếp theo")
- Remove leftover temporal/sequential connector words (first, then, after) once the single target
    moment has been chosen — this rewrite is for single-frame retrieval, including each individual
    TRAKE event
- If already in English, just clean and optimize it while preserving the anchor object and rules above

Preferred format: "[distinctive anchor object/display] + [main action] + [people/clothing/colors] + [visible setting]"
"""

# Đuôi cho chế độ 1 câu (rewrite_query) — giữ nguyên hành vi cũ.
_SINGLE_SUFFIX = """
Query: {query}

Rewritten query:"""

# Đuôi cho chế độ nhiều phương án (rewrite_query_candidates) — mỗi phương án là 1 dòng đánh số.
# Số lượng KHÔNG cố định — LLM tự quyết định cần bao nhiêu phương án tuỳ độ mơ hồ/ngữ cảnh của
# query (có thể chỉ 1 nếu query đã rõ ràng), tối đa max_n, thay vì ép đủ số dòng bằng paraphrase
# thừa. Vẫn chỉ 1 lần gọi LLM (không gọi riêng cho từng phương án) để đỡ tốn thời gian/chi phí.
_CANDIDATES_SUFFIX = """
Additionally: decide how many candidate rewrites are actually useful here, from 1 up to {max_n}.
Only output MORE THAN ONE candidate if the query genuinely has multiple plausible interpretations or
multiple distinctive objects/moments worth emphasizing differently — in that case make each candidate
emphasize a different one (still following all rules above, each candidate independently valid on its
own). If the query is unambiguous and has one clear best rewrite, output ONLY 1 candidate — do NOT pad
with near-duplicate paraphrases just to reach {max_n}.

Query: {query}

Output ONLY the candidates you decide are meaningfully different (1 to {max_n} lines), nothing else
(no blank lines, no extra commentary). Each line format:
N. <rewritten query>"""


def rewrite_query(query: str, feedback: str | None = None, question: str | None = None) -> str:
    """
    Dịch và tối ưu query cho CLIP/SigLIP search.

    Args:
        query:    Query gốc (tiếng Việt hoặc Anh).
        feedback: Feedback từ lần search trước (để cải thiện, dùng cho vòng lặp thứ 2).
        question: Câu hỏi Q&A cụ thể nếu có (dùng cho pipeline_qa.py) — giúp rewrite giữ lại đúng
                  vật thể/cảnh cần nhìn thấy để trả lời, thay vì vô tình bỏ qua nó khi query mô tả
                  nhiều cảnh nối tiếp nhau.

    Returns:
        Query tiếng Anh đã tối ưu.
    """
    prompt = REWRITE_INTRO.format(n_desc="ONE") + _SINGLE_SUFFIX.format(query=query)
    prompt += _build_extra_context(question, feedback)

    try:
        result = call_llm(prompt, model="text", temperature=0.2, max_tokens=60)
        # Clean up: bỏ dấu ngoặc kép, xuống dòng thừa
        result = result.strip().strip('"').strip("'").split("\n")[0].strip()
        return result if result else query.strip()
    except Exception as e:
        print(f"[rewrite] call_llm lỗi ({type(e).__name__}: {e}), fallback về query gốc")
        return query.strip()


def rewrite_query_candidates(
    query: str,
    max_n: int = 3,
    feedback: str | None = None,
    question: str | None = None,
) -> list[str]:
    """
    Sinh TỐI ĐA max_n phương án rewrite KHÁC NHAU cho query — số lượng thực tế do LLM tự quyết định
    tuỳ theo query có nhiều cách hiểu/nhiều vật thể đáng chú ý hay không (query rõ ràng -> có thể
    chỉ 1 phương án), để người dùng chọn 1 hoặc tự viết lại trong UI (xem frontend/) thay vì hệ
    thống tự động dùng 1 câu rewrite rồi search luôn.

    Args:
        query:    Query gốc (tiếng Việt hoặc Anh).
        max_n:    Số phương án tối đa (mặc định 3) — LLM có thể trả về ít hơn nếu không cần thiết.
        feedback: Xem rewrite_query().
        question: Xem rewrite_query().

    Returns:
        list[str] độ dài trong [1, max_n] — nếu LLM lỗi hoặc không trả về dòng nào parse được,
        fallback về 1 phần tử là kết quả của rewrite_query().
    """
    prompt = REWRITE_INTRO.format(n_desc=f"1 to {max_n} DIFFERENT") + _CANDIDATES_SUFFIX.format(max_n=max_n, query=query)
    prompt += _build_extra_context(question, feedback)

    try:
        result = call_llm(prompt, model="text", temperature=0.4, max_tokens=200)
        candidates = _parse_candidates(result)
    except Exception as e:
        print(f"[rewrite] rewrite_query_candidates lỗi ({type(e).__name__}: {e}), fallback về 1 câu")
        candidates = []

    if not candidates:
        # Fallback: LLM không trả về dòng nào parse được (hoặc lỗi) -> dùng lại rewrite 1 câu.
        candidates = [rewrite_query(query, feedback=feedback, question=question)]

    return candidates[:max_n]


def _build_extra_context(question: str | None, feedback: str | None) -> str:
    """Đoạn prompt bổ sung dùng chung cho cả rewrite_query và rewrite_query_candidates."""
    extra = ""
    if question:
        extra += (
            f"\n\nThis rewritten query will be used to retrieve the video frame needed to answer this "
            f"question: {question}\nMake sure the object/detail the question asks about (e.g. a number "
            f"on a display, a sign, a specific item) is kept in the rewritten query, even if it was "
            f"described earlier in the query than other moments."
        )
    if feedback:
        extra += f"\n\nPrevious search failed. Feedback: {feedback}\nRewrite with different keywords:"
    return extra


_CANDIDATE_LINE_RE = re.compile(r"^\s*\d+[\.\)]\s*(.+?)\s*$")


def _parse_candidates(raw: str) -> list[str]:
    """Tách output nhiều dòng dạng '1. ...' / '2) ...' thành list string sạch (bỏ số thứ tự,
    ngoặc kép thừa). Bỏ qua dòng không khớp pattern thay vì crash — LLM đôi khi chèn dòng trống
    hoặc ghi chú ngoài ý muốn."""
    candidates = []
    for line in raw.strip().splitlines():
        m = _CANDIDATE_LINE_RE.match(line)
        if not m:
            continue
        text = m.group(1).strip().strip('"').strip("'").strip()
        if text:
            candidates.append(text)
    return candidates


# ─── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_queries = [
        "Một người đang phát biểu tại cuộc họp báo ngoài trời, phía sau có nhiều cây xanh",
        "Trẻ em đang chơi bóng đá trên sân cỏ xanh",
        "A red sports car driving on a highway at night",
        "Trong video về lễ trao giải âm nhạc, người phụ nữ mặc váy đỏ đang cầm ly màu gì?",
    ]
    print("[rewrite] Testing query rewriter (1 cau)...\n")
    for q in test_queries:
        en = rewrite_query(q)
        print(f"  VI: {q[:60]}...")
        print(f"  EN: {en}")
        print()

    print("[rewrite] Testing query rewriter (nhiều phương án)...\n")
    for q in test_queries:
        cands = rewrite_query_candidates(q, max_n=3)
        print(f"  VI: {q[:60]}...")
        for i, c in enumerate(cands, 1):
            print(f"    {i}. {c}")
        print()
