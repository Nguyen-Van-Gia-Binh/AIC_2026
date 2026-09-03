# CLAUDE.md — scripts/agent/

Quy tắc riêng cho thư mục này. Root [CLAUDE.md](../../CLAUDE.md) vẫn áp dụng đầy đủ —
đây chỉ là phần bổ sung khi bạn đang sửa code trong `scripts/agent/`.

## Tầng runtime — code chạy trên query path

- `config.py` là **nơi duy nhất** gọi LLM (`call_llm()`, qua LiteLLM → OpenRouter). Đừng
  `import litellm` ở bất kỳ file nào khác trong thư mục này.
- Một pipeline cho mỗi loại truy vấn: `pipeline_kis.py` / `pipeline_qa.py` / `pipeline_trake.py`.
  Không gộp, không thêm loại thứ tư mà chưa bàn.
- `pipeline_kis.py` **không tự dịch VN→EN** (cố ý — xem [ARCHITECTURE.md](../../ARCHITECTURE.md)).
  Các pipeline agent (qa/trake) mới dùng `tools/rewrite.py`.

## Module pure — không được thêm phụ thuộc nặng

`fusion.py` · `temporal_nms.py` · `query_expand.py` · `trake_align.py` là **pure**: không đụng
index, không load model, không gọi LLM, không I/O. `tests/eval/run_eval.py` import lại đúng các
module này để không giữ bản sao thuật toán bị lệch. Nếu thấy mình cần thêm I/O vào đây → tách
phần đó ra chỗ khác.

## Vòng lặp LLM

Mọi vòng reflection/retry phải có trần cứng. Hiện tại `MAX_AGENT_LOOPS = 2` trong `config.py`.
Không viết loop LLM không chặn.

## Comment/docstring: tiếng Việt CÓ DẤU

Ngoại lệ duy nhất: prompt tiếng Anh trong `tools/qa_prompts.py` và prompt crosscheck trong
`pipeline_trake.py` — đổi một ký tự ở đó là đổi hành vi hệ thống.
