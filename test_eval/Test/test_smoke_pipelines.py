"""
test_smoke_pipelines.py — Smoke test end-to-end cho ca 3 pipeline + duong xuat submission.

Gop tu test_day1.py (nhanh KIS + build/validate) + test_day2_full.py (QA + TRAKE). Muc dich: xac
nhan pipeline_kis/qa/trake chay tron, build_submission ghi CSV/ZIP dung dinh dang, validate PASS —
KHONG cham diem dung/sai (viec do la cua test_eval/Test/score_pipelines.py + test_phase*.py).

Can: data/extracted/ (index + model) va OPENROUTER_API_KEY (qa/trake goi LLM; kis khong).
CSV/ZIP test ghi vao submissions/ voi tien to "smoke_".

Usage:
    .venv\\Scripts\\python.exe test_eval\\Test\\test_smoke_pipelines.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"  # test_eval/Test/ -> repo root -> scripts
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

_OUT_DIR = Path(__file__).resolve().parents[2] / "submissions"


def main() -> None:
    from submit.build_submission import (
        build_kis_csv, build_qa_csv, build_trake_csv, build_zip_submission,
    )
    from submit.validate_submission import validate_file

    csvs = []

    # ─── [1] KIS ──────────────────────────────────────────────────────────────
    print("=" * 60)
    print("[1] pipeline_kis - KIS end-to-end")
    from agent.pipeline_kis import run_kis
    kis_rows = run_kis("children playing soccer on a green field", top_k=5)
    for h in kis_rows:
        print(f"    {h['video_id']}, {h['frame_id']}  (score={h['score']:.4f})")
    csv_kis = build_kis_csv("smoke-001-kis", kis_rows, output_dir=_OUT_DIR)
    print(f"  CSV: {csv_kis.name}  valid={validate_file(csv_kis)}")
    csvs.append(csv_kis)

    # ─── [2] Q&A ──────────────────────────────────────────────────────────────
    print("\n[2] pipeline_qa - Q&A end-to-end")
    from agent.pipeline_qa import run_qa
    out_qa = run_qa(
        query_text="Mot nguoi dang phat bieu tai cuoc hop bao ngoai troi",
        question="What is happening in this scene?",
        top_k=20,
    )
    print(f"  Answer: {out_qa['answer']!r}  confidence={out_qa['confidence']:.2f}  "
          f"n_loops={out_qa['n_loops']}")
    for r in out_qa["results"][:3]:
        print(f"    {r['video_id']}, {r['frame_id']}, {r['answer']!r}")
    csv_qa = build_qa_csv("smoke-001-qa", out_qa["results"][:5], output_dir=_OUT_DIR)
    print(f"  CSV: {csv_qa.name}  valid={validate_file(csv_qa)}")
    csvs.append(csv_qa)

    # ─── [3] TRAKE ────────────────────────────────────────────────────────────
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
    print(f"  N events: {out_t['n_events']}  best video: {out_t['best'].get('video_id')}  "
          f"frame_ids: {out_t['best'].get('frame_ids')}")
    csv_trake = build_trake_csv("smoke-001-trake", out_t["results"][:5], output_dir=_OUT_DIR)
    print(f"  CSV: {csv_trake.name}  valid={validate_file(csv_trake)}")
    csvs.append(csv_trake)

    # ─── [4] ZIP ──────────────────────────────────────────────────────────────
    print("\n[4] build_zip_submission + validate")
    zip_path = build_zip_submission(csvs, tag="smoke_test")
    ok_zip = validate_file(zip_path)
    print(f"  ZIP: {zip_path.name}  valid={ok_zip}")

    print("\n" + "=" * 60)
    print("SMOKE PIPELINES: DONE" if ok_zip else "SMOKE PIPELINES: ZIP VALIDATION FAILED")
    print("=" * 60)


if __name__ == "__main__":
    main()
