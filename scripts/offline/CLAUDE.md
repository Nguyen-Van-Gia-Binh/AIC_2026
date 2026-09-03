# CLAUDE.md — scripts/offline/

Quy tắc riêng cho thư mục này. Root [CLAUDE.md](../../CLAUDE.md) vẫn áp dụng đầy đủ —
đây chỉ là phần bổ sung. Chi tiết từng thư mục con (`captions/`, `ocr/`, `shards/`,
`analysis/`) nằm trong [README.md](README.md) cùng cấp.

## Bất biến

- Code ở đây **chạy một lần, ghi vào `data/`**, không bao giờ nằm trên query path. Nếu một hàm
  ở đây bị pipeline realtime import → nó đã đặt sai chỗ.
- **Không** precompute OCR/VLM description cho toàn bộ 177K keyframe. Tín hiệu evidence mới chạy
  on-demand trên candidate đã retrieve (thuộc `scripts/agent/tools/`). Encode lại text đã có
  thì được; cấm là *sinh* nội dung ở quy mô đó.
- Dependency nặng (torch CUDA, paddleocr, vietocr) **không** có trong `requirements.txt` — xem
  docstring từng file.

## Đường dẫn

Mọi script tự trỏ về repo root bằng `Path(__file__).resolve().parent...` — **không cần `cd`**
trước khi chạy.
