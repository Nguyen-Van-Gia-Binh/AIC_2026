"""Kiểm tra router /api/qa/run và /api/trake/run truyền đúng tham số query_en xuống pipeline."""
from __future__ import annotations

from fastapi.testclient import TestClient
from scripts.api.main import app
from scripts.api.routers import qa as qa_router
from scripts.api.routers import trake as trake_router


def test_qa_run_passes_query_en(monkeypatch) -> None:
    captured: dict = {}

    def _fake_run_qa(query_text, question=None, top_k=100, query_en=None, use_hybrid=True, trace=None):
        captured["query_text"] = query_text
        captured["question"] = question
        captured["top_k"] = top_k
        captured["query_en"] = query_en
        return {
            "results": [{"video_id": "L21_V001", "frame_id": 1, "frame_idx": 0, "pts_time": 0.0, "score": 0.9, "answer": "test"}],
            "answer": "test",
            "confidence": 0.95,
            "n_loops": 1,
        }

    monkeypatch.setattr(qa_router, "run_qa", _fake_run_qa)

    client = TestClient(app)
    # 1. Trường hợp có query_en
    res = client.post("/api/qa/run", json={
        "query": "người mặc áo đỏ",
        "question": "ai mặc áo đỏ?",
        "top_k": 10,
        "query_en": "a person wearing a red shirt",
    })
    assert res.status_code == 200, res.text
    assert captured["query_en"] == "a person wearing a red shirt"
    assert captured["query_text"] == "người mặc áo đỏ"

    # 2. Trường hợp không truyền query_en (mặc định None)
    res2 = client.post("/api/qa/run", json={
        "query": "người mặc áo đỏ",
        "question": "ai mặc áo đỏ?",
        "top_k": 10,
    })
    assert res2.status_code == 200, res2.text
    assert captured["query_en"] is None


def test_trake_run_passes_query_en(monkeypatch) -> None:
    captured: dict = {}

    def _fake_run_trake(query_text, events, top_k_video=5, top_k_frame=10, query_en=None, trace=None, strict_monotonic=True):
        captured["query_text"] = query_text
        captured["events"] = events
        captured["top_k_video"] = top_k_video
        captured["query_en"] = query_en
        return {
            "results": [{"video_id": "L21_V001", "frame_ids": [1, 2], "score": 0.85}],
            "n_events": len(events),
        }

    monkeypatch.setattr(trake_router, "run_trake", _fake_run_trake)

    client = TestClient(app)
    # 1. Có query_en
    res = client.post("/api/trake/run", json={
        "query": "lễ hội xe hoa",
        "events": ["xe hoa xuất phát", "pháo hoa"],
        "top_k_video": 3,
        "query_en": "parade with flower float and fireworks",
    })
    assert res.status_code == 200, res.text
    assert captured["query_en"] == "parade with flower float and fireworks"

    # 2. Không truyền query_en
    res2 = client.post("/api/trake/run", json={
        "query": "lễ hội xe hoa",
        "events": ["xe hoa xuất phát", "pháo hoa"],
        "top_k_video": 3,
    })
    assert res2.status_code == 200, res2.text
    assert captured["query_en"] is None
