"""
caption_lookup.py — Doc caption Vintern-1B da tinh san (batch job 7, merge_captions.py).

Khong goi API. Tra ve mo ta canh (1 cau tieng Viet) cho 1 keyframe, dung de bo sung nguon kiem tra
cho Q&A (answer_qa.py) va TRAKE crosscheck (pipeline_trake.py) — caption mo ta HANH DONG/BOI CANH
canh, khac voi objects (ocr_lookup.py, chi liet ke TEN VAT THE chung chung) va OCR (ocr_read.py, chi
doc CHU/SO hien thi tren man hinh) — 3 nguon nay bo sung cho nhau, khong nguon nao thay the nguon nao.

Data path: data/extracted/caption_vintern1b/{video_id}.jsonl
  Moi dong: {"n": int, "caption": str} — "n": so thu tu keyframe (cot "n" trong map-keyframes CSV).

Do phu offline (2026-08-28): 873/873 video da co caption (merge_captions.py da chay du) — day du hon
OCR offline (652/873 luc nay), nen la nguon co the tin cay quanh nam cho ca 873 video.

Neu file .jsonl chua ton tai (video chua duoc gan vao manifest loc caption — build_caption_manifest.py
chi loc tap con keyframe theo semantic similarity, khong phai TOAN BO nhu OCR) hoac khong co dong nao
khop "n", tra ve chuoi rong — KHONG raise loi, de pipeline goi tiep tuc chay binh thuong khong co
caption cho keyframe do (fail-soft, giong ocr_lookup.get_objects).

Usage:
    from scripts.agent.tools.caption_lookup import get_caption
    caption = get_caption("L21_V001", 45)   # "" neu khong co
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CAPTION_DIR = _ROOT / "data" / "extracted" / "caption_vintern1b"

# Cache {video_id: {n: caption} | None} — None nghia la video CHUA co file .jsonl (chua duoc chon
# vao manifest loc caption, hoac batch job chua chay toi) — tranh doc lai dia moi lan goi get_caption
# cho cung 1 video (Q&A/TRAKE thuong goi lien tiep nhieu "n" khac nhau trong CUNG 1 video).
_CACHE: dict[str, Optional[dict[int, str]]] = {}


def _load_caption_map(video_id: str) -> Optional[dict[int, str]]:
    if video_id in _CACHE:
        return _CACHE[video_id]
    path = CAPTION_DIR / f"{video_id}.jsonl"
    if not path.exists():
        _CACHE[video_id] = None
        return None
    result: dict[int, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    result[int(rec["n"])] = str(rec.get("caption", "")).strip()
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
    except OSError:
        _CACHE[video_id] = None
        return None
    _CACHE[video_id] = result
    return result


def get_caption(video_id: str, keyframe_n: int) -> str:
    """
    Tra ve caption (1 cau tieng Viet) cho 1 keyframe, hoac "" neu khong co.

    Args:
        video_id:    Vi du "L21_V001"
        keyframe_n:  So thu tu keyframe (cot "n" trong map-keyframes, bat dau tu 1)

    Returns:
        str: caption hoac "" neu video chua co file / khong co dong khop "n".
    """
    caption_map = _load_caption_map(video_id)
    if caption_map is None:
        return ""
    return caption_map.get(keyframe_n, "")


# CLI test
if __name__ == "__main__":
    print("[caption_lookup] === Self-test 1: video khong ton tai -> '' khong crash ===")
    assert get_caption("__video_khong_ton_tai__", 1) == ""
    print("[caption_lookup] Self-test 1: PASS")

    print("\n[caption_lookup] === Self-test 2: doc caption that (kiem tra bang mat) ===")
    sample_files = sorted(CAPTION_DIR.glob("*.jsonl"))[:3]
    for p in sample_files:
        vid = p.stem
        first_line = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
        n = first_line["n"]
        caption = get_caption(vid, n)
        print(f"  {vid} n={n}: {caption!r}")
    print("[caption_lookup] Self-test 2 xong — tu kiem tra bang mat: caption co hop ly khong.")
