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
    cleanup_old_run_traces,
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


def test_cleanup_old_run_traces(tmp_path: Path):
    runs = tmp_path / "runs"
    for day in ("20260101", "20260102", "20260103", "20260104", "20260105"):
        d = runs / day
        d.mkdir(parents=True)
        (d / f"{day}_120000_host_abc123.json").write_text("{}", encoding="utf-8")
    (runs / "incoming").mkdir()  # không đụng tới

    deleted = cleanup_old_run_traces(tmp_path, max_days=3)

    assert len(deleted) == 2
    remaining = sorted(d.name for d in runs.iterdir() if d.is_dir())
    assert remaining == ["20260103", "20260104", "20260105", "incoming"]


def test_is_pipeline_path_phan_loai_dung():
    from scripts.api.main import _is_pipeline_path

    assert _is_pipeline_path("/api/kis/search")
    assert _is_pipeline_path("/api/qa/run")
    assert _is_pipeline_path("/api/trake/run")
    assert _is_pipeline_path("/api/queue/export")
    assert _is_pipeline_path("/api/rewrite")
    # Nhiễu — phục vụ UI, không phải đường pipeline:
    assert not _is_pipeline_path("/api/health")
    assert not _is_pipeline_path("/api/images/L01_V001/1")
    assert not _is_pipeline_path("/api/videos/L01_V001")
    assert not _is_pipeline_path("/api/keyframes/L01_V001/all")


def test_middleware_bo_qua_route_nhieu_nhung_van_log_loi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("scripts.agent.tools.index_store.preload", lambda: None)
    logs_dir = tmp_path / "logs_mw"

    from scripts.api.main import app

    session_file, _ = setup_logging(log_dir=logs_dir, capture_stdout=False, force=True)

    try:
        with TestClient(app) as client:
            assert client.get("/api/health").status_code == 200          # route nhiễu, 200 nhanh
            assert client.get("/api/khong-ton-tai").status_code == 404   # lỗi -> luôn log

        for h in logging.getLogger().handlers:
            h.flush()

        content = session_file.read_text(encoding="utf-8")
        assert "/api/health" not in content, "route healthcheck 200 nhanh không được ghi vào log"
        assert "[RES] GET /api/khong-ton-tai -> 404" in content, "request lỗi phải luôn được ghi"
    finally:
        restore_stdout_stderr()


def test_uvicorn_access_khong_propagate_xuong_file(tmp_path: Path):
    try:
        setup_logging(log_dir=tmp_path / "logs_ua", capture_stdout=False, force=True)
        assert logging.getLogger("uvicorn.access").propagate is False, (
            "uvicorn.access trùng lặp api.http — không được đẩy xuống file handler của root"
        )
    finally:
        restore_stdout_stderr()
