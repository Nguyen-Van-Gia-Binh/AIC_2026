"""
test_smoke_tools.py — Smoke test cho cac tool nen tang (goi truc tiep, khong qua pipeline).

Gop tu test_day2_basic.py cu + phan retrieve cua test_day1.py. Muc dich: xac nhan moi tool doc
duoc du lieu / goi duoc API sau khi setup moi hoac doi dependency — KHONG cham diem dung/sai.

Bao gom:
  1. retrieve.fast_retrieve      — can data/extracted/ (index + model), KHONG can API key
  2. ocr_lookup.get_objects      — can data/extracted/objects-*, KHONG can API key
  3. config.call_llm             — can OPENROUTER_API_KEY
  4. rewrite.rewrite_query       — can OPENROUTER_API_KEY

Usage:
    .venv\\Scripts\\python.exe tests\\Test\\test_smoke_tools.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Chi dat REPO ROOT len sys.path — khong bao gio dat scripts/ (dat scripts/ khien Python nap cung
# mot module duoi hai ten `agent.tools.retrieve` va `scripts.agent.tools.retrieve`, tuc la nap
# index + SigLIP HAI BAN). Xem docs/decisions-log.md.
_ROOT = Path(__file__).resolve().parents[2]   # tests/e2e/ -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> None:
    print("=== Test 1: retrieve.fast_retrieve (khong can API) ===")
    from scripts.agent.tools.retrieve import fast_retrieve
    hits = fast_retrieve("a cyclist racing on a road", top_k=5)
    for i, h in enumerate(hits, 1):
        img = " [img]" if h["jpg_path"] else ""
        print(f"  #{i}  {h['video_id']}  frame_id={h['frame_id']}  t={h['pts_time']:.1f}s  "
              f"score={h['score']:.4f}{img}")
    print()

    print("=== Test 2: ocr_lookup.get_objects (khong can API) ===")
    from scripts.agent.tools.ocr_lookup import get_objects, objects_contain_keywords
    objs = get_objects("L21_V001", 1)
    print(f"  L21_V001/001: {len(objs)} objects: {objs[:8]}")
    objs2 = get_objects("L23_V001", 1)
    print(f"  L23_V001/001: {len(objs2)} objects: {objs2[:8]}")
    print(f"  Contains person/man: {objects_contain_keywords(objs, ['person', 'man', 'woman'])}")
    print()

    print("=== Test 3: config.call_llm (can OPENROUTER_API_KEY) ===")
    from scripts.agent.config import call_llm
    resp = call_llm("Say only: OK_AIC2026", model="text", max_tokens=10)
    print(f"  LLM response: {resp!r}")
    print()

    print("=== Test 4: rewrite.rewrite_query (can OPENROUTER_API_KEY) ===")
    from scripts.agent.tools.rewrite import rewrite_query
    vi_query = "Mot nguoi dang di xe dap tren duong nui, troi xanh"
    en_query = rewrite_query(vi_query)
    print(f"  VI: {vi_query}")
    print(f"  EN: {en_query}")
    print()

    print("ALL TOOL SMOKE TESTS RAN (tu doc ket qua o tren de danh gia).")


if __name__ == "__main__":
    main()
