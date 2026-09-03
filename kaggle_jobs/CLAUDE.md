# CLAUDE.md — kaggle_jobs/

Quy tắc riêng cho thư mục này. Root [CLAUDE.md](../CLAUDE.md) vẫn áp dụng đầy đủ —
đây chỉ là phần bổ sung. Quy trình chi tiết + sự cố đã gặp nằm trong [README.md](README.md)
(đọc phần đầu README trước khi sửa bất cứ `main.py` nào).

## Bất biến

- Job GPU **standalone**, encode keyframe / chạy OCR-caption bằng model mạnh hơn — **không đụng
  pipeline live**. Không import gì từ đây vào `scripts/agent/`.
- **Đừng tự push job GPU thật.** Chỉ sửa file cục bộ, compile-check, và nếu cần chẩn đoán thì
  dùng `_diag/` (không tốn GPU đáng kể). Sau khi sửa: báo rõ đã đổi gì + kiểm chứng tới đâu,
  rồi hỏi người dùng chọn GPU / tự push.
- Muốn thử nhanh: bật `SMOKE_TEST = True` đầu `main.py` (vài video), nhớ tắt lại trước khi chạy full.

## Quy ước tên

`NN_model/` (ví dụ `01_vit_l14`, `05_qwen_vl_ocr_caption`); job chia shard thêm hậu tố
`_shardN`. `_archive_*` và `_archive_logs_*` là lịch sử — không auto-load, đừng sửa.

`colab_jobs/` chạy theo cùng bộ quy ước này.
