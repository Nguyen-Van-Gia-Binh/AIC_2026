# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Other docs: [ARCHITECTURE.md](ARCHITECTURE.md) (system design, module responsibilities, locked
> decisions) · [PLAN.md](PLAN.md) (what's left to do, by phase) · [SESSION_LOG.md](SESSION_LOG.md)
> (what happened in each past session). This file only covers stable, day-to-day facts — how to run
> things, where files go, what conventions to follow. It does not track progress or history.

## What this is

A text-to-video-frame search system for **AIC 2026** (Hội thi Thử thách Trí tuệ Nhân tạo TP.HCM), a
video retrieval competition. Given a natural-language description of an event, the system must return
the `video_id` + `frame_id` (KIS), plus an `answer` (Q&A) or a sequence of `frame_id`s (TRAKE). Scoring
is R-Score/R@k averaged across ranks 1/5/20/50/100 — full rules in
[docs/Thong tin vong So tuyen AIC2026.md](<docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>) and
`docs/Training/`.

The system has grown from a single-file CLIP search demo into: a shared retriever, three per-query-type
pipelines (KIS/Q&A/TRAKE), an LLM agent layer for Q&A/TRAKE, a submission CSV/ZIP builder + validator,
and a Gradio UI tying them together. See [ARCHITECTURE.md](ARCHITECTURE.md) for how these fit together
and why.

## Quick Start

Setup (first time):
```
.venv\Scripts\python.exe -m pip install -r requirements.txt
```
Then copy `.env.example` to `.env` and fill in a real `GEMINI_API_KEY` (get one free at
[aistudio.google.com](https://aistudio.google.com/apikey)).

Daily commands — always run through the project venv's Python directly (no activation needed):
```
.venv\Scripts\python.exe scripts\app.py              # main entry point: Gradio UI (KIS/Q&A/TRAKE/Export tabs), http://127.0.0.1:7860
.venv\Scripts\python.exe scripts\index.py             # build the index standalone, print stats (sanity check)
.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "<query>"   # run one pipeline from the CLI, e.g. for debugging
.venv\Scripts\python.exe scripts\submit\validate_submission.py    # validate the newest file in submissions/
```
There is no `npm test`-equivalent test runner configured — `scripts/test_day1.py`, `test_day2_basic.py`,
`test_day2_full.py` are ad-hoc integration scripts, run directly with the venv Python, not via a test
framework. There is no linter/formatter configured either.

## Folder Structure

- `scripts/index.py` — original baseline: builds the CLIP embedding matrix + metadata from `data/extracted/`.
- `scripts/app.py` — Gradio UI, the main entry point when operating the system (human-in-the-loop).
- `scripts/agent/` — pipelines and LLM/tool code:
  - `config.py` — the one place that calls the LLM (`call_llm()`, via LiteLLM → Gemini).
  - `pipeline_kis.py` / `pipeline_qa.py` / `pipeline_trake.py` — one pipeline per query type.
  - `tools/` — `retrieve.py` (CLIP search), `rewrite.py` (VN→EN query rewrite), `ocr_lookup.py`
    (offline Objects JSON reader), `answer_qa.py` (Q&A answer + cross-check).
- `scripts/submit/` — `build_submission.py` (CSV/ZIP writer), `validate_submission.py` (format checker).
  This is the only place that should serialize a submission file.
- `queries/` — sample/test query sets (JSON), not competition-official queries.
- `submissions/` — generated CSV/ZIP output. `*.zip` is git-ignored; keep CSVs for inspection.
- `data/` — git-ignored, external state (video/keyframe/CLIP-feature/Objects-JSON files from BTC).
  Must already be unzipped locally before any script will run.
- `docs/` — competition rules, `docs/Training/` transcripts, and generated reports. Reference material,
  not code — don't treat anything under `docs/` as something to keep in sync with the codebase.
- `.env` / `.env.example` — API keys. `.env` is git-ignored; `.env.example` must only ever contain
  placeholder values, never a real key.

New files go under `scripts/agent/tools/` if they're a single-purpose capability used by more than one
pipeline, or under `scripts/agent/` directly if they're a new top-level pipeline. Don't add new
top-level folders under `scripts/` without a reason — keep pipeline vs. tool vs. submission code in the
three buckets above.

## Tech Stack

- Python via project `.venv` (no Node/JS anywhere in this repo).
- `sentence-transformers` (`clip-ViT-B-32`) — both the image and text encoder; one shared embedding space.
- `torch` (CPU build) — backing framework for `sentence-transformers`.
- `pandas` / `numpy` — metadata table and the embedding matrix.
- `gradio` — the UI (`scripts/app.py`).
- `litellm` — routes LLM calls; currently wired to Google Gemini (`gemini/gemini-3.5-flash`) only.
- No database, no ORM, no message queue — everything is files under `data/`, `queries/`, `submissions/`.

## Code Rules

- **UI text and code comments are written in Vietnamese** — this applies repo-wide now (not just
  `app.py`/`index.py`), including new modules under `scripts/agent/` and `scripts/submit/`. Match the
  surrounding file's comment density; don't switch a Vietnamese-commented file to English mid-edit.
- Function/variable naming: `snake_case` throughout (standard Python convention), e.g. `fast_retrieve`,
  `run_kis`, `build_kis_csv`. No camelCase.
- `video_id` format: `{batch}_{video_num}`, e.g. `L21_V001` — never include the `.mp4` extension in
  anything that touches retrieval, pipelines, or submission output.
- `frame_id` = `frame_idx + 1` (BTC counts frames from 1, the index is 0-based). This conversion happens
  in exactly one place — `scripts/agent/tools/retrieve.py` — don't re-derive it elsewhere.
- CLIP (`clip-ViT-B-32`) is strongest on **English** — query text should be English for best retrieval;
  `scripts/agent/tools/rewrite.py` handles VN→EN translation for the agent pipelines. `pipeline_kis.py`
  alone does not auto-translate (by design — see [ARCHITECTURE.md](ARCHITECTURE.md)).
- Embeddings are stored as float16 in `.npy` files but upcast to float32 and re-normalized on load
  (`index.py`) to avoid drift from float16 rounding — don't skip the re-normalize step if you touch
  index-loading code.
- Error handling: fail loud with a clear message for setup/data problems (e.g. `index.py` raises
  `FileNotFoundError` immediately if `clip-features-32/` is empty); in the Gradio UI, catch and show a
  short `⚠️` status message instead of letting the callback crash — don't let a bad user edit (e.g. an
  emptied `frame_id` cell) take down the whole app.
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
etc.), `docs/paper/`, `docs/slide/`, `submissions/`, caches, and `.env` — check it before adding a new
large-file category rather than duplicating rules. `.gitignore` covers `.venv`, `data/`, `.env`, and
`submissions/*.zip`.

## Updating this file

Update when: a new dependency is added, a command changes, a new top-level folder is introduced, or a
convention above stops being true. Don't record task history, per-feature decisions, or session
summaries here — those belong in [PLAN.md](PLAN.md) / [SESSION_LOG.md](SESSION_LOG.md). This file should
stay stable across sessions, not get an edit every time.
