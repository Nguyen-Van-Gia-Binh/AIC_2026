"""
rewrite.py — Dich query tieng Viet sang tieng Anh + lam ro mo ta visual.

CLIP-family hieu tieng Anh tot hon nhieu. Mo ta visual-centric (vat the neo,
mau sac, hanh dong, boi canh) se cho ket qua retrieval tot hon.

Usage:
    from scripts.agent.tools.rewrite import rewrite_query
    en = rewrite_query("Mot nguoi dang di xe dap tren duong nui")
    # -> "a person cycling on a mountain road, outdoor scenery"
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.config import call_llm  # noqa: E402

# Phan "rules" dung chung cho ca che do rewrite 1 cau (REWRITE_PROMPT) va nhieu cau
# (REWRITE_CANDIDATES_PROMPT) — tach rieng de khong lap lai/lech nhau giua 2 prompt.
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

# Duoi cho che do 1 cau (rewrite_query) — giu nguyen hanh vi cu.
_SINGLE_SUFFIX = """
Query: {query}

Rewritten query:"""

# Duoi cho che do nhieu phuong an (rewrite_query_candidates) — moi phuong an la 1 dong danh so.
# So luong KHONG co dinh — LLM tu quyet dinh can bao nhieu phuong an tuy do mo ho/ngu canh cua
# query (co the chi 1 neu query da ro rang), toi da max_n, thay vi ep du so dong bang paraphrase
# thua. Van chi 1 lan goi LLM (khong goi rieng cho tung phuong an) de do ton thoi gian/chi phi.
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
    Dich va toi uu query cho CLIP search.

    Args:
        query:    Query goc (tieng Viet hoac Anh).
        feedback: Feedback tu lan search truoc (de cai thien, dung cho vong lap thu 2).
        question: Cau hoi Q&A cu the neu co (dung cho pipeline_qa.py) — giup rewrite giu lai dung
                  vat the/canh can nhin thay de tra loi, thay vi vo tinh bo qua no khi query mo ta
                  nhieu canh noi tiep nhau.

    Returns:
        Query tieng Anh da toi uu.
    """
    prompt = REWRITE_INTRO.format(n_desc="ONE") + _SINGLE_SUFFIX.format(query=query)
    prompt += _build_extra_context(question, feedback)

    result = call_llm(prompt, model="text", temperature=0.2, max_tokens=60)
    # Clean up: bo dau ngoac kep, xuong dong thua
    result = result.strip().strip('"').strip("'").split("\n")[0].strip()
    return result


def rewrite_query_candidates(
    query: str,
    max_n: int = 3,
    feedback: str | None = None,
    question: str | None = None,
) -> list[str]:
    """
    Sinh TOI DA max_n phuong an rewrite KHAC NHAU cho query — so luong thuc te do LLM tu quyet dinh
    tuy theo query co nhieu cach hieu/nhieu vat the dang chu y hay khong (query ro rang -> co the
    chi 1 phuong an), de nguoi dung chon 1 hoac tu viet lai trong UI (xem scripts/app.py) thay vi he
    thong tu dong dung 1 cau rewrite roi search luon.

    Args:
        query:    Query goc (tieng Viet hoac Anh).
        max_n:    So phuong an toi da (mac dinh 3) — LLM co the tra ve it hon neu khong can thiet.
        feedback: Xem rewrite_query().
        question: Xem rewrite_query().

    Returns:
        list[str] do dai trong [1, max_n] — neu LLM loi hoac khong tra ve dong nao parse duoc,
        fallback ve 1 phan tu la ket qua cua rewrite_query().
    """
    prompt = REWRITE_INTRO.format(n_desc=f"1 to {max_n} DIFFERENT") + _CANDIDATES_SUFFIX.format(max_n=max_n, query=query)
    prompt += _build_extra_context(question, feedback)

    try:
        result = call_llm(prompt, model="text", temperature=0.4, max_tokens=200)
        candidates = _parse_candidates(result)
    except Exception as e:
        print(f"[rewrite] rewrite_query_candidates loi ({type(e).__name__}: {e}), fallback ve 1 cau")
        candidates = []

    if not candidates:
        # Fallback: LLM khong tra ve dong nao parse duoc (hoac loi) -> dung lai rewrite 1 cau.
        candidates = [rewrite_query(query, feedback=feedback, question=question)]

    return candidates[:max_n]


def _build_extra_context(question: str | None, feedback: str | None) -> str:
    """Doan prompt bo sung dung chung cho ca rewrite_query va rewrite_query_candidates."""
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
    """Tach output nhieu dong dang '1. ...' / '2) ...' thanh list string sach (bo so thu tu,
    ngoac kep thua). Bo qua dong khong khop pattern thay vi crash — LLM doi khi chen dong trong
    hoac ghi chu ngoai y muon."""
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
        "Mot nguoi dang phat bieu tai cuoc hop bao ngoai troi, phia sau co nhieu cay xanh",
        "Tre em dang choi bong da tren san co xanh",
        "A red sports car driving on a highway at night",
        "Trong video ve le trao giai am nhac, nguoi phu nu mac vay do dang cam ly mau gi?",
    ]
    print("[rewrite] Testing query rewriter (1 cau)...\n")
    for q in test_queries:
        en = rewrite_query(q)
        print(f"  VI: {q[:60]}...")
        print(f"  EN: {en}")
        print()

    print("[rewrite] Testing query rewriter (nhieu phuong an)...\n")
    for q in test_queries:
        cands = rewrite_query_candidates(q, max_n=3)
        print(f"  VI: {q[:60]}...")
        for i, c in enumerate(cands, 1):
            print(f"    {i}. {c}")
        print()
