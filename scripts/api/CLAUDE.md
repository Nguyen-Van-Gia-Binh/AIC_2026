# CLAUDE.md — scripts/api/

Quy tắc riêng cho thư mục này. Root [CLAUDE.md](../../CLAUDE.md) vẫn áp dụng đầy đủ —
đây chỉ là phần bổ sung khi bạn đang sửa code trong `scripts/api/`.

## Backend chỉ là lớp mỏng bọc pipeline

FastAPI expose các pipeline qua HTTP. Không nhồi logic retrieval/agent vào đây — gọi xuống
`scripts/agent/`.

Hai luật một-call-site vẫn giữ khi gọi từ lớp API:

- LLM: chỉ qua `scripts/agent/config.py:call_llm()`. Không `import litellm` ở đây.
- File nộp: chỉ qua `scripts/submit/build_submission.py`. Router `queue` export bằng cách gọi
  hàm đó, không tự ghi CSV/ZIP.

## Router

Một router cho mỗi loại truy vấn dưới `routers/`:

- `kis.py` — KIS search + `POST /api/rewrite` + frame lân cận (màn chi tiết keyframe)
- `qa.py` · `trake.py`
- `queue.py` — hàng đợi + export submission
- `images.py` · `videos.py` — phục vụ file media cho UI

## Lỗi và state

- Endpoint phải **bắt lỗi và trả HTTP status rõ ràng**, không để exception làm sập server.
  (Khác với script setup/offline: ở đó fail loud là đúng.)
- State session/queue giữ **trong RAM** (`state.py`) — không có DB, không persist. Restart là mất.

## Smoke test

`_smoke_test.py` chạy end-to-end KIS/QA/TRAKE/queue/export — cần API key.
