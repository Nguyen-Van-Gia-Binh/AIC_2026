# AIC2026 — Architecture

> Xem [PLAN.md](PLAN.md) cho tiến độ/việc cần làm, [CLAUDE.md](CLAUDE.md) cho quy ước code chung.
> File này ghi cấu trúc và các quyết định đã chốt — không lặp lại nội dung code, chỉ trỏ tới nó.

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
        submit/build_submission.py → CSV (kis/qa/trake) → submit/validate_submission.py → zip
```

## 2. Trách nhiệm từng module

| Path                                                                          | Vai trò                                                                                                                                              | Vì sao ở đây                                                                                                          |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| [scripts/index.py](scripts/index.py)                                           | Build ma trận CLIP`(N,512)` + metadata từ `data/extracted/`                                                                                     | Layer dữ liệu gốc, không đổi từ baseline ban đầu                                                                 |
| [scripts/agent/tools/retrieve.py](scripts/agent/tools/retrieve.py)             | Singleton nạp index 1 lần/process;`fast_retrieve()`, `fast_retrieve_for_video()`. Mặc định luôn dùng `clip_vitb32`; biến môi trường `AIC_RETRIEVE_MODEL` (`vitl14`/`siglip`/`dfn`) là escape-hatch để thử model khác qua `scripts/eval/multi_index.py` — chỉ dùng để so điểm thủ công, KHÔNG đổi mặc định production | Điểm truy cập duy nhất tới ma trận vector — mọi pipeline đều gọi qua đây, không tự`build_index()` riêng |
| [scripts/agent/config.py](scripts/agent/config.py)                             | `call_llm(prompt, image_paths, model, temperature, max_tokens)` — bọc LiteLLM, tự fallback qua `PROVIDER_CHAIN` (Gemini → Groq → NVIDIA NIM) | Nguồn cấu hình LLM duy nhất (API key, model name,`MIN_OUTPUT_TOKENS`, `MAX_AGENT_LOOPS`)                          |
| [scripts/agent/tools/rewrite.py](scripts/agent/tools/rewrite.py)               | `rewrite_query(query, feedback=None)` — dịch VN→EN + tối ưu visual-centric cho CLIP                                                            | Tách riêng khỏi pipeline để dùng chung cho cả Q&A và TRAKE                                                        |
| [scripts/agent/tools/ocr_lookup.py](scripts/agent/tools/ocr_lookup.py)         | `get_objects()`, `get_objects_for_hits()` — đọc Objects JSON (Faster R-CNN) offline                                                            | Không tốn gọi API; nguồn "sự thật" để cross-check answer                                                          |
| [scripts/agent/tools/answer_qa.py](scripts/agent/tools/answer_qa.py)           | `answer_from_hits()` — 2 tầng (objects JSON → LLM Vision) + `_crosscheck_answer()`                                                             | Cô lập logic chống ảo giác (rủi ro AI-safety lớn nhất của bài Q&A)                                              |
| [scripts/agent/pipeline_kis.py](scripts/agent/pipeline_kis.py)                 | `run_kis()` — 1 lệnh gọi `fast_retrieve`, không LLM                                                                                           | KIS không cần agent (xem §3)                                                                                           |
| [scripts/agent/pipeline_qa.py](scripts/agent/pipeline_qa.py)                   | `run_qa()` — orchestrator: rewrite → retrieve → answer → (nếu confidence<0.5) rewrite+feedback → retrieve → answer lại                      | Orchestrator-workers pattern, có gate rõ ràng (không phải free-form agent loop)                                      |
| [scripts/agent/pipeline_trake.py](scripts/agent/pipeline_trake.py)             | `run_trake()` — giai đoạn 1 chọn top-video, giai đoạn 2 align N event tuần tự (`frame_idx` phải tăng dần)                              | Structured pipeline cố định, không để LLM tự quyết định số bước                                              |
| [scripts/submit/build_submission.py](scripts/submit/build_submission.py)       | `build_kis_csv/build_qa_csv/build_trake_csv/build_zip_submission`                                                                                   | Điểm duy nhất sinh format nộp bài — pipeline không tự ghi CSV                                                     |
| [scripts/submit/validate_submission.py](scripts/submit/validate_submission.py) | `validate_csv_file()`, `validate_zip()`                                                                                                           | Lưới an toàn cuối trước khi nộp; chạy độc lập, không phụ thuộc pipeline                                     |
| [scripts/app.py](scripts/app.py)                                               | Gradio UI — 4 tab, hàng đợi submission trong session, human-in-the-loop edit trước export                                                       | UI**gọi** pipeline/submit, không chứa logic retrieval/answer riêng                                              |

## 3. Quyết định kiến trúc đã chốt

- **Không dùng 1 kiến trúc agent chung cho cả 3 dạng bài** — chọn theo độ mở của task
  (nguyên tắc từ `docs/Training/AIC2026_TongHop_LuatThi_va_KienTrucAgent.md`, dựa trên
  "Building Effective AI Agents" của Anthropic):
  - **KIS** = workflow tuyến tính, không LLM. Task đóng, không cần agent.
  - **Q&A** = orchestrator-workers, loop có trần (`MAX_AGENT_LOOPS=2`), có gate confidence rõ ràng.
    Task mở vừa phải (không biết trước câu hỏi cần bao nhiêu tầng info) nhưng rủi ro sai cao
    (trả lời sai answer = R-Score về 0 dù đúng frame) nên **bắt buộc cross-check** trước khi trả lời.
  - **TRAKE** = pipeline 2 giai đoạn cố định (không phải agent tự do), vì thứ tự N mốc đã biết trước.
- **1 nguồn cấu hình LLM duy nhất**: `scripts/agent/config.py`. Mọi lời gọi LLM đi qua `call_llm()`,
  không gọi `litellm` trực tiếp ở nơi khác.
- **Anti-hallucination bắt buộc cho Q&A**: mọi answer từ tầng vision (Gemini/Groq/NVIDIA NIM tuỳ
  provider nào đang phục vụ trong `PROVIDER_CHAIN`) phải qua `_crosscheck_answer()` đối chiếu với
  Objects JSON trước khi coi là đáng tin (`confidence` cao/thấp theo kết quả cross-check).
- **File-based, không DB**: toàn bộ state là file (`.npy`/`.csv` index, `queries/*.json`,
  `submissions/*.csv|zip`). Hàng đợi submission trong `app.py` chỉ sống trong session Gradio (RAM),
  mất khi restart — chấp nhận được vì vòng sơ tuyển không phải chạy 24/7.
- **frame_id luôn tính từ `frame_idx + 1`** ngay tại `retrieve.py` (điểm duy nhất) — pipeline và UI
  phía sau không tự +1 lần nữa ở đâu khác.
- **Human-in-the-loop là một phần thiết kế, không phải fallback**: `app.py` luôn cho sửa tay
  (dataframe) trước khi add-to-queue, đúng tinh thần luật thi cho phép con người rà soát.

## 4. Không được làm (forbidden)

- Không gọi `litellm` (Gemini/Groq/NVIDIA NIM) trực tiếp bên ngoài `agent/config.py:call_llm()`.
- Không viết CSV/ZIP submission ở đâu khác ngoài `submit/build_submission.py`.
- Không để pipeline (`pipeline_kis/qa/trake.py`) tự thêm `.mp4` hoặc tự trừ/cộng `frame_id` — việc
  chuẩn hoá `video_id`/`frame_id` chỉ xảy ra ở `retrieve.py` (đọc) và `build_submission.py` (ghi).
- Không thêm code/comment tiếng Anh vào `scripts/app.py`, `scripts/index.py` — quy ước Vietnamese-only
  của repo (xem `CLAUDE.md`).
- Không commit `.env` hoặc bất kỳ file nào chứa key thật (chỉ `.env.example` với placeholder được
  commit).
- Không để TRAKE/Q&A pipeline chạy vòng lặp không giới hạn — mọi reflection loop phải có trần cứng
  (hiện là `MAX_AGENT_LOOPS=2`), theo nguyên tắc ACI (giới hạn tool-call loop để kiểm soát cost/latency).

## 5. Điểm giao tiếp (interface)

- **Entry point ứng dụng**: `scripts/app.py` (Gradio, `python scripts/app.py`, mặc định
  `http://127.0.0.1:7860`).
- **Entry point pipeline (dùng độc lập/CLI)**:
  - `run_kis(query_text: str, top_k: int = 100) -> list[dict]`
  - `run_qa(query_text: str, question: str | None = None, top_k: int = 100) -> dict`
    (trả `results`, `answer`, `best_hit`, `n_loops`, `confidence`)
  - `run_trake(query_text: str, events: list[str], top_k_video=5, top_k_frame=10) -> dict`
    (trả `results`, `best`, `n_events`)
- **Schema hit chuẩn** (trả về từ `retrieve.py`, dùng xuyên suốt mọi pipeline):
  `{video_id, n, frame_idx, frame_id, pts_time, score, jpg_path}`
- **Không có database/API bên ngoài nào khác** ngoài LLM provider (qua LiteLLM). Dữ liệu vào
  là file tĩnh dưới `data/extracted/` (git-ignored, xem `CLAUDE.md`).
- **External service**: LLM qua LiteLLM, theo chuỗi fallback `PROVIDER_CHAIN` trong
  `agent/config.py` — Google Gemini (`gemini/gemini-3.5-flash`, ưu tiên 1) → Groq
  (`llama-3.3-70b-versatile`/`llama-3.2-11b-vision-preview`, fallback 2) → NVIDIA NIM
  (`meta/llama-3.3-70b-instruct`/`meta/llama-3.2-90b-vision-instruct`, fallback 3). Key trong `.env`
  (`GEMINI_API_KEY`, `GROQ_API_KEY`, `NVIDIA_NIM_API_KEY`, không commit); provider nào thiếu key sẽ
  tự bị bỏ qua trong chuỗi.
