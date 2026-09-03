"""Test cho scripts/agent/pipeline_qa.py — chuyển từ _run_self_tests() cũ, giữ nguyên mọi assert.

Kiểm tra gom cụm theo video + gán answer riêng cho từng cụm. Không gọi LLM/index thật.
"""
from __future__ import annotations

from scripts.agent import pipeline_qa
from scripts.agent.pipeline_qa import _cluster_by_video, answer_by_video_cluster


def _hit(vid: str, i: int, rrf: float) -> dict:
    return {"video_id": vid, "n": i, "frame_idx": i, "frame_id": i + 1, "pts_time": float(i),
            "score": 0.1, "rrf_score": rrf, "jpg_path": None}


def _hits() -> list[dict]:
    return [_hit("A", 0, 0.016), _hit("B", 1, 0.015), _hit("A", 2, 0.014), _hit("C", 3, 0.010)]


def test_gom_cum_theo_video_xep_theo_diem() -> None:
    clusters = _cluster_by_video(_hits())
    assert [vid for vid, _ in clusters] == ["A", "B", "C"], f"Cum phai xep theo diem: {clusters}"
    assert len(clusters[0][1]) == 2, "Cum A phai gom ca 2 hit cua A"


def test_moi_cum_video_co_answer_rieng(monkeypatch) -> None:
    calls: list = []

    def _fake_answer(question, cluster_hits, top_n=5, max_tier=2):
        vid = cluster_hits[0]["video_id"]
        calls.append(vid)
        conf = {"A": 0.4, "B": 0.9, "C": 0.2}[vid]
        return {"answer": f"answer-{vid}", "best_hit": cluster_hits[0],
                "confidence": conf, "method": "objects"}

    monkeypatch.setattr(pipeline_qa, "answer_from_hits", _fake_answer)
    answers, best = answer_by_video_cluster("q?", _hits(), max_clusters=3)
    assert calls == ["A", "B", "C"], f"Phai chay trich xuat cho tung cum: {calls}"
    assert answers == {"A": "answer-A", "B": "answer-B", "C": "answer-C"}
    assert best["answer"] == "answer-B", "Cum co confidence cao nhat phai duoc chon lam best"


def test_max_clusters_gioi_han_chi_phi_llm(monkeypatch) -> None:
    calls: list = []

    def _fake_answer(question, cluster_hits, top_n=5, max_tier=2):
        vid = cluster_hits[0]["video_id"]
        calls.append(vid)
        return {"answer": f"answer-{vid}", "best_hit": cluster_hits[0],
                "confidence": {"A": 0.4, "B": 0.9, "C": 0.2}[vid], "method": "objects"}

    monkeypatch.setattr(pipeline_qa, "answer_from_hits", _fake_answer)
    answers, _ = answer_by_video_cluster("q?", _hits(), max_clusters=2)
    assert calls == ["A", "B"] and set(answers) == {"A", "B"}, f"max_clusters=2: {calls}"


def test_cluster_tier_assignment(monkeypatch) -> None:
    """3 cụm đầu nhận tier 2 (full), các cụm tiếp theo nhận tier 1 (cheap)."""
    tiers_called: list[tuple[str, int]] = []

    def _fake_answer(question, cluster_hits, top_n=5, max_tier=2):
        vid = cluster_hits[0]["video_id"]
        tiers_called.append((vid, max_tier))
        return {"answer": f"ans-{vid}", "best_hit": cluster_hits[0], "confidence": 0.5, "method": "objects"}

    monkeypatch.setattr(pipeline_qa, "answer_from_hits", _fake_answer)

    hits_5_vids = [
        _hit("V1", 1, 0.5), _hit("V2", 2, 0.4), _hit("V3", 3, 0.3),
        _hit("V4", 4, 0.2), _hit("V5", 5, 0.1),
    ]
    answer_by_video_cluster("q?", hits_5_vids, max_clusters=5)
    assert tiers_called == [("V1", 2), ("V2", 2), ("V3", 2), ("V4", 1), ("V5", 1)]

