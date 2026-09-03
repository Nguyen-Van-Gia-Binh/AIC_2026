# Migrate to Split Ground Truth Files and Remove Monolithic File Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay thế toàn bộ các nơi trỏ vào file tổng thể `tests/eval/eval_ground_truth.json` bằng việc trỏ trực tiếp vào 3 file con đã tách (`eval_ground_truth_kis.json`, `eval_ground_truth_qa.json`, `eval_ground_truth_trake.json`) thông qua module loader tập trung `tests/eval/gt_loader.py`, cập nhật tất cả test harness, script đo đạc và tài liệu, sau đó xoá bỏ hoàn toàn file `eval_ground_truth.json` để kiểm soát dữ liệu dễ dàng và rõ ràng hơn.

**Architecture:** Xây dựng module `tests/eval/gt_loader.py` làm tầng truy cập dữ liệu ground truth chuẩn hoá (hỗ trợ nạp theo type riêng lẻ, danh sách type hoặc hợp nhất cả 3 file theo thứ tự xác định); cập nhật tất cả harness (`score_pipelines.py`, `run_eval.py`, `golden_kis_snapshot.py`, `test_phase3_rerank.py`, `test_phase4_trake.py`, `sweep_rerank.py`, `widen_gt_windows.py`, `normalize_gt.py`); cập nhật test suite và xoá file `eval_ground_truth.json` cũ sau khi toàn bộ test pass 100%.

**Tech Stack:** Python 3.13 (`pathlib`, `json`, `typing`), `pytest` test suite.

**Spec:** Yêu cầu người dùng ngày 2026-08-31 về việc chuyển toàn bộ hệ thống sang dùng 3 file ground truth con KIS / QA / TRAKE và xoá bỏ file `eval_ground_truth.json` cũ.

## Global Constraints

- **Bảo toàn dữ liệu**: Tuyệt đối không làm thay đổi hay thất thoát 91 entries hiện có trong 3 file `eval_ground_truth_kis.json` (59), `eval_ground_truth_qa.json` (17), `eval_ground_truth_trake.json` (15).
- **Không để sót tham chiếu chết**: Tất cả các script, harness, unit test và docstring phải được chuyển đổi sang nạp từ các file con hoặc qua `gt_loader.py`.
- **Thực thi an toàn**: Chỉ xoá `tests/eval/eval_ground_truth.json` khi đã hoàn thành việc chuyển đổi code và toàn bộ unit test chạy qua (100% green).

---

### Task 1: Xây dựng Module Loader Tập Trung (`tests/eval/gt_loader.py`) & Unit Tests

**Files:**
- Create: `tests/eval/gt_loader.py`
- Create: `tests/unit/test_gt_loader.py`

**Interfaces:**
- `get_gt_path(query_type: str, eval_dir: Path | None = None) -> Path`: Trả về đường dẫn file JSON của từng loại (`KIS`, `QA`, `TRAKE`).
- `load_ground_truth(types: str | list[str] | None = None, eval_dir: Path | None = None) -> list[dict]`: Nạp danh sách entries theo loại yêu cầu (mặc định nạp cả 3 file gộp lại: KIS -> QA -> TRAKE).
- `save_ground_truth(entries: list[dict], query_type: str, eval_dir: Path | None = None) -> Path`: Ghi danh sách entries vào đúng file con tương ứng.

- [x] **Step 1: Viết failing test cho `gt_loader.py`**

Tạo `tests/unit/test_gt_loader.py`:

```python
"""
test_gt_loader.py — Kiểm tra module nạp dữ liệu ground truth tập trung từ 3 file con.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from tests.eval.gt_loader import get_gt_path, load_ground_truth, save_ground_truth


def test_get_gt_path_returns_correct_sub_file_paths(tmp_path):
    assert get_gt_path("KIS", tmp_path) == tmp_path / "eval_ground_truth_kis.json"
    assert get_gt_path("qa", tmp_path) == tmp_path / "eval_ground_truth_qa.json"
    assert get_gt_path("TRAKE", tmp_path) == tmp_path / "eval_ground_truth_trake.json"

    with pytest.raises(ValueError, match="Không hỗ trợ type"):
        get_gt_path("INVALID", tmp_path)


def test_load_ground_truth_loads_single_type(tmp_path):
    kis_mock = [{"query_id": "k1", "type": "KIS"}]
    (tmp_path / "eval_ground_truth_kis.json").write_text(json.dumps(kis_mock), encoding="utf-8")

    loaded = load_ground_truth(types="KIS", eval_dir=tmp_path)
    assert loaded == kis_mock


def test_load_ground_truth_loads_and_combines_all_types(tmp_path):
    kis_mock = [{"query_id": "k1", "type": "KIS"}]
    qa_mock = [{"query_id": "q1", "type": "QA"}]
    trake_mock = [{"query_id": "t1", "type": "TRAKE"}]

    (tmp_path / "eval_ground_truth_kis.json").write_text(json.dumps(kis_mock), encoding="utf-8")
    (tmp_path / "eval_ground_truth_qa.json").write_text(json.dumps(qa_mock), encoding="utf-8")
    (tmp_path / "eval_ground_truth_trake.json").write_text(json.dumps(trake_mock), encoding="utf-8")

    loaded = load_ground_truth(eval_dir=tmp_path)
    assert len(loaded) == 3
    assert [d["query_id"] for d in loaded] == ["k1", "q1", "t1"]


def test_save_ground_truth_writes_to_correct_file(tmp_path):
    qa_data = [{"query_id": "q2", "type": "QA"}]
    saved_path = save_ground_truth(qa_data, "QA", eval_dir=tmp_path)
    assert saved_path == tmp_path / "eval_ground_truth_qa.json"
    assert json.loads(saved_path.read_text(encoding="utf-8")) == qa_data
```

- [x] **Step 2: Chạy test để xác nhận fail**

Run: `.venv\Scripts\pytest.exe tests\unit\test_gt_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.eval.gt_loader'`

- [x] **Step 3: Cài đặt module `tests/eval/gt_loader.py`**

Tạo `tests/eval/gt_loader.py`:

```python
"""
gt_loader.py — Quản lý và nạp dữ liệu ground truth từ 3 file con KIS / QA / TRAKE.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

_EVAL_DIR = Path(__file__).resolve().parent

GT_FILENAMES: Dict[str, str] = {
    "KIS": "eval_ground_truth_kis.json",
    "QA": "eval_ground_truth_qa.json",
    "TRAKE": "eval_ground_truth_trake.json",
}


def get_gt_path(query_type: str, eval_dir: Optional[Path] = None) -> Path:
    """Trả về đường dẫn file JSON của loại câu hỏi tương ứng."""
    t = str(query_type).strip().upper()
    if t not in GT_FILENAMES:
        raise ValueError(f"Không hỗ trợ type '{query_type}'. Các type hợp lệ: {list(GT_FILENAMES.keys())}")
    base_dir = Path(eval_dir).resolve() if eval_dir else _EVAL_DIR
    return base_dir / GT_FILENAMES[t]


def load_ground_truth(
    types: Optional[Union[str, Iterable[str]]] = None,
    eval_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Nạp danh sách entries ground truth từ các file con.
    
    Args:
        types: Loại câu hỏi cần nạp ('KIS', 'QA', 'TRAKE', hoặc chuỗi cách nhau dấu phẩy 'kis,qa',
               hoặc iterable ['KIS', 'TRAKE']). Nếu None hoặc 'ALL', nạp cả 3 file theo thứ tự KIS -> QA -> TRAKE.
        eval_dir: Thư mục chứa các file ground truth (mặc định tests/eval/).
    
    Returns:
        Danh sách gộp các query entries.
    """
    if types is None or (isinstance(types, str) and types.strip().upper() == "ALL"):
        selected_types = ["KIS", "QA", "TRAKE"]
    elif isinstance(types, str):
        selected_types = [t.strip().upper() for t in types.split(",") if t.strip()]
    else:
        selected_types = [str(t).strip().upper() for t in types if str(t).strip()]

    combined: List[Dict[str, Any]] = []
    base_dir = Path(eval_dir).resolve() if eval_dir else _EVAL_DIR

    for t in selected_types:
        path = get_gt_path(t, base_dir)
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"File {path} phải chứa một JSON array ở top-level")
        combined.extend(data)

    return combined


def save_ground_truth(
    entries: List[Dict[str, Any]],
    query_type: str,
    eval_dir: Optional[Path] = None,
) -> Path:
    """Ghi danh sách entries vào file con tương ứng với query_type."""
    path = get_gt_path(query_type, eval_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
```

- [x] **Step 4: Chạy test để xác nhận pass**

Run: `.venv\Scripts\pytest.exe tests\unit\test_gt_loader.py -v`
Expected: PASS

- [x] **Step 5: Commit**

```powershell
git add tests/eval/gt_loader.py tests/unit/test_gt_loader.py
git commit -m "feat(eval): add centralized ground truth loader module for split sub-files"
```

---

### Task 2: Chuyển đổi các Harness & Script Đánh giá sang Dùng File Con / `gt_loader`

**Files:**
- Modify: `tests/e2e/score_pipelines.py`
- Modify: `tests/eval/run_eval.py`
- Modify: `tests/e2e/golden_kis_snapshot.py`
- Modify: `tests/e2e/test_phase3_rerank.py`
- Modify: `tests/e2e/test_phase4_trake.py`
- Modify: `tests/eval/widen_gt_windows.py`
- Modify: `tests/eval/sweep_rerank.py`

**Interfaces:**
- Thay thế các biến đường dẫn cứng `_EVAL_SET_PATH = ... / "eval_ground_truth.json"` bằng việc gọi `load_ground_truth()` hoặc trỏ trực tiếp vào `eval_ground_truth_{type}.json`.

- [x] **Step 1: Cập nhật `tests/e2e/score_pipelines.py`**

Thay thế việc đọc trực tiếp `eval_ground_truth.json`:
- Import `from tests.eval.gt_loader import load_ground_truth, _EVAL_DIR`
- Trong `main()`:
  - Nếu `args.eval_set` là file cụ thể (người dùng tự truyền file riêng qua CLI): đọc file đó.
  - Nếu là mặc định: gọi `eval_set = load_ground_truth(types=args.types)`.

- [x] **Step 2: Cập nhật `tests/eval/run_eval.py`**

- Import `from tests.eval.gt_loader import load_ground_truth`
- Sửa hàm `load_eval_set(path: Path | None)`:
  - Nếu `path` là `None` hoặc trỏ vào thư mục `tests/eval`: gọi `load_ground_truth()`.
  - Nếu là file cụ thể: đọc file đó.
- Sửa mặc định CLI `--eval-set` thành `None` (mặc định nạp toàn bộ qua `load_ground_truth()`).

- [x] **Step 3: Cập nhật `tests/e2e/golden_kis_snapshot.py`**

- Đổi `_EVAL_SET = _ROOT / "tests" / "eval" / "eval_ground_truth_kis.json"`
- Hàm `_load_kis_queries()`: nạp trực tiếp file KIS.

- [x] **Step 4: Cập nhật `tests/e2e/test_phase3_rerank.py` và `tests/e2e/test_phase4_trake.py`**

- Trong `test_phase3_rerank.py`: dùng `load_ground_truth(types=["KIS", "QA"])`.
- Trong `test_phase4_trake.py`: trỏ `EVAL_SET_PATH = _ROOT / "tests" / "eval" / "eval_ground_truth_trake.json"`.

- [x] **Step 5: Cập nhật `tests/eval/widen_gt_windows.py` và `tests/eval/sweep_rerank.py`**

- Trong `sweep_rerank.py`: đổi `_DEFAULT_GT` trỏ về `tests/eval/eval_ground_truth_kis.json`.
- Trong `widen_gt_windows.py`: hỗ trợ xử lý cả 3 file con `eval_ground_truth_kis.json`, `eval_ground_truth_qa.json`, `eval_ground_truth_trake.json`.

- [x] **Step 6: Chạy kiểm thử tự động xác minh các harness**

Run: `.venv\Scripts\python.exe tests\e2e\score_pipelines.py --self-test`
Expected: `[score_pipelines] self-test PASS`

Run: `.venv\Scripts\pytest.exe tests\unit`
Expected: 100% PASS

- [x] **Step 7: Commit**

```powershell
git add tests/e2e/score_pipelines.py tests/eval/run_eval.py tests/e2e/golden_kis_snapshot.py tests/e2e/test_phase3_rerank.py tests/e2e/test_phase4_trake.py tests/eval/widen_gt_windows.py tests/eval/sweep_rerank.py
git commit -m "refactor(eval): update benchmark harnesses and evaluation scripts to use split ground truth files"
```

---

### Task 3: Cập nhật Công Cụ Chuẩn Hoá & Ghép Dữ Liệu (`normalize_gt.py`, `split_eval_gt.py`)

**Files:**
- Modify: `tests/eval/normalize_gt.py`
- Modify: `tests/eval/split_eval_gt.py`

**Interfaces:**
- `normalize_gt.py`: Hỗ trợ `--merge-split` (tự động phân loại KIS/QA/TRAKE và nối vào đúng file con tương ứng mà không cần file tổng thể).

- [x] **Step 1: Cập nhật `tests/eval/normalize_gt.py`**

- Tích hợp `gt_loader`:
  - Khi người dùng truyền `--merge <file>`, nếu truyền file con cụ thể thì nối vào file đó.
  - Nếu truyền `--merge-split` (hoặc truyền thư mục `tests/eval/`), tự động lọc entries theo `type` và nối vào từng file con `eval_ground_truth_kis.json`, `eval_ground_truth_qa.json`, `eval_ground_truth_trake.json`.

- [x] **Step 2: Cập nhật `tests/eval/split_eval_gt.py`**

- Cập nhật mô tả và mặc định: `split_eval_gt.py` đóng vai trò tiện ích phân tách từ bất kỳ file v1 nguồn nào ra 3 file con.

- [x] **Step 3: Chạy test cho `normalize_gt.py` và `split_eval_gt.py`**

Run: `.venv\Scripts\pytest.exe tests\unit\test_normalize_gt.py tests\unit\test_split_eval_gt.py -v`
Expected: PASS

- [x] **Step 4: Commit**

```powershell
git add tests/eval/normalize_gt.py tests/eval/split_eval_gt.py
git commit -m "feat(eval): update normalize_gt to support merging directly into split ground truth files"
```

---

### Task 4: Cập nhật Test Suite, Xoá File `eval_ground_truth.json` Cũ và Cập nhật Tài Liệu

**Files:**
- Modify: `tests/unit/test_eval_ground_truth.py`
- Modify: `tests/unit/test_normalize_gt.py`
- Modify: `tests/unit/test_split_eval_gt.py`
- Delete: `tests/eval/eval_ground_truth.json`
- Modify: `tests/eval/EVAL_GUIDE.md`
- Modify: `tests/eval/AUDIT_REPORT.md`
- Modify: `tests/README.md`
- Modify: `README.md`
- Modify: `GEMINI.md`

**Interfaces:**
- Đảm bảo toàn bộ hệ thống hoạt động hoàn hảo khi KHÔNG CÒN file `eval_ground_truth.json`.

- [x] **Step 1: Cập nhật `tests/unit/test_eval_ground_truth.py` và `tests/unit/test_normalize_gt.py`**

- Sửa `test_eval_ground_truth.py`: hàm `_load()` nạp thông qua `load_ground_truth()`.
- Sửa `test_normalize_gt.py`: `test_tag_chuan_phu_het_tag_dang_dung_trong_bo_eval` nạp qua `load_ground_truth()`.

- [x] **Step 2: Xoá bỏ hoàn toàn file `tests/eval/eval_ground_truth.json`**

Thực thi xoá file:
```powershell
git rm tests/eval/eval_ground_truth.json
```

- [x] **Step 3: Cập nhật các tài liệu hướng dẫn và mô tả repo**

- `tests/eval/EVAL_GUIDE.md`: Cập nhật bảng và lệnh merge trỏ vào các file con.
- `tests/eval/AUDIT_REPORT.md`: Cập nhật ghi chú phạm vi trỏ vào 3 file con.
- `tests/README.md`, `README.md`, `GEMINI.md`: Cập nhật cấu trúc thư mục mô tả 3 file con (`eval_ground_truth_kis.json`, `eval_ground_truth_qa.json`, `eval_ground_truth_trake.json`).

- [x] **Step 4: Chạy toàn bộ test suite để xác minh không còn lỗi nào**

Run: `.venv\Scripts\pytest.exe tests\unit`
Expected: 100% tests pass (tất cả 90+ tests pass, không có lỗi file not found).

- [x] **Step 5: Commit**

```powershell
git add tests/unit/ tests/eval/ tests/README.md README.md GEMINI.md
git commit -m "chore(eval): delete monolithic eval_ground_truth.json and finalize split ground truth migration"
```

---

## Verification Plan

### Automated Tests
1. **Kiểm thử bộ loader và các file con**:
   ```powershell
   .venv\Scripts\pytest.exe tests\unit\test_gt_loader.py tests\unit\test_split_eval_gt.py tests\unit\test_eval_ground_truth.py -v
   ```
2. **Kiểm thử tính năng merge của normalize_gt**:
   ```powershell
   .venv\Scripts\pytest.exe tests\unit\test_normalize_gt.py -v
   ```
3. **Chạy toàn bộ pytest unit tests**:
   ```powershell
   .venv\Scripts\pytest.exe tests\unit
   ```
4. **Kiểm tra không còn tham chiếu rác đến `eval_ground_truth.json` trong source code active**:
   ```powershell
   .venv\Scripts\python.exe -c "import subprocess; out = subprocess.check_output(['git', 'grep', 'eval_ground_truth.json', '--', 'scripts/', 'tests/'], encoding='utf-8', errors='ignore'); print('Matches in code:', out)"
   ```
   (Chỉ còn trong các tài liệu log/archive hoặc comment giải thích lịch sử nếu có, không còn trong code logic).

### Manual Verification
1. Xác nhận file `tests/eval/eval_ground_truth.json` đã được xoá hoàn toàn khỏi git và ổ đĩa.
2. Xác nhận 3 file `eval_ground_truth_kis.json` (59), `eval_ground_truth_qa.json` (17), `eval_ground_truth_trake.json` (15) hiện diện đầy đủ và hợp lệ.
