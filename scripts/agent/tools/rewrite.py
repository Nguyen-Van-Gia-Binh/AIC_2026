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

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from agent.config import call_llm  # noqa: E402

REWRITE_PROMPT = """\
You are a visual search query optimizer for a video retrieval system using CLIP (image-text matching).

Task: Translate and rewrite the following query into a concise English description optimized for CLIP image search.

Rules:
- Output ONLY the rewritten query (no explanations, no quotes)
- Keep it concise (max 35 words)
- FIRST identify and preserve the most distinctive visual anchor object or landmark
    (for example: helicopter, wind turbine, red octopus toy, sand sculpture)
- Put that anchor object near the START of the rewritten query; never omit it even
    when the query also describes people or an action
- Then include the main action and the important people/clothing, followed by location
    or background context if useful
- Prefer concrete visual nouns and verbs; remove vague filler and factual details
    that cannot be seen in a frame
- Remove temporal/sequential words (first, then, after) — this rewrite is for
    single-frame retrieval, including each individual TRAKE event
- If already in English, just clean and optimize it while preserving the anchor object

Preferred format: "[distinctive anchor object] + [main action] + [people/clothing] + [visible setting]"

Query: {query}

Rewritten query:"""


def rewrite_query(query: str, feedback: str | None = None) -> str:
    """
    Dich va toi uu query cho CLIP search.

    Args:
        query:    Query goc (tieng Viet hoac Anh).
        feedback: Feedback tu lan search truoc (de cai thien, dung cho vong lap thu 2).

    Returns:
        Query tieng Anh da toi uu.
    """
    prompt = REWRITE_PROMPT.format(query=query)
    if feedback:
        prompt += f"\n\nPrevious search failed. Feedback: {feedback}\nRewrite with different keywords:"

    result = call_llm(prompt, model="text", temperature=0.2, max_tokens=60)
    # Clean up: bo dau ngoac kep, xuong dong thua
    result = result.strip().strip('"').strip("'").split("\n")[0].strip()
    return result


# ─── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_queries = [
        "Mot nguoi dang phat bieu tai cuoc hop bao ngoai troi, phia sau co nhieu cay xanh",
        "Tre em dang choi bong da tren san co xanh",
        "A red sports car driving on a highway at night",
        "Trong video ve le trao giai am nhac, nguoi phu nu mac vay do dang cam ly mau gi?",
    ]
    print("[rewrite] Testing query rewriter...\n")
    for q in test_queries:
        en = rewrite_query(q)
        print(f"  VI: {q[:60]}...")
        print(f"  EN: {en}")
        print()
