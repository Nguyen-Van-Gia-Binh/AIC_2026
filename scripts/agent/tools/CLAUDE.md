# CLAUDE.md — scripts/agent/tools/

Quy tắc riêng cho thư mục này. Root [CLAUDE.md](../../../CLAUDE.md) vẫn áp dụng đầy đủ —
đây chỉ là phần bổ sung khi bạn đang sửa code trong `scripts/agent/tools/`.

## frame_id — quy đổi CHỈ ở một chỗ

`frame_id = frame_idx + 1` (BTC đếm frame từ 1, index 0-based) xảy ra trong đúng một hàm:
`index_store.py:row_to_hit()`. Đừng tự cộng `+ 1` ở retrieve/rerank/pipeline/submission.

## index_store là singleton tiến trình

`index_store.py` sở hữu ma trận embedding + metadata + text encoder, load **một lần** cho cả
tiến trình. Đừng gọi lại loader từ chỗ khác, đừng import module qua tên khác (chỉ để repo root
trên `sys.path`, luôn `from scripts.agent.tools...`) — làm sai là load index + SigLIP hai lần
(bug này đã xảy ra 3 lần, xem [docs/decisions-log.md](../../../docs/decisions-log.md)).

Embeddings là float16 trong `.npy` nhưng **upcast float32 + chuẩn hoá lại** khi load — đừng bỏ
bước re-normalize nếu chạm code load index.

## Pure vs impure

- **Pure** (không index/model/LLM/I/O): `fusion.py`, `temporal_nms.py`, `query_expand.py`,
  `trake_align.py`. Giữ nguyên tính chất này.
- **Impure**: mọi file còn lại (dùng index, gọi LLM, hoặc đọc file trong `data/`).

## Evidence — đọc cái gì từ đâu

- `objects_lookup.py` đọc **Objects JSON** của BTC — **không phải OCR**.
- `ocr_read.py` mới là OCR thật, chạy **on-demand** chỉ trên candidate đã retrieve. Không
  precompute OCR/VLM cho toàn bộ 177K keyframe.
- `asr_lookup.py` tra transcript; `translate_raw.py` dịch máy (không LLM); `rewrite.py` VN→EN
  qua LLM.

## sparse_index.py

Build cache BM25 offline một lần (`--build`, ~3.5 phút) trước khi `hybrid.py` có tác dụng.
