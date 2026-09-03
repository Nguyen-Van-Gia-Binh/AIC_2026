"""Test cho scripts/agent/tools/query_expand.py — chuyển từ khối __main__ cũ, giữ nguyên mọi assert."""
from __future__ import annotations

import sys
import types

from scripts.agent.tools.query_expand import expand_aspects, expand_aspects_llm


def test_sinh_3_goc_nhin_va_giu_nguyen_query_goc_o_dau() -> None:
    out = expand_aspects("a cyclist racing on a mountain road")
    assert len(out) == 3, f"Phai sinh 3 goc nhin, duoc {len(out)}"
    assert out[0] == "a cyclist racing on a mountain road", "Goc nhin dau phai la query goc nguyen van"
    assert all("cyclist" in a for a in out), "Moi goc nhin phai giu noi dung goc"


def test_truong_hop_bien() -> None:
    assert expand_aspects("a red car", max_aspects=1) == ["a red car"], "max_aspects=1 -> tat expansion"
    assert expand_aspects("") == []
    assert expand_aspects("   ") == []


def test_query_dai_chi_giu_2_goc_nhin() -> None:
    long_q = " ".join(["word"] * 30)
    assert len(expand_aspects(long_q)) == 2, "Query dai -> chi giu 2 goc nhin (v1 + v3)"


def test_nhanh_llm_parse_dung(monkeypatch) -> None:
    fake_config = types.ModuleType("scripts.agent.config")
    fake_config.call_llm = lambda *a, **k: (
        "a mountain road in daylight\n"
        "a cyclist in the center of the frame\n"
        "a cyclist in red pedalling fast"
    )
    monkeypatch.setitem(sys.modules, "scripts.agent.config", fake_config)
    out = expand_aspects_llm("a cyclist racing on a mountain road")
    assert out[0] == "a cyclist racing on a mountain road", "Goc nhin dau van phai la query goc"
    assert len(out) == 3, f"Phai co 3 goc nhin, duoc {out}"


def test_nhanh_llm_loi_thi_rot_ve_template_tat_dinh(monkeypatch) -> None:
    def _raise(*a, **k):
        raise RuntimeError("simulated failure")

    fake_config = types.ModuleType("scripts.agent.config")
    fake_config.call_llm = _raise
    monkeypatch.setitem(sys.modules, "scripts.agent.config", fake_config)
    fallback = expand_aspects_llm("a cyclist racing on a mountain road")
    assert fallback == expand_aspects("a cyclist racing on a mountain road"), (
        "LLM loi phai rot ve template tat dinh"
    )
