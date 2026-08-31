# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Other docs: [ARCHITECTURE.md](ARCHITECTURE.md) (system design, module responsibilities, tuned
> parameters) · [PLAN.md](PLAN.md) (what's left to do, by phase) ·
> [docs/decisions-log.md](docs/decisions-log.md) (why past decisions were made, and past mistakes —
> read before repeating a debugging path). This file only covers stable, day-to-day facts — how to
> run things, where files go, what conventions to follow. It does not track progress or history.

## What this is

A text-to-video-frame search system for **AIC 2026** (Hội thi Thử thách Trí tuệ Nhân tạo TP.HCM), a
video retrieval competition. Given a natural-language description of an event, the system must return
the `video_id` + `frame_id` (KIS), plus an `answer` (Q&A) or a sequence of `frame_id`s (TRAKE). Scoring
is R-Score/R@k averaged across ranks 1/5/20/50/100 — full rules in
[docs/rules/Thong tin vong So tuyen AIC2026.md](<docs/rules/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>)
and `docs/training/`.

The system: a shared retriever, three per-query-type pipelines (KIS/Q&A/TRAKE), an LLM agent layer for
Q&A/TRAKE, and a submission CSV/ZIP builder + validator. The UI is decoupled into a FastAPI backend
(`scripts/api/`) and a React/Vite frontend (`frontend/`) — see [ARCHITECTURE.md](ARCHITECTURE.md).

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
.venv\Scripts\python.exe -m uvicorn scripts.api.main:app --reload --port 8000   # Backend, http://127.0.0.1:8000/api/health
cd frontend; npm run dev                                                        # Frontend, http://localhost:5173 (proxy /api → :8000)

# Kiểm tra (nhanh → chậm):
.venv\Scripts\python.exe -m pytest tests\unit -q                  # ~10s, tất định, KHÔNG cần data/ hay API key
.venv\Scripts\python.exe tests\e2e\golden_kis_snapshot.py --check # ảnh chụp tất định của cả đường KIS production
.venv\Scripts\python.exe scripts\api\_smoke_test.py               # backend end-to-end (KIS/QA/TRAKE/queue/export) — cần API key
.venv\Scripts\python.exe scripts\submit\validate_submission.py    # validate file mới nhất trong submissions/

# Đo chất lượng:
.venv\Scripts\python.exe tests\eval\run_eval.py                   # so backbone embedding (retrieval-only, không LLM) → docs/reports/
.venv\Scripts\python.exe tests\e2e\score_pipelines.py --types kis # Final Score BTC thật qua pipeline production (cần API key)

# Pipeline CLI (gỡ lỗi từng bước):
.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "<query>"
.venv\Scripts\python.exe scripts\agent\tools\sparse_index.py --build   # build cache BM25 1 lần (~3.5 phút), bắt buộc trước khi hybrid có tác dụng
```

## Folder Structure

`scripts/` has exactly **four buckets**, split by *when code runs* — not by topic:

- `scripts/agent/` — **runtime**: pipelines and LLM/tool code.
  - `config.py` — the one place that calls the LLM (`call_llm()`, via LiteLLM → OpenRouter).
  - `pipeline_kis.py` / `pipeline_qa.py` / `pipeline_trake.py` — one pipeline per query type.
  - `tools/`:
    - **Retrieval** — `index_store.py` (owns the embedding matrix + metadata + text encoder as a
      process singleton; **the only place `frame_id = frame_idx + 1` happens**),
      `multi_index.py` (`MODEL_REGISTRY`; builds an index + text encoder per backbone tag — lives
      here, not under `tests/`, because production loads it; `tests/eval/run_eval.py` imports it
      from here, never the reverse), `retrieve.py` (dense
      cosine queries), `hybrid.py` (dense + BM25 fused by RRF, multi-model RRF), `frames.py`
      (keyframe lookups for the UI layer), `sparse_index.py` (offline BM25 over Objects JSON +
      captions), `fusion.py` (pure RRF), `temporal_nms.py` (pure temporal dedup), `query_expand.py`
      (pure multi-aspect prompt expansion), `rerank.py` (risk-aware ranking + recall-tail preservation).
    - **Q&A** — `answer_qa.py` (3-tier answering + cross-check), `qa_prompts.py` (prompt templates),
      `qa_classify.py` (question-type regexes), `qa_normalize.py` (canonicalize / anti-hallucination).
    - **TRAKE** — `trake_align.py` (pure: monotonic DP + rule-based plausibility).
    - **Evidence** — `objects_lookup.py` (Objects JSON reader — **not OCR**), `ocr_read.py` (real OCR,
      on-demand), `asr_lookup.py` (transcript lookup), `rewrite.py` (VN→EN query rewrite),
      `translate_raw.py` (machine translation, no LLM).
  - `fusion.py` / `temporal_nms.py` / `query_expand.py` / `trake_align.py` are **pure** modules (no
    index, no model, no LLM, no I/O) — deliberately separated so `tests/eval/run_eval.py` can reuse
    production's exact algorithm instead of keeping a second copy that drifts.
- `scripts/api/` — the FastAPI backend exposing the pipelines over HTTP. Routers under `routers/`:
  `kis` (+ `/api/rewrite`, keyframe neighbors), `qa`, `trake`, `queue` (+ export), `images`, `videos`.
  It must call `scripts/agent/config.py:call_llm()` and `scripts/submit/build_submission.py` — no
  bypassing those two single-call-site rules from the API layer.
- `scripts/submit/` — `build_submission.py` (CSV/ZIP writer), `validate_submission.py`. The only place
  that serializes a submission file.
- `scripts/offline/` — **runs once, writes into `data/`**; never on the query path.
  `captions/` · `ocr/` (incl. `es_index.py`, `vlm_ocr_caption.py`) · `shards/` · `analysis/`.

Everything else:

- `tests/` — `unit/` (pytest, deterministic, no `data/` or API key needed) · `eval/` (backbone
  bake-off + ground truth, needs `data/`) · `e2e/` (runs the production path; needs API key, except
  `golden_kis_snapshot.py` which is deterministic) · `data/` (shared query files). See `tests/README.md`.
- `frontend/` — React + Vite (the Node/npm toolchain lives only here).
- `submissions/` — generated CSV/ZIP. `*.zip` is git-ignored; keep CSVs for inspection.
- `data/` — git-ignored external state (video/keyframe/feature/Objects-JSON from BTC). Must be
  unzipped locally before any script will run.
- `docs/` — reference material, not code. `rules/` (competition rules) · `training/` (transcripts) ·
  `reports/` (generated eval numbers) · `presentation/` · `superpowers/` (specs + plans) ·
  `paper/` · `slide/` · `_archive/` (superseded versions, historical only — never auto-loaded).
- `kaggle_jobs/` / `colab_jobs/` — standalone GPU jobs that encode keyframes with stronger embedding
  models. Pushed and run by hand; they don't touch the live pipeline. Don't push a real GPU job yourself.
- `.env` / `.env.example` — API keys. `.env` is git-ignored; `.env.example` must only ever contain
  placeholders.
- `GEMINI.md` / `.agents/` — a parallel setup for a different coding agent (Antigravity), not Claude
  Code's. `.claudeignore` excludes both — don't treat their content as instructions here. They are
  still editable by explicit path if asked.

New files go under `scripts/agent/tools/` if they're a single-purpose capability used by more than one
pipeline, or under `scripts/agent/` directly if they're a new top-level pipeline. **Don't add a fifth
bucket under `scripts/`** — if something doesn't fit runtime/api/submit/offline, that's a signal the
boundary is wrong, not that a new folder is needed.

## Tech Stack

- Python via project `.venv` for everything under `scripts/` and `tests/`. This part of the repo stays
  Node/JS-free.
- `transformers` — text encoder for **siglip** (`google/siglip-so400m-patch14-384`) and **siglip2**
  (`google/siglip2-so400m-patch14-384`); loaded through `scripts/agent/tools/multi_index.py`.
- `torch` (CUDA build `2.8.0+cu129`; the machine has an RTX 5050 Laptop, sm_120, **8 GB VRAM**) ·
  `pandas` / `numpy` — the metadata table and embedding matrix.
- `litellm` — routes every text and vision LLM call; provider chosen by `AIC_MODE`:

  | `AIC_MODE` | Provider | Use it for | Cost |
  |---|---|---|---|
  | `local` | LM Studio (`LM_STUDIO_BASE`, `LM_STUDIO_MODEL`) | smoke tests, edit-run loops | free |
  | `test` | Gemini free tier → OpenRouter (`OPENROUTER_MODEL`) | **every number you compare** | cheap |
  | `contest` | OpenRouter (`OPENROUTER_MODEL_CONTEST`) | the real submission | expensive |

  **Never take a comparison number from `AIC_MODE=local`.** 8 GB VRAM means a quantized ~7B VLM,
  materially worse than the contest model at reading a scene — tuning a parameter against a local
  score optimizes for the wrong model. `local` has no paid fallback on purpose: if LM Studio is
  down it fails loudly rather than silently spending money.
- `fastapi` + `uvicorn` (`scripts/api/`) · `pytest` (`tests/unit/`).
- Frontend is React + Vite under `frontend/`.
- No database, no ORM, no message queue — everything is files under `data/`, `tests/`, `submissions/`;
  the backend keeps session/queue state in-process (RAM).

## Code Rules

- **UI text and code comments are written in Vietnamese, with diacritics** — repo-wide, including
  `scripts/agent/`, `scripts/api/`, `scripts/submit/`. The one deliberate exception is the LLM prompt
  text in `qa_prompts.py` and the crosscheck prompt in `pipeline_trake.py` (English — models follow
  them better; changing a character there changes system behavior).
- Function/variable naming: `snake_case` throughout. No camelCase.
- **Internal imports use the `scripts.` prefix** — `from scripts.agent.tools.retrieve import …` — and
  **only the repo root** goes on `sys.path`. Never put `scripts/` on `sys.path`: that makes Python
  load the same module under two names and load the index + SigLIP twice (this bug has now bitten
  three times — see docs/decisions-log.md).
- **`sys.path` boilerplate**: keep it in files that have a `__main__` block you can run directly;
  remove it from import-only modules. `tests/conftest.py` handles it for the whole test suite.
- `video_id` format: `{batch}_{video_num}`, e.g. `L21_V001` — never include the `.mp4` extension in
  anything touching retrieval, pipelines, or submission output.
- `frame_id = frame_idx + 1` (BTC counts frames from 1, the index is 0-based). This conversion happens
  in exactly one function — `scripts/agent/tools/index_store.py:row_to_hit()`. Don't re-derive it.
- SigLIP is strongest on **English** — query text should be English for best retrieval;
  `rewrite.py` handles VN→EN for the agent pipelines. `pipeline_kis.py` alone does not auto-translate
  (by design — see [ARCHITECTURE.md](ARCHITECTURE.md)).
- Embeddings are float16 in `.npy` but upcast to float32 and re-normalized on load — don't skip the
  re-normalize step if you touch index-loading code.
- Error handling: fail loud with a clear message for setup/data problems; in API endpoints, catch and
  return clear error statuses instead of crashing.
- Logging: plain `print()` with a `[module_name]` prefix (e.g. `[retrieve]`, `[qa]`, `[trake]`).

## Testing Convention

- **A block with `assert` goes to `tests/unit/`** as a pytest function — not into a `__main__` block.
- **`__main__` blocks are for CLI demos and tools only** (things that print output for a human to read,
  or that need `data/`/an API key).
- Monkeypatch the **module that owns the function being called**, using pytest's `monkeypatch` fixture
  — not by assigning over a global. Patching the wrong module makes a test pass for the wrong reason
  (this has happened; see docs/decisions-log.md).
- After any refactor, `tests/e2e/golden_kis_snapshot.py --check` must still match. It is deterministic
  (KIS calls no LLM), so any difference is a real behavior change, not noise.

## DO NOT

- ❌ Don't call `litellm` directly anywhere except `scripts/agent/config.py:call_llm()`.
- ❌ Don't write submission CSV/ZIP files anywhere except through `scripts/submit/build_submission.py`.
- ❌ Don't commit `.env`, or put a real API key in `.env.example`.
- ❌ Don't add a new LLM provider or a heavy dependency without checking it's actually needed — the
  time budget before the contest is tight (see [PLAN.md](PLAN.md)).
- ❌ Don't let a pipeline run an unbounded LLM loop — reflection/retry loops need a hard cap
  (`MAX_AGENT_LOOPS` in `config.py`).
- ❌ Don't run OCR/VLM generation over all 177K keyframes **on the query path or on the dev machine**
  — new evidence signals run **on-demand**, only on already-retrieved candidates. (Encoding text
  that already exists is fine. A deliberate offline shard job on Kaggle/Colab is also fine — that's
  what `scripts/offline/ocr/run_ocr_shard_local.py` and `colab_jobs/06_paddleocr_vietocr_shard*/`
  exist for. The ban is on doing it inline, not on doing it at all.)
- ❌ Don't change tuned thresholds without re-measuring **on a harness that actually reaches the code
  you changed** — check with grep before trusting one:
  - `MARGIN_THRESHOLD`, `RECALL_HEAD_N`, `SPREAD_MAX_PER_VIDEO` live in `rerank.py`, which
    `run_eval.py` **never imports**. Use `tests/e2e/score_pipelines.py --types kis` (real `run_kis()`,
    no LLM, free).
  - `run_eval.py` measures backbone retrieval only, through `multi_index.py`.
- ❌ Don't force-push or rewrite git history on `main`.

## Ignoring files

`.claudeignore` excludes `.venv/`, `data/`, media/binary formats (`*.npy`, `*.jpg`, `*.mp4`, …),
`docs/paper/`, `docs/slide/`, `submissions/`, caches, `.env`, and `GEMINI.md`/`.agents/`. `.gitignore`
covers `.venv`, `data/`, `.env`, `submissions/*.zip`, and generated manifests.

## Updating this file

Update when: a dependency is added, a command changes, a bucket under `scripts/` changes meaning, or a
convention above stops being true. Don't record task history, per-feature decisions, or session
summaries here — those belong in [PLAN.md](PLAN.md) (progress) or
[docs/decisions-log.md](docs/decisions-log.md) (why / lessons). This file should stay stable across
sessions.
