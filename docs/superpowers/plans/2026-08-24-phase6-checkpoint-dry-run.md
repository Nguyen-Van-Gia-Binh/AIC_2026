# Phase 6 Checkpoint & Dry-run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Đóng Phase 6 (PLAN.md) — dọn 2 lỗi/cosmetic còn sót từ Phase 3/4/5, chuẩn bị công cụ đo
`TRAKE_CROSSCHECK_MARGIN`, chạy review tổng nhánh Phase 4, và soạn sẵn 2 "runbook" (checkpoint
benchmark + dry-run contest mode) dưới dạng lệnh copy-paste — **không tự chạy benchmark thật rồi tự
kết luận số liệu tốt/xấu**, vì người dùng đã yêu cầu tự chạy và tự đánh giá phần đó.

**Architecture:** Không đổi kiến trúc nào ở ARCHITECTURE.md — toàn bộ Phase 6 là sửa lỗi nhỏ + công
cụ đo lường + review + tài liệu quy trình. 2 việc có test tự động được (docstring, encoding) đi theo
flow sửa lỗi thường; margin-sweep script chỉ tự-test bằng dữ liệu giả lập (không gọi model/index thật,
không kết luận ngưỡng cuối cùng); checkpoint benchmark / dry-run là danh sách lệnh cho người dùng tự
chạy trên máy họ.

**Tech Stack:** Python qua `.venv` (không dùng pytest — self-test kiểu `if __name__ == "__main__"`,
đúng quy ước hiện có ở `rerank.py`/`test_phase4_trake.py`).

**Spec:** [PLAN.md §Phase 6](../../../PLAN.md), [ARCHITECTURE.md](../../../ARCHITECTURE.md).

## Global Constraints

- Freeze code 03/09/2026, nộp đợt 4 ngày 04/09/2026 — không merge thay đổi mới sau freeze, chỉ sửa
  blocking bug.
- Không đổi ngưỡng risk-aware ranking / margin cross-check TRAKE mà không hiệu chỉnh lại bằng
  `scripts/eval/run_eval.py` (hoặc benchmark phase-specific tương ứng) trên `queries/eval_ground_truth.json`
  trước (ARCHITECTURE.md §4).
- UI text và code comment viết bằng tiếng Việt, kể cả trong `scripts/agent/` và test script mới
  (CLAUDE.md).
- `snake_case` cho mọi tên hàm/biến mới. Không camelCase.
- Không gọi `litellm` trực tiếp ngoài `scripts/agent/config.py:call_llm()`.
- Không viết CSV/ZIP submission ở đâu ngoài `scripts/submit/build_submission.py`.
- Logging: `print()` với prefix `[module_name]`, không thêm logging framework mới.
- Repo không có pytest — mọi self-test là block `if __name__ == "__main__":` chạy bằng
  `.venv\Scripts\python.exe <file>.py` trực tiếp.

---

## Việc KHÔNG nằm trong danh sách Task dưới đây (giao cho người, không giao cho executor)

- **Mở rộng bộ eval TRAKE** (PLAN.md Phase 6, mục "chặn trước các mục dưới"): hiện chỉ có 4 câu TRAKE
  trong `queries/eval_ground_truth.json` (KIS=18, QA=5, TRAKE=4, tổng 27 — đã kiểm tra lại lúc viết
  plan này), `queries/EVAL_GUIDE.md` đề xuất ~10 câu TRAKE. Việc này cần **xem video thật** để gắn
  nhãn `gt_frame_start/end` — không có cách nào để 1 agent không xem được video làm thay. Người dùng
  (vai "eval owner", xem PLAN.md mục 0) tự làm theo quy trình đã có sẵn ở `EVAL_GUIDE.md`, dùng
  `.venv\Scripts\python.exe scripts\eval\lookup_frame.py <video_id> <giây>` để tra `frame_id`.
- **Freeze 03/09**: không phải việc code, chỉ là mốc quy trình — không merge gì mới sau ngày đó, trừ
  fix blocking bug.
- **Quyết định "no regression" / chọn giá trị `TRAKE_CROSSCHECK_MARGIN` cuối cùng**: Task 3 dưới đây
  chỉ dựng **công cụ đo**, không tự chọn số — người dùng đọc bảng kết quả rồi tự quyết theo đúng yêu
  cầu ("tôi đánh giá chính xác hơn bạn").

---

### Task 1: Sửa docstring lỗi thời ở `pipeline_trake.py`

**Files:**
- Modify: [scripts/agent/pipeline_trake.py:1-21](../../../scripts/agent/pipeline_trake.py#L1-L21)

**Interfaces:** Không đổi — chỉ sửa comment/docstring, không đổi bất kỳ signature/hành vi nào.

Bối cảnh: docstring đầu file vẫn ghi `fast_retrieve(100)` và `top-5 video candidates`, nhưng code
thật (dòng 161, 174) dùng `fast_retrieve(query_en, top_k=RETRIEVAL_POOL_SIZE)` (=500, import từ
`rerank.py`) và `top_k_video` mặc định là 20, không phải 5.

- [x] **Step 1: Đọc lại đúng 2 dòng cần sửa**

Nội dung hiện tại (dòng 4-9):

```python
Workflow co dinh 2 giai doan (khong de LLM tu quyet dinh so buoc):

Giai doan 1 - Retrieval:
  query tong quat -> rewrite -> fast_retrieve(100)
  -> group by video_id -> rank video theo tong score
  -> chon top-5 video candidates
```

- [x] **Step 2: Sửa lại cho khớp code thật**

```python
Workflow co dinh 2 giai doan (khong de LLM tu quyet dinh so buoc):

Giai doan 1 - Retrieval:
  query tong quat -> rewrite -> fast_retrieve(top_k=RETRIEVAL_POOL_SIZE)  # =500, xem rerank.py
  -> group by video_id -> rank video theo diem trung binh (video_avg)
  -> chon top_k_video video candidates (mac dinh 20, xem run_trake())
```

- [x] **Step 3: Verify không đổi hành vi**

Chạy self-test có sẵn của module (không tốn LLM call thật, chỉ chạy `_run_self_tests()` ở đầu
`__main__`):

```
.venv\Scripts\python.exe -c "import ast; ast.parse(open('scripts/agent/pipeline_trake.py', encoding='utf-8').read())"
```

Expected: không lỗi cú pháp (script này chỉ parse, không chạy toàn bộ pipeline — đủ để xác nhận sửa
docstring không làm hỏng file, không cần load index/model).

- [x] **Step 4: Commit**

```bash
git add scripts/agent/pipeline_trake.py
git commit -m "docs(phase6): fix stale fast_retrieve(100)/top-5 docstring in pipeline_trake.py"
```

---

### Task 2: Sửa `UnicodeEncodeError` khi in log tiếng Việt trên console Windows mặc định

**Files:**
- Modify: [scripts/agent/tools/retrieve.py:22-34](../../../scripts/agent/tools/retrieve.py#L22-L34)

**Interfaces:** Không đổi public API (`fast_retrieve`, `fast_retrieve_for_video`, `preload`) — chỉ
thêm 1 khối reconfigure stdout ở module-level, chạy 1 lần lúc import.

Bối cảnh (PLAN.md Phase 6): console Windows mặc định dùng code page cp1252, dòng
`print(f"[retrieve] ĐANG DÙNG MODEL: {_MODEL_TAG}")` (dòng 76) chứa ký tự `Đ` không encode được ở
cp1252 → crash `UnicodeEncodeError` ngay khi import `retrieve.py`. Test dưới đây mô phỏng đúng lỗi này
bằng cách bọc `sys.stdout` bằng 1 `TextIOWrapper` ép encoding `cp1252` (độc lập với code page thật của
máy chạy plan này — máy này đã set sẵn UTF-8 nên không tự nhiên reproduce được), rồi xác nhận
`sys.stdout.reconfigure(encoding="utf-8")` khắc phục.

- [x] **Step 1: Viết script tái hiện lỗi (trước khi sửa) để xác nhận chẩn đoán đúng**

Lưu tạm `scratch_repro.py` ở thư mục gốc repo:

```python
import io
import sys

# Mo phong console cp1252 (code page mac dinh Windows) bat ke code page that cua may dang chay —
# gia lap dung 1 bien so (encoding) de kiem tra chan doan, khong dung production code.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="cp1252", errors="strict")
print("[retrieve] ĐANG DÙNG MODEL: clip_vitb32")
```

Chạy: `.venv\Scripts\python.exe scratch_repro.py`
Expected: `UnicodeEncodeError: 'charmap' codec can't encode character 'Đ'...` — xác nhận đúng lỗi
PLAN.md mô tả trước khi sửa bất cứ gì.

- [x] **Step 2: Xoá script tái hiện lỗi**

```bash
rm scratch_repro.py
```

(Chỉ dùng để xác nhận chẩn đoán ở Step 1, không phải 1 phần deliverable.)

- [x] **Step 3: Thêm reconfigure stdout vào `retrieve.py`**

Thêm ngay sau khối import ở đầu file (sau dòng `import pandas as pd`, trước
`_SCRIPTS_DIR = Path(...)`):

```python
# Console Windows mac dinh dung code page cp1252, khong encode duoc ky tu co dau (vd "Đ" trong log
# ben duoi) -> UnicodeEncodeError ngay luc import module nay. Ep stdout sang UTF-8 tai day (diem
# import duy nhat cua module nay) thay vi doi nguoi dung phai tu set PYTHONIOENCODING=utf-8 truoc khi
# chay (PLAN.md Phase 6). Boc try/except vi 1 so moi truong (vd stdout da bi redirect/pipe trong test)
# khong ho tro reconfigure().
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
```

- [x] **Step 4: Verify lỗi đã hết với cùng kiểu mô phỏng ở Step 1**

Lưu tạm `scratch_verify.py` ở thư mục gốc repo:

```python
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="cp1252", errors="strict")

sys.path.insert(0, "scripts")
sys.path.insert(0, "scripts/agent/tools")
import retrieve  # noqa: E402 -- module tu reconfigure stdout sang utf-8 luc import

print("[verify] Sau import retrieve.py, stdout encoding =", sys.stdout.encoding)
print("[retrieve] ĐANG DÙNG MODEL: clip_vitb32")
print("[verify] Khong crash - PASS")
```

Chạy: `.venv\Scripts\python.exe scratch_verify.py`
Expected: in ra `stdout encoding = utf-8` rồi dòng có dấu tiếng Việt không crash, kết thúc bằng
`[verify] Khong crash - PASS`. (Import `retrieve` ở đây chỉ chạy tới hết module-level code, KHÔNG gọi
`_ensure_loaded()`/`fast_retrieve()` nên không tải index/model CLIP — verify nhanh, không cần
`data/extracted/`.)

- [x] **Step 5: Xoá script verify tạm**

```bash
rm scratch_verify.py
```

- [x] **Step 6: Commit**

```bash
git add scripts/agent/tools/retrieve.py
git commit -m "fix(phase6): reconfigure stdout to utf-8 in retrieve.py to avoid cp1252 crash on Windows console"
```

---

### Task 3: Công cụ sweep `TRAKE_CROSSCHECK_MARGIN` (đo, không tự chọn ngưỡng)

**Files:**
- Create: `scripts/test_phase6_margin_sweep.py`

**Interfaces:**
- Consumes: `run_trake(query_text: str, events: list[str], top_k_video=20, top_k_frame=20) -> dict`
  từ `scripts/agent/pipeline_trake.py` (không đổi); `TRAKE_CROSSCHECK_MARGIN` (module-level float,
  ghi đè được từ ngoài module — đã dùng theo đúng cách này ở `scripts/test_phase4_trake.py:97-103`).
- Produces: script CLI độc lập, không hàm nào được import bởi module khác.

Bối cảnh: `scripts/test_phase4_trake.py` đã có sẵn logic 2-pass (before/after cross-check) đúng ngưỡng
hiện tại `0.012`. Việc còn thiếu ở Phase 6 là chạy **nhiều** ngưỡng khác nhau trên cùng 1 lần retrieval
(để loại nhiễu rewrite/LLM giống file gốc) rồi in bảng so sánh — không tự kết luận ngưỡng nào "tốt
nhất", chỉ in số cho người dùng đọc. Tái dùng `_run_pass`/`_rank_of_video`/`EVAL_SET_PATH` từ
`test_phase4_trake.py` (DRY, cùng 1 nguồn logic tính điểm) thay vì viết lại.

- [x] **Step 1: Viết script với self-test bằng dữ liệu giả (không gọi model/index thật)**

```python
"""
test_phase6_margin_sweep.py — Do TRAKE_CROSSCHECK_MARGIN o nhieu gia tri khac nhau tren cung 1 lan
retrieval (PLAN.md Phase 6: "Tinh chinh TRAKE_CROSSCHECK_MARGIN").

CHI IN BANG SO LIEU — khong tu chon nguong "tot nhat". Nguoi dung tu doc bang ket qua va quyet dinh
gia tri cuoi cung cho TRAKE_CROSSCHECK_MARGIN trong scripts/agent/pipeline_trake.py, roi tu chinh tay
neu muon doi.

Tai dung dung logic tinh diem (_run_pass/_rank_of_video) va cach khu nhieu rewrite_query (monkeypatch
thanh identity) da co san o scripts/test_phase4_trake.py — khong viet lai (DRY).

Usage (chay that, can data/extracted/ + LLM key hop le vi run_trake() con goi rewrite_query cho tung
event — da bi patch thanh identity o day, nhung fast_retrieve van can index/model that):
    .venv\\Scripts\\python.exe scripts\\test_phase6_margin_sweep.py
    .venv\\Scripts\\python.exe scripts\\test_phase6_margin_sweep.py --margins -1.0,0.006,0.012,0.018,0.024,0.030

Self-test (khong can data/extracted/, khong goi model that):
    .venv\\Scripts\\python.exe scripts\\test_phase6_margin_sweep.py --self-test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEFAULT_MARGINS = [-1.0, 0.006, 0.012, 0.018, 0.024, 0.030]


def _sweep(margins: list[float]) -> list[dict]:
    """Chay _run_pass() 1 lan cho moi gia tri margin, tra ve list dict (1 dict/margin)."""
    import scripts.test_phase4_trake as t4

    eval_set = json.loads(t4.EVAL_SET_PATH.read_text(encoding="utf-8"))
    queries = [q for q in eval_set if q["type"] == "TRAKE"]
    print(f"[margin_sweep] {len(queries)} cau TRAKE tu {t4.EVAL_SET_PATH}")
    if not queries:
        raise SystemExit("[margin_sweep] Khong co cau TRAKE nao trong eval set - xem EVAL_GUIDE.md")

    rows = []
    for m in margins:
        t4._trake_module.TRAKE_CROSSCHECK_MARGIN = m
        label = f"margin={m}"
        print(f"\n[margin_sweep] === {label} ===")
        result = t4._run_pass(queries, label)
        result["margin"] = m
        rows.append(result)
    return rows


def _print_table(rows: list[dict]) -> None:
    print("\n[margin_sweep] === Bang tong hop (nguoi dung tu doc, KHONG tu ket luan) ===")
    print(f"  {'margin':>8} | {'video_top1':>12} | {'video_any_rank':>15} | {'events_matched':>15}")
    for r in rows:
        print(
            f"  {r['margin']:>8} | {r['video_top1']:>3}/{r['n']:<8} | "
            f"{r['video_any_rank']:>3}/{r['n']:<11} | {r['events_matched']:>3}/{r['events_total']:<11}"
        )


def _self_test() -> None:
    """Khong goi model/index that - fake run_trake() tra ve ket qua co dinh, chi kiem tra vong lap
    sweep + bang tong hop chay dung, khong crash. KHONG danh gia do chinh xac that (viec do la cua
    nguoi dung tren du lieu that - xem docstring dau file)."""
    import scripts.test_phase4_trake as t4

    fake_eval_set = [
        {
            "query_id": "fake-trake-001",
            "type": "TRAKE",
            "text_en": "fake global query",
            "gt_video_id": "L99_V001",
            "events": [
                {"text_en": "event A", "gt_frame_start": 10, "gt_frame_end": 12},
                {"text_en": "event B", "gt_frame_start": 20, "gt_frame_end": 22},
            ],
        }
    ]

    def _fake_run_trake(query_text, events, top_k_video=20, top_k_frame=20):
        return {
            "results": [{"video_id": "L99_V001", "frame_ids": [11, 21], "score": 0.5}],
            "best": {"video_id": "L99_V001", "frame_ids": [11, 21]},
            "n_events": len(events),
        }

    eval_path = _ROOT / "queries" / "_fake_eval_for_selftest.json"
    eval_path.write_text(json.dumps(fake_eval_set), encoding="utf-8")
    try:
        with patch.object(t4, "EVAL_SET_PATH", eval_path), patch.object(t4, "run_trake", _fake_run_trake):
            rows = _sweep([-1.0, 0.012])
    finally:
        eval_path.unlink(missing_ok=True)

    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
    for r in rows:
        assert r["video_top1"] == 1, f"Fake video luon dung hang 1, got {r}"
        assert r["events_matched"] == 2, f"Fake ca 2 event deu dung khoang, got {r}"
    _print_table(rows)
    print("\n[margin_sweep] Self-test PASS (du lieu gia lap, khong phai ket qua that)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--margins", type=str, default=",".join(str(m) for m in DEFAULT_MARGINS))
    parser.add_argument("--self-test", action="store_true", help="Chay self-test bang du lieu gia, khong dung index/model that")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return

    margins = [float(m.strip()) for m in args.margins.split(",") if m.strip()]
    rows = _sweep(margins)
    _print_table(rows)


if __name__ == "__main__":
    main()
```

- [x] **Step 2: Chạy self-test (không đụng index/model thật)**

```
.venv\Scripts\python.exe scripts\test_phase6_margin_sweep.py --self-test
```

Expected: in bảng 2 dòng (margin=-1.0, margin=0.012), kết thúc `Self-test PASS (du lieu gia lap,
khong phai ket qua that)`. **Không chạy `--self-test` bằng dữ liệu thật và không tự đọc/so sánh số ở
bước này** — việc đó thuộc Task 4.

- [x] **Step 3: Commit**

```bash
git add scripts/test_phase6_margin_sweep.py
git commit -m "feat(phase6): add TRAKE_CROSSCHECK_MARGIN sweep tool (measurement only, no threshold decision)"
```

---

### Task 4: Runbook — Checkpoint benchmark (lệnh cho người dùng tự chạy + tự đánh giá)

**Files:**
- Modify: [PLAN.md](../../../PLAN.md) — nối thêm 1 mục con "Runbook checkpoint benchmark" vào cuối
  Phase 6 (trước dòng `Success: nộp đợt 4 với cả 5 cải tiến...`), dạng danh sách lệnh, không phải
  code.

**Interfaces:** Không đổi code nào — deliverable của task này là văn bản (danh sách lệnh + cách đọc
kết quả) chèn vào PLAN.md, không phải hàm/module mới.

- [x] **Step 1: Thêm khối runbook vào PLAN.md**

Chèn ngay trước dòng `Success: nộp đợt 4 với cả 5 cải tiến đã qua benchmark xác nhận không regress
so với đợt 1.` ở cuối mục Phase 6:

```markdown
**Runbook checkpoint benchmark (tự chạy, tự đọc kết quả — không nhờ AI kết luận đúng/sai):**

1. So sánh baseline embedding (đã có từ Phase 6 cũ, dùng lại nguyên trạng để phát hiện regression do
   thay đổi khác gây ra, KHÔNG phải benchmark rewrite/rerank/OCR — script này bypass các module đó,
   xem docstring `run_eval.py`):
   ```
   .venv\Scripts\python.exe scripts\eval\run_eval.py
   ```
   Đọc `docs\eval_baseline_comparison.md` sau khi chạy xong, so với số cũ đã có trong file này (nếu
   đã từng chạy trước đó) — R@k tụt rõ rệt ở model `clip_vitb32` (model production) là dấu hiệu cần
   điều tra trước khi merge tiếp.

2. Phase 3 (risk-aware rerank) — so lại với số đã ghi trong PLAN.md Phase 3
   (R@1=0.130, R@5=0.217, R@20=0.348, R@50=0.478, R@100=0.565, đo trên 23 câu KIS+QA):
   ```
   .venv\Scripts\python.exe scripts\test_phase3_rerank.py
   ```

3. Phase 4 (TRAKE DP + cross-check) — so lại với số đã ghi trong PLAN.md Phase 4
   (video hạng #1: 0/4→0/4, video xuất hiện: 1/4→1/4, event đúng: 0/11→0/11, đo trên 4 câu TRAKE):
   ```
   .venv\Scripts\python.exe scripts\test_phase4_trake.py
   ```

4. Sweep `TRAKE_CROSSCHECK_MARGIN` trên dữ liệu TRAKE thật (dùng công cụ mới ở Task 3 — chỉ chạy
   SAU KHI đã mở rộng bộ eval TRAKE, xem mục "Việc không nằm trong Task" ở đầu plan này; chạy trên 4
   câu hiện có cũng được nhưng số liệu sẽ rất nhiễu vì mẫu quá nhỏ):
   ```
   .venv\Scripts\python.exe scripts\test_phase6_margin_sweep.py
   ```
   Đọc cột `video_top1` / `events_matched` ở từng dòng margin — tự chọn giá trị `TRAKE_CROSSCHECK_MARGIN`
   mới (nếu có) rồi sửa tay hằng số đó ở `scripts/agent/tools/pipeline_trake.py` (dòng khai báo
   `TRAKE_CROSSCHECK_MARGIN`), chạy lại bước 3 để xác nhận không tệ hơn số cũ trước khi commit.

5. Phase 5 (OCR hint) — so answer/confidence/method của 3 câu tự tạo, xem lại số đã ghi trong PLAN.md
   Phase 5:
   ```
   .venv\Scripts\python.exe scripts\test_phase5_ocr.py
   ```

**Tiêu chí "không merge nếu R@k tụt"**: so từng số ở trên với số đã ghi lại trong PLAN.md của đúng
Phase đó — tụt rõ rệt (không phải nhiễu do mẫu nhỏ/1 câu đổi hạng) thì dừng, không merge, quay lại
điều tra nguyên nhân trước khi tiếp tục Phase 6.
```

- [x] **Step 2: Verify PLAN.md vẫn hợp lệ Markdown**

```
.venv\Scripts\python.exe -c "import pathlib; s = pathlib.Path('PLAN.md').read_text(encoding='utf-8'); print(len(s), 'chars, OK doc duoc')"
```

Expected: in ra số ký tự, không lỗi encoding.

- [x] **Step 3: Commit**

```bash
git add PLAN.md
git commit -m "docs(phase6): add checkpoint-benchmark runbook (commands only, user runs+judges)"
```

---

### Task 5: Runbook — Dry-run `AIC_MODE=contest` (lệnh cho người dùng tự chạy + tự quan sát)

**Files:**
- Modify: [PLAN.md](../../../PLAN.md) — nối thêm mục con "Runbook dry-run contest mode" ngay sau
  khối runbook checkpoint benchmark thêm ở Task 4.

**Interfaces:** Không đổi code — cùng dạng deliverable văn bản như Task 4.

- [x] **Step 1: Thêm khối runbook vào PLAN.md**

```markdown
**Runbook dry-run contest mode (tự chạy, tự quan sát log — trước 03/09):**

1. Xác nhận `.env` có `OPENROUTER_MODEL_CONTEST` hợp lệ (khác rỗng) — nếu để trống, `config.py` tự
   fallback về `OPENROUTER_MODEL` kèm cảnh báo `[config] WARNING: AIC_MODE=contest nhung
   OPENROUTER_MODEL_CONTEST trong .env trong rong...`, tức là dry-run KHÔNG thật sự test model mạnh
   hơn — kiểm tra dòng log này xuất hiện hay không mỗi lần chạy dưới đây.

2. Kiểm tra quota Gemini còn lại tại https://ai.dev/rate-limit trước khi chạy (bài học đợt 1 — xem
   EXPERIMENT.md) — dry-run tốn quota giống lúc thi thật.

3. Chạy cả 3 pipeline với `AIC_MODE=contest`, đọc log xác nhận dòng
   `[config] OpenRouter AIC_MODE=contest model=...` xuất hiện đúng model mạnh (không phải model dev):

   PowerShell:
   ```powershell
   $env:AIC_MODE = "contest"
   .venv\Scripts\python.exe scripts\agent\pipeline_kis.py "a cyclist racing on a mountain road"
   .venv\Scripts\python.exe scripts\agent\pipeline_qa.py
   .venv\Scripts\python.exe scripts\agent\pipeline_trake.py
   Remove-Item Env:\AIC_MODE
   ```

4. So thời gian chạy (tự bấm giờ hoặc đọc timestamp log) với 1 lần chạy tương đương ở `AIC_MODE=test`
   (mặc định, không set biến) — chênh lệch lớn bất thường (không chỉ do model mạnh hơn chậm hơn chút,
   mà crash/treo/timeout) là dấu hiệu cần điều tra trước 03/09, không phải lúc thi thật mới phát hiện.

5. Chạy hết cả 3 pipeline không lỗi + xác nhận đúng model contest được dùng ở CẢ 3 (kể cả lời gọi
   vision trong `pipeline_qa.py` khi có ảnh — đã verify ở Phase 1, dry-run này chỉ là xác nhận lại lần
   cuối trước freeze, không phải lần đầu kiểm tra) → coi dry-run PASS, ghi lại kết quả (hoặc bất kỳ
   vấn đề gặp phải) vào PLAN.md Phase 6.
```

- [x] **Step 2: Verify PLAN.md vẫn hợp lệ Markdown**

```
.venv\Scripts\python.exe -c "import pathlib; s = pathlib.Path('PLAN.md').read_text(encoding='utf-8'); print(len(s), 'chars, OK doc duoc')"
```

- [x] **Step 3: Commit**

```bash
git add PLAN.md
git commit -m "docs(phase6): add AIC_MODE=contest dry-run runbook (commands only, user runs+observes)"
```

---

### Task 6: Review tổng nhánh cho Phase 4 (`pipeline_trake.py`)

**Files:** Không tạo/sửa file cố định trước — phạm vi review là toàn bộ diff của `pipeline_trake.py`
kể từ khi Phase 4 bắt đầu (không chỉ diff hiện tại của Phase 6). Nếu review ra finding, sửa trực tiếp
tại `scripts/agent/pipeline_trake.py` và (nếu finding liên quan) `scripts/agent/tools/rerank.py`.

**Interfaces:** Không thêm interface mới — task này chỉ chạy review + áp fix nếu có finding thật.

Bối cảnh (PLAN.md Phase 6): phiên làm Phase 4 (subagent-driven) đã review từng Task riêng lẻ (2/2
sạch, 1 finding đã fix) nhưng bỏ qua review toàn nhánh cuối cùng. Việc này KHÔNG phải benchmark/đo độ
chính xác retrieval — là review chất lượng code (đúng logic DP, đúng cross-check, không leak
side-effect...) nên vẫn nằm trong phạm vi tôi tự làm được, không cần người dùng tự chạy.

- [x] **Step 1: Xác định phạm vi diff cần review**

```bash
git log --oneline -- scripts/agent/pipeline_trake.py scripts/agent/tools/rerank.py
```

Lấy commit đầu tiên chạm tới `pipeline_trake.py` trong Phase 4 (trước Phase 4, file này chỉ có greedy
logic cũ) làm điểm base cho diff review.

- [x] **Step 2: Chạy review toàn nhánh**

Dùng skill `code-review` (level `high`, không cần `ultra` — thay đổi nằm trong 1 file chính, không
cần multi-agent cloud review) trên diff từ base commit đó tới `HEAD` của `scripts/agent/pipeline_trake.py`
(và `rerank.py` nếu diff động tới `RETRIEVAL_POOL_SIZE`).

- [x] **Step 3: Áp fix nếu có finding thật (không áp fix cho finding sai/không chắc)**

Theo `superpowers:receiving-code-review` — verify kỹ thuật trước khi sửa, không sửa theo phản xạ.

- [x] **Step 4: Nếu có sửa, chạy lại self-test có sẵn của `pipeline_trake.py`**

```
.venv\Scripts\python.exe scripts\agent\pipeline_trake.py
```

Expected: 6 self-test PASS (như đã ghi trong PLAN.md Phase 4), không lỗi mới phát sinh từ fix.

- [x] **Step 5: Commit (chỉ nếu có thay đổi thật)**

```bash
git add scripts/agent/pipeline_trake.py scripts/agent/tools/rerank.py
git commit -m "fix(phase6): address full-branch review findings for pipeline_trake.py"
```

Nếu review không ra finding nào cần sửa, không tạo commit — chỉ ghi lại vào PLAN.md Phase 6 rằng
review toàn nhánh đã chạy và sạch (fold vào Task 7 dưới).

---

### Task 7: Cập nhật PLAN.md Phase 6 — đánh dấu các mục đã xong

**Files:**
- Modify: [PLAN.md](../../../PLAN.md)

**Interfaces:** Không đổi code — chỉ cập nhật trạng thái tài liệu.

- [x] **Step 1: Sau khi Task 1–6 xong, cập nhật mục Phase 6 trong PLAN.md**

Đánh dấu các gạch đầu dòng đã hoàn tất (docstring, encoding fix, margin-sweep tool, runbook,
full-branch review) theo đúng văn phong "Đã làm:" đã dùng ở Phase 1–5, giữ nguyên các mục vẫn chờ
người dùng tự chạy (checkpoint benchmark thật, dry-run thật, mở rộng eval TRAKE, freeze) ở trạng thái
chưa tick — vì đây là việc người dùng tự làm, không phải tôi tự nhận đã xong thay họ.

- [x] **Step 2: Commit**

```bash
git add PLAN.md
git commit -m "docs(phase6): mark completed sub-items, leave user-run verification open"
```

---

## Self-Review (đã chạy khi viết plan này)

**1. Spec coverage** (từng gạch đầu dòng PLAN.md Phase 6):
- Checkpoint benchmark (chạy + không merge nếu tụt) → Task 4 (runbook) + Task 7 (đánh dấu tiến độ,
  không tự kết luận số liệu).
- Dry-run contest mode → Task 5.
- Freeze 03/09 → liệt kê ở mục "Việc không nằm trong Task" (không phải việc code).
- Mở rộng bộ eval TRAKE → liệt kê ở mục "Việc không nằm trong Task" (cần xem video thật, không giao
  được cho executor).
- Tinh chỉnh `TRAKE_CROSSCHECK_MARGIN` → Task 3 (công cụ đo) + bước 4 trong runbook Task 4 (người dùng
  tự chọn số sau khi chạy công cụ).
- Review tổng nhánh Phase 4 → Task 6.
- Sửa docstring `pipeline_trake.py` → Task 1.
- Lỗi encoding console Windows → Task 2.

**2. Placeholder scan:** Không còn "TBD"/"tự thêm sau" nào trong các Step — mọi code block đều là nội
dung thật (script margin-sweep đầy đủ, đoạn text runbook đầy đủ câu lệnh thật).

**3. Type consistency:** `run_trake()` signature dùng trong Task 3/Task 6 khớp đúng
`run_trake(query_text: str, events: list[str], top_k_video=20, top_k_frame=20) -> dict` đã định nghĩa
ở `pipeline_trake.py:132-137` (ARCHITECTURE.md §5 cũng ghi đúng chữ ký này, không đổi). `TRAKE_CROSSCHECK_MARGIN`
dùng thống nhất tên biến giữa `pipeline_trake.py`, `test_phase4_trake.py` (đã có sẵn) và
`test_phase6_margin_sweep.py` (Task 3, mới).
