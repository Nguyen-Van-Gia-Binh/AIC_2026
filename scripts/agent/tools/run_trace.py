"""
run_trace.py — Dấu vết có cấu trúc cho MỖI lần chạy pipeline (1 query = 1 run).

Ghi ngay lúc chạy, gói gọn trong 2 file cùng tên:
    logs/runs/<YYYYMMDD>/<run_id>.json   # cho máy đọc — lọc / thống kê
    logs/runs/<YYYYMMDD>/<run_id>.txt    # cho người đọc — toàn bộ 1 query gọn 1 màn hình

run_id = <YYYYMMDD>_<HHMMSS>_<host>_<rand6>, ví dụ 20260903_182557_binhpc_a1b2c3
  - host  : socket.gethostname() đã lọc ký tự lạ → file bạn bè gửi qua Zalo không đụng file mình
  - rand6 : secrets.token_hex(3) → hai run cùng giây trên cùng máy không trùng

Kill switch: đặt biến môi trường AIC_TRACE=0 → RunTrace thành no-op, KHÔNG ghi file (run_id
vẫn sinh ra để tra cứu). Dùng cho golden snapshot / môi trường không muốn rác.

Module THUẦN: chỉ import stdlib, không đụng index / model / LLM / config.py → không vòng import.
`config.call_llm()` chỉ gọi ngược lại `current_trace()` + `trace.add_llm_call(...)`.
"""
from __future__ import annotations

import contextvars
import json
import os
import re
import secrets
import socket
import time
import traceback
from contextlib import contextmanager, nullcontext
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1
_RESPONSE_MAX = 300  # cắt câu trả lời LLM cho gọn file

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUT_DIR = _REPO_ROOT / "logs" / "runs"

# contextvar (KHÔNG phải global) → an toàn với các request đồng thời của uvicorn
_CURRENT: contextvars.ContextVar["RunTrace | None"] = contextvars.ContextVar(
    "aic_current_run_trace", default=None
)


def tracing_enabled() -> bool:
    """False khi AIC_TRACE=0 (kill switch). Mặc định bật."""
    return os.environ.get("AIC_TRACE", "").strip() != "0"


def current_trace() -> "RunTrace | None":
    """Trace đang mở của luồng hiện tại, hoặc None nếu đang ở ngoài `with RunTrace(...)`."""
    return _CURRENT.get()


def _host_tag() -> str:
    raw = re.sub(r"[^A-Za-z0-9]", "", socket.gethostname() or "").lower()
    return raw[:12] or "host"


def _new_run_id() -> str:
    now = datetime.now()
    return f"{now:%Y%m%d}_{now:%H%M%S}_{_host_tag()}_{secrets.token_hex(3)}"


class RunTrace:
    """Context manager gom dấu vết 1 lần chạy pipeline rồi ghi ra file khi thoát `with`."""

    def __init__(
        self,
        query_type: str,
        query_text: str,
        params: dict[str, Any] | None = None,
        out_dir: str | Path | None = None,
    ) -> None:
        self.run_id: str = _new_run_id()
        self._enabled: bool = tracing_enabled()
        self._out_dir: Path = Path(out_dir) if out_dir is not None else _DEFAULT_OUT_DIR
        self._t0: float = time.perf_counter()
        self._token: contextvars.Token | None = None
        self._llm_seq: int = 0

        self._data: dict[str, Any] = {
            "run_id": self.run_id,
            "schema_version": SCHEMA_VERSION,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "host": _host_tag(),
            "aic_mode": os.environ.get("AIC_MODE", ""),
            "query_type": query_type,
            "query_text": query_text,
            "params": dict(params or {}),
            "stages": [],
            "retrieval": None,
            "rerank": None,
            "qa": None,
            "trake": None,
            "llm_calls": [],
            "result": {"video_id": None, "frame_ids": None, "answer": None},
            "totals": {"wall_ms": 0.0, "llm_calls": 0, "llm_ms": 0.0, "llm_by_model": {}},
            "errors": [],
        }

    # -- context manager ----------------------------------------------------
    def __enter__(self) -> "RunTrace":
        self._token = _CURRENT.set(self)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            self.add_error("__run__", exc)
        if self._token is not None:
            _CURRENT.reset(self._token)
            self._token = None
        self._data["totals"]["wall_ms"] = round((time.perf_counter() - self._t0) * 1000.0, 1)
        if self._enabled:
            self._write()
        return None  # không nuốt exception

    # -- ghi dữ liệu ------------------------------------------------------
    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Đo ms + ok/lỗi của một khâu. Exception vẫn được ghi lại rồi ném tiếp."""
        t0 = time.perf_counter()
        ok = True
        try:
            yield
        except Exception as error:
            ok = False
            self.add_error(name, error)
            raise
        finally:
            self._data["stages"].append(
                {"name": name, "ms": round((time.perf_counter() - t0) * 1000.0, 1), "ok": ok}
            )

    def record(self, section: str, data: Any) -> None:
        """Gắn dữ liệu có cấu trúc cho một section: retrieval / rerank / qa / trake."""
        if section not in ("retrieval", "rerank", "qa", "trake"):
            raise ValueError(f"section không hợp lệ: {section!r}")
        self._data[section] = data

    def add_llm_call(
        self,
        *,
        purpose: str,
        model: str,
        key_index: str = "",
        ms: float = 0.0,
        response: str = "",
        candidate: str | None = None,
        prompt_chars: int | None = None,
    ) -> None:
        self._llm_seq += 1
        text = response if isinstance(response, str) else str(response)
        if len(text) > _RESPONSE_MAX:
            text = text[:_RESPONSE_MAX]
        self._data["llm_calls"].append(
            {
                "seq": self._llm_seq,
                "purpose": purpose,
                "model": model,
                "key_index": key_index,
                "ms": round(float(ms), 1),
                "candidate": candidate,
                "prompt_chars": prompt_chars,
                "response": text,
            }
        )
        totals = self._data["totals"]
        totals["llm_calls"] += 1
        totals["llm_ms"] = round(totals["llm_ms"] + float(ms), 1)
        totals["llm_by_model"][model] = totals["llm_by_model"].get(model, 0) + 1

    def add_error(self, stage: str, exc: BaseException, fallback: str | None = None) -> None:
        self._data["errors"].append(
            {
                "stage": stage,
                "type": type(exc).__name__,
                "message": str(exc),
                "fallback": fallback,
                "traceback": "".join(traceback.format_exception_only(type(exc), exc)).strip(),
            }
        )

    def set_result(
        self,
        video_id: str | None = None,
        frame_ids: list[int] | None = None,
        answer: str | None = None,
    ) -> None:
        self._data["result"] = {"video_id": video_id, "frame_ids": frame_ids, "answer": answer}

    # -- xuất file ---------------------------------------------------------
    def _write(self) -> None:
        day_dir = self._out_dir / self.run_id[:8]
        day_dir.mkdir(parents=True, exist_ok=True)
        (day_dir / f"{self.run_id}.json").write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (day_dir / f"{self.run_id}.txt").write_text(self._render_txt(), encoding="utf-8")

    def _render_txt(self) -> str:
        d = self._data
        tot = d["totals"]
        lines: list[str] = []
        lines.append(f"run_id : {d['run_id']}")
        lines.append(
            f"type   : {d['query_type'].upper():6s} mode={d['aic_mode'] or '?'}   "
            f"wall={tot['wall_ms'] / 1000:.1f}s   llm={tot['llm_calls']} calls / "
            f"{tot['llm_ms'] / 1000:.1f}s"
        )
        lines.append(f"query  : {d['query_text']!r}")
        lines.append("")

        if d["stages"]:
            seg = " · ".join(f"{s['name']} {s['ms']:.0f}ms" for s in d["stages"])
            lines.append(f"[stages]  {seg}")
        if d["retrieval"]:
            r = d["retrieval"]
            top = (r.get("candidates") or [])[:3]
            vids = ", ".join(str(c.get("video_id")) for c in top)
            lines.append(f"[retrieve] backbone={r.get('backbone')}  top=[{vids}]")
        if d["rerank"]:
            rr = d["rerank"]
            lines.append(
                f"[rerank]  margin_top2={rr.get('margin_top2')}  "
                f"gate_opened={rr.get('gate_opened')}"
            )
        if d["qa"]:
            q = d["qa"]
            lines.append(
                f"[qa]      tier={q.get('tier')}  source={q.get('evidence_source')}  "
                f"answer={q.get('normalized') or q.get('answer_raw')!r}"
            )
        if d["trake"]:
            tk = d["trake"]
            lines.append(
                f"[trake]   events={len(tk.get('events') or [])}  "
                f"candidates={tk.get('video_candidates')}"
            )
        if d["llm_calls"]:
            for c in d["llm_calls"]:
                lines.append(
                    f"[llm #{c['seq']}] {c['purpose']} ({c['model']}, key {c['key_index']}, "
                    f"{c['ms']:.0f}ms)"
                )

        res = d["result"]
        lines.append("")
        lines.append(
            f"[result]  video={res.get('video_id')}  frames={res.get('frame_ids')}  "
            f"answer={res.get('answer')!r}"
        )
        if d["errors"]:
            for e in d["errors"]:
                lines.append(f"[error]   {e['stage']}: {e['type']}: {e['message']}")
        else:
            lines.append("[errors]  none")
        return "\n".join(lines) + "\n"


class _NullTrace:
    """Null-object: pipeline gọi thoải mái khi caller không truyền trace, không ghi gì, không lỗi."""

    run_id = ""

    def __enter__(self) -> "_NullTrace":
        return self

    def __exit__(self, *exc) -> None:
        return None

    def stage(self, name: str):  # noqa: ARG002
        return nullcontext()

    def record(self, *a, **k) -> None:
        return None

    def add_llm_call(self, *a, **k) -> None:
        return None

    def add_error(self, *a, **k) -> None:
        return None

    def set_result(self, *a, **k) -> None:
        return None


NULL_TRACE = _NullTrace()
