import sys
sys.path.insert(0, "scripts")

print("=== Test 1: ocr_lookup (no API needed) ===")
from agent.tools.ocr_lookup import get_objects, objects_contain_keywords
objs = get_objects("L21_V001", 1)
print(f"  L21_V001/001: {len(objs)} objects: {objs[:8]}")
objs2 = get_objects("L23_V001", 1)
print(f"  L23_V001/001: {len(objs2)} objects: {objs2[:8]}")
print(f"  Contains person/man: {objects_contain_keywords(objs, ['person', 'man', 'woman'])}")
print()

print("=== Test 2: config.py (Gemini API) ===")
from agent.config import call_llm
resp = call_llm("Say only: OK_AIC2026", model="text", max_tokens=10)
print(f"  Gemini response: {resp!r}")
print()

print("=== Test 3: rewrite.py ===")
from agent.tools.rewrite import rewrite_query
vi_query = "Mot nguoi dang di xe dap tren duong nui, troi xanh"
en_query = rewrite_query(vi_query)
print(f"  VI: {vi_query}")
print(f"  EN: {en_query}")
print()

print("ALL BASIC TESTS PASSED!")
