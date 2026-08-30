"""Test cho _llm_crosscheck_chain() của scripts/agent/pipeline_trake.py (cổng LLM của Giai đoạn 3).

Chuyển từ _run_self_tests() cũ (test 5-8), giữ nguyên mọi assert. Không gọi LLM thật.
"""
from __future__ import annotations

import pytest

from scripts.agent import pipeline_trake
from scripts.agent.pipeline_trake import DEFAULT_LLM_CROSSCHECK_SCORE, _llm_crosscheck_chain


def _fake_hit(video_id: str, frame_idx: int, score: float) -> dict:
    return {"video_id": video_id, "n": frame_idx, "frame_idx": frame_idx, "frame_id": frame_idx + 1,
            "pts_time": 0.0, "score": score, "jpg_path": None}


@pytest.fixture
def chain_va_events():
    return [_fake_hit("V", 1, 0.5), _fake_hit("V", 2, 0.6)], ["athlete takes off", "athlete lands"]


def test_parse_dung_score_tu_response_chuan(monkeypatch, chain_va_events) -> None:
    chain, events = chain_va_events
    monkeypatch.setattr(pipeline_trake, "call_llm", lambda *a, **k: "SCORE: 0.82")
    score = _llm_crosscheck_chain("high jump", events, chain)
    assert abs(score - 0.82) < 1e-9, f"Phai parse dung 0.82, duoc {score}"


def test_call_llm_loi_tra_diem_trung_lap(monkeypatch, chain_va_events) -> None:
    chain, events = chain_va_events

    def _raise(*a, **k):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(pipeline_trake, "call_llm", _raise)
    score = _llm_crosscheck_chain("high jump", events, chain)
    assert score == DEFAULT_LLM_CROSSCHECK_SCORE, f"Loi call_llm phai tra diem trung lap, duoc {score}"


def test_response_khong_parse_duoc_tra_diem_trung_lap(monkeypatch, chain_va_events) -> None:
    chain, events = chain_va_events
    monkeypatch.setattr(pipeline_trake, "call_llm", lambda *a, **k: "I cannot determine this.")
    score = _llm_crosscheck_chain("high jump", events, chain)
    assert score == DEFAULT_LLM_CROSSCHECK_SCORE, (
        f"Response khong hop le phai tra diem trung lap, duoc {score}"
    )


def test_clamp_ve_khoang_0_1(monkeypatch, chain_va_events) -> None:
    chain, events = chain_va_events
    monkeypatch.setattr(pipeline_trake, "call_llm", lambda *a, **k: "SCORE: 1.50")
    assert _llm_crosscheck_chain("q", events, chain) == 1.0, "Phai clamp ve 1.0"
    monkeypatch.setattr(pipeline_trake, "call_llm", lambda *a, **k: "SCORE: -0.20")
    assert _llm_crosscheck_chain("q", events, chain) == 0.0, "Phai clamp ve 0.0"
