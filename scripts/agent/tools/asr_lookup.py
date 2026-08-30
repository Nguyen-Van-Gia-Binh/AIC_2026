"""
asr_lookup.py — Doc ASR transcript (PhoWhisper) cua BTC/tu trich xuat.

Khong can goi API. Tra ve doan transcript trong 1 khoang thoi gian quanh mot pts_time,
dung de bo sung ngu canh cho LLM khi tra loi Q&A / cross-check TRAKE.

Data path: data/extracted/ASR_json_PhoWhisper_base/{video_id}.json
  JSON format: {"video_id": str, "segments": [{"start": float, "end": float, "text": str}, ...]}
  (segments sap xep tang dan theo start, KHONG dam bao lien tuc 100%)

Luu y chat luong: PhoWhisper co the phien am sai/thieu dau cau — coi day la HINT, khong phai
su that tuyet doi (giong cach OCR_HINT_TEMPLATE trong answer_qa.py duoc dung).
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
ASR_DIR = _ROOT / "data" / "extracted" / "ASR_json_PhoWhisper_base"

DEFAULT_WINDOW_SECONDS = 7.5


def get_transcript(
    video_id: str,
    pts_time: float,
    window: float = DEFAULT_WINDOW_SECONDS,
) -> str:
    """
    Tra ve transcript trong khoang [pts_time - window, pts_time + window].

    Args:
        video_id: Vi du "L21_V001"
        pts_time: Thoi diem cua frame (giay), lay tu hit["pts_time"] (xem retrieve.py)
        window:   Bien do (giay) quanh pts_time de gom segment lien quan — mac dinh 7.5s,
                  phong truong hop loi noi lien quan bi lech nhip so voi hinh anh.

    Returns:
        str: Text cac segment giao voi khoang thoi gian, noi theo thu tu thoi gian
             (cach nhau 1 khoang trang). Rong neu khong co file JSON hoac khong segment nao giao.
    """
    json_path = ASR_DIR / f"{video_id}.json"
    if not json_path.exists():
        return ""

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    lo, hi = pts_time - window, pts_time + window
    segments = data.get("segments", [])
    matched = [
        seg["text"].strip()
        for seg in segments
        if seg.get("end", 0) >= lo and seg.get("start", 0) <= hi and seg.get("text")
    ]
    return " ".join(matched)


def get_transcript_for_hits(
    hits: list[dict],
    window: float = DEFAULT_WINDOW_SECONDS,
) -> dict[int, str]:
    """
    Lay transcript cho nhieu hit cung luc (dung sau khi retrieve).

    Args:
        hits: list[dict] tu fast_retrieve(), moi item can co 'video_id' va 'pts_time'

    Returns:
        dict: {hit_index: str} — transcript theo thu tu hit
    """
    result = {}
    for i, hit in enumerate(hits):
        vid = hit.get("video_id", "")
        pts = hit.get("pts_time")
        if vid and pts is not None:
            result[i] = get_transcript(vid, float(pts), window)
        else:
            result[i] = ""
    return result


# ─── CLI self-test (repo khong dung pytest — xem CLAUDE.md) ────────────────────
def _run_self_tests() -> None:
    # Test 1: pts_time=20.0, window=7.5 -> khoang [12.5, 27.5] giao voi segment 0 ([0, 15.1]) va
    # segment 1 ([15.1, 32.06]) cua L21_V001 that (da extract vao data/extracted/) -> noi ca 2.
    text = get_transcript("L21_V001", pts_time=20.0, window=7.5)
    assert "chào mừng" in text, f"Phai chua text cua segment 0, duoc: {text!r}"
    assert "sông cửu long" in text, f"Phai chua text cua segment 1, duoc: {text!r}"
    print(f"[asr_lookup] Test overlap 2 segment: OK ({len(text)} ky tu)")

    # Test 2: pts_time nam ngoai moi segment (qua lon) -> rong.
    empty = get_transcript("L21_V001", pts_time=99999.0, window=7.5)
    assert empty == "", f"Ngoai moi segment phai tra rong, duoc: {empty!r}"
    print("[asr_lookup] Test ngoai khoang: OK (rong)")

    # Test 3: video khong co file ASR -> rong, khong crash.
    missing = get_transcript("L99_V999", pts_time=10.0)
    assert missing == "", f"Video khong ton tai phai tra rong, duoc: {missing!r}"
    print("[asr_lookup] Test video khong ton tai: OK (rong)")

    # Test 4: batch helper cho nhieu hit cung luc.
    hits = [
        {"video_id": "L21_V001", "pts_time": 20.0},
        {"video_id": "L21_V001", "pts_time": 99999.0},
    ]
    batch = get_transcript_for_hits(hits, window=7.5)
    assert "chào mừng" in batch[0], f"Hit 0 phai co transcript, duoc: {batch[0]!r}"
    assert batch[1] == "", f"Hit 1 (ngoai khoang) phai rong, duoc: {batch[1]!r}"
    print("[asr_lookup] Test get_transcript_for_hits: OK")

    print("[asr_lookup] Tat ca self-test PASS")

# Bo test: tests/unit/test_asr_lookup.py
