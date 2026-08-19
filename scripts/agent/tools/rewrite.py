"""
rewrite.py — Dich query tieng Viet sang tieng Anh + lam ro mo ta visual.

CLIP-ViT-B-32 hieu tieng Anh tot hon nhieu. Mo ta visual-centric (mau sac,
vat the, hanh dong, boi canh) se cho ket qua CLIP search tot hon.

Usage:
    from scripts.agent.tools.rewrite import rewrite_query
    en = rewrite_query("Mot nguoi dang di xe dap tren duong nui")
    # -> "a person cycling on a mountain road, outdoor scenery"
"""
from __future__ import annotations

import sys
from pathlib import Path

_AGENT_DIR = Path(__file__).resolve().parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

from config import call_llm  # noqa: E402

REWRITE_PROMPT = """\
You are a visual search query optimizer for a video retrieval system using CLIP (image-text matching).

Task: Translate and rewrite the following query into a concise English description optimized for CLIP image search.

Rules:
- Output ONLY the rewritten query (no explanations, no quotes)
- Keep it SHORT (max 20 words)
- Focus on VISUAL elements: objects, colors, actions, scene/location, clothing
- Remove temporal/sequential words (first, then, after) — CLIP searches single frames
- If already in English, just clean and optimize it

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
