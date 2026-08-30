"""
objects_lookup.py — Đọc Objects JSON của BTC (Faster R-CNN, OpenImages V4), offline.

ĐÂY KHÔNG PHẢI OCR: module chỉ trả về TÊN OBJECT chung chung ("person", "car", "fish"), không
đọc được chữ, số, giá hay biển hiệu trên khung hình. Muốn đọc chữ thật → agent/tools/ocr_read.py.
(Tên cũ `ocr_lookup.py` đã bỏ 2026-08-31 vì gây hiểu nhầm đúng điều trên.)

Không cần gọi API. Trả về danh sách object detect được trong 1 keyframe.
Dùng để cross-check answer Q&A và rerank KIS.

Data path: data/extracted/objects/{video_id}/{n:03d}.json
  n: so thu tu keyframe (cot "n" trong map-keyframes CSV, bat dau tu 1)

JSON format:
  detection_class_entities: list[str]  — ten object (tieng Anh)
  detection_scores:         list[str]  — confidence score (dang string)
  detection_boxes:          list[list] — bounding box [y1,x1,y2,x2] normalized
"""
from __future__ import annotations

import json
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DATA_DIR = _ROOT / "data" / "extracted"
OBJECTS_DIR = (
    _DATA_DIR / "objects"
    if (_DATA_DIR / "objects").is_dir()
    else _DATA_DIR / "objects-aic25-b1" / "objects"
)

DEFAULT_SCORE_THRESHOLD = 0.3


def get_objects(
    video_id: str,
    keyframe_n: int,
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> list[str]:
    """
    Tra ve danh sach object detect duoc trong 1 keyframe.

    Args:
        video_id:        Vi du "L21_V001"
        keyframe_n:      So thu tu keyframe (cot "n" trong map-keyframes, bat dau tu 1)
        score_threshold: Chi giu object co confidence >= nguong nay

    Returns:
        list[str]: Ten cac object (unique, sap xep theo score giam dan).
                   Tra ve [] neu khong co file JSON.
    """
    json_path = OBJECTS_DIR / video_id / f"{keyframe_n:03d}.json"
    if not json_path.exists():
        return []

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    scores   = [float(s) for s in data.get("detection_scores", [])]
    entities = data.get("detection_class_entities", [])

    # Loc theo nguong confidence, giu unique
    seen = set()
    result = []
    for entity, score in zip(entities, scores):
        if score >= score_threshold and entity not in seen:
            seen.add(entity)
            result.append(entity)

    return result


def get_objects_for_hits(
    hits: list[dict],
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> dict[int, list[str]]:
    """
    Lay objects cho nhieu hit cung luc (dung sau khi retrieve).

    Args:
        hits: list[dict] tu fast_retrieve(), moi item can co 'video_id' va 'n'

    Returns:
        dict: {hit_index: list[str]} — objects theo thu tu hit
    """
    result = {}
    for i, hit in enumerate(hits):
        vid = hit.get("video_id", "")
        n   = hit.get("n")  # so thu tu keyframe trong map-keyframes (cot "n")
        if vid and n is not None:
            result[i] = get_objects(vid, int(n), score_threshold)
        else:
            result[i] = []
    return result


def objects_contain_keywords(objects: list[str], keywords: list[str]) -> bool:
    """
    Kiem tra xem danh sach object co chua bat ky keyword nao khong.
    So sanh case-insensitive.
    """
    obj_lower = {o.lower() for o in objects}
    return any(kw.lower() in obj_lower or
               any(kw.lower() in o for o in obj_lower)
               for kw in keywords)


# ─── CLI test ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os, sys
    # Test voi L21_V001, keyframe n=1
    objs = get_objects("L21_V001", 1)
    print(f"[objects_lookup] L21_V001 keyframe 001: {len(objs)} objects")
    print(f"  {objs[:10]}")

    # Test voi vai video khac
    for vid in ["L22_V001", "L23_V001", "L25_V001"]:
        objs2 = get_objects(vid, 1)
        print(f"  {vid}/001: {objs2[:5]}")

    # Test objects_contain_keywords
    print(f"\n  'Person' in L21_V001/001: {objects_contain_keywords(objs, ['person', 'man', 'woman'])}")
    print(f"  'Car' in L21_V001/001:    {objects_contain_keywords(objs, ['car', 'vehicle'])}")
