"""
test_phase5_ocr.py — Benchmark truoc/sau cho OCR on-demand (Phase 5, answer_qa.py Tier 2).

Dung 3 cau hoi tu tao, moi cau tro thang vao 1 frame GT co san trong eval_ground_truth.json ma mo ta
ro chu/so nhin thay duoc (e-kis-ai-007/016/013) — KHONG goi fast_retrieve() de tranh phu thuoc chat
luong retrieval, hit duy nhat duoc dung la dung video_id/n cua GT (giong tinh than Phase 4 Task2 fix
round 1: khu nhieu benchmark bang cach co dinh dau vao, chi do dung 1 bien so — o day la co/khong OCR
hint, khong phai retrieval).

Chay 2 lan tren cung 1 bo cau: pass "before" monkeypatch read_text_from_hits() thanh ham tra ve {}
(mo phong "chua co Phase 5"), pass "after" dung ham that. In answer/confidence/method canh nhau —
KHONG cham diem dung/sai (khong co gt_answer cho 3 cau nay, chi la cau tu tao de kiem tra OCR co doc
duoc chu that hay khong) — nguoi dung tu doc va danh gia.

Usage:
    .venv\\Scripts\\python.exe test_eval\\Test\\test_phase5_ocr.py
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_ROOT = Path(__file__).resolve().parents[2]  # test_eval/Test/ -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import scripts.agent.tools.answer_qa as _answer_qa_module
from scripts.agent.tools.answer_qa import answer_from_hits

_KEYFRAMES_DIR = _ROOT / "data" / "extracted" / "keyframes"


def _hit(video_id: str, n: int) -> dict:
    batch = video_id.split("_")[0]
    jpg_path = _KEYFRAMES_DIR / batch / video_id / f"{n:03d}.jpg"
    return {
        "video_id": video_id, "n": n, "frame_idx": n - 1, "frame_id": n,
        "pts_time": 0.0, "score": 1.0,
        "jpg_path": str(jpg_path) if jpg_path.exists() else None,
    }


# 3 cau hoi tu tao, moi cau 1 hit duy nhat tro dung frame GT da biet ro noi dung chu/so (n tra tu
# data/extracted/map-keyframes/{video_id}.csv, xem chi tiet trong docs/superpowers/plans/2026-08-24-phase5-ocr-on-demand.md).
#
# Fix round 1: 3 cau hoi ban dau ("What years are written...", "What Vietnamese phrase is written...")
# KHONG khop _TEXT_READING_HINTS trong answer_qa.py (regex chi bat "number"/"how many"/"what number"
# ben tieng Anh, cac cum tieng Viet "ghi gi"/"chu gi"/... ben tieng Viet — khong co trigger cho kieu
# cau "what does it say"/"what phrase is written"), nen skip_objects_tier=False va OCR KHONG duoc goi
# o ca 2 pass cho 2 cau do — da xac minh lai tung cau bang _TEXT_READING_HINTS.search(question) truoc
# khi sua, ca 3 cau duoi day deu tra True.
CASES = [
    {
        "question": "What number range is shown on the memorial poster?",
        "hits": [_hit("L22_V001", 120)],  # GT text: "DIANA 1961 1997"
    },
    {
        "question": "What are the registration numbers painted on the two ferries?",
        "hits": [_hit("L28_V003", 190)],  # GT text: "AG-09399" / "AG-12627"
    },
    {
        "question": "Bảng chữ trong miếu ghi gì?",
        "hits": [_hit("L27_V001", 110)],  # GT text: "CHÚA XỨ THÁNH MẪU"
    },
]


def _run_pass(label: str) -> list[dict]:
    results = []
    for case in CASES:
        out = answer_from_hits(case["question"], case["hits"], top_n=1)
        print(f"  [{label}] Q: {case['question']!r}")
        print(f"        answer={out['answer']!r}  confidence={out['confidence']:.2f}  method={out['method']}")
        results.append(out)
    return results


def main() -> None:
    print(f"[test_phase5] {len(CASES)} cau hoi tu tao, moi cau 1 frame GT co san (xem comment CASES).")

    # answer_from_hits() goi read_text_from_hits(...) nhu 1 ten global tra trong namespace cua module
    # answer_qa — patch thang _answer_qa_module.read_text_from_hits la du, khong can reload module
    # (giong ky thuat monkeypatch rewrite_query cua test_phase4_trake.py, khong dung lai ham da import).
    _original_read_text_from_hits = _answer_qa_module.read_text_from_hits

    print("\n[test_phase5] === Pass 1: KHONG co OCR hint (mo phong truoc Phase 5) ===")
    _answer_qa_module.read_text_from_hits = lambda hits, top_n=3: {}
    before = _run_pass("before")

    print("\n[test_phase5] === Pass 2: CO OCR hint (Phase 5 that) ===")
    _answer_qa_module.read_text_from_hits = _original_read_text_from_hits
    after = _run_pass("after")

    print("\n[test_phase5] === Ket qua tho, chua danh gia — xem lai bang mat ===")
    for case, b, a in zip(CASES, before, after):
        print(f"  Q: {case['question']!r}")
        print(f"    before: {b['answer']!r}")
        print(f"    after:  {a['answer']!r}")


if __name__ == "__main__":
    main()
