import sys
sys.path.insert(0, "scripts")
from agent.tools.retrieve import fast_retrieve
from agent.pipeline_kis import run_kis
from submit.build_submission import build_kis_csv, build_zip_submission
from submit.validate_submission import validate_file
from pathlib import Path

# --- Test 1: retrieve ---
hits = fast_retrieve("a cyclist racing on a road", top_k=5)
print("=== fast_retrieve ===")
for i, h in enumerate(hits, 1):
    img = " [img]" if h["jpg_path"] else ""
    print(f"  #{i}  {h['video_id']}  frame_id={h['frame_id']}  t={h['pts_time']:.1f}s  score={h['score']:.4f}{img}")

# --- Test 2: pipeline KIS ---
print("\n=== pipeline_kis ===")
r = run_kis("children playing soccer on a green field", top_k=5)
for h in r:
    print(f"  {h['video_id']}, {h['frame_id']}  (score={h['score']:.4f})")

# --- Test 3: build CSV ---
print("\n=== build_submission ===")
out_dir = Path("submissions")
csv1 = build_kis_csv("test_q001", hits, output_dir=out_dir)
csv2 = build_kis_csv("test_q002", r, output_dir=out_dir)

# --- Test 4: build ZIP ---
zip_path = build_zip_submission([csv1, csv2], tag="day1_test")
print(f"ZIP: {zip_path.name}")

# --- Test 5: validate ---
print("\n=== validate_submission ===")
ok = validate_file(zip_path)
print(f"Validation passed: {ok}")
