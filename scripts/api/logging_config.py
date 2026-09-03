"""
logging_config.py — Cấu hình logging tự động theo phiên cho backend AIC2026.

Chức năng:
- Mỗi lần backend khởi động tạo một file log độc lập: logs/backend_YYYYMMDD_HHMMSS.log
- Tạo/cập nhật file alias logs/backend_latest.log trỏ vào phiên mới nhất.
- Bắt trọn vẹn cả uvicorn logging lẫn các câu lệnh print("[kis] ...") từ pipeline qua StdoutTeeStream.
- Dọn dẹp tự động các phiên log cũ (mặc định giữ lại 30 phiên).
"""
from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
import sys
from typing import Any, TextIO

_ROOT = Path(__file__).resolve().parent.parent.parent
_ORIGINAL_STDOUT = sys.stdout
_ORIGINAL_STDERR = sys.stderr

_CONFIGURED: bool = False
_ACTIVE_SESSION_FILE: Path | None = None
_ACTIVE_LATEST_FILE: Path | None = None


class StdoutTeeStream:
    """Tee stream: Vừa xuất ra stream gốc (terminal) vừa gửi vào file logging."""

    def __init__(self, original_stream: TextIO, logger_name: str, level: int = logging.INFO):
        self.original_stream = original_stream
        self.logger = logging.getLogger(logger_name)
        self.level = level
        self._buffer = ""

    def write(self, message: str) -> int:
        res = self.original_stream.write(message)
        try:
            self.original_stream.flush()
        except Exception:
            pass

        self._buffer += message
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line_stripped = line.strip()
            if line_stripped:
                self.logger.log(self.level, line_stripped)
        return res

    def flush(self) -> None:
        try:
            self.original_stream.flush()
        except Exception:
            pass
        if self._buffer.strip():
            self.logger.log(self.level, self._buffer.strip())
            self._buffer = ""

    def isatty(self) -> bool:
        return getattr(self.original_stream, "isatty", lambda: False)()

    def fileno(self) -> int:
        return getattr(self.original_stream, "fileno", lambda: 1)()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.original_stream, name)


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
    force: bool = False,
) -> tuple[Path, Path]:
    """
    Khởi tạo hệ thống logging cho backend theo từng phiên khởi động:
    - File phiên: logs/backend_YYYYMMDD_HHMMSS.log
    - File latest: logs/backend_latest.log
    """
    global _CONFIGURED, _ACTIVE_SESSION_FILE, _ACTIVE_LATEST_FILE

    if _CONFIGURED and not force and _ACTIVE_SESSION_FILE and _ACTIVE_LATEST_FILE:
        return _ACTIVE_SESSION_FILE, _ACTIVE_LATEST_FILE

    logs_path = Path(log_dir) if Path(log_dir).is_absolute() else _ROOT / log_dir
    logs_path.mkdir(parents=True, exist_ok=True)

    # Dọn dẹp phiên cũ
    cleanup_old_logs(logs_path, max_keep=max_sessions)

    # Tạo tên file theo timestamp phiên
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_file = logs_path / f"backend_{session_id}.log"
    latest_file = logs_path / "backend_latest.log"

    _ACTIVE_SESSION_FILE = session_file
    _ACTIVE_LATEST_FILE = latest_file
    _CONFIGURED = True

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

    # Đóng và loại bỏ các FileHandler cũ trên root logger
    old_handlers = []
    for h in root_logger.handlers:
        if isinstance(h, logging.FileHandler):
            try:
                h.close()
            except Exception:
                pass
        else:
            old_handlers.append(h)

    root_logger.handlers = old_handlers
    root_logger.addHandler(session_handler)
    root_logger.addHandler(latest_handler)

    # Cấu hình loggers của Uvicorn & FastAPI để truyền tin về root logger
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "api.http"):
        l = logging.getLogger(logger_name)
        l.setLevel(logging.INFO)
        l.propagate = True
        # Gỡ handlers riêng nếu có để tránh ghi lặp 2 lần
        for h in list(l.handlers):
            if isinstance(h, logging.FileHandler):
                try:
                    h.close()
                except Exception:
                    pass
                l.removeHandler(h)

    # Bọc stdout và stderr để bắt tất cả lệnh print()
    if capture_stdout:
        if not isinstance(sys.stdout, StdoutTeeStream):
            sys.stdout = StdoutTeeStream(_ORIGINAL_STDOUT, "stdout", level=logging.INFO)
        if not isinstance(sys.stderr, StdoutTeeStream):
            sys.stderr = StdoutTeeStream(_ORIGINAL_STDERR, "stderr", level=logging.ERROR)

    return session_file, latest_file


def restore_stdout_stderr() -> None:
    """Khôi phục lại stdout/stderr gốc khi cần (dùng trong test teardown)."""
    global _ORIGINAL_STDOUT, _ORIGINAL_STDERR, _CONFIGURED
    sys.stdout = _ORIGINAL_STDOUT
    sys.stderr = _ORIGINAL_STDERR
    _CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Lấy logger có tên chuẩn."""
    return logging.getLogger(name)
