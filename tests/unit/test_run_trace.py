"""Test cho run_trace.py — dấu vết có cấu trúc cho mỗi lần chạy pipeline.

Các test dùng out_dir=tmp_path để không đụng logs/runs/ thật. Kill switch AIC_TRACE=0
được set qua monkeypatch.setenv.
"""
from __future__ import annotations

import json

import pytest

from scripts.agent.tools.run_trace import NULL_TRACE, RunTrace, current_trace, summarize_hits


def _load(tmp_path, trace: RunTrace) -> dict:
    path = tmp_path / trace.run_id[:8] / f"{trace.run_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_id_dinh_dang_va_khong_trung() -> None:
    ids = {RunTrace("kis", "q", {}).run_id for _ in range(1000)}
    assert len(ids) == 1000, "run_id phai duy nhat qua 1000 lan tao"
    parts = next(iter(ids)).split("_")
    assert len(parts) == 4, "dinh dang: <ngay>_<gio>_<host>_<rand>"
    assert len(parts[0]) == 8 and parts[0].isdigit()
    assert len(parts[1]) == 6 and parts[1].isdigit()
    assert len(parts[3]) == 6


def test_ghi_ca_json_va_txt(tmp_path) -> None:
    with RunTrace("kis", "a cyclist", {"top_k": 100}, out_dir=tmp_path) as t:
        t.set_result(video_id="L01_V001", frame_ids=[42])
    day_dir = tmp_path / t.run_id[:8]
    assert (day_dir / f"{t.run_id}.json").exists()
    assert (day_dir / f"{t.run_id}.txt").exists()
    data = _load(tmp_path, t)
    assert data["schema_version"] == 1
    assert data["query_type"] == "kis"
    assert data["query_text"] == "a cyclist"
    assert data["params"] == {"top_k": 100}
    assert data["result"]["video_id"] == "L01_V001"
    assert data["result"]["frame_ids"] == [42]


def test_kill_switch_khong_ghi_gi(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AIC_TRACE", "0")
    with RunTrace("kis", "q", {}, out_dir=tmp_path) as t:
        t.set_result(video_id="X")
    assert list(tmp_path.rglob("*.json")) == []
    assert list(tmp_path.rglob("*.txt")) == []
    assert t.run_id, "van phai co run_id de tra cuu"


def test_current_trace_chi_song_trong_with(tmp_path) -> None:
    assert current_trace() is None
    with RunTrace("qa", "q", {}, out_dir=tmp_path) as t:
        assert current_trace() is t
    assert current_trace() is None


def test_stage_ghi_thoi_gian_va_loi(tmp_path) -> None:
    with RunTrace("kis", "q", {}, out_dir=tmp_path) as t:
        with t.stage("retrieve"):
            pass
        with pytest.raises(ValueError):
            with t.stage("rank"):
                raise ValueError("boom")
    data = _load(tmp_path, t)
    stages = {s["name"]: s for s in data["stages"]}
    assert stages["retrieve"]["ok"] is True
    assert "ms" in stages["retrieve"]
    assert stages["rank"]["ok"] is False
    assert any(e["stage"] == "rank" and e["type"] == "ValueError" for e in data["errors"])


def test_llm_calls_cong_don_totals(tmp_path) -> None:
    with RunTrace("trake", "q", {}, out_dir=tmp_path) as t:
        t.add_llm_call(purpose="p1", model="m/a", key_index="1/5", ms=100, response="x")
        t.add_llm_call(purpose="p2", model="m/a", key_index="2/5", ms=250, response="y")
    data = _load(tmp_path, t)
    assert data["totals"]["llm_calls"] == 2
    assert data["totals"]["llm_ms"] == 350
    assert data["totals"]["llm_by_model"]["m/a"] == 2
    assert data["llm_calls"][0]["seq"] == 1
    assert data["llm_calls"][1]["seq"] == 2


def test_llm_response_bi_cat_300_ky_tu(tmp_path) -> None:
    with RunTrace("qa", "q", {}, out_dir=tmp_path) as t:
        t.add_llm_call(purpose="p", model="m", key_index="1/1", ms=1, response="z" * 1000)
    data = _load(tmp_path, t)
    assert len(data["llm_calls"][0]["response"]) <= 300


def test_record_gan_section_co_cau_truc(tmp_path) -> None:
    with RunTrace("kis", "q", {}, out_dir=tmp_path) as t:
        t.record("retrieval", {"backbone": "siglip", "candidates": [{"rank": 1, "video_id": "V"}]})
    data = _load(tmp_path, t)
    assert data["retrieval"]["backbone"] == "siglip"
    assert data["qa"] is None and data["trake"] is None


def test_exception_trong_with_van_ghi_file(tmp_path) -> None:
    with pytest.raises(RuntimeError):
        with RunTrace("kis", "q", {}, out_dir=tmp_path) as t:
            raise RuntimeError("mid")
    data = _load(tmp_path, t)
    assert any(e["type"] == "RuntimeError" for e in data["errors"])


def test_summarize_hits_giu_dung_truong_can() -> None:
    hits = [
        {"video_id": "L01_V001", "frame_id": 42, "score": 0.87654, "rrf_score": 0.01234, "junk": 1},
        {"video_id": "L02_V003", "frame_id": 7, "score": 0.5, "answer": "màu đỏ"},
    ]
    rows = summarize_hits(hits, 20)
    assert rows[0] == {"rank": 1, "video_id": "L01_V001", "frame_id": 42,
                       "score": 0.8765, "rrf_score": 0.01234}
    assert rows[1]["rank"] == 2 and rows[1]["answer"] == "màu đỏ"
    assert "rrf_score" not in rows[1]
    assert len(summarize_hits(hits, 1)) == 1


def test_null_trace_moi_thao_tac_deu_no_op() -> None:
    # Dùng làm null-object trong pipeline khi caller không truyền trace — không ghi file, không lỗi.
    NULL_TRACE.record("retrieval", {"x": 1})
    NULL_TRACE.add_llm_call(purpose="p", model="m")
    NULL_TRACE.set_result(video_id="V")
    NULL_TRACE.add_error("s", ValueError("e"))
    with NULL_TRACE.stage("retrieve"):
        pass
    assert NULL_TRACE.run_id == ""


def test_txt_tom_tat_chua_run_id_va_ket_qua(tmp_path) -> None:
    with RunTrace("kis", "a dog running", {}, out_dir=tmp_path) as t:
        t.set_result(video_id="L02_V003", frame_ids=[7])
    txt = (tmp_path / t.run_id[:8] / f"{t.run_id}.txt").read_text(encoding="utf-8")
    assert t.run_id in txt
    assert "L02_V003" in txt
    assert "a dog running" in txt
