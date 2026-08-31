# Split Eval Ground Truth and Content Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tách bộ ground truth `tests/eval/eval_ground_truth.json` (91 câu) thành 3 file độc lập theo dạng bài (`eval_ground_truth_kis.json`, `eval_ground_truth_qa.json`, `eval_ground_truth_trake.json`), đồng thời thực hiện kiểm toán toàn diện (audit) từng câu hỏi về nhãn, chất lượng dịch `text_vi` vs `text_en`, câu hỏi/đáp án QA, chuỗi sự kiện TRAKE, và lập báo cáo lỗi `tests/eval/AUDIT_REPORT.md` riêng biệt mà không tự ý sửa đổi dữ liệu gốc trong quá trình tách.

**Architecture:** Tạo script tách dữ liệu tất định và phi huỷ diệt (`split_eval_gt.py`) bảo toàn 100% nội dung gốc; thực hiện quy trình audit tự động kết hợp rà soát nội dung từng câu trên toàn bộ 91 mục; xuất báo cáo `AUDIT_REPORT.md` phân loại lỗi theo 4 nhóm (Schema/Dữ liệu, Phân loại nhãn, Chất lượng dịch thuật, Chuẩn hoá tag); bổ sung bộ unit test xác minh tính toàn vẹn và không thất thoát dữ liệu.

**Tech Stack:** Python 3.13 (`json`, `pathlib`, `collections`), `pytest` test suite.

**Spec:** User request ngày 2026-08-31 về việc phân tách ground truth thành 3 file KIS/QA/TRAKE và lập báo cáo kiểm toán nội dung độc lập.

## Global Constraints

- **Không tự ý sửa nội dung dữ liệu trong các file ground truth khi tách**: Quá trình tách phải là ánh xạ 1:1 bảo toàn nguyên trạng từng entry (không tự ý normalize, sanitize hay xóa trường bị lỗi) để tránh làm sai lệch dữ liệu trước khi được người dùng duyệt.
- **Bảo tồn tính tương thích ngược**: Giữ nguyên `tests/eval/eval_ground_truth.json` làm file tổng hợp để không làm gãy các pipeline/harness hiện có (`tests/e2e/score_pipelines.py`, `tests/eval/run_eval.py`, `tests/e2e/golden_kis_snapshot.py`).
- **Báo cáo lỗi độc lập**: Tất cả các lỗi phát hiện (sai nhãn, ngược khoảng frame, thiếu trường, dịch sai lệch ý nghĩa) phải được ghi chép đầy đủ vào `tests/eval/AUDIT_REPORT.md` kèm đề xuất hướng xử lý cho phase tiếp theo.
- **Tuân thủ quy ước repo**: Code Python chuẩn snake_case, UTF-8 encoding (`ensure_ascii=False, indent=2`), comment tiếng Việt.

---

### Task 1: Xây dựng công cụ phân tách ground truth tất định (`tests/eval/split_eval_gt.py`)

**Files:**
- Create: `tests/eval/split_eval_gt.py`
- Test: `tests/unit/test_split_eval_gt.py`

**Interfaces:**
- Consumes: `tests/eval/eval_ground_truth.json` (mảng JSON gồm 91 entries)
- Produces: 
  - `split_ground_truth(source_path, out_dir)` -> `dict[str, list[dict]]`
  - Ghi ra 3 file:
    - `tests/eval/eval_ground_truth_kis.json`
    - `tests/eval/eval_ground_truth_qa.json`
    - `tests/eval/eval_ground_truth_trake.json`

- [ ] **Step 1: Viết failing test cho hàm tách ground truth**

Tạo file `tests/unit/test_split_eval_gt.py`:

```python
"""
test_split_eval_gt.py — Kiểm tra tính toàn vẹn và phi huỷ diệt của công cụ tách ground truth.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from tests.eval.split_eval_gt import split_ground_truth


def test_split_ground_truth_preserves_all_records(tmp_path):
    mock_data = [
        {"query_id": "k1", "type": "KIS", "text_vi": "mèo", "text_en": "cat", "gt_video_id": "L21_V001", "gt_frame_start": 1, "gt_frame_end": 2},
        {"query_id": "q1", "type": "QA", "text_vi": "chó?", "text_en": "dog?", "gt_video_id": "L21_V002", "gt_frame_start": 5, "gt_frame_end": 6, "question": "dog?", "gt_answer": "1", "gt_answers": ["1"]},
        {"query_id": "t1", "type": "TRAKE", "text_vi": "chuỗi", "text_en": "seq", "gt_video_id": "L21_V003", "events": [{"text_en": "e1", "gt_frame_start": 10, "gt_frame_end": 20}]},
    ]
    src_file = tmp_path / "eval_ground_truth.json"
    src_file.write_text(json.dumps(mock_data, ensure_ascii=False, indent=2), encoding="utf-8")

    result = split_ground_truth(src_file, tmp_path)

    assert len(result["KIS"]) == 1
    assert len(result["QA"]) == 1
    assert len(result["TRAKE"]) == 1
    assert result["KIS"][0]["query_id"] == "k1"
    assert result["QA"][0]["query_id"] == "q1"
    assert result["TRAKE"][0]["query_id"] == "t1"

    # Kiểm tra file sinh ra trên đĩa
    kis_file = tmp_path / "eval_ground_truth_kis.json"
    qa_file = tmp_path / "eval_ground_truth_qa.json"
    trake_file = tmp_path / "eval_ground_truth_trake.json"

    assert kis_file.exists()
    assert qa_file.exists()
    assert trake_file.exists()

    loaded_kis = json.loads(kis_file.read_text(encoding="utf-8"))
    assert loaded_kis == [mock_data[0]]
```

- [ ] **Step 2: Chạy test để xác nhận fail**

Run: `.venv\Scripts\pytest.exe tests\unit\test_split_eval_gt.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.eval.split_eval_gt'`

- [ ] **Step 3: Cài đặt module `tests/eval/split_eval_gt.py`**

Tạo `tests/eval/split_eval_gt.py`:

```python
"""
split_eval_gt.py — Tách file eval_ground_truth.json thành 3 file con theo dạng bài KIS / QA / TRAKE.

Đảm bảo nguyên tắc PHI HUỶ DIỆT (non-destructive):
- Giữ nguyên 100% nội dung gốc của từng entry (không thay đổi giá trị, không tự sửa lỗi).
- Bảo toàn thứ tự xuất hiện gốc trong từng loại.
- Ghi ra UTF-8 chuẩn (ensure_ascii=False, indent=2).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def split_ground_truth(
    source_path: Path | str,
    output_dir: Path | str | None = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Đọc file ground truth tổng hợp và tách thành 3 mảng KIS, QA, TRAKE.
    
    Nếu output_dir được chỉ định, ghi ra:
      - {output_dir}/eval_ground_truth_kis.json
      - {output_dir}/eval_ground_truth_qa.json
      - {output_dir}/eval_ground_truth_trake.json
    """
    src = Path(source_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Không tìm thấy file ground truth: {src}")

    raw_data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raise ValueError(f"Dữ liệu ground truth phải là list các entry, nhận được: {type(raw_data)}")

    buckets: Dict[str, List[Dict[str, Any]]] = {
        "KIS": [],
        "QA": [],
        "TRAKE": [],
    }

    for idx, entry in enumerate(raw_data):
        entry_type = str(entry.get("type", "")).upper()
        if entry_type in buckets:
            buckets[entry_type].append(entry)
        else:
            raise ValueError(f"Entry index {idx} ({entry.get('query_id')}) có type không hợp lệ: {entry_type}")

    if output_dir:
        out_path = Path(output_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        kis_file = out_path / "eval_ground_truth_kis.json"
        qa_file = out_path / "eval_ground_truth_qa.json"
        trake_file = out_path / "eval_ground_truth_trake.json"

        kis_file.write_text(json.dumps(buckets["KIS"], ensure_ascii=False, indent=2), encoding="utf-8")
        qa_file.write_text(json.dumps(buckets["QA"], ensure_ascii=False, indent=2), encoding="utf-8")
        trake_file.write_text(json.dumps(buckets["TRAKE"], ensure_ascii=False, indent=2), encoding="utf-8")

    return buckets


def main() -> None:
    parser = argparse.ArgumentParser(description="Tách eval_ground_truth.json thành 3 file KIS/QA/TRAKE.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parent / "eval_ground_truth.json",
        help="Đường dẫn file eval_ground_truth.json nguồn",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Thư mục xuất 3 file con (mặc định cùng thư mục với script)",
    )
    args = parser.parse_args()

    buckets = split_ground_truth(args.source, args.out_dir)
    total = sum(len(v) for v in buckets.values())
    print(f"✅ Đã tách thành công {total} entries từ {args.source.name}:")
    print(f"   - KIS:   {len(buckets['KIS'])} entries -> {args.out_dir / 'eval_ground_truth_kis.json'}")
    print(f"   - QA:    {len(buckets['QA'])} entries -> {args.out_dir / 'eval_ground_truth_qa.json'}")
    print(f"   - TRAKE: {len(buckets['TRAKE'])} entries -> {args.out_dir / 'eval_ground_truth_trake.json'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Chạy test để xác nhận pass**

Run: `.venv\Scripts\pytest.exe tests\unit\test_split_eval_gt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tests/eval/split_eval_gt.py tests/unit/test_split_eval_gt.py
git commit -m "feat(eval): add split_eval_gt script for lossless sub-file splitting"
```

---

### Task 2: Kiểm toán toàn diện 91 câu Ground Truth và Lập Báo cáo (`tests/eval/AUDIT_REPORT.md`)

**Files:**
- Create: `tests/eval/AUDIT_REPORT.md`
- Reference: `tests/eval/eval_ground_truth.json`

**Interfaces:**
- Input: Toàn bộ 91 entries trong `tests/eval/eval_ground_truth.json` (59 KIS, 17 QA, 15 TRAKE).
- Output: Báo cáo `tests/eval/AUDIT_REPORT.md` ghi nhận chi tiết mọi bất thường, lỗi cấu trúc, lỗi ngữ nghĩa dịch thuật, nhãn nghi vấn và đề xuất kế hoạch sửa.

- [ ] **Step 1: Rà soát cấu trúc & dữ liệu bằng script phân tích tự động**

Chạy script kiểm tra 91 câu để lập bảng thống kê lỗi cấu trúc:
- Tìm `gt_video_id` rỗng (`e-trake-thunghiem-001`, `e-trake-thunghiem-003`).
- Tìm khoảng frame bị đảo ngược `start > end` (`e-trake-thunghiem-001` event #1: 5140 > 5050, `query-p2-8-trake` event #1: 3909 > 3819).
- Tìm các câu QA bị thiếu `question` hoặc `gt_answers: []` (`query-p2-7-qa`, `query-p2-9-qa`, `query-p2-12-qa`, `query-p2-19-qa`, `query-p2-23-qa`, `query-p2-27-qa`, `query-p2-28-qa`, `query-p2-29-qa`, `query-p2-30-qa`).

- [ ] **Step 2: Đọc và rà soát thủ công chất lượng dịch thuật (`text_vi` vs `text_en`) & nhãn từng câu**

Đọc kỹ từng câu hỏi trong 3 nhóm:
1. **Nhóm KIS (59 câu):**
   - Kiểm tra các câu có chứa cụm từ "bắt đầu... kết thúc...", "sau đó..." (như `e-kis-ai-020`, `e-kis-ai-021`, `e-kis-ai-022`, `e-kis-ai-023`, `query-p2-2-kis`) xem có phải bản chất là câu chuỗi hành động (TRAKE) bị gán nhầm sang KIS không.
   - So sánh độ tương đương ngữ nghĩa `text_vi` vs `text_en`: các danh từ riêng, số lượng, màu sắc, chi tiết đồ vật, vị trí không gian.
2. **Nhóm QA (17 câu):**
   - Đọc câu hỏi và kiểm tra xem câu hỏi có thể hiện rõ mục tiêu thị giác không.
   - So sánh `gt_answer` và `text_vi`: câu trả lời có đúng trọng tâm câu hỏi không (ví dụ đếm số lượng, đọc chữ OCR, nhận diện vật thể).
   - Kiểm tra xem `question` tiếng Anh có tương xứng với phần hỏi trong `text_vi` không.
3. **Nhóm TRAKE (15 câu):**
   - Đọc từng sự kiện trong `events`: `text_en` mô tả sự kiện con có rõ ràng không, thứ tự thời gian có liên tục không (`gt_frame_start` của event sau có lớn hơn event trước không).

- [ ] **Step 3: Viết tài liệu báo cáo kiểm toán `tests/eval/AUDIT_REPORT.md`**

Tạo file `tests/eval/AUDIT_REPORT.md` với đầy đủ các mục:
1. **Tổng quan số lượng**: 91 câu (59 KIS, 17 QA, 15 TRAKE).
2. **Bảng tổng hợp lỗi nghiêm trọng (Critical / Blocker)**:
   - `e-trake-thunghiem-001`: Thiếu `gt_video_id` (trống `""`), khoảng frame event #1 bị ngược (`5140 > 5050`).
   - `e-trake-thunghiem-003`: Thiếu `gt_video_id` (trống `""`).
   - `query-p2-8-trake`: Khoảng frame event #1 bị ngược (`3909 > 3819`).
   - 8 câu QA thiếu trường `question` (`""`) và 9 câu QA có danh sách `gt_answers: []` trống.
3. **Bảng nghi vấn phân loại nhãn (Label Classification Ambiguity)**:
   - Các câu KIS mô tả diễn tiến thời gian (`e-kis-ai-020`, `e-kis-ai-021`, `e-kis-ai-022`, `e-kis-ai-023`, `query-p2-2-kis`) chỉ trỏ vào 1 frame đơn lẻ dù văn bản mô tả 2 mốc thời gian ("bắt đầu... kết thúc...").
4. **Bảng đánh giá chất lượng dịch thuật (`text_vi` vs `text_en`)**:
   - Ghi nhận các câu dịch máy bị mất chi tiết, sai sắc thái, hoặc từ ngữ chưa tối ưu cho mô hình text encoder của SigLIP.
5. **Kế hoạch đề xuất sửa chữa cho Phase tiếp theo (Action Plan)**:
   - Đề xuất các giá trị sửa cụ thể cho từng câu (bổ sung video ID, đảo lại khoảng frame, điền `question`/`gt_answers`, chuẩn hoá nhãn) để người dùng phê duyệt trước khi thực thi.

- [ ] **Step 4: Commit báo cáo kiểm toán**

```powershell
git add tests/eval/AUDIT_REPORT.md
git commit -m "docs(eval): add comprehensive audit report for 91 ground truth queries"
```

---

### Task 3: Thực thi phân tách và sinh 3 file ground truth con

**Files:**
- Create: `tests/eval/eval_ground_truth_kis.json` (59 items)
- Create: `tests/eval/eval_ground_truth_qa.json` (17 items)
- Create: `tests/eval/eval_ground_truth_trake.json` (15 items)
- Retain: `tests/eval/eval_ground_truth.json` (91 items)

**Interfaces:**
- Chạy lệnh CLI để sinh 3 file con từ file tổng thể.

- [ ] **Step 1: Thực thi lệnh tách file**

Run: `.venv\Scripts\python.exe tests\eval\split_eval_gt.py`
Expected Output:
```
✅ Đã tách thành công 91 entries từ eval_ground_truth.json:
   - KIS:   59 entries -> ...\eval_ground_truth_kis.json
   - QA:    17 entries -> ...\eval_ground_truth_qa.json
   - TRAKE: 15 entries -> ...\eval_ground_truth_trake.json
```

- [ ] **Step 2: Xác minh 3 file con được tạo đúng trên đĩa**

Kiểm tra sự tồn tại và số dòng của 3 file con:
```powershell
.venv\Scripts\python.exe -c "import json; k=json.load(open('tests/eval/eval_ground_truth_kis.json', encoding='utf-8')); q=json.load(open('tests/eval/eval_ground_truth_qa.json', encoding='utf-8')); t=json.load(open('tests/eval/eval_ground_truth_trake.json', encoding='utf-8')); print(f'KIS: {len(k)}, QA: {len(q)}, TRAKE: {len(t)}, SUM: {len(k)+len(q)+len(t)}')"
```
Expected: `KIS: 59, QA: 17, TRAKE: 15, SUM: 91`

- [ ] **Step 3: Commit 3 file ground truth con**

```powershell
git add tests/eval/eval_ground_truth_kis.json tests/eval/eval_ground_truth_qa.json tests/eval/eval_ground_truth_trake.json
git commit -m "feat(eval): generate separate ground truth files for KIS, QA, and TRAKE"
```

---

### Task 4: Cập nhật Unit Test xác minh tính toàn vẹn và không thất thoát dữ liệu

**Files:**
- Modify: `tests/unit/test_eval_ground_truth.py`
- Modify: `tests/unit/test_split_eval_gt.py`

**Interfaces:**
- Test suite kiểm tra cả file tổng (`eval_ground_truth.json`) lẫn 3 file con (`_kis.json`, `_qa.json`, `_trake.json`).

- [ ] **Step 1: Bổ sung test kiểm tra tính nhất quán giữa file tổng và 3 file con**

Cập nhật `tests/unit/test_split_eval_gt.py` thêm các ca kiểm thử:
- Mọi `query_id` trong file tổng xuất hiện chính xác 1 lần trong 3 file con.
- Nội dung (từng field) trong file con hoàn toàn giống hệt file tổng.
- File KIS chỉ chứa `type: "KIS"`.
- File QA chỉ chứa `type: "QA"`.
- File TRAKE chỉ chứa `type: "TRAKE"`.

- [ ] **Step 2: Cập nhật `tests/unit/test_eval_ground_truth.py` để validate 3 file con**

Thêm test case duyệt qua cả 3 file con để kiểm tra ID không trùng và type khớp tên file.

- [ ] **Step 3: Chạy toàn bộ test suite**

Run: `.venv\Scripts\pytest.exe tests\unit`
Expected: 100% tests pass (90+ passed, 0 failures).

- [ ] **Step 4: Commit test updates**

```powershell
git add tests/unit/test_eval_ground_truth.py tests/unit/test_split_eval_gt.py
git commit -m "test(eval): add integrity and consistency tests for split ground truth files"
```

---

## Verification Plan

### Automated Tests
1. **Kiểm tra tách file và tính toàn vẹn dữ liệu**:
   ```powershell
   .venv\Scripts\pytest.exe tests\unit\test_split_eval_gt.py -v
   ```
2. **Kiểm tra tính toàn vẹn ground truth tổng thể**:
   ```powershell
   .venv\Scripts\pytest.exe tests\unit\test_eval_ground_truth.py -v
   ```
3. **Toàn bộ regression test suite**:
   ```powershell
   .venv\Scripts\pytest.exe tests\unit
   ```
   Tất cả 90+ tests phải pass.

### Manual Verification
1. **Kiểm tra 3 file JSON được tách**:
   - Mở `tests/eval/eval_ground_truth_kis.json` và kiểm tra 59 entries.
   - Mở `tests/eval/eval_ground_truth_qa.json` và kiểm tra 17 entries.
   - Mở `tests/eval/eval_ground_truth_trake.json` và kiểm tra 15 entries.
2. **Kiểm tra báo cáo kiểm toán**:
   - Mở `tests/eval/AUDIT_REPORT.md` và rà soát các bảng phân tích lỗi chi tiết của từng câu.
   - Đảm bảo KHÔNG có file dữ liệu nào bị tự ý sửa đổi trước khi có plan sửa lỗi riêng.
