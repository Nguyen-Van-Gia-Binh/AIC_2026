"""Test cho scripts/agent/tools/temporal_nms.py — chuyển từ khối __main__ cũ, giữ nguyên mọi assert."""
from __future__ import annotations

from scripts.agent.tools.temporal_nms import temporal_nms


def _hit(vid: str, pts: float, score: float) -> dict:
    return {"video_id": vid, "pts_time": pts, "frame_idx": int(pts * 30), "score": score}


def test_loai_keyframe_sat_nhau_trong_cung_video() -> None:
    hits = [_hit("A", 10.0, 0.9), _hit("A", 11.0, 0.88), _hit("A", 12.0, 0.87), _hit("A", 30.0, 0.5)]
    out = temporal_nms(hits, min_gap=3.0)
    assert [h["pts_time"] for h in out] == [10.0, 30.0], f"Phai giu 10.0 va 30.0, duoc {out}"


def test_cac_video_doc_lap_voi_nhau_du_trung_thoi_diem() -> None:
    hits = [_hit("A", 10.0, 0.9), _hit("B", 10.5, 0.8), _hit("C", 11.0, 0.7)]
    assert len(temporal_nms(hits, min_gap=3.0)) == 3, "NMS chi ap dung TRONG cung 1 video"


def test_max_per_video_cat_dung_so_dinh() -> None:
    hits = [_hit("A", float(i * 10), 0.9 - i * 0.01) for i in range(6)]
    out = temporal_nms(hits, min_gap=3.0, max_per_video=3)
    assert len(out) == 3, f"max_per_video=3 phai giu dung 3 dinh, duoc {len(out)}"
    assert [h["pts_time"] for h in out] == [0.0, 10.0, 20.0], "Phai giu 3 dinh diem cao nhat"


def test_giu_dinh_diem_cao_nhat_khong_phai_dinh_gap_dau_tien() -> None:
    hits = [_hit("A", 11.0, 0.5), _hit("A", 10.0, 0.9)]
    out = temporal_nms(hits, min_gap=3.0)
    assert len(out) == 1 and out[0]["score"] == 0.9, f"Phai giu dinh 0.9, duoc {out}"


def test_dau_vao_rong_hoac_thieu_pts_time_khong_crash() -> None:
    assert temporal_nms([]) == []
    no_pts = [{"video_id": "A", "score": 0.5}, {"video_id": "A", "score": 0.4}]
    assert len(temporal_nms(no_pts, min_gap=3.0)) == 2, "Thieu pts_time -> giu nguyen, khong doan"
