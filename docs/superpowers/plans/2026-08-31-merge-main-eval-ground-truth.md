# Merge from `main` & Ground Truth Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Giải quyết triệt để xung đột merge từ `main` (commit `1c1ea8e`), sửa lỗi cú pháp JSON và đồng bộ 91 câu ground truth trong `tests/eval/eval_ground_truth.json`, cập nhật `normalize_gt.py`, và hoàn tất merge sạch sẽ với 100% unit test pass.

**Architecture:** Kết hợp (union) toàn bộ 86 query từ `main` (bao gồm các câu thử nghiệm Phase 2 và widened ground truth intervals) cùng 5 câu bổ sung `e-kis-ai-019`..`023` từ `fix/phase2` (commit `4436da1`). Sửa lỗi cú pháp thiếu dấu ngoặc `}, {` ở entry `query-p2-22-kis`, chuẩn hoá trailing spaces trong `gt_video_id`, bổ sung tag `mistranslation` vào `TAG_CHUAN`, và dọn dẹp template `eval_ground_truth_v2_template.json`.

**Tech Stack:** Python 3.13, Pytest, Git, JSON Schema

---

## Global Constraints

- Không được làm mất bất kỳ câu query nào của cả 2 nhánh (kết quả sau merge phải đủ 91 query không trùng lặp).
- Không được làm vỡ cấu trúc thư mục chuẩn hoá `tests/` của Phase 1 (`tests/eval/`, `tests/e2e/`, `tests/unit/`).
- Toàn bộ unit tests (`pytest tests/unit`) phải PASS 100% trước khi kết thúc merge.
- Tuân thủ quy ước comment/docstring tiếng Việt có dấu.

---

### Task 1: Cập nhật `TAG_CHUAN` trong `normalize_gt.py`

**Files:**
- Modify: `tests/eval/normalize_gt.py:52-68`
- Test: `tests/unit/test_normalize_gt.py`

**Interfaces:**
- Consumes: `TAG_CHUAN` definition in `tests/eval/normalize_gt.py`
- Produces: `TAG_CHUAN` containing `"mistranslation"`

- [x] **Step 1: Thêm tag `"mistranslation"` vào `TAG_CHUAN`**

```python
TAG_CHUAN = {
    "temporal_order",        # mô tả phụ thuộc thứ tự thời gian ("trước khi X thì Y")
    "multi_similar_object",  # nhiều đối tượng giống nhau, chỉ khác 1 chi tiết
    "action_sequence",       # chuỗi động tác nối tiếp (chủ yếu TRAKE)
    "small_object",          # đối tượng nhỏ / khuất một phần khung hình
    "short_action",          # hành động rất ngắn giữa video dài
    "fine_detail",           # phải nhìn chi tiết nhỏ mới phân biệt được
    "naming",                # đòi tên riêng / danh từ định danh cụ thể
    "easy_sanity_check",     # câu dễ, để phát hiện hệ thống hỏng
    "counting",              # đếm số lượng (điểm yếu của vision LLM)
    "multi_object",          # nhiều loại đối tượng cùng lúc trong khung
    "image_in_image",        # ảnh lồng trong ảnh / màn hình TV trong khung
    "text_in_frame",         # phải đọc chữ/số in trong khung (cần OCR)
    "negation",              # câu phủ định/loại trừ ("cảnh không có người")
    "local_dialect",         # từ địa phương/viết tắt (thử sức rewrite.py)
    "chart_reading",         # phải đọc biểu đồ/đồ thị
    "mistranslation",        # bẫy dịch sai thuật ngữ chuyên môn hoặc từ đồng âm
}
```

- [x] **Step 2: Chạy unit test kiểm tra tag chuẩn**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_normalize_gt.py -k test_tag_chuan_phu_het_tag_dang_dung_trong_bo_eval -v`
Expected: PASS (sau khi GT hợp nhất được giải quyết)

---

### Task 2: Hợp nhất `tests/eval/eval_ground_truth.json` và sửa lỗi cú pháp

**Files:**
- Modify: `tests/eval/eval_ground_truth.json`
- Modify: `tests/eval/eval_ground_truth_v2_template.json`

**Interfaces:**
- Consumes: JSON data từ `MERGE_HEAD:test_eval/Eval/eval_ground_truth.json` và `HEAD:tests/eval/eval_ground_truth.json`
- Produces: 91 entries JSON hợp lệ, không chứa conflict markers, không có query_id trùng lặp, trim trailing spaces trong `gt_video_id`

- [x] **Step 1: Tạo và chạy script hợp nhất ground truth tự động**

Chạy script Python để:
1. Đọc và vá lỗi cú pháp thiếu `}, {` ở `MERGE_HEAD` (trước `"query_id": "query-p2-22-kis"`).
2. Lấy 86 queries từ `MERGE_HEAD` (giữ nguyên widened intervals `gt_frame_end`).
3. Bổ sung 5 queries `e-kis-ai-019`, `e-kis-ai-020`, `e-kis-ai-021`, `e-kis-ai-022`, `e-kis-ai-023` từ `HEAD`.
4. Chuẩn hoá `gt_video_id` (strip whitespace thừa như `"L30_V046 "`).
5. Ghi đè vào `tests/eval/eval_ground_truth.json`.
6. Dọn dẹp phần tử rỗng `{}` cuối file `tests/eval/eval_ground_truth_v2_template.json`.

- [x] **Step 2: Xác minh cú pháp JSON và số lượng query**

Run: `.venv\Scripts\python.exe -c "import json; data = json.load(open('tests/eval/eval_ground_truth.json', encoding='utf-8')); print(f'Total valid queries: {len(data)}'); assert len(data) == 91; assert len(set(q['query_id'] for q in data)) == 91"`
Expected: Output `Total valid queries: 91`

---

### Task 3: Chạy bộ kiểm thử toàn diện và hoàn tất Git Merge

**Files:**
- Test: `tests/unit/test_eval_ground_truth.py`
- Test: `tests/unit/` (toàn bộ unit tests)

- [x] **Step 1: Chạy toàn bộ suite `tests/unit`**

Run: `.venv\Scripts\python.exe -m pytest tests/unit -v`
Expected: 89 passed, 0 failed.

- [x] **Step 2: Stage các file đã giải quyết xung đột**

```bash
git add tests/eval/eval_ground_truth.json tests/eval/eval_ground_truth_v2_template.json tests/eval/normalize_gt.py
```

- [x] **Step 3: Hoàn tất commit merge**

```bash
git commit -m "merge: resolve merge conflict in eval_ground_truth.json and unify 91 queries"
```

- [x] **Step 4: Kiểm tra lại `git status` và `git log`**

Run: `git status`
Expected: `working tree clean`, merge hoàn tất thành công.
