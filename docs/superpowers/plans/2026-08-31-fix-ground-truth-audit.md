# Kế Hoạch Sửa Chữa Dữ Liệu Ground Truth AIC 2026 (Fix Ground Truth Audit Issues)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Khắc phục triệt để toàn bộ 12 lỗi cấu trúc/dữ liệu nghiêm trọng, chuẩn hoá kiểu dữ liệu (chuyển string sang int), gán đầy đủ `difficulty_tags` chuẩn cho 52 câu chưa có tag, và sửa các lỗi chính tả/ngữ nghĩa được ghi nhận trong [AUDIT_REPORT.md](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/AUDIT_REPORT.md).

**Architecture:** Chuẩn hoá 3 file ground truth độc lập ([`eval_ground_truth_kis.json`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/eval_ground_truth_kis.json), [`eval_ground_truth_qa.json`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/eval_ground_truth_qa.json), [`eval_ground_truth_trake.json`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/eval_ground_truth_trake.json)) thông qua việc cập nhật trực tiếp dữ liệu theo schema v1 chuẩn, đồng thời nâng cấp bộ unit test [`test_eval_ground_truth.py`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/unit/test_eval_ground_truth.py) làm regression guard.

**Tech Stack:** Python 3.13, Pytest, JSON, Pandas.

**Spec:** [AUDIT_REPORT.md](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/AUDIT_REPORT.md), [EVAL_GUIDE.md](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/EVAL_GUIDE.md).

## Global Constraints

- **Không thay đổi query_id đã có** để bảo vệ tính toàn vẹn của lịch sử snapshot và tracking điểm số.
- **Không tự nới lỏng khoảng frame** bừa bãi; giữ nguyên tắc `[gt_frame_start, gt_frame_end]` chặt chẽ theo hướng dẫn [EVAL_GUIDE.md](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/EVAL_GUIDE.md).
- **Mọi tag độ khó phải thuộc `TAG_CHUAN`** được định nghĩa tại [`normalize_gt.py:TAG_CHUAN`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/normalize_gt.py#L54-L71).
- **Mọi trường frame_id phải là kiểu số nguyên (int)**, không lưu dạng chuỗi ký tự (`str`).

---

## Danh Sách Công Việc Cần Người Dùng (USER) Can Thiệp / Thao Tác

Dưới đây là các phần việc mà hệ thống chuẩn bị sẵn kết quả đề xuất, cần người dùng xem xét hoặc trực tiếp chạy thử trên máy:

1. **Xác nhận `gt_video_id` của 2 câu TRAKE thử nghiệm (Đã tự động truy vết khớp 100% keyframe):**

   - Câu `e-trake-thunghiem-001` (nấu ăn măng tây, keyframe `4708, 5140, 5416, 5796`): Khớp chính xác với video **`L26_V194`**.
   - Câu `e-trake-thunghiem-003` (nấu ăn nấm, củ năng, đậu hũ, keyframe `2467, 3134, 3421, 3828`): Khớp chính xác với video **`L26_V072`**.
   - *Hành động của bạn:* Duyệt chấp thuận gán 2 `gt_video_id` này vào dữ liệu.
2. **Duyệt bộ `question` & `gt_answers` cho 9 câu QA:**

   - Đã trích xuất câu hỏi từ `text_vi`/`text_en` và tổng hợp danh sách từ đồng nghĩa (`gt_answers`) cho các câu `query-p2-7-qa`, `query-p2-9-qa`, `query-p2-12-qa`, `query-p2-19-qa`, `query-p2-23-qa`, `query-p2-27-qa`, `query-p2-28-qa`, `query-p2-29-qa`, `query-p2-30-qa`.
   - *Hành động của bạn:* Xem bảng chi tiết ở **Task 2**, nếu muốn bổ sung thêm biến thể trả lời nào chỉ cần phản hồi để cập nhật.
3. **Chạy kiểm thử thực tế trên UI / CLI (Tuỳ chọn sau khi sửa):**

   - Sau khi hoàn thành kế hoạch, bạn có thể chạy thử pipeline QA hoặc TRAKE qua giao diện web hoặc terminal để kiểm tra độ nhạy của ground truth mới:
     ```powershell
     .venv\Scripts\python.exe scripts\agent\pipeline_qa.py "query-p2-9-qa"
     ```

---

## Chi Tiết Các Task Thực Hiện

### Task 1: Sửa Lỗi Cấu Trúc, Bổ Sung `gt_video_id` & Chuẩn Hoá Frame trong `eval_ground_truth_trake.json`

**Files:**

- Modify: [`tests/eval/eval_ground_truth_trake.json`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/eval_ground_truth_trake.json)
- Test: [`tests/unit/test_eval_ground_truth.py`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/unit/test_eval_ground_truth.py)

**Interfaces:**

- Consumes: [`TAG_CHUAN`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/normalize_gt.py#L54-L71) từ `normalize_gt.py`
- Produces: 15 câu TRAKE chuẩn định dạng, không còn `gt_video_id` rỗng, không đảo frame, 100% frame là integer.

- [x] **Step 1: Viết test kiểm tra cấu trúc nghiêm ngặt cho TRAKE trong `test_eval_ground_truth.py`**

Thêm các assertion kiểm tra `gt_video_id` không rỗng, `gt_frame_end >= gt_frame_start`, và kiểu dữ liệu frame là `int`.

```python
def test_trake_events_khong_nguoc_va_khong_trong_video_id():
    path = get_gt_path("TRAKE")
    items = json.loads(path.read_text(encoding="utf-8"))
    for q in items:
        assert q.get("gt_video_id"), f"{q.get('query_id')}: gt_video_id bi rong"
        assert q.get("difficulty_tags"), f"{q.get('query_id')}: thieu difficulty_tags"
        for i, ev in enumerate(q.get("events", [])):
            s = ev.get("gt_frame_start")
            e = ev.get("gt_frame_end")
            assert isinstance(s, int) and isinstance(e, int), f"{q.get('query_id')} event {i}: frame phai la int"
            assert e >= s, f"{q.get('query_id')} event {i}: gt_frame_end ({e}) < gt_frame_start ({s})"
```

- [x] **Step 2: Chạy test để xác nhận phát hiện đúng lỗi hiện tại**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_eval_ground_truth.py::test_trake_events_khong_nguoc_va_khong_trong_video_id -v`
Expected: FAIL với thông báo `gt_video_id bi rong` hoặc `gt_frame_end < gt_frame_start`.

- [x] **Step 3: Cập nhật `eval_ground_truth_trake.json`**

Thực hiện các chỉnh sửa:

1. `e-trake-thunghiem-001`:
   - `gt_video_id`: `"L26_V194"`
   - `difficulty_tags`: `["action_sequence", "temporal_order"]`
   - Event 0: `gt_frame_start: 4708, gt_frame_end: 4718`
   - Event 1: `gt_frame_start: 5050, gt_frame_end: 5140` (sửa ngược và chuyển sang int)
   - Event 2: `gt_frame_start: 5416, gt_frame_end: 5426`
   - Event 3: `gt_frame_start: 5796, gt_frame_end: 5806`
2. `e-trake-thunghiem-002`:
   - `difficulty_tags`: `["action_sequence", "temporal_order"]`
   - Chuyển toàn bộ `gt_frame_start`/`gt_frame_end` sang kiểu `int` (`15961, 15971`, `16113, 16123`, `16569, 16579`, `16873, 16883`).
3. `e-trake-thunghiem-003`:
   - `gt_video_id`: `"L26_V072"`
   - `difficulty_tags`: `["action_sequence", "temporal_order"]`
   - Chuyển frame sang kiểu `int` (`2467, 2477`, `3134, 3144`, `3421, 3431`, `3828, 3838`).
4. `query-p2-8-trake`:
   - `difficulty_tags`: `["action_sequence", "temporal_order", "fine_detail"]`
   - Event 1: Sửa đảo ngược thành `gt_frame_start: 3909, gt_frame_end: 3919`.
5. `query-p2-21-trake`:
   - `difficulty_tags`: `["action_sequence", "temporal_order"]`.

- [x] **Step 4: Chạy lại test để xác nhận vượt qua**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_eval_ground_truth.py::test_trake_events_khong_nguoc_va_khong_trong_video_id -v`
Expected: PASS.

---

### Task 2: Sửa Lỗi Cấu Trúc, Điền `question` / `gt_answers` & Tags trong `eval_ground_truth_qa.json`

**Files:**

- Modify: [`tests/eval/eval_ground_truth_qa.json`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/eval_ground_truth_qa.json)
- Test: [`tests/unit/test_eval_ground_truth.py`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/unit/test_eval_ground_truth.py)

**Interfaces:**

- Consumes: Ground truth QA schema v1
- Produces: 17 câu QA đầy đủ `question`, `gt_answers` (mảng đa dạng), `difficulty_tags`, frame kiểu int.

- [x] **Step 1: Viết test kiểm tra tính hợp lệ cho toàn bộ câu QA trong `test_eval_ground_truth.py`**

```python
def test_qa_day_du_question_va_gt_answers():
    path = get_gt_path("QA")
    items = json.loads(path.read_text(encoding="utf-8"))
    for q in items:
        assert q.get("question") and q.get("question").strip(), f"{q.get('query_id')}: thieu question"
        assert isinstance(q.get("gt_answers"), list) and len(q.get("gt_answers")) > 0, f"{q.get('query_id')}: thieu gt_answers"
        assert isinstance(q.get("gt_frame_start"), int) and isinstance(q.get("gt_frame_end"), int), f"{q.get('query_id')}: frame phai la int"
        assert q.get("difficulty_tags"), f"{q.get('query_id')}: thieu difficulty_tags"
```

- [x] **Step 2: Chạy test để xác nhận fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_eval_ground_truth.py::test_qa_day_du_question_va_gt_answers -v`
Expected: FAIL do 9 câu thiếu `question` / `gt_answers`.

- [x] **Step 3: Cập nhật dữ liệu `eval_ground_truth_qa.json`**

Cập nhật 9 câu QA và chuẩn hoá các câu thử nghiệm:

1. `e-qa-thunghiem-001`:
   - `difficulty_tags`: `["naming", "text_in_frame"]`
   - `gt_frame_start: 1746, gt_frame_end: 1950` (int)
2. `e-qa-thunghiem-002`:
   - `difficulty_tags`: `["text_in_frame", "fine_detail"]`
   - `gt_frame_start: 5475, gt_frame_end: 5536` (int)
3. `e-qa-thunghiem-003`:
   - `difficulty_tags`: `["text_in_frame", "naming"]`
   - `gt_frame_start: 1789, gt_frame_end: 1849` (int)
4. `query-p2-7-qa`:
   - `question`: `"Con số được viết trên phần hông xe màu trắng là số mấy?"`
   - `gt_answers`: `["1204", "1.204", "1 204", "1204."]`
   - `difficulty_tags`: `["text_in_frame", "fine_detail"]`
5. `query-p2-9-qa`:
   - `question`: `"Đây là loài cá gì?"`
   - `gt_answers`: `["Cá sòng", "cá sòng", "ca song", "Cá Sòng"]`
   - `difficulty_tags`: `["naming", "fine_detail"]`
6. `query-p2-12-qa`:
   - `question`: `"Mỗi lần khuôn này làm được bao nhiêu cái bánh?"`
   - `gt_answers`: `["7", "7 cái", "7 cái bánh", "bảy", "bảy cái"]`
   - `difficulty_tags`: `["counting"]`
7. `query-p2-19-qa`:
   - `question`: `"Quán trọ được nhắc đến trong đoạn phim nằm trên đường nào?"`
   - `gt_answers`: `["Lý Thường Kiệt", "đường Lý Thường Kiệt", "Ly Thuong Kiet", "duong Ly Thuong Kiet"]`
   - `difficulty_tags`: `["naming", "text_in_frame"]`
8. `query-p2-23-qa`:
   - `question`: `"Loài cây (II) đạt được tốc độ sinh trưởng tốt nhất khi môi trường sống có độ mặn là bao nhiêu phần nghìn?"`
   - `gt_answers`: `["20 phần nghìn", "20", "20‰", "20/1000", "hai mươi phần nghìn"]`
   - `difficulty_tags`: `["chart_reading", "fine_detail"]`
9. `query-p2-27-qa`:
   - `question`: `"Trong các số từ 16 giây đầu tiên của video, số nào không được nhìn thấy từ góc nhìn của camera trong các số từ 1-8?"`
   - `gt_answers`: `["2, 5", "2 và 5", "2,5", "số 2 và số 5", "2, 5.", "2 và 5."]`
   - `difficulty_tags`: `["negation", "counting", "fine_detail"]`
10. `query-p2-28-qa`:
    - `question`: `"Topping trong video là thịt của con gì?"`
    - `gt_answers`: `["Cá hồi", "cá hồi", "ca hoi", "Cá Hồi", "thịt cá hồi"]`
    - `difficulty_tags`: `["naming"]`
11. `query-p2-29-qa`:
    - `question`: `"Phần thịt có trọng lượng bao nhiêu trong bảng nguyên liệu?"`
    - `gt_answers`: `["300g", "300 g", "300 gam", "300 gram", "300gr", "300"]`
    - `difficulty_tags`: `["text_in_frame", "fine_detail"]`
12. `query-p2-30-qa`:
    - `question`: `"X là con gì?"`
    - `gt_answers`: `["Nghêu", "nghêu", "ngheu", "Nghêu trắng", "con nghêu"]`
    - `difficulty_tags`: `["naming", "fine_detail"]`

- [x] **Step 4: Chạy lại test để xác nhận hoàn tất QA**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_eval_ground_truth.py::test_qa_day_du_question_va_gt_answers -v`
Expected: PASS.

---

### Task 3: Sửa Lỗi Chính Tả, Chuẩn Hoá Kiểu Dữ Liệu & Gán Tags trong `eval_ground_truth_kis.json`

**Files:**

- Modify: [`tests/eval/eval_ground_truth_kis.json`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/eval_ground_truth_kis.json)
- Test: [`tests/unit/test_eval_ground_truth.py`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/unit/test_eval_ground_truth.py)

**Interfaces:**

- Consumes: `TAG_CHUAN`
- Produces: 59 câu KIS sạch lỗi chính tả, 100% frame là integer, 100% có difficulty_tags hợp lệ.

- [x] **Step 1: Viết test kiểm tra toàn bộ 59 câu KIS**

```python
def test_kis_toan_ven_du_lieu():
    path = get_gt_path("KIS")
    items = json.loads(path.read_text(encoding="utf-8"))
    for q in items:
        assert q.get("gt_video_id"), f"{q.get('query_id')}: thieu gt_video_id"
        assert isinstance(q.get("gt_frame_start"), int) and isinstance(q.get("gt_frame_end"), int), f"{q.get('query_id')}: frame phai la int"
        assert q.get("gt_frame_end") >= q.get("gt_frame_start"), f"{q.get('query_id')}: frame_end < frame_start"
        assert q.get("difficulty_tags"), f"{q.get('query_id')}: thieu difficulty_tags"
        assert "nột" not in q.get("text_vi", ""), f"{q.get('query_id')}: con loi chinh ta 'nột'"
```

- [x] **Step 2: Chạy test để xác nhận fail**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_eval_ground_truth.py::test_kis_toan_ven_du_lieu -v`
Expected: FAIL.

- [x] **Step 3: Cập nhật `eval_ground_truth_kis.json`**

1. Sửa lỗi chính tả `e-kis-ai-022`: Thay `"nột người đàn ông"` thành `"một người đàn ông"`.
2. Chuyển đổi toàn bộ frame từ `str` sang `int` cho 17 câu (`e-kis-thunghiem-001` đến `e-kis-thunghiem-018`).
3. Gán `difficulty_tags` chuẩn cho 35 câu chưa có tag:
   - Các câu chứa chuỗi hành động nối tiếp: gán tag `["temporal_order"]` hoặc `["temporal_order", "action_sequence"]` (ví dụ `query-p2-2-kis`, `query-p2-10-kis`, `query-p2-11-kis`, `query-p2-13-kis`, `query-p2-15-kis`, `query-p2-22-kis`, `e-kis-thunghiem-010`, `e-kis-thunghiem-011`, `e-kis-thunghiem-012`, `e-kis-thunghiem-018`).
   - Các câu chứa nhiều đối tượng / chi tiết nhỏ / đếm: gán `["multi_object"]`, `["fine_detail"]`, `["counting"]` (ví dụ `query-p2-1-kis`, `query-p2-4-kis`, `query-p2-5-kis`, `query-p2-6-kis`, `query-p2-14-kis`, `query-p2-16-kis`, `query-p2-18-kis`, `query-p2-20-kis`, `query-p2-24-kis`, `query-p2-25-kis`, `query-p2-26-kis`, v.v.).
   - Các câu có chữ / banner / slide: gán `["text_in_frame"]`.

- [x] **Step 4: Chạy lại test để xác nhận hoàn tất KIS**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_eval_ground_truth.py::test_kis_toan_ven_du_lieu -v`
Expected: PASS.

---

### Task 4: Kiểm Thử Tích Hợp Toàn Bộ Bộ Dữ Liệu & Chạy Validation Suite

**Files:**

- Modify: [`tests/unit/test_eval_ground_truth.py`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/unit/test_eval_ground_truth.py)
- Test: Toàn bộ unit test suite

- [x] **Step 1: Bổ sung comprehensive validation test trong `test_eval_ground_truth.py`**

Đảm bảo test kiểm tra tính nhất quán chéo:

- Tổng số câu đủ 91 (59 KIS + 17 QA + 15 TRAKE).
- Toàn bộ 91 câu không có query_id trùng lặp.
- 100% câu có difficulty_tags hợp lệ nằm trong `TAG_CHUAN`.
- 100% frame ranges hợp lệ (start <= end, kiểu int).
- 100% câu QA có question và gt_answers không rỗng.

- [x] **Step 2: Chạy toàn bộ unit test suite**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ -v`
Expected: Toàn bộ test PASS 100%.

- [x] **Step 3: Chạy script `normalize_gt.py` kiểm tra 3 file**

Run:

```powershell
.venv\Scripts\python.exe tests\eval\normalize_gt.py tests\eval\eval_ground_truth_kis.json --check
.venv\Scripts\python.exe tests\eval\normalize_gt.py tests\eval\eval_ground_truth_qa.json --check
.venv\Scripts\python.exe tests\eval\normalize_gt.py tests\eval\eval_ground_truth_trake.json --check
```

Expected: Không có bất kỳ lỗi cấu trúc/schema nào.

---

### Task 5: Cập Nhật `AUDIT_REPORT.md` & Bàn Giao

**Files:**

- Modify: [`tests/eval/AUDIT_REPORT.md`](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/tests/eval/AUDIT_REPORT.md)

- [x] **Step 1: Cập nhật trạng thái trong `AUDIT_REPORT.md`**

Đánh dấu các mục lỗi trong bảng đã được giải quyết ("ĐÃ KHẮC PHỤC"), ghi chú ngày sửa và cập nhật bảng tổng kết phân bố dữ liệu (Số câu lỗi cấu trúc: 0, Số câu thiếu tags: 0).

- [x] **Step 2: Commit toàn bộ thay đổi**

```bash
git add tests/eval/*.json tests/eval/AUDIT_REPORT.md tests/unit/test_eval_ground_truth.py
git commit -m "fix(eval): khac phuc toan bo loi trong AUDIT_REPORT va chuan hoa 3 bo ground truth"
```

---

## Verification Plan

### Automated Tests

1. **Chạy bộ unit test toàn diện cho ground truth:**
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/unit/test_eval_ground_truth.py -v
   .venv\Scripts\python.exe -m pytest tests/unit/test_split_eval_gt.py -v
   .venv\Scripts\python.exe -m pytest tests/unit/test_gt_loader.py -v
   ```
2. **Chạy toàn bộ unit test repo:**
   ```powershell
   .venv\Scripts\python.exe -m pytest tests/unit/ -v
   ```

### Manual Verification

1. **Kiểm tra schema bằng `normalize_gt.py`:**
   ```powershell
   .venv\Scripts\python.exe tests\eval\normalize_gt.py tests\eval\eval_ground_truth_kis.json --check
   .venv\Scripts\python.exe tests\eval\normalize_gt.py tests\eval\eval_ground_truth_qa.json --check
   .venv\Scripts\python.exe tests\eval\normalize_gt.py tests\eval\eval_ground_truth_trake.json --check
   ```
2. **Kiểm tra tải dữ liệu qua `gt_loader.py`:**
   ```powershell
   .venv\Scripts\python.exe -c "from tests.eval.gt_loader import load_ground_truth; data = load_ground_truth(); print(f'Tong: {len(data)} cau')"
   ```
