# GEMINI.md

Hướng dẫn cho Antigravity khi làm việc với repo này. File này được **tự động nạp** mỗi phiên —
chỉ chứa thông tin ổn định, không ghi lịch sử hay tiến độ.

> Tài liệu khác (nạp on-demand qua `.agents/skills/`):
> - Kiến trúc hệ thống → skill `architecture`
> - Kaggle GPU encoding → skill `kaggle-jobs`
> - Format nộp bài → skill `submission`
>
> Tài liệu tham chiếu thủ công: [PLAN.md](PLAN.md) (tiến độ)

## Dự án là gì

Hệ thống tìm kiếm video-frame bằng ngôn ngữ tự nhiên cho **AIC 2026** (Hội thi Thử thách Trí tuệ
Nhân tạo TP.HCM). Cho câu mô tả sự kiện, trả về `video_id` + `frame_id` (KIS), kèm `answer`
(Q&A) hoặc chuỗi `frame_id` (TRAKE). Scoring: R-Score/R@k trung bình tại rank 1/5/20/50/100.

3 dạng bài, 3 pipeline riêng biệt (không dùng chung 1 agent):
- **KIS** = workflow tuyến tính, không LLM
- **Q&A** = orchestrator-workers, tối đa 2 vòng reflection (`MAX_AGENT_LOOPS=2`)
- **TRAKE** = pipeline 2 giai đoạn cố định (chọn video → align N mốc)

## Quick Start

```powershell
# Cài đặt backend (lần đầu)
.venv\Scripts\python.exe -m pip install -r requirements.txt

# Cài đặt frontend (lần đầu)
cd frontend; npm install; cd ..

# Chạy hệ thống:
# 1. Khởi động Backend API (FastAPI)
.venv\Scripts\python.exe -m uvicorn scripts.api.main:app --reload --port 8000

# 2. Khởi động Frontend UI (React + Vite)
cd frontend; npm run dev                             # http://localhost:5173

# Lệnh phụ
.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "<query>"   # chạy pipeline từ CLI
.venv\Scripts\python.exe scripts\submit\validate_submission.py     # validate file mới nhất
.venv\Scripts\python.exe scripts\api\_smoke_test.py                # smoke test backend API
```

Cấu hình API key: copy `.env.example` → `.env`, điền ít nhất `GEMINI_API_KEY` hoặc `OPENROUTER_API_KEY`.

## Cấu trúc thư mục

- `frontend/` — Giao diện React (Vite + TypeScript), UI chính thức (http://localhost:5173)
- `scripts/api/` — Backend FastAPI cung cấp REST API cho frontend (http://127.0.0.1:8000)
- `scripts/agent/` — Pipeline & agent LLM:
  - `config.py` — Cấu hình LLM tập trung (`call_llm()`, `PROVIDER_CHAIN`)
  - `pipeline_kis.py` / `pipeline_qa.py` / `pipeline_trake.py`
  - `tools/` — `retrieve.py` (dense CLIP search), `rewrite.py` (VN→EN), `answer_qa.py`, `ocr_lookup.py`, `sparse_index.py` (BM25)
- `scripts/submit/` — `build_submission.py` (sinh CSV/ZIP), `validate_submission.py`
- `test_eval/` — Thư mục kiểm thử & đánh giá (2 nhánh độc lập):
  - `Test/` — Harness đường production: `score_pipelines.py` (Final Score BTC thật), `test_smoke_tools.py`, `test_smoke_pipelines.py`, các test phase 3–6
  - `Eval/` — Backbone bake-off (retrieval-only, không LLM): `run_eval.py` (so sánh embedding), `multi_index.py`, `widen_gt_windows.py`, `eval_ground_truth.json`
- `data/` — **git-ignored**, dữ liệu ngoại tuyến (keyframe, embedding, objects JSON)
- `kaggle_jobs/` — 4 job encode SOTA trên Kaggle GPU (thăm dò, ngoài pipeline chính)
- `submissions/` — Output CSV/ZIP (`*.zip` git-ignored)
- `docs/` — Luật thi, training transcript, paper/slide, và `_archive/` (lưu trữ code/tài liệu cũ gồm cả `app_gradio.py`)

## Tech Stack

- Backend: Python (`.venv`), FastAPI, Uvicorn
- Frontend: React 19, TypeScript, Vite, TailwindCSS
- Models: `sentence-transformers` (`siglip-base-patch16-384`, `siglip2-base-patch16-384`) + `torch` (CPU build)
- Data: `pandas` / `numpy` — metadata & embedding matrix
- LLM: `litellm` → fallback chain: Gemini (`gemini-3.5-flash`) → Groq → NVIDIA NIM / OpenRouter
- Config: `python-dotenv` — load `.env`
- Không database/ORM/message queue — backend quản lý in-memory session queue + file submission

## Quy ước code

- **Comment/UI text**: tiếng Việt (toàn repo)
- **Đặt tên**: `snake_case` — `fast_retrieve`, `run_kis`, `build_kis_csv`
- **`video_id`**: `{batch}_{video_num}` (vd `L21_V001`) — không kèm `.mp4`
- **`frame_id`**: = `frame_idx + 1`, chỉ chuyển đổi tại `retrieve.py`
- **Logging**: `print()` với prefix `[module_name]`
- **Lỗi**: fail loud cho setup/dữ liệu; bắt + hiển thị `⚠️` trên UI cho runtime

## KHÔNG được làm

- ❌ Gọi `litellm` trực tiếp bên ngoài `scripts/agent/config.py:call_llm()`
- ❌ Ghi CSV/ZIP ngoài `scripts/submit/build_submission.py`
- ❌ Commit `.env` hoặc đặt key thật vào `.env.example`
- ❌ Để pipeline chạy vòng LLM không giới hạn (phải có trần `MAX_AGENT_LOOPS`)
- ❌ Force-push hoặc rewrite git history trên `main`
- ❌ Thêm dependency nặng mới mà không kiểm tra thực sự cần
