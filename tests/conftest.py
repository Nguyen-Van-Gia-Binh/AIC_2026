"""
conftest.py — Đặt repo root lên sys.path cho toàn bộ bộ test.

Đây là ĐIỂM DUY NHẤT làm việc này cho pytest. Nhờ nó, các module chỉ-được-import trong scripts/
không cần lặp lại khối `sys.path.insert` của riêng mình (xem CLAUDE.md).

Không bao giờ đặt scripts/ lên sys.path — làm vậy khiến Python nạp cùng một module dưới hai tên
(`agent.tools.retrieve` và `scripts.agent.tools.retrieve`), tức là nạp index + SigLIP hai bản.
Xem docs/decisions-log.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
