"""Test: config.call_llm() tự ghi mỗi lần gọi vào RunTrace đang mở (nếu có).

Không gọi mạng — monkeypatch config._call_one trả chuỗi có sẵn, và thay PROVIDER_CHAIN
bằng một provider giả để vòng lặp chạm tới nhánh thành công đã được instrument.
"""
from __future__ import annotations

from scripts.agent import config
from scripts.agent.tools.run_trace import RunTrace

_FAKE_CHAIN = [
    {"name": "fake", "model_text": "fake/model", "model_vision": "fake/model", "api_keys": ["k1"]}
]


def test_call_llm_ghi_vao_trace_dang_mo(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "PROVIDER_CHAIN", _FAKE_CHAIN)
    monkeypatch.setattr(config, "_call_one", lambda *a, **k: "canned answer")

    with RunTrace("qa", "hoi gi do", {}, out_dir=tmp_path) as t:
        out = config.call_llm("prompt xin chao", purpose="qa_tier2")

    assert out == "canned answer"
    calls = t._data["llm_calls"]
    assert len(calls) == 1
    assert calls[0]["purpose"] == "qa_tier2"
    assert calls[0]["model"] == "fake/model"
    assert calls[0]["response"] == "canned answer"
    assert calls[0]["prompt_chars"] == len("prompt xin chao")
    assert t._data["totals"]["llm_calls"] == 1


def test_call_llm_khong_co_trace_van_chay_binh_thuong(monkeypatch) -> None:
    monkeypatch.setattr(config, "PROVIDER_CHAIN", _FAKE_CHAIN)
    monkeypatch.setattr(config, "_call_one", lambda *a, **k: "ok")
    assert config.call_llm("x", purpose="p") == "ok"


def test_call_llm_purpose_mac_dinh_khi_khong_truyen(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "PROVIDER_CHAIN", _FAKE_CHAIN)
    monkeypatch.setattr(config, "_call_one", lambda *a, **k: "r")
    with RunTrace("kis", "q", {}, out_dir=tmp_path) as t:
        config.call_llm("p")
    assert t._data["llm_calls"][0]["purpose"] == "unknown"
