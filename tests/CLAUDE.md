# CLAUDE.md — tests/

Quy tắc riêng cho thư mục này. Root [CLAUDE.md](../CLAUDE.md) vẫn áp dụng đầy đủ —
đây chỉ là phần bổ sung. Xem [README.md](README.md) cho mô tả từng tầng.

## Ba tầng

- `unit/` — pytest, **tất định**, KHÔNG cần `data/` hay API key (~10s). Đây là chỗ mặc định
  cho test mới.
- `eval/` — bake-off backbone embedding + ground truth, **cần `data/`**, không LLM.
- `e2e/` — chạy đúng đường production, **cần API key**. Ngoại lệ: `golden_kis_snapshot.py`
  tất định (KIS không gọi LLM).

## Luật viết test

- Block có `assert` → thành hàm pytest trong `unit/`, **không** nhét vào `__main__`.
- `__main__` chỉ dành cho demo CLI / công cụ (in ra cho người đọc, hoặc cần `data/` / API key).
- Monkeypatch **module sở hữu hàm được gọi**, dùng fixture `monkeypatch` của pytest — không gán
  đè global. Patch nhầm module làm test pass vì lý do sai (đã xảy ra — xem
  [docs/decisions-log.md](../docs/decisions-log.md)).
- `sys.path` boilerplate: `conftest.py` lo cho cả suite — đừng thêm vào từng file test.

## Sau refactor

`.venv\Scripts\python.exe tests\e2e\golden_kis_snapshot.py --check` phải còn khớp. Nó tất định,
nên mọi khác biệt là thay đổi hành vi thật, không phải nhiễu.
