# Backend Per-Session File Logging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tự động ghi toàn bộ log của backend AIC2026 (Uvicorn, HTTP middleware, stacktrace, và lệnh `print()` từ pipeline) vào **từng file log riêng biệt cho mỗi phiên khởi động** dạng `logs/backend_YYYYMMDD_HHMMSS.log` kèm file `logs/backend_latest.log`.

**Architecture:** Tạo module `scripts/api/logging_config.py` sinh session ID timestamp khi khởi động, cấu hình UTF-8 `FileHandler` cho file phiên và file latest, hỗ trợ `StdoutTeeStream` để bắt các câu lệnh `print()`, tích hợp HTTP request/response middleware vào `scripts/api/main.py`, dọn dẹp các phiên cũ (`max_sessions=30`), và cập nhật `.gitignore`.

**Tech Stack:** Python standard libraries (`logging`, `sys`, `time`, `pathlib`, `datetime`), FastAPI / Starlette middleware, pytest.

**Spec:** Yêu cầu người dùng: Mỗi lần chạy/khởi động backend tạo 1 file log riêng biệt theo phiên (không dồn chung 1 file), phục vụ phân tích độc lập từng phiên chạy.

## Global Constraints

- Không dùng thư viện ngoài ngoài standard library và FastAPI có sẵn.
- Comment và text log bằng tiếng Việt theo quy ước `GEMINI.md`.
- Mỗi phiên sinh file `logs/backend_YYYYMMDD_HHMMSS.log` và cập nhật `logs/backend_latest.log`.
- Log vừa hiện console vừa lưu file.
- `.gitignore` bỏ qua thư mục `logs/` và `*.log`.

---

### Task 1: Tạo module cấu hình logging theo phiên `scripts/api/logging_config.py` và Unit Test

**Files:**
- Create: `scripts/api/logging_config.py`
- Test: `tests/unit/test_logging_config.py`

**Interfaces:**
- Produces: `setup_logging(log_dir: str | Path = "logs", max_sessions: int = 30, capture_stdout: bool = True) -> tuple[Path, Path]`, `cleanup_old_logs(log_dir: Path, max_keep: int = 30) -> list[Path]`, `get_logger(name: str) -> logging.Logger`, `restore_stdout_stderr()`

- [x] **Step 1: Viết test failing cho per-session logging**

```python
# tests/unit/test_logging_config.py
from __future__ import annotations

import logging
from pathlib import Path
import pytest

from scripts.api.logging_config import setup_logging, get_logger, restore_stdout_stderr, cleanup_old_logs


def test_setup_logging_creates_session_and_latest_file(tmp_path: Path):
    logs_dir = tmp_path / "logs"
    session_file, latest_file = setup_logging(log_dir=logs_dir, capture_stdout=True)
    
    assert session_file.exists()
    assert latest_file.exists()
    assert session_file.name.startswith("backend_")
    assert session_file.name.endswith(".log")
    
    logger = get_logger("test_session")
    logger.info("Log thử nghiệm phiên tiếng Việt có dấu")
    print("[kis] print pipeline test: L21_V001")
    
    for h in logging.getLogger().handlers:
        h.flush()
        
    session_content = session_file.read_text(encoding="utf-8")
    latest_content = latest_file.read_text(encoding="utf-8")
    
    assert "Log thử nghiệm phiên tiếng Việt có dấu" in session_content
    assert "[kis] print pipeline test: L21_V001" in session_content
    assert "Log thử nghiệm phiên tiếng Việt có dấu" in latest_content
    
    restore_stdout_stderr()


def test_cleanup_old_logs(tmp_path: Path):
    logs_dir = tmp_path / "logs"
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
```

- [x] **Step 2: Chạy pytest xác nhận FAIL**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_logging_config.py -v`
Expected: FAIL (ModuleNotFoundError)

- [x] **Step 3: Cài đặt `scripts/api/logging_config.py`**

```python
# scripts/api/logging_config.py
from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import sys
from typing import TextIO

_ROOT = Path(__file__).resolve().parent.parent.parent
_ORIGINAL_STDOUT = sys.stdout
_ORIGINAL_STDERR = sys.stderr


class StdoutTeeStream:
    """Tee stream: Vừa xuất ra stream gốc (terminal) vừa gửi vào file logging."""

    def __init__(self, original_stream: TextIO, logger_name: str, level: int = logging.INFO):
        self.original_stream = original_stream
        self.logger = logging.getLogger(logger_name)
        self.level = level
        self._buffer = ""

    def write(self, message: str) -> int:
        res = self.original_stream.write(message)
        self.original_stream.flush()
        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line_stripped = line.strip()
            if line_stripped:
                self.logger.log(self.level, line_stripped)
        return res

    def flush(self) -> None:
        self.original_stream.flush()
        if self._buffer.strip():
            self.logger.log(self.level, self._buffer.strip())
            self._buffer = ""

    def isatty(self) -> bool:
        return getattr(self.original_stream, "isatty", lambda: False)()


def cleanup_old_logs(log_dir: Path, max_keep: int = 30) -> list[Path]:
    """Dọn dẹp các file log phiên cũ nếu vượt quá max_keep."""
    log_files = sorted(
        [f for f in log_dir.glob("backend_*.log") if f.name != "backend_latest.log"],
        key=lambda f: f.stat().st_mtime,
    )
    deleted: list[Path] = []
    if len(log_files) > max_keep:
        to_delete = log_files[: len(log_files) - max_keep]
        for f in to_delete:
            try:
                f.unlink(missing_ok=True)
                deleted.append(f)
            except Exception:
                pass
    return deleted


def setup_logging(
    log_dir: str | Path = "logs",
    max_sessions: int = 30,
    capture_stdout: bool = True,
) -> tuple[Path, Path]:
    """
    Khởi tạo hệ thống logging cho backend theo từng phiên khởi động:
    - File phiên: logs/backend_YYYYMMDD_HHMMSS.log
    - File latest: logs/backend_latest.log
    """
    logs_path = Path(log_dir) if Path(log_dir).is_absolute() else _ROOT / log_dir
    logs_path.mkdir(parents=True, exist_ok=True)

    # Dọn dẹp phiên cũ
    cleanup_old_logs(logs_path, max_keep=max_sessions)

    # Tạo tên file theo timestamp phiên
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = logs_path / f"backend_{session_id}.log"
    latest_file = logs_path / "backend_latest.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler cho file phiên (ghi mới)
    session_handler = logging.FileHandler(str(session_file), mode="w", encoding="utf-8")
    session_handler.setFormatter(formatter)
    session_handler.setLevel(logging.INFO)

    # Handler cho file latest (ghi mới mỗi phiên)
    latest_handler = logging.FileHandler(str(latest_file), mode="w", encoding="utf-8")
    latest_handler.setFormatter(formatter)
    latest_handler.setLevel(logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Xoá các file handler cũ để tránh duplicate
    root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, logging.FileHandler)]
    root_logger.addHandler(session_handler)
    root_logger.addHandler(latest_handler)

    # Cấu hình loggers của Uvicorn & FastAPI
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        l = logging.getLogger(logger_name)
        l.setLevel(logging.INFO)
        l.handlers = [h for h in l.handlers if not isinstance(h, logging.FileHandler)]
        l.addHandler(session_handler)
        l.addHandler(latest_handler)

    # Bọc stdout và stderr để bắt tất cả lệnh print()
    if capture_stdout:
        if not isinstance(sys.stdout, StdoutTeeStream):
            sys.stdout = StdoutTeeStream(_ORIGINAL_STDOUT, "stdout", level=logging.INFO)
        if not isinstance(sys.stderr, StdoutTeeStream):
            sys.stderr = StdoutTeeStream(_ORIGINAL_STDERR, "stderr", level=logging.ERROR)

    return session_file, latest_file


def restore_stdout_stderr() -> None:
    """Khôi phục lại stdout/stderr gốc khi cần (dùng trong test teardown)."""
    global _ORIGINAL_STDOUT, _ORIGINAL_STDERR
    sys.stdout = _ORIGINAL_STDOUT
    sys.stderr = _ORIGINAL_STDERR


def get_logger(name: str) -> logging.Logger:
    """Lấy logger có tên chuẩn."""
    return logging.getLogger(name)
```

- [x] **Step 4: Chạy test xác nhận PASS**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_logging_config.py -v`
Expected: PASS

---

### Task 2: Thêm Request/Response Logging Middleware và tích hợp vào `scripts/api/main.py`

**Files:**
- Modify: `scripts/api/main.py`
- Test: `tests/unit/test_logging_config.py`

- [x] **Step 1: Viết test cho Request Logging Middleware trong `test_logging_config.py`**

```python
from fastapi.testclient import TestClient
from scripts.api.main import app

def test_request_logging_middleware(tmp_path: Path):
    logs_dir = tmp_path / "logs_mw"
    session_file, _ = setup_logging(log_dir=logs_dir, capture_stdout=False)
    
    with TestClient(app) as client:
        res = client.get("/api/health")
        assert res.status_code == 200
        
    for h in logging.getLogger().handlers:
        h.flush()
        
    content = session_file.read_text(encoding="utf-8")
    assert "[REQ] GET /api/health" in content
    assert "[RES] GET /api/health -> 200" in content
```

- [x] **Step 2: Cập nhật `scripts/api/main.py`**

```python
import time
from fastapi import Request, Response
from scripts.api.logging_config import setup_logging, get_logger

# Khởi tạo per-session logging
session_file, _ = setup_logging()
logger = get_logger("api.http")

@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    method = request.method
    path = request.url.path
    query = request.url.query
    query_str = f"?{query}" if query else ""
    client_ip = request.client.host if request.client else "unknown"

    logger.info(f"[REQ] {method} {path}{query_str} (client: {client_ip})")
    try:
        response: Response = await call_next(request)
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(f"[RES] {method} {path} -> {response.status_code} ({duration_ms:.1f}ms)")
        return response
    except Exception as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        logger.error(f"[ERR] {method} {path} -> 500 ({duration_ms:.1f}ms): {exc}", exc_info=True)
        raise exc
```

- [x] **Step 3: Chạy test xác nhận PASS**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_logging_config.py -v`
Expected: PASS

---

### Task 3: Cập nhật `.gitignore` và chạy toàn bộ test suite

**Files:**
- Modify: `.gitignore`

- [x] **Step 1: Cập nhật `.gitignore` để bỏ qua `logs/` và `*.log`**
- [x] **Step 2: Chạy toàn bộ test suite `pytest tests/unit -v`**

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-31-backend-file-logging.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
