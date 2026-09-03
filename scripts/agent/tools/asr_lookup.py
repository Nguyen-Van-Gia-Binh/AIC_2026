"""
asr_lookup.py — Đọc ASR transcript (PhoWhisper) của BTC/tự trích xuất.

Không cần gọi API. Trả về đoạn transcript trong 1 khoảng thời gian quanh một pts_time,
dùng để bổ sung ngữ cảnh cho LLM khi trả lời Q&A / cross-check TRAKE.

Data path: data/extracted/ASR_json_PhoWhisper_base/{video_id}.json
  JSON format: {"video_id": str, "segments": [{"start": float, "end": float, "text": str}, ...]}
  (segments sắp xếp tăng dần theo start, KHÔNG đảm bảo liên tục 100%)

Lưu ý chất lượng: PhoWhisper có thể phiên âm sai/thiếu dấu câu — coi đây là HINT, không phải
sự thật tuyệt đối (giống cách OCR_HINT_TEMPLATE trong qa_prompts.py được dùng).
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
    Trả về transcript trong khoảng [pts_time - window, pts_time + window].

    Args:
        video_id: Vi du "L21_V001"
        pts_time: Thời điểm của frame (giây), lấy từ hit["pts_time"] (xem index_store.py)
        window:   Biên độ (giây) quanh pts_time để gom segment liên quan — mặc định 7.5s,
                  phòng trường hợp lời nói liên quan bị lệch nhịp so với hình ảnh.

    Returns:
        str: Text các segment giao với khoảng thời gian, nối theo thứ tự thời gian
             (cách nhau 1 khoảng trắng). Rỗng nếu không có file JSON hoặc không segment nào giao.
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
    Lấy transcript cho nhiều hit cùng lúc (dùng sau khi retrieve).

    Args:
        hits: list[dict] từ fast_retrieve(), mỗi item cần có 'video_id' và 'pts_time'

    Returns:
        dict: {hit_index: str} — transcript theo thứ tự hit
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

# Bo test: tests/unit/test_asr_lookup.py
