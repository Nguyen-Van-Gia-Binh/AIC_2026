"""
ocr_read.py — OCR that (PaddleOCR) chay on-demand tren cac keyframe candidate can doc chu/so.

Chi duoc goi khi cau hoi Q&A thuc su can doc chu/so tren man hinh (bien so, gia tien, so ao...) —
xem _needs_text_reading() trong answer_qa.py, ham nay tai su dung lam dieu kien kich hoat OCR luon.
KHONG precompute OCR cho toan bo 177K keyframe — chi nhan hits da retrieve san, gioi han cung top_n.

Ket qua OCR la GOI Y cho LLM Vision (chen vao prompt), khong tu dong tro thanh cau tra loi —
answer_qa.py van chay _crosscheck_answer() nhu cu, khong bo qua co che chong ao giac.

PaddleOCR nap model lan dau se tu tai model PP-OCRv4 (vai chuc MB, can mang lan dau chay). Neu
import/khoi tao/OCR that bai vi bat ky ly do gi, module nay KHONG crash pipeline — tra ve rong va in
canh bao, de answer_qa.py chay tiep binh thuong khong co goi y OCR.

Usage:
    from scripts.agent.tools.ocr_read import read_text_from_hits, format_ocr_hint
    ocr_results = read_text_from_hits(hits, top_n=3)   # {hit_index: [text_line, ...]}
    hint_text   = format_ocr_hint(ocr_results)          # "" neu khong doc duoc gi
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_ENGINE = None
_ENGINE_LOAD_FAILED = False


def _get_engine():
    """Singleton PaddleOCR — nap 1 lan/process. Tra ve None neu load that bai (khong retry lai trong
    cung 1 process, tranh lap lai loi mang/thieu dependency nhieu lan)."""
    global _ENGINE, _ENGINE_LOAD_FAILED
    if _ENGINE is not None or _ENGINE_LOAD_FAILED:
        return _ENGINE
    try:
        import torch  # noqa: F401 — phai import truoc paddleocr: tren Windows, thu tu nguoc lai co the
                       # gay loi nap DLL "shm.dll" do opencv (dependency cua paddleocr qua albumentations)
                       # nap runtime DLL truoc va che khuat DLL torch can — xac nhan bang test truc tiep.
        from paddleocr import PaddleOCR
        print("[ocr_read] Dang nap PaddleOCR (lan dau co the tu tai model PP-OCRv4)...")
        _ENGINE = PaddleOCR(use_angle_cls=True, lang="vi", ocr_version="PP-OCRv4", show_log=False)
        print("[ocr_read] PaddleOCR san sang.")
    except Exception as error:
        print(f"[ocr_read] CANH BAO: khong nap duoc PaddleOCR ({type(error).__name__}: {error}) "
              f"— bo qua OCR cho phien nay, answer_qa.py se chay tiep khong co goi y OCR.")
        _ENGINE_LOAD_FAILED = True
        _ENGINE = None
    return _ENGINE


def _ocr_single_image(image_path: str) -> list[str]:
    """OCR 1 anh, tra ve list dong chu doc duoc (co the rong neu anh khong co chu hoac OCR loi)."""
    engine = _get_engine()
    if engine is None:
        return []
    try:
        result = engine.ocr(image_path, cls=True)
    except Exception as error:
        print(f"[ocr_read] CANH BAO: OCR that bai tren {image_path} ({type(error).__name__}: {error})")
        return []

    lines: list[str] = []
    for page in (result or []):
        for entry in (page or []):
            # entry dang [box, (text, confidence)] theo API PaddleOCR 2.7.x
            if len(entry) > 1 and entry[1]:
                text = entry[1][0]
                if text:
                    lines.append(text)
    return lines


def read_text_from_hits(hits: list[dict], top_n: int = 3) -> dict[int, list[str]]:
    """
    Chay OCR tren toi da top_n candidate hit dau tien co jpg_path ton tai tren dia.

    Args:
        hits:  list[dict] tu fast_retrieve()/fast_retrieve_for_video(), can co truong 'jpg_path'.
        top_n: So anh toi da can OCR (mac dinh 3 — gioi han chi phi/thoi gian on-demand).

    Returns:
        dict[int, list[str]]: {hit_index: [text_line, ...]}. Chi hit doc duoc >=1 dong chu moi co
        mat trong dict — dung de format_ocr_hint() phan biet duoc "khong OCR duoc gi" (dict rong).
    """
    result: dict[int, list[str]] = {}
    for i, hit in enumerate(hits[:top_n]):
        jpg_path = hit.get("jpg_path")
        if jpg_path and Path(jpg_path).exists():
            lines = _ocr_single_image(jpg_path)
            if lines:
                result[i] = lines
    return result


def format_ocr_hint(ocr_results: dict[int, list[str]]) -> str:
    """Dinh dang ket qua OCR thanh doan text ngan de chen vao prompt Vision. Rong neu khong doc
    duoc gi tu bat ky candidate nao."""
    if not ocr_results:
        return ""
    lines = []
    for hit_index in sorted(ocr_results):
        texts = ", ".join(f'"{t}"' for t in ocr_results[hit_index])
        lines.append(f"  - Candidate frame #{hit_index + 1}: {texts}")
    return "\n".join(lines)


# CLI test
if __name__ == "__main__":
    _ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

    def _fake_hit(jpg_rel_path: str) -> dict:
        return {"video_id": "", "n": 0, "frame_idx": 0, "frame_id": 1, "pts_time": 0.0,
                 "score": 1.0, "jpg_path": str(_ROOT_DIR / jpg_rel_path)}

    print("[ocr_read] === Self-test 1: hits rong / jpg_path None khong crash ===")
    assert read_text_from_hits([]) == {}
    assert read_text_from_hits([{"jpg_path": None}]) == {}
    assert read_text_from_hits([{"jpg_path": "khong_ton_tai.jpg"}]) == {}
    print("[ocr_read] Self-test 1: PASS")

    print("\n[ocr_read] === Self-test 2: OCR anh that co chu (kiem tra bang mat) ===")
    known_hits = [
        _fake_hit("data/extracted/keyframes/L22/L22_V001/120.jpg"),   # GT: "DIANA 1961 1997"
        _fake_hit("data/extracted/keyframes/L28/L28_V003/190.jpg"),   # GT: "AG-09399" / "AG-12627"
        _fake_hit("data/extracted/keyframes/L27/L27_V001/110.jpg"),   # GT: "CHÚA XỨ THÁNH MẪU"
    ]
    ocr_out = read_text_from_hits(known_hits, top_n=3)
    for i, hit in enumerate(known_hits):
        lines = ocr_out.get(i, [])
        print(f"  candidate #{i+1} ({Path(hit['jpg_path']).name}): {lines}")
    print(f"\n  format_ocr_hint():\n{format_ocr_hint(ocr_out)}")
    print("\n[ocr_read] Self-test 2 xong — tu kiem tra bang mat: co doc duoc it nhat 1 phan chu/so "
          "gan dung so voi GT ghi trong comment o tren khong? (khong hard-assert vi OCR khong dam bao "
          "chinh xac 100%).")
