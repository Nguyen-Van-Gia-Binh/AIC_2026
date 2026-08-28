---
name: submission
description: >-
  Format nộp bài AIC2026: cấu trúc CSV/ZIP, cách dùng build_submission.py và
  validate_submission.py, quy trình export từ Gradio UI. Dùng khi sửa format
  nộp bài, debug submission, chuẩn bị thi, hoặc đối chiếu validator BTC.
---

# Format nộp bài AIC2026

> ✅ **2026-08-20 — đã fix 2 lỗi xác nhận đối chiếu với hướng dẫn nộp bài chính thức BTC** (xem
> [docs/Thong tin vong So tuyen AIC2026.md](../../../docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md)
> §4): (1) ZIP nay nén CSV vào thư mục con `submission/` (`build_zip_submission`,
> `arcname=f"submission/{csv_path.name}"`), có kiểm tra lại trong `validate_zip()`; (2)
> `build_kis_csv`/`build_qa_csv`/`build_trake_csv` nay nhận thẳng tên file đích (`filename`, giữ
> nguyên tên BTC cấp, chỉ đổi đuôi thành `.csv`) thay vì tự ghép hậu tố. Đã thêm luôn kiểm tra
> answer Q&A ≤ 100 ký tự vào validator. Chi tiết đầy đủ xem nội dung file này bên dưới.

## Cấu trúc CSV

3 loại CSV, mỗi loại cho 1 dạng bài:

### KIS CSV
```csv
video_id,frame_id
L21_V001,42
L15_V003,187
```
- `video_id`: format `{batch}_{video_num}`, **không** kèm `.mp4`
- `frame_id`: số nguyên ≥ 1 (BTC đếm frame từ 1, không phải 0)
- Tối đa **100 dòng** (không kể header)

### Q&A CSV
```csv
video_id,frame_id,answer
L21_V001,42,red car
```
- Cùng quy tắc `video_id`/`frame_id` như KIS
- `answer`: text trả lời câu hỏi, tiếng Việt hoặc tiếng Anh — cùng ngôn ngữ với câu hỏi (luật thi
  cho phép cả 2, xem `docs/Thong tin vong So tuyen AIC2026.md`)
- Tối đa **100 dòng**

### TRAKE CSV
```csv
video_id,frame_id_1,frame_id_2,frame_id_3
L21_V001,100,250,400
L21_V001,95,245,390
```
- **1 dòng = 1 phương án dự đoán TRỌN VẸN cho cả chuỗi N sự kiện** (không phải 1 dòng/event) —
  mỗi dòng là 1 candidate khác nhau cho cùng câu hỏi, tối đa 100 dòng như mọi loại truy vấn khác
- Số cột `frame_id` trên mỗi dòng phải khớp đúng số event N của câu hỏi
- Thứ tự `frame_id` trên 1 dòng phải theo đúng thứ tự thời gian của các event

## ZIP submission

File ZIP chứa tất cả CSV cần nộp, **bên trong phải có 1 thư mục con tên `submission/`** chứa các
CSV đó (BTC từ chối ZIP nén CSV trực tiếp vào gốc). Cấu trúc đúng:
```
<tên_zip>.zip
└── submission/
    ├── query-1-kis.csv
    ├── query-2-kis.csv
    ├── query-3-qa.csv
    └── query-4-trake.csv
```
Tên file zip tùy chọn, khuyến nghị chỉ chữ/số (ví dụ `team_ABC_round1.zip`).

## API sử dụng

### Build CSV
```python
from submit.build_submission import build_kis_csv, build_qa_csv, build_trake_csv, build_zip_submission

# filename = tên file truy vấn gốc BTC cấp (có/không đuôi .txt/.csv đều được, luôn ra .csv)
# KIS
build_kis_csv("query-1-kis", results)  # results = [{"video_id": ..., "frame_id": ...}, ...]

# Q&A
build_qa_csv("query-2-qa", results)  # results item có thêm key "answer"

# TRAKE
build_trake_csv("query-3-trake", results)  # results item có "video_id" + "frame_ids" (list[int])

# ZIP — gom CSV, tự đặt vào thư mục submission/ bên trong ZIP
build_zip_submission(csv_paths, tag="manual")
```

### Validate
```python
from submit.validate_submission import validate_csv_file, validate_zip

# Validate 1 CSV
errors = validate_csv_file(Path("submissions/query-1-kis.csv"))

# Validate ZIP
errors, warnings = validate_zip(Path("submissions/submission_manual_20260819.zip"))
```

Hoặc chạy từ CLI:
```powershell
.venv\Scripts\python.exe scripts\submit\validate_submission.py
# → tự validate file mới nhất trong submissions/
```

## Quy tắc validator nội bộ

- Encoding: UTF-8
- `video_id` không chứa `.mp4`
- `frame_id` ≥ 1 (số nguyên)
- Tối đa 100 dòng per CSV
- Q&A: answer ≤ 100 ký tự
- ZIP: mọi CSV phải nằm trong thư mục con `submission/` bên trong ZIP
- Không có header row (không tự động kiểm tra được — tự rà tay theo checklist BTC §4.6)

## Quy trình export từ React UI

1. Chạy search ở tab KIS/Q&A/TRAKE
2. Rà soát kết quả trên bảng / video player, sửa tay nếu cần
3. Bấm **Add to Queue** → kết quả vào hàng đợi trên API backend
4. Chuyển sang tab **Export**
5. Bấm **Export ZIP** → file ZIP được tạo tự động trong `submissions/`
6. Nộp file ZIP lên hệ thống chấm (Codabench)

## Lưu ý

- Hàng đợi submission nằm trong RAM của Backend API session — restart server = reset hàng đợi
- `submissions/*.zip` bị git-ignored, CSV được giữ để inspect
- BTC đã công bố hướng dẫn nộp bài chính thức (2026-08-20) — xem
  [docs/Thong tin vong So tuyen AIC2026.md](../../../docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md)
  §4 cho toàn bộ chi tiết. Code đã đối chiếu và khớp với hướng dẫn này (xem ghi chú ✅ đầu file).
- Tối đa **3 lần nộp/gói truy vấn**, chỉ **lần cuối** được tính điểm xếp hạng (Private LB, 100%
  đáp án) — Public LB lúc thi chỉ tính trên 50% đáp án nên có nhiễu, đừng chốt "lần cuối" quá sớm
  chỉ vì điểm Public LB tạm thời thấp/cao.
- **Chỉ `build_submission.py` được ghi CSV/ZIP** — không ghi submission ở nơi khác
