import sys
sys.path.insert(0, "scripts")

print("=" * 60)
print("TEST DAY 2 - Full Pipeline")
print("=" * 60)

# === Test pipeline_qa ===
print("\n[1] pipeline_qa - Q&A end-to-end")
from agent.pipeline_qa import run_qa

out = run_qa(
    query_text="Mot nguoi dang phat bieu tai cuoc hop bao ngoai troi",
    question="What is happening in this scene?",
    top_k=20,
)
print(f"\n  Answer:     {out['answer']!r}")
print(f"  Confidence: {out['confidence']:.2f}")
print(f"  N_loops:    {out['n_loops']}")
print(f"  Top-3 submission rows:")
for r in out["results"][:3]:
    print(f"    {r['video_id']}, {r['frame_id']}, {r['answer']!r}")

# === Test build_submission Q&A ===
print("\n[2] build_submission - Q&A CSV")
from pathlib import Path
sys.path.insert(0, "scripts")
from submit.build_submission import build_qa_csv, build_zip_submission
from submit.validate_submission import validate_file

csv_qa = build_qa_csv("test_qa_001", out["results"][:5], output_dir=Path("submissions"))
print(f"  CSV: {csv_qa.name}")

# Validate
ok = validate_file(csv_qa)
print(f"  Valid: {ok}")

# === Test pipeline_trake ===
print("\n[3] pipeline_trake - TRAKE end-to-end")
from agent.pipeline_trake import run_trake

out_t = run_trake(
    query_text="A sports competition with athletes performing jumping events",
    events=[
        "athlete running during approach",
        "athlete jumping over the bar",
        "athlete landing on the mat",
    ],
    top_k_video=3,
    top_k_frame=5,
)
print(f"\n  N events:   {out_t['n_events']}")
print(f"  Best video: {out_t['best'].get('video_id')}")
print(f"  Frame IDs:  {out_t['best'].get('frame_ids')}")

# Build TRAKE submission
from submit.build_submission import build_trake_csv
csv_trake = build_trake_csv("test_trake_001", out_t["results"][:5], output_dir=Path("submissions"))
ok_t = validate_file(csv_trake)
print(f"  TRAKE CSV valid: {ok_t}")

# === Final ZIP ===
print("\n[4] Final ZIP")
zip_path = build_zip_submission([csv_qa, csv_trake], tag="day2_test")
ok_z = validate_file(zip_path)
print(f"  ZIP valid: {ok_z}")

print("\n" + "=" * 60)
print("ALL DAY 2 TESTS PASSED!" if ok and ok_t and ok_z else "SOME TESTS FAILED")
print("=" * 60)
