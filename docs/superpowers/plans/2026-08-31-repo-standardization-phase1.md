# Chuẩn hoá repo AIC2026 — Pha 1 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chuẩn hoá cấu trúc thư mục, tên module, kích thước file và toàn bộ tầng tài liệu của repo AIC2026 mà **không đổi một chút hành vi nào** của hệ thống.

**Architecture:** Gom `scripts/` theo *thời điểm chạy* (runtime vs offline) thay vì theo chủ đề; tách 3 file quá lớn thành module một-trách-nhiệm với `index_store.py` sở hữu singleton index; đổi `test_eval/` thành `tests/` chuẩn pytest; rút 7 file `.md` ở root xuống 4. Giữ nguyên tiền tố import `scripts.` nên **không câu import nào phải đổi vì lý do cấu trúc**.

**Tech Stack:** Python 3.11 (`.venv`), pytest (mới thêm), numpy/pandas, git mv.

**Spec:** [docs/superpowers/specs/2026-08-31-repo-standardization-design.md](../specs/2026-08-31-repo-standardization-design.md)

## Global Constraints

- **KHÔNG đổi hành vi.** Mọi thay đổi phải giữ nguyên kết quả. 4 lỗi thuật toán đã biết (mặc định model Q&A, `top_k_video` TRAKE, fallback strict monotonic, chấm điểm ứng viên đào sâu) thuộc **Pha 2** — không đụng trong plan này.
- **Tiêu chí cứng sau MỖI task đụng code:** `golden_kis_snapshot.py --check` phải in `KHỚP TUYỆT ĐỐI` và thoát code 0. Mốc: `digest=81448536a4f1245f`.
- **Không shim, không alias tương thích ngược.** Đổi tên/đường dẫn thì cập nhật hết call site; để lại alias là tái tạo đúng vấn đề đang sửa.
- **Mọi import nội bộ dùng tiền tố `scripts.`** (`from scripts.agent.tools.X import ...`). Không bao giờ đặt `scripts/` lên `sys.path`.
- Python chạy qua `.venv\Scripts\python.exe`. Shell trong plan này viết theo bash (Git Bash); trên PowerShell đổi `/` thành `\` ở đường dẫn.
- Comment và tài liệu viết **tiếng Việt có dấu**. `video_id` không kèm `.mp4`.
- Dùng `git mv` (không `mv` + `git add`) để git giữ được lịch sử đổi tên.

---

### Task 1: Dọn rác gốc repo và khai báo pytest

**Files:**
- Xoá: `graphify-out/`, `providers_import.csv`, `providers_import.json`, `.venv-broken/`, mọi `__pycache__/`
- Modify: `.gitignore`, `requirements.txt`

**Interfaces:**
- Consumes: (không)
- Produces: `pytest` khả dụng trong `.venv` cho mọi task sau.

- [x] **Step 1: Xác nhận đây đúng là rác không track git**

```bash
git ls-files graphify-out providers_import.csv providers_import.json .venv-broken
```
Expected: không in ra gì (rỗng = không file nào được track → xoá an toàn).

- [x] **Step 2: Xoá**

```bash
rm -rf graphify-out providers_import.csv providers_import.json .venv-broken
find . -name __pycache__ -type d -not -path "./.venv/*" -not -path "./frontend/node_modules/*" -exec rm -rf {} +
```

- [x] **Step 3: Bổ sung `.gitignore`**

Thêm vào cuối `.gitignore`:

```gitignore
# Venv hỏng để lại khi cài lại môi trường
.venv-broken/
```

- [x] **Step 4: Thêm pytest vào `requirements.txt`**

Thêm ngay dưới dòng `python-dotenv==1.2.3`:

```
pytest==8.4.2                # chạy bộ test tất định trong tests/unit (xem tests/README.md)
```

- [x] **Step 5: Cài và xác nhận**

```bash
.venv/Scripts/python.exe -m pip install "pytest==8.4.2"
.venv/Scripts/python.exe -m pytest --version
```
Expected: in ra `pytest 8.4.2`.

- [x] **Step 6: Commit**

```bash
git add .gitignore requirements.txt
git commit -m "chore: don rac goc repo (graphify-out, providers_import, .venv-broken) va khai bao pytest"
```

---

### Task 2: `test_eval/` → `tests/`, thêm `conftest.py`, sửa bug double-load

**Files:**
- Move: `test_eval/Eval/*` → `tests/eval/`, `test_eval/Test/*` → `tests/e2e/`, `test_eval/{sample_queries.json,sotuyen1_bo_de_thi.csv,thunghiem_bo_de_thi.csv}` → `tests/data/`, `test_eval/README.md` → `tests/README.md`
- Create: `tests/conftest.py`
- Modify (hằng đường dẫn): `tests/eval/run_eval.py:65`, `tests/e2e/golden_kis_snapshot.py:38`, `tests/e2e/score_pipelines.py:43-45`, `tests/e2e/test_phase{3,4,5,6}_*.py` (hằng `EVAL_SET_PATH`)
- Modify (bug double-load): `tests/e2e/test_smoke_tools.py`, `tests/e2e/test_smoke_pipelines.py`

**Interfaces:**
- Consumes: pytest từ Task 1.
- Produces: `tests/conftest.py` đặt repo root lên `sys.path` cho toàn bộ pytest — Task 8 dựa vào đó để xoá boilerplate.

- [x] **Step 1: Di chuyển bằng `git mv`**

```bash
mkdir -p tests/eval tests/e2e tests/data tests/unit
git mv test_eval/Eval/* tests/eval/
git mv test_eval/Test/* tests/e2e/
git mv test_eval/sample_queries.json test_eval/sotuyen1_bo_de_thi.csv test_eval/thunghiem_bo_de_thi.csv tests/data/
git mv test_eval/README.md tests/README.md
rmdir test_eval/Eval test_eval/Test test_eval 2>/dev/null || true
```

- [x] **Step 2: Tạo `tests/conftest.py`**

```python
"""
conftest.py — Đặt repo root lên sys.path cho toàn bộ bộ test.

Đây là ĐIỂM DUY NHẤT làm việc này cho pytest. Nhờ nó, các module chỉ-được-import trong
scripts/ không cần lặp lại khối `sys.path.insert` của riêng mình (xem CLAUDE.md).

Không bao giờ đặt scripts/ lên sys.path — làm vậy khiến Python nạp cùng một module dưới hai
tên (`agent.tools.retrieve` và `scripts.agent.tools.retrieve`), tức là nạp index + SigLIP hai
bản. Xem docs/decisions-log.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
```

- [x] **Step 3: Sửa hằng đường dẫn**

`tests/e2e/golden_kis_snapshot.py` dòng 38:
```python
_EVAL_SET = _ROOT / "tests" / "eval" / "eval_ground_truth.json"
```

`tests/e2e/score_pipelines.py` dòng 43-45:
```python
_EVAL_SET_PATH = _ROOT / "tests" / "eval" / "eval_ground_truth.json"
_DEFAULT_OUT = _ROOT / "docs" / "reports" / "eval_e2e_scores.md"
_DEFAULT_BASELINE = _ROOT / "tests" / "e2e" / "e2e_baseline.json"
```

`tests/eval/run_eval.py` dòng 65:
```python
_DEFAULT_OUT = _REPO_ROOT / "docs" / "reports" / "eval_baseline_comparison.md"
```

Trong `tests/e2e/test_phase3_rerank.py`, `test_phase4_trake.py`, `test_phase5_ocr.py`, `test_phase6_margin_sweep.py`, đổi mọi dòng có dạng:
```python
EVAL_SET_PATH = _ROOT / "test_eval" / "Eval" / "eval_ground_truth.json"
```
thành:
```python
EVAL_SET_PATH = _ROOT / "tests" / "eval" / "eval_ground_truth.json"
```

> `_REPO_ROOT = _THIS_DIR.parent.parent` trong `run_eval.py:53` và `widen_gt_windows.py:34`, và `_ROOT = Path(__file__).resolve().parents[2]` trong `tests/e2e/*` **vẫn đúng** sau khi di chuyển (`tests/eval/x.py` → parent → `tests` → parent → repo root). Không đổi.

- [x] **Step 4: Sửa bug double-load ở 2 smoke test**

Trong `tests/e2e/test_smoke_tools.py`, thay khối dòng 19-21:
```python
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"  # test_eval/Test/ -> repo root -> scripts
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
```
bằng:
```python
_ROOT = Path(__file__).resolve().parents[2]   # tests/e2e/ -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
```

rồi đổi 4 câu import bên trong các hàm:
```python
from scripts.agent.tools.retrieve import fast_retrieve
from scripts.agent.tools.ocr_lookup import get_objects, objects_contain_keywords
from scripts.agent.config import call_llm
from scripts.agent.tools.rewrite import rewrite_query
```

Làm y hệt cho `tests/e2e/test_smoke_pipelines.py` (khối `_SCRIPTS` dòng 19-21), rồi đổi 3 import:
```python
from scripts.agent.pipeline_kis import run_kis
from scripts.agent.pipeline_qa import run_qa
from scripts.agent.pipeline_trake import run_trake
```

> Đây là phần còn sót của bug đã ghi trong `EXPERIMENT.md`: đặt `scripts/` lên `sys.path` rồi `from agent...` khiến index + SigLIP nạp **hai bản**. `ocr_lookup` sẽ được đổi tên ở Task 4 — ở task này giữ nguyên tên cũ.

- [x] **Step 5: Quét sạch chuỗi `test_eval` còn sót trong code**

```bash
grep -rn "test_eval" --include=*.py tests scripts
```
Sửa từng dòng còn lại (đa số nằm trong docstring hướng dẫn chạy) thành đường dẫn `tests\...` tương ứng. Chạy lại lệnh trên tới khi không còn kết quả.

- [x] **Step 6: Nghiệm thu**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/e2e/golden_kis_snapshot.py --check
```
Expected: `KHỚP TUYỆT ĐỐI trên 18 câu`, exit 0.

```bash
.venv/Scripts/python.exe -m pytest tests/e2e/test_rrf_fusion.py tests/e2e/test_qa_answer_contract.py -q
```
Expected: tất cả PASS (đây là lần đầu 2 file này thực sự chạy được).

- [x] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: test_eval/ -> tests/ (eval|e2e|data) + conftest.py, sua bug nap index 2 ban o smoke test"
```

---

### Task 3: `preprocess/` + `experiments/` → `scripts/offline/`

**Files:**
- Move: `scripts/preprocess/captions/*` → `scripts/offline/captions/`, `scripts/preprocess/ocr/*` → `scripts/offline/ocr/`, `scripts/preprocess/shards/*` → `scripts/offline/shards/`, `scripts/experiments/analyze_frame_similarity.py` → `scripts/offline/analysis/`
- Move: `scripts/agent/tools/es_index.py`, `scripts/agent/tools/vlm_ocr_caption.py` → `scripts/offline/ocr/`
- Modify: `scripts/offline/ocr/index_ocr_es.py` (2 câu import)

**Interfaces:**
- Consumes: (không)
- Produces: `scripts/offline/` là bucket thứ tư chính thức; Task 10 sẽ ghi vào CLAUDE.md.

- [x] **Step 1: Xác nhận `es_index` + `vlm_ocr_caption` chỉ dùng offline**

```bash
grep -rn "es_index\|vlm_ocr_caption" --include=*.py scripts tests | grep -v "scripts/agent/tools/es_index.py\|scripts/agent/tools/vlm_ocr_caption.py"
```
Expected: chỉ ra kết quả trong `scripts/preprocess/ocr/index_ocr_es.py`. Nếu có file khác → **dừng lại**, báo lại, đừng di chuyển.

- [x] **Step 2: Di chuyển**

```bash
mkdir -p scripts/offline/captions scripts/offline/ocr scripts/offline/shards scripts/offline/analysis
git mv scripts/preprocess/captions/* scripts/offline/captions/
git mv scripts/preprocess/ocr/* scripts/offline/ocr/
git mv scripts/preprocess/shards/* scripts/offline/shards/
git mv scripts/experiments/analyze_frame_similarity.py scripts/offline/analysis/
git mv scripts/agent/tools/es_index.py scripts/offline/ocr/es_index.py
git mv scripts/agent/tools/vlm_ocr_caption.py scripts/offline/ocr/vlm_ocr_caption.py
rmdir scripts/preprocess/captions scripts/preprocess/ocr scripts/preprocess/shards scripts/preprocess scripts/experiments 2>/dev/null || true
```

- [x] **Step 3: Sửa import trong `scripts/offline/ocr/index_ocr_es.py`**

```python
from scripts.offline.ocr.es_index import ...
from scripts.offline.ocr.vlm_ocr_caption import ...
```
(giữ nguyên danh sách tên được import, chỉ đổi đường dẫn module)

- [x] **Step 4: Thêm `__init__.py` cho package mới**

```bash
for d in scripts/offline scripts/offline/captions scripts/offline/ocr scripts/offline/shards scripts/offline/analysis; do
  test -f "$d/__init__.py" || echo '' > "$d/__init__.py"
done
```

- [x] **Step 5: Nghiệm thu**

```bash
grep -rn "scripts.preprocess\|scripts/preprocess\|scripts.experiments\|scripts/experiments" --include=*.py --include=*.md . | grep -v docs/_archive
```
Expected: rỗng (trừ `docs/_archive/`). Sửa nốt nếu còn.

```bash
.venv/Scripts/python.exe -c "import scripts.offline.ocr.es_index; import scripts.offline.ocr.vlm_ocr_caption; print('offline import OK')"
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/e2e/golden_kis_snapshot.py --check
```
Expected: `offline import OK`, rồi `KHỚP TUYỆT ĐỐI`.

- [x] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: gom preprocess/ + experiments/ thanh scripts/offline/, chuyen es_index + vlm_ocr_caption ra khoi agent/tools"
```

---

### Task 4: Đổi tên `ocr_lookup.py` → `objects_lookup.py`

**Files:**
- Move: `scripts/agent/tools/ocr_lookup.py` → `scripts/agent/tools/objects_lookup.py`
- Modify: `scripts/agent/pipeline_qa.py`, `scripts/agent/pipeline_trake.py`, `scripts/agent/tools/answer_qa.py`, `tests/e2e/test_smoke_tools.py`

**Interfaces:**
- Consumes: (không)
- Produces: `scripts.agent.tools.objects_lookup` với API không đổi: `get_objects(video_id, n)`, `get_objects_for_hits(hits)`, `objects_contain_keywords(...)`, hằng `DEFAULT_SCORE_THRESHOLD`.

- [x] **Step 1: Liệt kê call site**

```bash
grep -rn "ocr_lookup" --include=*.py scripts tests
```
Expected: 4 file (`pipeline_qa.py`, `pipeline_trake.py`, `answer_qa.py`, `tests/e2e/test_smoke_tools.py`) + chính file đó.

- [x] **Step 2: Đổi tên và cập nhật call site**

```bash
git mv scripts/agent/tools/ocr_lookup.py scripts/agent/tools/objects_lookup.py
grep -rl "ocr_lookup" --include=*.py scripts tests | xargs sed -i 's/ocr_lookup/objects_lookup/g'
```

- [x] **Step 3: Sửa docstring đầu `objects_lookup.py`**

Đổi dòng mô tả đầu file thành:

```python
"""
objects_lookup.py — Đọc Objects JSON (Faster R-CNN / OpenImages) đã tính sẵn, offline.

ĐÂY KHÔNG PHẢI OCR: module chỉ trả về TÊN OBJECT chung chung ("person", "car", "fish"), không
đọc được chữ, số, giá hay biển hiệu trên khung hình. Muốn đọc chữ thật → scripts/agent/tools/ocr_read.py.

(Tên cũ `ocr_lookup.py` đã bỏ 2026-08-31 vì gây hiểu nhầm đúng điều trên.)
"""
```
Giữ nguyên phần còn lại của docstring cũ (usage, ghi chú ngưỡng) bên dưới.

- [x] **Step 4: Nghiệm thu**

```bash
grep -rn "ocr_lookup" --include=*.py --include=*.md . | grep -v docs/_archive
```
Expected: rỗng (trừ `docs/_archive/`).

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/e2e/golden_kis_snapshot.py --check
```
Expected: `KHỚP TUYỆT ĐỐI`.

- [x] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: ocr_lookup.py -> objects_lookup.py (module doc Objects JSON, khong lam OCR)"
```

---

### Task 5: Tách `retrieve.py` → `index_store.py` + `retrieve.py` + `hybrid.py` + `frames.py`

> **Task rủi ro nhất của plan.** Nghiệm thu bằng golden snapshot là bắt buộc, không bỏ qua.

**Files:**
- Create: `scripts/agent/tools/index_store.py`, `scripts/agent/tools/hybrid.py`, `scripts/agent/tools/frames.py`
- Modify: `scripts/agent/tools/retrieve.py`, `scripts/agent/pipeline_kis.py`, `scripts/agent/pipeline_qa.py`, `scripts/api/main.py`, `scripts/api/routers/kis.py`, `scripts/api/routers/images.py`, `scripts/agent/tools/rerank.py`

**Interfaces:**
- Consumes: (không)
- Produces:
  - `index_store.get_index(qa: bool = False) -> tuple[np.ndarray, pd.DataFrame, Callable[[str], np.ndarray]]`
  - `index_store.preload() -> None`
  - `index_store.row_to_hit(meta: pd.DataFrame, row_idx: int, score: float) -> dict` — **điểm duy nhất** cộng `frame_idx + 1`
  - `index_store.key_index(qa: bool = False) -> dict[tuple[str, int], int]`
  - `index_store.load_model(tag: str) -> tuple[np.ndarray, pd.DataFrame, Callable]`
  - `index_store.encode_mean(texts: list[str], qa: bool = False) -> np.ndarray`
  - `retrieve.fast_retrieve`, `fast_retrieve_for_video`, `fast_retrieve_qa`, `fast_retrieve_multi` — chữ ký **không đổi**
  - `hybrid.hybrid_retrieve`, `hybrid.fast_retrieve_multi_model`, `hybrid.SPARSE_TOP_K` — chữ ký **không đổi**
  - `frames.get_neighbor_frames`, `frames.get_all_frames`, `frames.get_keyframe_path` — chữ ký **không đổi**

- [x] **Step 1: Tạo `index_store.py`**

Chuyển nguyên văn (không sửa logic) từ `retrieve.py` sang: khối `sys.stdout.reconfigure`, `_SCRIPTS_DIR`/`_REPO_ROOT`, `_MODEL_TAG`/`_QA_MODEL_TAG`, mọi biến global `_MATRIX`/`_META`/`_ENCODE_FN`/`_QA_*`/`_KEY_INDEX`/`_QA_KEY_INDEX`, `_add_jpg_paths()`, `_load_model()`, `_ensure_loaded()`, `_ensure_qa_loaded()`, `preload()`, `_row_to_hit()`, `_get_key_index()`, `_encode_mean()`.

Đổi tên thành API công khai:

```python
def get_index(qa: bool = False):
    """Trả về (matrix, meta, encode_fn) của không gian embedding tương ứng. Nạp lười, 1 lần/process."""
    if qa:
        _ensure_qa_loaded()
        return _QA_MATRIX, _QA_META, _QA_ENCODE_FN
    _ensure_loaded()
    return _MATRIX, _META, _ENCODE_FN


def key_index(qa: bool = False) -> dict:
    """{(video_id, n): chỉ số dòng} — dùng để map kết quả BM25 về dòng meta dense."""
    return _get_key_index(qa=qa)


def row_to_hit(meta, row_idx: int, score: float) -> dict:
    """Dựng hit dict chuẩn từ 1 dòng meta.

    ĐÂY LÀ ĐIỂM DUY NHẤT trong toàn repo quy đổi frame_id = frame_idx + 1 (BTC đếm frame từ 1,
    index đếm từ 0). Không được cộng/trừ frame_id ở bất kỳ chỗ nào khác — xem CLAUDE.md.
    """
    row = meta.iloc[row_idx]
    frame_idx = int(row["frame_idx"])
    return {
        "video_id":  row["video_id"],
        "n":         int(row["n"]),
        "frame_idx": frame_idx,
        "frame_id":  frame_idx + 1,
        "pts_time":  float(row["pts_time"]),
        "score":     float(score),
        "jpg_path":  row["jpg_path"] if isinstance(row["jpg_path"], str) else None,
    }


def encode_mean(texts: list[str], qa: bool = False):
    """Trung bình + chuẩn hoá L2 nhiều cách diễn đạt của CÙNG 1 truy vấn (giữ nguyên `_encode_mean` cũ)."""
    ...
```

`load_model(tag)` = `_load_model()` cũ đổi tên (đã gồm `_add_jpg_paths`).

- [x] **Step 2: Viết lại `retrieve.py` chỉ còn 4 hàm truy vấn**

Mọi hàm dùng `index_store.get_index()` + `index_store.row_to_hit()` thay cho global và vòng lặp dựng dict thủ công. Ví dụ:

```python
from scripts.agent.tools import index_store


def fast_retrieve(query_text: str, top_k: int = 100) -> list[dict]:
    """Tìm top_k keyframe gần nhất với query_text bằng cosine similarity. Dùng cho KIS và TRAKE."""
    matrix, meta, encode_fn = index_store.get_index(qa=False)
    top_k = min(top_k, 1000)
    scores = matrix @ encode_fn(query_text)
    top_idx = np.argsort(-scores)[:top_k]
    return [index_store.row_to_hit(meta, int(i), float(scores[i])) for i in top_idx]
```

`fast_retrieve_qa` y hệt với `qa=True`. `fast_retrieve_for_video` giữ nguyên logic mask + `local_meta.reset_index(drop=True)`, dùng `row_to_hit(local_meta, idx, score)`. `fast_retrieve_multi` dùng `index_store.encode_mean(texts, qa=qa)`.

> **Cẩn thận:** `fast_retrieve` cũ trả `"n"` từ `row["n"]` và `jpg_path` theo cùng quy tắc `_row_to_hit`. Sau khi thống nhất qua `row_to_hit`, kết quả phải **giống hệt từng trường**. Golden snapshot sẽ bắt được nếu lệch.

- [x] **Step 3: Tạo `hybrid.py`**

Chuyển nguyên văn `SPARSE_TOP_K`, `hybrid_retrieve()`, `fast_retrieve_multi_model()` sang file mới. Thay `_ensure_loaded()/_MATRIX/_META` bằng `index_store.get_index(qa=qa)`, `_get_key_index` bằng `index_store.key_index(qa=qa)`, `_row_to_hit` bằng `index_store.row_to_hit`, `_encode_mean` bằng `index_store.encode_mean`, `_load_model` bằng `index_store.load_model`.

- [x] **Step 4: Tạo `frames.py`**

Chuyển `get_neighbor_frames()`, `get_all_frames()`, `get_keyframe_path()`. Ba hàm này **không** trả hit đầy đủ (không có score) nên giữ nguyên việc dựng dict tại chỗ, nhưng thêm comment trỏ về `index_store.row_to_hit` để người đọc biết vì sao có ngoại lệ:

```python
# Ba hàm dưới trả "tham chiếu frame" (không có score) cho tầng UI, không phải kết quả truy vấn,
# nên không đi qua index_store.row_to_hit(). Phép +1 vẫn phải khớp đúng quy ước ở đó.
```

- [x] **Step 5: Cập nhật mọi call site**

```bash
grep -rn "from scripts.agent.tools.retrieve import\|tools.retrieve import\|import retrieve" --include=*.py scripts tests
```
Với từng kết quả, đổi sang module mới theo bảng:

| Tên hàm | Module mới |
|---|---|
| `fast_retrieve`, `fast_retrieve_for_video`, `fast_retrieve_qa`, `fast_retrieve_multi` | `scripts.agent.tools.retrieve` (không đổi) |
| `hybrid_retrieve`, `fast_retrieve_multi_model` | `scripts.agent.tools.hybrid` |
| `get_neighbor_frames`, `get_all_frames`, `get_keyframe_path` | `scripts.agent.tools.frames` |
| `preload` | `scripts.agent.tools.index_store` |

Chú ý `scripts/agent/tools/rerank.py` có import trễ `from scripts.agent.tools.retrieve import fast_retrieve_for_video` bên trong `_bet_mode` — giữ nguyên module `retrieve`.

- [x] **Step 6: Nghiệm thu — tiêu chí cứng**

```bash
.venv/Scripts/python.exe -c "
from scripts.agent.tools import index_store, retrieve, hybrid, frames
print('import 4 module OK')
"
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/e2e/golden_kis_snapshot.py --check
```
Expected: `KHỚP TUYỆT ĐỐI trên 18 câu`, exit 0. **Nếu lệch dù 1 dòng → dừng, tìm nguyên nhân, không đi tiếp.**

- [x] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: tach retrieve.py thanh index_store + retrieve + hybrid + frames; gom quy doi frame_id ve 1 cho"
```

---

### Task 6: Tách `answer_qa.py` → `qa_prompts` + `qa_classify` + `qa_normalize`

**Files:**
- Create: `scripts/agent/tools/qa_prompts.py`, `scripts/agent/tools/qa_classify.py`, `scripts/agent/tools/qa_normalize.py`
- Modify: `scripts/agent/tools/answer_qa.py`, `tests/e2e/test_qa_answer_contract.py`

**Interfaces:**
- Consumes: `index_store`/`retrieve` từ Task 5 (chỉ trong khối `__main__` demo).
- Produces:
  - `qa_prompts`: `ANSWER_FROM_OBJECTS_PROMPT`, `ANSWER_FROM_IMAGES_PROMPT`, `VISUAL_COUNT_PROMPT`, `VISUAL_COUNT_REPAIR_PROMPT`, `OCR_HINT_TEMPLATE`, `TRANSCRIPT_HINT_TEMPLATE`, `CROSSCHECK_PROMPT`, `KNOWLEDGE_FALLBACK_PROMPT`, `CANONICAL_PROMPT` (đều là `str`)
  - `qa_classify`: `is_visual_count_question(q: str) -> bool`, `needs_text_reading(q: str) -> bool`, `asks_displayed_number(q: str) -> bool`
  - `qa_normalize`: `normalize_answer(s: str) -> str`, `is_non_answer(s: str) -> bool`, `extract_visual_count(s: str) -> str | None`, `canonicalize_answer(raw, question="", use_llm=True) -> str`, hằng `MAX_ANSWER_CHARS = 100`, `CANONICAL_MAX_WORDS = 5`
  - `answer_qa`: `answer_from_hits(question, hits, top_n=5) -> dict` — chữ ký và shape trả về **không đổi** (`answer`, `best_hit`, `confidence`, `method`)

> **Ba file mới ở task này KHÔNG được chứa khối `sys.path.insert`** — chúng chỉ-được-import, và
> `tests/conftest.py` (Task 2) đã lo phần đó. Chỉ import `from scripts...` trực tiếp.

- [x] **Step 1: Tạo `qa_prompts.py`**

Chuyển nguyên văn 9 hằng prompt (không sửa một ký tự nào trong nội dung prompt — đổi prompt = đổi hành vi LLM). Đầu file:

```python
"""
qa_prompts.py — Toàn bộ prompt template của nhánh Q&A, tách khỏi answer_qa.py.

Để riêng vì đây là phần được đọc/sửa nhiều nhất khi tinh chỉnh chất lượng trả lời, trong khi
logic 3 tầng ở answer_qa.py gần như không đổi. Sửa nội dung ở đây LÀ đổi hành vi hệ thống —
phải đo lại bằng tests/e2e/score_pipelines.py.
"""
```

- [x] **Step 2: Tạo `qa_classify.py`**

Chuyển `_VISUAL_COUNT_HINTS`, `_TEXT_READING_HINTS`, `_DISPLAYED_NUMBER_RE`, `_DIGIT_TOKEN_RE`, `is_visual_count_question()`, `_needs_text_reading()` → đổi tên công khai `needs_text_reading()`, `_asks_displayed_number()` → `asks_displayed_number()`.

- [x] **Step 3: Tạo `qa_normalize.py`**

Chuyển `MAX_ANSWER_CHARS`, `CANONICAL_MAX_WORDS`, `_CONVERSATIONAL_PREFIX`, `_NON_ANSWER_HINTS`, `_STANDALONE_INTEGER`, `_normalize_answer()` → `normalize_answer()`, `is_non_answer()`, `extract_visual_count()`, `canonicalize_answer()`. `canonicalize_answer` vẫn `from scripts.agent.config import call_llm` và dùng `CANONICAL_PROMPT` từ `qa_prompts`.

- [x] **Step 4: Rút gọn `answer_qa.py`**

Giữ lại: `_trace_evidence`, `_load_captions`, `_build_evidence_bundle`, `_trace_prompt`, `ocr_direct_answer`, `answer_from_hits`, `_crosscheck_answer`, `_CAPTION_CACHE`, `QA_EVIDENCE_TOP_N`. Thêm import:

```python
from scripts.agent.tools.qa_prompts import (
    ANSWER_FROM_OBJECTS_PROMPT, ANSWER_FROM_IMAGES_PROMPT, VISUAL_COUNT_PROMPT,
    VISUAL_COUNT_REPAIR_PROMPT, OCR_HINT_TEMPLATE, TRANSCRIPT_HINT_TEMPLATE,
    CROSSCHECK_PROMPT, KNOWLEDGE_FALLBACK_PROMPT,
)
from scripts.agent.tools.qa_classify import (
    is_visual_count_question, needs_text_reading, asks_displayed_number,
)
from scripts.agent.tools.qa_normalize import (
    canonicalize_answer, is_non_answer, normalize_answer, extract_visual_count,
)
```

Trong thân hàm đổi `_needs_text_reading(` → `needs_text_reading(`, `_asks_displayed_number(` → `asks_displayed_number(`, `_normalize_answer(` → `normalize_answer(`.

- [x] **Step 5: Cập nhật test đang import trực tiếp**

`tests/e2e/test_qa_answer_contract.py` đang có:
```python
from scripts.agent.tools.answer_qa import extract_visual_count, is_visual_count_question
```
đổi thành:
```python
from scripts.agent.tools.qa_classify import is_visual_count_question
from scripts.agent.tools.qa_normalize import extract_visual_count
```

- [x] **Step 6: Nghiệm thu**

```bash
.venv/Scripts/python.exe -m pytest tests/e2e/test_qa_answer_contract.py -q
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "
from scripts.agent.tools.answer_qa import _run_self_tests
_run_self_tests()
"
```
Expected: pytest PASS; self-test in `[answer_qa] Tat ca self-test PASS`.

- [x] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: tach answer_qa.py thanh qa_prompts + qa_classify + qa_normalize + answer_qa"
```

---

### Task 7: Tách thuật toán TRAKE ra `tools/trake_align.py`

**Files:**
- Create: `scripts/agent/tools/trake_align.py`
- Modify: `scripts/agent/pipeline_trake.py`

**Interfaces:**
- Consumes: `scripts.agent.tools.objects_lookup.get_objects` (Task 4), `scripts.agent.tools.sparse_index.tokenize`
- Produces:
  - `trake_align.find_best_increasing_chain(event_hits: list[list[dict]], strict: bool = True) -> list[dict] | None`
  - `trake_align.rule_plausibility(event_queries_en: list[str], chain: list[dict]) -> float`

- [x] **Step 1: Tạo `trake_align.py`**

Chuyển nguyên văn `_find_best_increasing_chain()` → `find_best_increasing_chain()` và `_rule_plausibility()` → `rule_plausibility()`, kèm nguyên vẹn docstring giải thích DP thắng greedy. Đầu file:

```python
"""
trake_align.py — Thuật toán căn chỉnh chuỗi mốc thời gian cho TRAKE (module thuần).

Tách khỏi pipeline_trake.py để phần thuật toán (quy hoạch động + chấm điểm rule) kiểm thử được
độc lập, không cần nạp index hay gọi LLM. pipeline_trake.py chỉ còn phần điều phối 3 giai đoạn.
"""
```

- [x] **Step 2: Sửa `pipeline_trake.py`**

Xoá 2 hàm vừa chuyển đi, thêm:
```python
from scripts.agent.tools.trake_align import find_best_increasing_chain, rule_plausibility
```
Đổi call site: `_find_best_increasing_chain(` → `find_best_increasing_chain(`, `_rule_plausibility(` → `rule_plausibility(`.

- [x] **Step 3: Chuyển phần self-test tương ứng**

Trong `_run_self_tests()` của `pipeline_trake.py`, các test 1/2/3/4/4c thao tác trên hai hàm vừa tách. Giữ nguyên chúng ở chỗ cũ trong task này (Task 8 sẽ chuyển sang pytest) — chỉ đổi tên hàm được gọi.

- [x] **Step 4: Nghiệm thu**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/agent/pipeline_trake.py --self-test
```
Expected: in `[trake] Test DP thang greedy: OK`, `[trake] Test strict monotonic: OK`, `[trake] Test cong rule-based: OK`.

- [x] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: tach DP + rule plausibility cua TRAKE ra tools/trake_align.py"
```

---

### Task 8: Chuyển self-test sang `tests/unit/` và xoá `sys.path` boilerplate

**Files:**
- Create: `tests/unit/test_fusion.py`, `test_temporal_nms.py`, `test_query_expand.py`, `test_rerank.py`, `test_answer_qa.py`, `test_pipeline_qa.py`, `test_trake_align.py`, `test_ocr_read.py`, `test_asr_lookup.py`, `test_sparse_index.py`
- Move: `tests/e2e/test_rrf_fusion.py`, `tests/e2e/test_qa_answer_contract.py` → `tests/unit/`
- Modify (xoá khối `sys.path`): `rerank.py`, `fusion.py`, `temporal_nms.py`, `query_expand.py`, `asr_lookup.py`, `index_store.py`, `hybrid.py`, `frames.py`, `trake_align.py`, `qa_prompts.py`, `qa_classify.py`, `qa_normalize.py`

**Interfaces:**
- Consumes: `tests/conftest.py` (Task 2) đặt repo root lên `sys.path`.
- Produces: `pytest tests/unit` là lệnh kiểm tra tất định của repo.

- [x] **Step 1: Đếm số assert hiện có (mốc để không làm mất test)**

```bash
grep -c "assert " scripts/agent/tools/fusion.py scripts/agent/tools/temporal_nms.py \
  scripts/agent/tools/query_expand.py scripts/agent/tools/rerank.py \
  scripts/agent/tools/answer_qa.py scripts/agent/pipeline_qa.py \
  scripts/agent/pipeline_trake.py scripts/agent/tools/ocr_read.py \
  scripts/agent/tools/asr_lookup.py scripts/agent/tools/sparse_index.py
```
Ghi lại tổng số. Sau khi chuyển xong, tổng số assert trong `tests/unit/` phải **≥** con số này.

- [x] **Step 2: Chuyển từng file, mỗi khối assert thành một hàm `test_*`**

Mẫu cho `tests/unit/test_fusion.py` (làm y hệt cho các file còn lại, mỗi nhóm assert trong khối `__main__` cũ thành một hàm test riêng, giữ nguyên từng câu assert và thông điệp lỗi):

```python
"""Test cho scripts/agent/tools/fusion.py — chuyển từ khối __main__ cũ, giữ nguyên mọi assert."""
from __future__ import annotations

from scripts.agent.tools.fusion import (
    reciprocal_rank_fusion, rrf_fuse_hits, RRF_K, W_DENSE, W_SPARSE,
)


def test_dung_hop_co_ban_uu_tien_key_ca_hai_he_thong_dong_y() -> None:
    dense = ["A", "B", "C"]
    sparse = ["B", "D", "E"]
    fused = reciprocal_rank_fusion([(dense, W_DENSE), (sparse, W_SPARSE)])
    keys = [key for key, _ in fused]
    assert keys[0] == "B", (
        f"B (dense #2 + sparse #1 — CẢ HAI hệ thống đồng ý) phải vượt A (chỉ dense #1): {fused}"
    )
    assert keys[1] == "A", f"A (dense #1, w=0.75) phải đứng ngay sau B: {fused}"
    assert keys.index("C") < keys.index("D"), "Dense #3 (w=0.75) phải trên sparse #2 (w=0.25)"
    assert set(keys) == {"A", "B", "C", "D", "E"}, "RRF phải giữ cả key chỉ có ở 1 hệ thống"


def test_danh_sach_rong_va_trong_so_0() -> None:
    dense = ["A", "B", "C"]
    only_dense = reciprocal_rank_fusion([(dense, W_DENSE), ([], W_SPARSE)])
    assert [k for k, _ in only_dense] == dense, "Sparse rỗng -> giữ nguyên thứ tự dense"
    assert reciprocal_rank_fusion([]) == []


def test_top_k_cat_dung_so_luong() -> None:
    fused = reciprocal_rank_fusion([(["A", "B", "C"], W_DENSE), (["B", "D"], W_SPARSE)], top_k=2)
    assert len(fused) == 2


def test_rrf_chi_phu_thuoc_thu_hang_khong_phu_thuoc_diem_goc() -> None:
    fused_a = reciprocal_rank_fusion([(["X", "Y"], 1.0)])
    assert abs(fused_a[0][1] - 1.0 / (RRF_K + 1)) < 1e-12, "Điểm RRF phải là w/(k+rank)"
```

Với `test_rerank.py`: khối `__main__` cũ có monkeypatch `_retrieve_module.fast_retrieve_for_video`. Trong pytest dùng fixture `monkeypatch`:

```python
def test_bet_mode_khong_loai_nham_ung_vien_trung_frame_idx(monkeypatch) -> None:
    import scripts.agent.tools.retrieve as retrieve_module
    monkeypatch.setattr(retrieve_module, "fast_retrieve_for_video",
                        lambda q, vid, top_k: [_fake_hit("A", 99, 0.85)])
    ...
```

Với `test_answer_qa.py` và `test_pipeline_qa.py`: khối cũ gán đè biến global (`call_llm = _fake_call_llm`). Dùng `monkeypatch.setattr(module, "call_llm", fake)` thay cho gán trực tiếp.

- [x] **Step 3: Xoá khối `__main__` self-test khỏi module nguồn**

Chỉ xoá phần self-test. **Giữ nguyên** khối `__main__` là CLI demo/công cụ ở: `retrieve.py`, `objects_lookup.py`, `rewrite.py`, `sparse_index.py` (giữ `--build`/`--query`, bỏ `--self-test`), `answer_qa.py` (giữ phần demo `fast_retrieve` cuối), `ocr_read.py`, `pipeline_kis.py`, `pipeline_qa.py`, `pipeline_trake.py`, `config.py`.

- [x] **Step 4: Xoá `sys.path` boilerplate ở module chỉ-được-import**

Xoá khối dưới đây khỏi 12 file liệt kê trong **Files** (chúng không có `__main__` chạy trực tiếp):

```python
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
```

**KHÔNG xoá** ở file có `__main__` — bỏ nhầm sẽ làm `python scripts/agent/tools/sparse_index.py --build` gãy với `ModuleNotFoundError` (đúng lỗi đã xảy ra ở commit `f569a62`).

**Chỉ xoá đúng 3 dòng `sys.path`, KHÔNG xoá hằng đường dẫn dữ liệu.** Nhiều file dùng chính biến
`_ROOT`/`_SCRIPTS_DIR` để định vị `data/` — ví dụ `index_store._add_jpg_paths()` dựng
`data/extracted/keyframes/...` từ `_SCRIPTS_DIR`, và `sparse_index.py` dựng `OBJECTS_DIR`/`CACHE_DIR`
từ `_ROOT`. Xoá nhầm hằng này thì `jpg_path` thành `None` toàn bộ và BM25 không tìm thấy cache.
Giữ lại phép gán `_ROOT = ...`, chỉ bỏ hai dòng `if str(_ROOT) not in sys.path: sys.path.insert(...)`
(và `import sys` nếu không còn ai dùng).

- [x] **Step 5: Chuyển 2 file pytest sẵn có**

```bash
git mv tests/e2e/test_rrf_fusion.py tests/unit/
git mv tests/e2e/test_qa_answer_contract.py tests/unit/
```
Rồi xoá khối `_ROOT`/`sys.path.insert` ở đầu hai file đó (đã có `conftest.py` lo).

- [x] **Step 6: Nghiệm thu**

```bash
.venv/Scripts/python.exe -m pytest tests/unit -q
grep -rc "assert " tests/unit/*.py | awk -F: '{s+=$2} END {print "Tong assert trong tests/unit:", s}'
```
Expected: pytest tất cả PASS; tổng assert ≥ con số ghi ở Step 1.

```bash
for f in sparse_index retrieve objects_lookup ocr_read; do
  .venv/Scripts/python.exe scripts/agent/tools/$f.py --help >/dev/null 2>&1 || \
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "import runpy; runpy.run_path('scripts/agent/tools/$f.py', run_name='__not_main__')"
done
echo "CLI entry point con import duoc"
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/e2e/golden_kis_snapshot.py --check
```
Expected: không `ModuleNotFoundError`; golden `KHỚP TUYỆT ĐỐI`.

- [x] **Step 7: Commit**

```bash
git add -A
git commit -m "test: chuyen self-test tu khoi __main__ sang tests/unit (pytest), xoa sys.path boilerplate o module chi-duoc-import"
```

---

### Task 9: Sắp xếp lại `docs/` và gộp `DECISION.md` + `EXPERIMENT.md`

**Files:**
- Create: `docs/decisions-log.md`
- Move: nhiều (xem Step 1)
- Delete: `DECISION.md`, `EXPERIMENT.md` (sau khi gộp)

**Interfaces:**
- Consumes: `_DEFAULT_OUT` đã trỏ `docs/reports/` từ Task 2.
- Produces: cây `docs/` để Task 10 tham chiếu.

- [x] **Step 1: Di chuyển**

```bash
mkdir -p docs/rules docs/training docs/reports docs/presentation
git mv "docs/Thong tin vong So tuyen AIC2026.md" docs/rules/
git mv "docs/Bo De Kiem Thu va Phan Tich Bay AIC2026.md" docs/rules/
git mv docs/Training/* docs/training/
rmdir docs/Training 2>/dev/null || true
git mv docs/eval_baseline_comparison.md docs/eval_e2e_scores.md docs/eval_siglip2_comparison.md docs/reports/
git add docs/presentation_aic2026.html docs/team_presentation_guide.md docs/diagrams
git mv docs/presentation_aic2026.html docs/team_presentation_guide.md docs/presentation/
git mv docs/diagrams docs/presentation/diagrams
git add docs/_archive/PipelineDPDiagram.png docs/_archive/manifest_vitl14.csv
```

- [x] **Step 2: Tạo `docs/decisions-log.md`**

Cấu trúc:

```markdown
# Nhật ký quyết định & bài học — AIC2026

> Gộp từ `DECISION.md` (vì sao đã chọn thế) và `EXPERIMENT.md` (đã sai thế nào, sửa ra sao),
> 2026-08-31. Hai file cũ có cùng thể loại nội dung và cùng tần suất đọc — chỉ đọc khi cần
> truy nguyên một quyết định — nên tách đôi chỉ tạo thêm một chỗ để trôi khỏi thực tế.
>
> Đọc file này khi: định đảo ngược một quyết định cũ, hoặc sắp lặp lại một đường debug đã đi.
> KHÔNG ghi tiến độ ở đây (→ PLAN.md) và không ghi quy ước (→ CLAUDE.md).

## Phần 1 — Quyết định kiến trúc & quy trình
[nguyên văn nội dung DECISION.md, giữ thứ tự và tiêu đề mục]

## Phần 2 — Sai lầm đã mắc và cách sửa
[nguyên văn nội dung EXPERIMENT.md, giữ thứ tự và tiêu đề mục]
```

Chuyển **nguyên văn** nội dung 2 file, không tóm tắt lại — chúng là bản ghi lịch sử.

- [x] **Step 3: Bổ sung 2 mục mới vào Phần 2**

```markdown
### Bug nạp index 2 bản — phần còn sót ở smoke test (2026-08-31)

Bản sửa 2026-08-27 chuẩn hoá import về tiền tố `scripts.` chỉ phủ `scripts/`, không phủ
`test_eval/`. `test_smoke_tools.py` và `test_smoke_pipelines.py` vẫn đặt `scripts/` lên
`sys.path` rồi `from agent.tools.retrieve import ...` — nạp SigLIP + index hai bản suốt từ đó.
Bài học: khi sửa lỗi kiểu "quy ước bị vi phạm", phải grep TOÀN repo chứ không chỉ thư mục đang sửa.

### OCR chết âm thầm vì chứng chỉ hết hạn (phát hiện 2026-08-31)

`ocr_read` tải config VietOCR từ `vocr.vn`, chứng chỉ SSL của site đã hết hạn →
`read_text_from_hits()` luôn trả rỗng. Cache offline `data/extracted/ocr_text_paddleocr/` cũng
chưa build. Hệ quả: OCR Direct Overwrite không bao giờ kích hoạt, gợi ý OCR không vào prompt
Vision. Module bắt lỗi và chạy tiếp rất gọn nên **không ai nhận ra tín hiệu đã mất**.
Bài học: degradation êm ái cần đi kèm một chỗ báo cáo trạng thái, nếu không nó thành lỗi vô hình.
```

- [x] **Step 4: Xoá 2 file cũ**

```bash
git rm DECISION.md EXPERIMENT.md
```

- [x] **Step 5: Sửa mọi tham chiếu tới đường dẫn cũ**

```bash
grep -rn "DECISION.md\|EXPERIMENT.md\|docs/Training\|docs/eval_" --include=*.py --include=*.md . | grep -v docs/_archive | grep -v decisions-log.md
```
Sửa hết sang `docs/decisions-log.md` / `docs/training/` / `docs/reports/`. Chạy lại tới khi rỗng.

- [x] **Step 6: Nghiệm thu**

```bash
test -f docs/decisions-log.md && test ! -f DECISION.md && test ! -f EXPERIMENT.md && echo "gop OK"
ls docs/rules docs/training docs/reports docs/presentation
```

- [x] **Step 7: Commit**

```bash
git add -A
git commit -m "docs: sap xep docs/ theo nhom (rules|training|reports|presentation) va gop DECISION+EXPERIMENT thanh decisions-log"
```

---

### Task 10: Viết lại 4 file tài liệu gốc

**Files:**
- Modify: `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, `PLAN.md`

**Interfaces:**
- Consumes: cây thư mục cuối cùng từ Task 1-9.
- Produces: tài liệu khớp thực tế — điều kiện để Task 12 grep sạch.

- [x] **Step 1: `CLAUDE.md`**

Cập nhật, giữ nguyên giọng văn và cấu trúc mục hiện có:
- Mục **Folder Structure**: ghi 4 bucket thật (`agent` / `api` / `submit` / `offline`), bỏ mọi nhắc tới `scripts/index.py`, `scripts/app.py`, `preprocess/`, `experiments/`, `test_eval/`.
- Mục **Code Rules**: sửa luật `frame_id` thành *"quy đổi `frame_id = frame_idx + 1` chỉ xảy ra ở `scripts/agent/tools/index_store.py:row_to_hit()`"*.
- Mục **Quick Start**: đổi mọi lệnh `test_eval\...` sang `tests\...`, thêm `python -m pytest tests/unit`.
- Thêm quy ước test: self-test → `tests/unit/`; khối `__main__` chỉ dành cho CLI demo/công cụ.
- Thêm quy ước `sys.path`: giữ ở file có `__main__`, bỏ ở file chỉ-được-import; không bao giờ đặt `scripts/` lên path.

- [x] **Step 2: `ARCHITECTURE.md`**

- Vẽ lại sơ đồ §1: thay `scripts/app.py (Gradio)` bằng `frontend/ (React) → scripts/api/ (FastAPI)`.
- Bảng §2: bỏ dòng `scripts/index.py`, đổi `rank.py` → `rerank.py`, `ocr_lookup.py` → `objects_lookup.py`, thêm dòng cho `index_store.py`, `hybrid.py`, `frames.py`, `trake_align.py`, `qa_prompts.py`, `qa_classify.py`, `qa_normalize.py`.
- Thêm mục **Tham số đã hiệu chỉnh**, ghi rõ thang đo gốc:

```markdown
| Tham số | Giá trị | Hiệu chỉnh trên | Ghi chú |
|---|---|---|---|
| `MARGIN_THRESHOLD` | 0.012 | cosine của `clip_vitb32` (**đã retire**) | Thang cosine SigLIP hẹp hơn (~0.05-0.15). Giá trị chưa hiệu chỉnh lại — Pha 2. |
| `MIN_TIME_GAP` | 3.0s | bước lấy keyframe BTC (~2.5-3s) | Thực chất chỉ loại keyframe kề, không loại cảnh trùng dài. |
| `SPARSE_TOP_K` | 50 | 18 câu KIS, 2026-08-28 | 500 ứng viên BM25 làm Final 0.667 → 0.656. |
| `RECALL_HEAD_N` | 20 | 18 câu KIS, 2026-08-31 | Final 0.667 → 0.722. |
```

- [x] **Step 3: `README.md`**

Đổi mọi lệnh sang cây mới; bỏ phần mô tả Gradio là UI hiện hành; thêm `pytest tests/unit` vào phần kiểm tra.

- [x] **Step 4: `PLAN.md`**

Thêm mục **Pha 2 — sửa lỗi hành vi (chưa làm)**, liệt kê đúng 6 việc, mỗi việc một dòng kèm chứng cứ:

```markdown
1. `_QA_MODEL_TAG` mặc định là `siglip` trong khi mọi tài liệu ghi `siglip2`
   (retrieve.py). Bake-off: QA Final siglip2=0.440 vs siglip=0.120.
2. TRAKE `top_k_video=20` khoá cứng R@50 = R@100 = R@20 — mở rộng không tốn lượt LLM nào.
3. TRAKE `strict_monotonic` loại thẳng video khi không có chuỗi hợp lệ; nên rơi về
   `strict=False` thay vì bỏ (keyframe cách nhau ~3s, chuỗi động tác nhanh gói trong 1 keyframe).
4. `_bet_mode` chấm điểm ứng viên đào sâu bằng `W_DENSE/(RRF_K + len(hits) + 1 + i)` — luôn
   thấp hơn mọi ứng viên trong pool 500, nên chúng không bao giờ lọt vào top-100.
5. OCR chết: `vocr.vn` hết hạn chứng chỉ SSL + `data/extracted/ocr_text_paddleocr/` chưa build.
6. Q&A chỉ trích answer riêng cho 3 cụm video đầu; ~97 dòng còn lại mang answer của video khác.
```

- [x] **Step 5: Nghiệm thu**

```bash
grep -rn "scripts/index.py\|scripts/app.py\|test_eval\|ocr_lookup\|preprocess/\|experiments/\|rank\.py" \
  README.md CLAUDE.md ARCHITECTURE.md PLAN.md
```
Expected: rỗng.

- [x] **Step 6: Commit**

```bash
git add README.md CLAUDE.md ARCHITECTURE.md PLAN.md
git commit -m "docs: viet lai 4 tai lieu goc cho khop cay thu muc va code thuc te"
```

---

### Task 11: Chuẩn hoá comment tiếng Việt có dấu

**Files:**
- Modify: mọi `.py` trong `scripts/agent/`, `scripts/api/`, `scripts/submit/`

**Interfaces:**
- Consumes: cây file cuối cùng (làm SAU mọi task tách/di chuyển để không sửa hai lần).
- Produces: (không có API mới)

- [x] **Step 1: Liệt kê file cần sửa**

```bash
grep -rln "khong\|duoc\|ung vien\|tuong ung\|thu hang" --include=*.py scripts/agent scripts/api scripts/submit
```

- [x] **Step 2: Sửa từng file một, chỉ comment và docstring**

Bỏ dấu → có dấu. **Không đụng vào:** chuỗi trong `print()` có tiền tố `[module]` nếu chúng đang được test so khớp, tên biến/hàm, và **toàn bộ nội dung prompt LLM trong `qa_prompts.py`** (tiếng Anh, đổi = đổi hành vi).

Sau mỗi file, chạy ngay:
```bash
.venv/Scripts/python.exe -c "import scripts.agent.tools.<ten_module>; print('OK')"
```

- [x] **Step 3: Nghiệm thu**

```bash
.venv/Scripts/python.exe -m pytest tests/unit -q
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/e2e/golden_kis_snapshot.py --check
```
Expected: pytest PASS, golden `KHỚP TUYỆT ĐỐI`.

- [x] **Step 4: Commit**

```bash
git add -A
git commit -m "style: thong nhat comment/docstring tieng Viet co dau trong scripts/agent, api, submit"
```

---

### Task 12: Nghiệm thu toàn bộ Pha 1

**Files:**
- Modify: `tests/README.md`

**Interfaces:**
- Consumes: toàn bộ Task 1-11.
- Produces: bằng chứng Pha 1 không đổi hành vi.

- [x] **Step 1: Tiêu chí cứng — golden snapshot**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/e2e/golden_kis_snapshot.py --check
```
Expected: `mốc digest=81448536a4f1245f | lần này digest=81448536a4f1245f`, `KHỚP TUYỆT ĐỐI trên 18 câu`, exit 0.

- [x] **Step 2: Đối chiếu `run_eval`**

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe tests/eval/run_eval.py \
  --models siglip --all-features --out /tmp/eval_after.md
diff tests/e2e/eval_before_snapshot.md /tmp/eval_after.md
```
Expected: `diff` không in gì (khác biệt duy nhất được phép là dòng ngày/giờ nếu file có).

- [x] **Step 3: Bộ test đơn vị**

```bash
.venv/Scripts/python.exe -m pytest tests/unit -q
```
Expected: tất cả PASS.

- [x] **Step 4: Smoke test API**

```bash
AIC_MODE=test PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/api/_smoke_test.py
```
Expected: `[smoke] TAT CA BUOC PASS`.

- [x] **Step 5: Quét tham chiếu chết**

```bash
grep -rn "scripts/index\.py\|scripts/app\.py\|test_eval\|ocr_lookup\|scripts\.preprocess\|scripts\.experiments\|rank\.py" \
  --include=*.py --include=*.md . | grep -v docs/_archive | grep -v node_modules
```
Expected: rỗng.

- [x] **Step 6: Mỗi module import được độc lập**

```bash
.venv/Scripts/python.exe - <<'PY'
import importlib, pkgutil, scripts
bad = []
for m in pkgutil.walk_packages(scripts.__path__, "scripts."):
    if ".offline." in m.name or m.name.endswith("_smoke_test"):
        continue
    try:
        importlib.import_module(m.name)
    except Exception as e:
        bad.append((m.name, type(e).__name__, str(e)[:80]))
print("LOI:", bad) if bad else print("Moi module runtime import duoc")
PY
```
Expected: `Moi module runtime import duoc`.

- [x] **Step 7: Cập nhật `tests/README.md`**

Ghi 3 tầng test và khi nào dùng cái nào:

```markdown
| Thư mục | Cần gì | Tất định | Khi nào chạy |
|---|---|---|---|
| `tests/unit/` | không cần data/API | có | mọi lần sửa code — `pytest tests/unit` |
| `tests/eval/` | cần `data/extracted/` | có | so sánh backbone, đo thuật toán retrieval |
| `tests/e2e/` | cần data + `OPENROUTER_API_KEY` | không (trừ `golden_kis_snapshot.py`) | trước khi nộp bài |

`tests/e2e/golden_kis_snapshot.py` là ngoại lệ: nó tất định (KIS không gọi LLM) và là lưới
regression cho toàn bộ đường KIS production. Chạy `--check` sau mọi refactor.
```

- [x] **Step 8: Commit cuối**

```bash
git add -A
git commit -m "docs: ghi 3 tang test vao tests/README.md — ket thuc pha 1 chuan hoa"
```

---

## Sau khi xong

Pha 1 kết thúc khi Task 12 xanh toàn bộ. **Pha 2** (sửa 6 lỗi hành vi đã ghi trong `PLAN.md`) là một plan riêng — mỗi lỗi sửa xong phải chạy `golden_kis_snapshot.py --save` để chốt mốc mới, vì lúc đó hành vi *cố ý* thay đổi.
