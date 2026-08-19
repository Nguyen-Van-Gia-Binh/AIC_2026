---
name: architecture
description: >-
  Kiến trúc hệ thống AIC2026: sơ đồ luồng dữ liệu, trách nhiệm từng module,
  quyết định thiết kế đã chốt, interface giữa các thành phần, và danh sách
  "forbidden". Dùng khi cần hiểu cách pipeline hoạt động, thêm/sửa module,
  refactor, hoặc debug flow xuyên suốt hệ thống.
---

# Kiến trúc hệ thống AIC2026

## 1. Sơ đồ luồng dữ liệu

```
Người dùng (thí sinh)
        │  nhập query trên UI, rà soát/sửa kết quả (human-in-the-loop)
        ▼
scripts/app.py  (Gradio, 4 tab: KIS / Q&A / TRAKE / Export)
        │
   ┌────┴─────────────────┬──────────────────────┐
   ▼                      ▼                       ▼
pipeline_kis.py     pipeline_qa.py          pipeline_trake.py
(tuyến tính,         (orchestrator,          (2 giai đoạn cố định:
 không LLM)           tối đa 2 vòng           retrieve video → align
                       reflection)             N mốc theo thứ tự)
   │                      │                       │
   └──────────┬───────────┴───────────┬───────────┘
              ▼                       ▼
   agent/tools/retrieve.py    agent/tools/rewrite.py, answer_qa.py, ocr_lookup.py
   (CLIP cosine similarity     (agent/config.py: call_llm() → LiteLLM → PROVIDER_CHAIN)
    trên ma trận 177K keyframe)
              │
              ▼
        submit/build_submission.py → CSV (kis/qa/trake) → validate_submission.py → ZIP
```

## 2. Trách nhiệm từng module

| Path | Vai trò | Vì sao ở đây |
|------|---------|---------------|
| `scripts/index.py` | Build ma trận CLIP `(N,512)` + metadata từ `data/extracted/` | Layer dữ liệu gốc |
| `scripts/agent/tools/retrieve.py` | Singleton nạp index 1 lần/process; `fast_retrieve()`, `fast_retrieve_for_video()` | Điểm truy cập duy nhất tới ma trận vector |
| `scripts/agent/config.py` | `call_llm(prompt, image_paths, model, temperature, max_tokens)` — bọc LiteLLM, tự fallback qua `PROVIDER_CHAIN` | Nguồn cấu hình LLM duy nhất |
| `scripts/agent/tools/rewrite.py` | `rewrite_query(query, feedback=None)` — dịch VN→EN + tối ưu cho CLIP | Dùng chung cho Q&A và TRAKE |
| `scripts/agent/tools/ocr_lookup.py` | `get_objects()`, `get_objects_for_hits()` — đọc Objects JSON offline | Nguồn "sự thật" cross-check |
| `scripts/agent/tools/answer_qa.py` | `answer_from_hits()` — 2 tầng (objects JSON → LLM Vision) + `_crosscheck_answer()` | Cô lập logic chống ảo giác |
| `scripts/agent/pipeline_kis.py` | `run_kis()` — 1 lệnh gọi `fast_retrieve`, không LLM | KIS không cần agent |
| `scripts/agent/pipeline_qa.py` | `run_qa()` — orchestrator: rewrite → retrieve → answer → (nếu confidence<0.5) reflection | Có gate rõ ràng |
| `scripts/agent/pipeline_trake.py` | `run_trake()` — giai đoạn 1 chọn top-video, giai đoạn 2 align N event tuần tự | Pipeline cố định |
| `scripts/submit/build_submission.py` | `build_kis_csv/build_qa_csv/build_trake_csv/build_zip_submission` | Điểm duy nhất sinh format nộp bài |
| `scripts/submit/validate_submission.py` | `validate_csv_file()`, `validate_zip()` | Lưới an toàn cuối trước nộp |
| `scripts/app.py` | Gradio UI — 4 tab, hàng đợi submission, human-in-the-loop | UI gọi pipeline, không chứa logic riêng |

## 3. Quyết định kiến trúc đã chốt

- **Không dùng 1 agent chung** — chọn theo độ mở: KIS = workflow, Q&A = orchestrator-workers, TRAKE = pipeline cố định.
- **1 nguồn LLM duy nhất**: `scripts/agent/config.py`. Mọi lời gọi LLM đi qua `call_llm()`.
- **Anti-hallucination bắt buộc cho Q&A**: mọi answer qua `_crosscheck_answer()` đối chiếu Objects JSON.
- **File-based, không DB**: state là file (`.npy`/`.csv`/`.json`/`.zip`). Hàng đợi submission chỉ sống trong session Gradio (RAM).
- **`frame_id = frame_idx + 1`** tại `retrieve.py` (điểm duy nhất).
- **Human-in-the-loop là thiết kế chính thức**, không phải fallback.

## 4. Điểm giao tiếp (Interface)

**Entry point ứng dụng**: `scripts/app.py` → `http://127.0.0.1:7860`

**Entry point pipeline (CLI):**
- `run_kis(query_text, top_k=100) -> list[dict]`
- `run_qa(query_text, question=None, top_k=100) -> dict` (trả `results`, `answer`, `best_hit`, `n_loops`, `confidence`)
- `run_trake(query_text, events, top_k_video=5, top_k_frame=10) -> dict` (trả `results`, `best`, `n_events`)

**Schema hit chuẩn** (từ `retrieve.py`, xuyên suốt mọi pipeline):
```python
{"video_id", "n", "frame_idx", "frame_id", "pts_time", "score", "jpg_path"}
```

**LLM Provider Chain** (`config.py`):
- Gemini (`gemini/gemini-3.5-flash`, ưu tiên 1) → Groq (`llama-3.3-70b-versatile` / `llama-3.2-11b-vision-preview`) → NVIDIA NIM (`meta/llama-3.3-70b-instruct` / `meta/llama-3.2-90b-vision-instruct`)
- Key rotation trong nội bộ 1 provider (nhiều key trong `.env`)
- Provider thiếu key → tự bỏ qua

## 5. Forbidden

- Không gọi `litellm` ngoài `agent/config.py:call_llm()`
- Không ghi CSV/ZIP ngoài `submit/build_submission.py`
- Không để pipeline tự thêm `.mp4` hoặc tự ±`frame_id`
- Không thêm code/comment tiếng Anh — quy ước Vietnamese-only
- Không commit `.env`
- Không để pipeline chạy loop không giới hạn (trần `MAX_AGENT_LOOPS=2`)
