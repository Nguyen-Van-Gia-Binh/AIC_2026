# CLAUDE.md — frontend/

Quy tắc riêng cho thư mục này. Root [CLAUDE.md](../CLAUDE.md) vẫn áp dụng đầy đủ —
đây chỉ là phần bổ sung. Xem [README.md](README.md) cho hướng dẫn chạy.

## Đây là vùng Node/JS DUY NHẤT của repo

- Toàn bộ toolchain Node/npm chỉ sống ở đây. Phần `scripts/` + `tests/` giữ Python thuần, không JS.
- Quy ước `snake_case` của Python **không** áp dụng ở đây — dùng đúng quy ước React/TS
  (`camelCase` cho biến/hàm, `PascalCase` cho component).
- Comment tiếng Việt CÓ DẤU vẫn áp dụng.

## Kiến trúc

React + Vite. Frontend chạy `http://localhost:5173`, proxy `/api` → `http://127.0.0.1:8000`
(backend `scripts/api/`). Không gọi thẳng OpenRouter hay đọc `data/` từ frontend — mọi thứ đi
qua backend.

## Chạy

```
cd frontend; npm install     # lần đầu
cd frontend; npm run dev
```
