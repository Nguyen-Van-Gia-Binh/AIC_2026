# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Other docs: [ARCHITECTURE.md](ARCHITECTURE.md) (system design, module responsibilities, locked
> decisions) · [PLAN.md](PLAN.md) (what's left to do, by phase) · [DECISION.md](DECISION.md) (why past
> architectural/process decisions were made) · [EXPERIMENT.md](EXPERIMENT.md) (past mistakes and how
> they were fixed — read before repeating a debugging path). This file only covers stable, day-to-day
> facts — how to run things, where files go, what conventions to follow. It does not track progress or
> history.

## What this is

A text-to-video-frame search system for **AIC 2026** (Hội thi Thử thách Trí tuệ Nhân tạo TP.HCM), a
video retrieval competition. Given a natural-language description of an event, the system must return
the `video_id` + `frame_id` (KIS), plus an `answer` (Q&A) or a sequence of `frame_id`s (TRAKE). Scoring
is R-Score/R@k averaged across ranks 1/5/20/50/100 — full rules in
[docs/Thong tin vong So tuyen AIC2026.md](<docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>) and
`docs/Training/`.

The system has grown from a single-file CLIP search demo into: a shared retriever, three per-query-type
pipelines (KIS/Q&A/TRAKE), an LLM agent layer for Q&A/TRAKE, and a submission CSV/ZIP builder +
validator. The UI layer is decoupled into a FastAPI backend (`scripts/api/`) and a modern React/Vite
frontend (`frontend/`) (see [ARCHITECTURE.md](ARCHITECTURE.md)).

## Quick Start

Setup (first time):
```
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend; npm install; cd ..
```
Then copy `.env.example` to `.env` and fill in a real `OPENROUTER_API_KEY` (get one at
[openrouter.ai/keys](https://openrouter.ai/keys)).

Daily commands:
```
# Chạy hệ thống sản xuất:
.venv\Scripts\python.exe -m uvicorn scripts.api.main:app --reload --port 8000   # Backend API, http://127.0.0.1:8000/api/health
cd frontend; npm run dev                                                        # React/Vite frontend, http://localhost:5173 (proxy /api → :8000)

# Pipeline & Evaluation CLI:
.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "<query>"   # run one pipeline from the CLI, e.g. for debugging
.venv\Scripts\python.exe scripts\submit\validate_submission.py    # validate the newest file in submissions/
.venv\Scripts\python.exe scripts\agent\tools\sparse_index.py --build       # build BM25 cache 1 lần (~3.5 phút) — bắt buộc trước khi hybrid retrieval có tác dụng
.venv\Scripts\python.exe test_eval\Eval\run_eval.py               # compare embedding backbones (retrieval-only, no LLM) → docs/eval_baseline_comparison.md
.venv\Scripts\python.exe test_eval\Test\score_pipelines.py --types kis  # true BTC Final Score through the production pipelines (needs OPENROUTER_API_KEY)
.venv\Scripts\python.exe scripts\api\_smoke_test.py               # backend API end-to-end smoke test (KIS/QA/TRAKE/queue/export)
```
There is no `npm test`-equivalent test runner configured — the scripts under `test_eval/Test/`
(`test_phase3_rerank.py`, `test_phase4_trake.py`, `test_phase5_ocr.py`, `test_phase6_margin_sweep.py`,
`test_smoke_tools.py`, `test_smoke_pipelines.py`) are ad-hoc integration/benchmark scripts, run
directly with the venv Python, not via a test framework. There is no linter/formatter configured either.

## Folder Structure

- `docs/_archive/app_gradio.py` — **[RETIRED 2026-08-29]** Giao diện Gradio cũ (4 tab KIS/Q&A/TRAKE/Export). Đã chuyển sang `docs/_archive/` sau khi hoàn thiện React UI (`frontend/`) và FastAPI backend (`scripts/api/`).
- `docs/_archive/index_retired.py` — **[RETIRED 2026-08-28]** Từng build CLIP embedding matrix từ `clip-features-32/`.
  Không dùng trong production nữa sau khi `clip-features-32/` đã bị xóa (benchmark 33 query:
  `clip_vitb32` Final=0.290 vs `siglip`=0.549). Giữ nguyên để tham chiếu lịch sử.
- `scripts/agent/` — pipelines and LLM/tool code:
  - `config.py` — the one place that calls the LLM (`call_llm()`, via LiteLLM → Gemini).
  - `pipeline_kis.py` / `pipeline_qa.py` / `pipeline_trake.py` — one pipeline per query type.
  - `tools/` — `retrieve.py` (dense search — **2 singleton**: `fast_retrieve`/`fast_retrieve_for_video`
    dùng **siglip** cho KIS/TRAKE, `fast_retrieve_qa` dùng **siglip2** cho Q&A; `hybrid_retrieve()`
    ghép dense + BM25 qua RRF), `sparse_index.py` (BM25 offline trên Objects JSON + caption — phải
    build cache 1 lần, xem Quick Start), `fusion.py` (RRF thuần), `temporal_nms.py` (khử trùng lặp
    thời gian, thuần), `query_expand.py` (Multi-Aspect Prompt Expansion, template tất định),
    `rerank.py` (risk-aware ranking + Temporal NMS), `rewrite.py` (VN→EN query rewrite),
    `ocr_lookup.py` (offline Objects JSON reader), `answer_qa.py` (Q&A answer + canonical extractor
    + cross-check). `fusion.py`/`temporal_nms.py`/`query_expand.py` là module THUẦN (không nạp
    index/model, không gọi LLM) — cố ý tách riêng để `test_eval/Eval/run_eval.py` dùng lại đúng
    thuật toán của production mà không phải chép thành phiên bản thứ 2 dễ lệch.
- `scripts/submit/` — `build_submission.py` (CSV/ZIP writer), `validate_submission.py` (format checker).
  This is the only place that should serialize a submission file.
- `test_eval/` — everything for testing the system and scoring/comparing quality by the BTC formula
  (see `test_eval/README.md`). Two branches:
  - `test_eval/Eval/` — Phase 6 offline backbone bake-off: `multi_index.py` (index loader + per-model
    text encoders, self-contained — deliberately does NOT import `index.py`/`retrieve.py`),
    `run_eval.py` (compares `clip_vitb32`/`vitl14`/`siglip`/`dfn`/... by R@k, reads
    `eval_ground_truth.json` here, writes `docs/eval_baseline_comparison.md`; cờ `--hybrid`/
    `--expand`/`--nms`/`--strict-dp`/`--coverage-pool`/`--all-features` bật từng bước thuật toán mới
    để đo trước-sau, mặc định TẮT nên số cũ vẫn so sánh được — **Tầng 1 của Regression Guard**), `lookup_frame.py` +
    `widen_gt_windows.py` (ground-truth labeling helpers — see `EVAL_GUIDE.md`),
    `eval_ground_truth.json` (hand-labeled eval set). Retrieval-only, no LLM, deterministic; never
    touches the KIS/QA/TRAKE production path.
  - `test_eval/Test/` — harnesses that DO run the production path (`scripts/agent/*`), need an API
    key, results may vary between runs: `test_phase{3,4,5,6}_*.py` (before/after benchmarks per
    phase), `score_pipelines.py` (true BTC Final Score end-to-end, incl. Q&A answer match; **Tầng 2 của
    Regression Guard** — `--save-baseline` chốt mốc vào `test_eval/Test/e2e_baseline.json`, lần chạy
    sau tự so và thoát code 1 nếu Final tụt quá 0.01),
    `test_smoke_{tools,pipelines}.py` (setup sanity checks).
  - Root of `test_eval/` also holds shared query data: `sample_queries.json`,
    `sotuyen1_bo_de_thi.csv`, `thunghiem_bo_de_thi.csv` (BTC query packages).
- `submissions/` — generated CSV/ZIP output. `*.zip` is git-ignored; keep CSVs for inspection.
- `data/` — git-ignored, external state (video/keyframe/CLIP-feature/Objects-JSON files from BTC).
  Must already be unzipped locally before any script will run.
- `docs/` — competition rules, `docs/Training/` transcripts, and generated reports. Reference material,
  not code — don't treat anything under `docs/` as something to keep in sync with the codebase.
  `docs/_archive/` holds superseded versions of root docs (e.g. `PLAN_Lan1.md`, `ARCHITECTURE_Lan1.md`,
  `CLAUDE_Lan1.md` from the round-1 submission cycle) — historical reference only, never auto-loaded.
- `kaggle_jobs/` — 4 standalone Kaggle-GPU jobs (`01_vit_l14/`, `02_siglip/`, `03_jina/`, `04_dfn/`)
  that encode all 177K keyframes with stronger embedding models (ViT-L/14, SigLIP SO400M, Jina CLIP
  v2, DFN-5B ViT-H/14) than the `clip-ViT-B-32` baseline. Exploratory/ensemble track — pushed and run
  manually via the Kaggle CLI, doesn't touch the live pipeline unless/until a model is deliberately
  swapped into `scripts/index.py`. Each job is pushed by hand; don't push a real GPU job yourself.
- `.env` / `.env.example` — API keys. `.env` is git-ignored; `.env.example` must only ever contain
  placeholder values, never a real key.
- `GEMINI.md` / `.agents/` — a parallel instructions/skills setup for a different coding agent
  (Antigravity), not Claude Code's. `.claudeignore` excludes both from this tool's context — don't
  treat their content as instructions for a Claude Code session. If asked to edit files under
  `.agents/skills/` (e.g. to prep a task for that other agent), edit them explicitly by path like
  any other file — the ignore only affects automatic context loading, not editability.
- `scripts/api/` — **new, being introduced** — the FastAPI backend (app + routers + session state)
  that exposes the existing `scripts/agent/*` pipelines and `scripts/submit/*` over HTTP for the new
  frontend. Sibling to `scripts/agent/` and `scripts/submit/`, same reasoning: a new top-level
  concern gets its own folder under `scripts/`, not scattered across existing ones. It must call into
  `scripts/agent/config.py:call_llm()` and `scripts/submit/build_submission.py` the same way
  `scripts/app.py` does today — no bypassing those two single-call-site rules from the API layer.
  Routers under `scripts/api/routers/`: `kis` (+ `/api/rewrite`, keyframe neighbors), `qa`, `trake`,
  `queue` (+ export), `images` (serve keyframe `.jpg`), `videos` (serve source `.mp4` with HTTP
  Range for in-browser scrubbing, + `/meta` for fps/duration).
- `frontend/` — **new, being introduced** — the React + Vite frontend (Node/npm toolchain lives only
  here, isolated from the rest of the Python repo), replacing the Gradio UI. See
  `docs/superpowers/specs/2026-08-27-multiagent-chat-architecture-design.md` and the Phase 7 plan(s)
  under `docs/superpowers/plans/` for the build-out. The `Chat` tab is enabled but runs on **static
  fixtures** (`src/mock/chatScenarios.ts`, components under `src/components/chat/`) — the real LLM
  router / `scripts/api/routers/chat.py` is Phase con 2/3, not wired yet.

New files go under `scripts/agent/tools/` if they're a single-purpose capability used by more than one
pipeline, or under `scripts/agent/` directly if they're a new top-level pipeline. Don't add new
top-level folders under `scripts/` without a reason — keep pipeline vs. tool vs. submission vs. API
code in the four buckets above.

## Tech Stack

- Python via project `.venv` for everything under `scripts/`, `test_eval/` — retrieval, pipelines,
  agent/LLM code, submission building. This part of the repo stays Node/JS-free.
- `transformers` — text encoder cho **siglip** (`google/siglip-so400m-patch14-384`, KIS/TRAKE)
  và **siglip2** (`google/siglip2-so400m-patch14-384`, Q&A); load qua `multi_index.py`.
  `clip-ViT-B-32` (`sentence-transformers`) đã retire 2026-08-28.
- `torch` (CPU build) — backing framework for `sentence-transformers`.
- `pandas` / `numpy` — metadata table and the embedding matrix.
- `litellm` — routes all text and vision LLM calls through OpenRouter; the model is configured by
  `OPENROUTER_MODEL` and defaults to `google/gemini-2.5-flash`.
- `fastapi` + `uvicorn` (`scripts/api/`) — the backend API that fronts the pipelines/submission code
  for the frontend. New in the decoupled architecture; see `scripts/api/` above.
- **Frontend is React + Vite** under `frontend/` (Node/npm toolchain, isolated to that folder) —
  thay thế hoàn toàn cho Gradio UI (`scripts/app.py` đã chuyển sang `docs/_archive/app_gradio.py`).
- No database, no ORM, no message queue — everything is files under `data/`, `test_eval/`,
  `submissions/`; the backend keeps session/queue state in-process (RAM), not a DB (see the
  architecture spec referenced above for why).

## Code Rules

- **UI text and code comments are written in Vietnamese** — this applies repo-wide now,
  including modules under `scripts/agent/`, `scripts/api/`, and `scripts/submit/`. Match the
  surrounding file's comment density; don't switch a Vietnamese-commented file to English mid-edit.
- Function/variable naming: `snake_case` throughout (standard Python convention), e.g. `fast_retrieve`,
  `run_kis`, `build_kis_csv`. No camelCase.
- **Internal imports use the `scripts.` prefix** — `from scripts.agent.tools.retrieve import …`,
  `from scripts.index import build_index`, etc. — and entry-point scripts put the **repo root** on
  `sys.path` (never `scripts/`). Mixing `from agent…` / `from index…` with the `scripts.` form makes
  Python load a module twice under two names (this caused the CLIP index to load twice at API
  startup); keep the one convention.
- `video_id` format: `{batch}_{video_num}`, e.g. `L21_V001` — never include the `.mp4` extension in
  anything that touches retrieval, pipelines, or submission output.
- `frame_id` = `frame_idx + 1` (BTC counts frames from 1, the index is 0-based). This conversion happens
  in exactly one place — `scripts/agent/tools/retrieve.py` — don't re-derive it elsewhere.
- CLIP / SigLIP is strongest on **English** — query text should be English for best retrieval;
  `scripts/agent/tools/rewrite.py` handles VN→EN translation for the agent pipelines. `pipeline_kis.py`
  alone does not auto-translate (by design — see [ARCHITECTURE.md](ARCHITECTURE.md)).
- Embeddings are stored as float16 in `.npy` files but upcast to float32 and re-normalized on load
  (`index.py`) to avoid drift from float16 rounding — don't skip the re-normalize step if you touch
  index-loading code.
- Error handling: fail loud with a clear message for setup/data problems (e.g. `multi_index.py` raises
  `FileNotFoundError` immediately if `features_siglip/` or `features_siglip2/` is empty); in API endpoints
  / UI, catch and return clear error statuses instead of crashing — don't let a bad user edit take
  down the backend.
- Logging: plain `print()` with a `[module_name]` prefix (e.g. `[retrieve]`, `[qa]`, `[trake]`) — no
  logging framework configured, keep using this convention for consistency.

## DO NOT

- ❌ Don't call `litellm`/Gemini directly anywhere except `scripts/agent/config.py:call_llm()`.
- ❌ Don't write submission CSV/ZIP files anywhere except through `scripts/submit/build_submission.py`.
- ❌ Don't commit `.env`, or put a real API key in `.env.example` — placeholders only.
- ❌ Don't add a new LLM provider or a heavy new dependency without checking it's actually needed —
  time budget before the contest is tight (see [PLAN.md](PLAN.md)); prefer the simplest workflow that
  works over adding agent complexity (see [ARCHITECTURE.md](ARCHITECTURE.md) §3 for the reasoning).
- ❌ Don't let a pipeline (`pipeline_kis/qa/trake.py`) run an unbounded LLM loop — reflection/retry loops
  must have a hard cap (`MAX_AGENT_LOOPS` in `config.py`).
- ❌ Don't force-push or rewrite git history on `main`.

## Ignoring files

`.claudeignore` already excludes `.venv/`, `data/`, all media/binary formats (`*.npy`, `*.jpg`, `*.mp4`,
etc.), `docs/paper/`, `docs/slide/`, `submissions/`, caches, `.env`, and `GEMINI.md`/`.agents/`
(Antigravity's parallel docs, not Claude Code's — see Folder Structure) — check it before adding a new
large-file category rather than duplicating rules. `.gitignore` covers `.venv`, `data/`, `.env`, and
`submissions/*.zip`.

## Updating this file

Update when: a new dependency is added, a command changes, a new top-level folder is introduced, or a
convention above stops being true. Don't record task history, per-feature decisions, or session
summaries here — those belong in [PLAN.md](PLAN.md) (progress) / [DECISION.md](DECISION.md) (why) /
[EXPERIMENT.md](EXPERIMENT.md) (lessons from past mistakes). This file should stay stable across
sessions, not get an edit every time.
