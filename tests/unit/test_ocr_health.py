"""
test_ocr_health.py — Unit test cho ocr_health() và offline config loading.
"""
from __future__ import annotations

from pathlib import Path
from scripts.agent.tools import ocr_read
from scripts.agent.tools.ocr_read import ocr_health


def test_ocr_health_success() -> None:
    ok, msg = ocr_health()
    assert ok is True
    assert "OCR Engine sẵn sàng" in msg


def test_ocr_health_missing_weights(monkeypatch) -> None:
    monkeypatch.setattr(ocr_read, "_find_vietocr_weights", lambda: None)
    ok, msg = ocr_health()
    assert ok is False
    assert "Thiếu file weights VietOCR offline" in msg
