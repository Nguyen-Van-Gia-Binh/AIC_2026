"""
test_logging_config.py — Kiểm thử cấu hình per-session file logging cho backend.
"""
from __future__ import annotations

import logging
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from scripts.api.logging_config import (
    setup_logging,
    get_logger,
    restore_stdout_stderr,
    cleanup_old_logs,
)


def test_setup_logging_creates_session_and_latest_file(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    session_file, latest_file = setup_logging(
        log_dir=logs_dir, capture_stdout=True, force=True
    )

    try:
        assert session_file.exists(), "File log phiên phải được tạo tự động"
        assert latest_file.exists(), "File log latest phải được tạo tự động"
        assert session_file.name.startswith("backend_")
        assert session_file.name.endswith(".log")

        logger = get_logger("test_session")
        logger.info("Log thử nghiệm phiên tiếng Việt có dấu: thành công")
        print("[kis] print pipeline test: truy vấn L21_V001")

        # Flush tất cả handlers
        for h in logging.getLogger().handlers:
            h.flush()

        session_content = session_file.read_text(encoding="utf-8")
        latest_content = latest_file.read_text(encoding="utf-8")

        assert "Log thử nghiệm phiên tiếng Việt có dấu: thành công" in session_content
        assert "[kis] print pipeline test: truy vấn L21_V001" in session_content
        assert "Log thử nghiệm phiên tiếng Việt có dấu: thành công" in latest_content
        assert "[kis] print pipeline test: truy vấn L21_V001" in latest_content
    finally:
        restore_stdout_stderr()


def test_cleanup_old_logs(tmp_path: Path):
    logs_dir = tmp_path / "logs_cleanup"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Tạo 5 file giả lập phiên cũ
    for i in range(5):
        f = logs_dir / f"backend_2026010{i+1}_120000.log"
        f.write_text(f"Session {i+1}", encoding="utf-8")

    # Giữ lại 3 file mới nhất
    deleted = cleanup_old_logs(logs_dir, max_keep=3)
    assert len(deleted) == 2
    remaining = sorted([f.name for f in logs_dir.glob("backend_*.log")])
    assert len(remaining) == 3
    assert "backend_20260101_120000.log" not in remaining
    assert "backend_20260102_120000.log" not in remaining


def test_request_logging_middleware(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("scripts.agent.tools.index_store.preload", lambda: None)
    logs_dir = tmp_path / "logs_mw"

    from scripts.api.main import app

    session_file, _ = setup_logging(log_dir=logs_dir, capture_stdout=False, force=True)

    try:
        with TestClient(app) as client:
            res = client.get("/api/health")
            assert res.status_code == 200

        for h in logging.getLogger().handlers:
            h.flush()

        content = session_file.read_text(encoding="utf-8")
        assert "[REQ] GET /api/health" in content
        assert "[RES] GET /api/health -> 200" in content
    finally:
        restore_stdout_stderr()
