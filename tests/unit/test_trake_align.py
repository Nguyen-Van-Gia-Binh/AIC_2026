"""Test cho scripts/agent/tools/trake_align.py — chuyển từ _run_self_tests() của pipeline_trake.py.

Giữ nguyên mọi assert. Khối cũ gán đè biến global `get_objects`; ở đây dùng fixture `monkeypatch`
và patch ĐÚNG module chứa hàm (bài học từ lần tách file: patch nhầm module thì test vẫn "pass" vì
lý do sai).
"""
from __future__ import annotations

from scripts.agent.tools import trake_align
from scripts.agent.tools.trake_align import find_best_increasing_chain, rule_plausibility


def _fake_hit(video_id: str, frame_idx: int, score: float) -> dict:
    return {"video_id": video_id, "n": frame_idx, "frame_idx": frame_idx, "frame_id": frame_idx + 1,
            "pts_time": 0.0, "score": score, "jpg_path": None}


def test_dp_thang_greedy() -> None:
    """Event 0 co frame diem cao nhat (100, 0.9) nam MUON, chan mat event 1 co frame diem cao
    (10, 0.95) nam SOM hon. Greedy khoa X1 (0.9) ngay -> tong 1.2. DP phai chon X2+Y1 = 1.75."""
    event_hits = [
        [_fake_hit("V", 100, 0.9), _fake_hit("V", 5, 0.8)],
        [_fake_hit("V", 10, 0.95), _fake_hit("V", 200, 0.3)],
    ]
    chain = find_best_increasing_chain(event_hits)
    assert chain is not None, "Phai tim duoc chuoi hop le"
    total = sum(h["score"] for h in chain)
    assert abs(total - 1.75) < 1e-9, f"DP phai chon X2+Y1 (0.8+0.95=1.75), duoc {total}"
    assert chain[0]["frame_idx"] == 5 and chain[1]["frame_idx"] == 10, (
        f"DP phai chon frame_idx=5 roi 10, duoc {[h['frame_idx'] for h in chain]}"
    )


def test_khong_co_chuoi_hop_le_tra_none() -> None:
    event_hits = [[_fake_hit("V", 100, 0.9)], [_fake_hit("V", 50, 0.8)]]
    assert find_best_increasing_chain(event_hits) is None, "Khong co chuoi hop le phai tra None"


def test_mot_event_chon_frame_diem_cao_nhat() -> None:
    event_hits = [[_fake_hit("V", 10, 0.5), _fake_hit("V", 20, 0.9)]]
    chain = find_best_increasing_chain(event_hits)
    assert chain is not None and chain[0]["frame_idx"] == 20, "1 event phai chon diem cao nhat"


def test_strict_monotonic() -> None:
    event_hits = [[_fake_hit("V", 10, 0.5)], [_fake_hit("V", 10, 0.6)]]
    assert find_best_increasing_chain(event_hits) is None, (
        "Mac dinh strict: 2 moc trung frame_idx phai bi loai"
    )
    assert find_best_increasing_chain(event_hits, strict=False) is not None, (
        "strict=False phai cho phep frame_idx bang nhau (hanh vi cu)"
    )
    event_hits_b = [[_fake_hit("V", 10, 0.5)],
                    [_fake_hit("V", 10, 0.6), _fake_hit("V", 11, 0.4)]]
    chain_b = find_best_increasing_chain(event_hits_b)
    assert chain_b is not None and chain_b[1]["frame_idx"] == 11, (
        f"Strict phai chon phuong an tang nghiem ngat con lai: {chain_b}"
    )


def test_rule_plausibility_khop_tu_khoa_cho_diem_cao_hon(monkeypatch) -> None:
    monkeypatch.setattr(trake_align, "get_objects",
                        lambda vid, n: {1: ["Bicycle", "Person"], 2: ["Car"]}.get(n, []))
    chain = [_fake_hit("V", 1, 0.5), _fake_hit("V", 2, 0.5)]
    chain[0]["n"], chain[1]["n"] = 1, 2
    score_match = rule_plausibility(["a person riding a bicycle", "a car on the road"], chain)
    score_miss = rule_plausibility(["an airplane taking off", "a boat on a river"], chain)
    assert score_match > score_miss, f"Khop tu khoa phai cho diem cao hon: {score_match} vs {score_miss}"
    assert 0.0 <= score_match <= 1.0 and 0.0 <= score_miss <= 1.0, "rule_score phai nam trong [0,1]"
    assert rule_plausibility([], []) == 0.0, "Chuoi rong -> 0.0, khong crash"
