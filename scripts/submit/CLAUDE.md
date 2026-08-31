# CLAUDE.md — scripts/submit/

Quy tắc riêng cho thư mục này. Root [CLAUDE.md](../../CLAUDE.md) vẫn áp dụng đầy đủ —
đây chỉ là phần bổ sung khi bạn đang sửa code trong `scripts/submit/`.

## Nơi DUY NHẤT serialize file nộp

- `build_submission.py` — ghi CSV/ZIP. Không có chỗ nào khác trong repo được phép ghi file nộp.
- `validate_submission.py` — kiểm file mới nhất trong `submissions/`.

Nếu một chỗ khác (API router, script) cần xuất submission → nó phải gọi `build_submission.py`,
không tự format.

## Format bắt buộc

- `video_id`: `{batch}_{video_num}`, ví dụ `L21_V001`. **Không** kèm đuôi `.mp4` ở bất cứ đâu.
- `frame_id`: đếm từ 1 (đã quy đổi ở `scripts/agent/tools/index_store.py:row_to_hit()` — đừng
  cộng `+ 1` lại lần nữa ở đây).
- KIS: `video_id` + `frame_id`. Q&A: thêm `answer`. TRAKE: dãy `frame_id`.

## Đầu ra

`submissions/` — giữ lại CSV để soi; `*.zip` bị git-ignore.
