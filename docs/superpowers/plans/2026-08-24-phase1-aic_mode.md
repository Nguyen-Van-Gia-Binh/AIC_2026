# Phase 1 Implementation Plan: AIC_MODE Environment Variable

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add an `AIC_MODE` environment variable to select between test (cheap) and contest (stronger) LLM models, without changing the `call_llm()` signature.

**Architecture:** Extend the existing pattern in `config.py` where `OPENROUTER_MODEL` is read from `.env`. Add `AIC_MODE` (default: "test"), which routes to either `OPENROUTER_MODEL` (test) or `OPENROUTER_MODEL_CONTEST` (contest). The model selection happens at module load time, so all calls to `call_llm()` automatically use the correct model.

**Tech Stack:** Python `os.getenv()`, LiteLLM, OpenRouter API

**Spec:** [PLAN.md](../../PLAN.md) — Phase 1 section

## Global Constraints

- No changes to `call_llm()` signature or behavior
- Default to test mode (cheap model) when `AIC_MODE` is not set
- Log output must clearly indicate which model and mode is active
- Follow existing code conventions: Vietnamese comments, `[config]` log prefix

---

## Task 1: Extend config.py to support AIC_MODE selection

**Files:**
- Modify: `scripts/agent/config.py:35-40` (OPENROUTER_MODEL loading section)
- Modify: `scripts/agent/config.py:44-55` (PROVIDER_CHAIN section)

**Interfaces:**
- Consumes: Environment variables `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_MODEL_CONTEST`, `AIC_MODE`
- Produces: Module-level constants `OPENROUTER_MODEL`, `AIC_MODE`, `MODEL_TEXT`, `MODEL_VISION` (unchanged signatures)

- [x] **Step 1: Add AIC_MODE environment variable reading**

After line 37 (after `OPENROUTER_MODEL` is defined), add:

```python
AIC_MODE = os.getenv("AIC_MODE", "test").strip().lower()
if AIC_MODE not in ("test", "contest"):
    print(f"[config] WARNING: AIC_MODE='{AIC_MODE}' khong hop le, dung 'test' hoac 'contest' thay the. Mac dinh: 'test'")
    AIC_MODE = "test"
```

- [x] **Step 2: Add OPENROUTER_MODEL_CONTEST reading**

After the `AIC_MODE` block, add:

```python
OPENROUTER_MODEL_CONTEST = os.getenv("OPENROUTER_MODEL_CONTEST", "").strip()
if OPENROUTER_MODEL_CONTEST.startswith("openrouter/"):
    OPENROUTER_MODEL_CONTEST = OPENROUTER_MODEL_CONTEST[len("openrouter/"):]
```

- [x] **Step 3: Select model based on AIC_MODE**

Before line 44 (before `PROVIDER_CHAIN` definition), add:

```python
# Chon model theo che do test/contest
_selected_model = OPENROUTER_MODEL_CONTEST if AIC_MODE == "contest" else OPENROUTER_MODEL
if AIC_MODE == "contest" and not OPENROUTER_MODEL_CONTEST:
    print("[config] WARNING: AIC_MODE=contest nhung OPENROUTER_MODEL_CONTEST trong .env trong. Dung OPENROUTER_MODEL thay the.")
    _selected_model = OPENROUTER_MODEL
```

- [x] **Step 4: Update PROVIDER_CHAIN to use selected model**

Modify the PROVIDER_CHAIN definition (lines 45-52) to use `_selected_model`:

```python
PROVIDER_CHAIN = [
    {
        "name": "openrouter",
        "model_text": f"openrouter/{_selected_model}",
        "model_vision": f"openrouter/{_selected_model}",
        "api_keys": OPENROUTER_API_KEYS,
    },
]
```

- [x] **Step 5: Update call_llm() log to show AIC_MODE and model**

Modify line 124 to include mode information:

```python
print(f"[config] OpenRouter AIC_MODE={AIC_MODE} model={_selected_model} ({'vision' if is_vision else 'text'})")
```

- [x] **Step 6: Run config.py test to verify variables load correctly**

Execute:
```bash
.venv\Scripts\python.exe scripts\agent\config.py
```

Expected output should show:
- `[config] Testing OpenRouter...`
- `[config] OpenRouter AIC_MODE=test model=google/gemini-2.5-flash (text)` (or whatever OPENROUTER_MODEL is set to)
- No errors

If you see `AIC_MODE=contest`, confirm OPENROUTER_MODEL_CONTEST is actually being read.

- [x] **Step 7: Commit the config changes**

```bash
git add scripts/agent/config.py
git commit -m "feat: add AIC_MODE environment variable for test/contest model selection"
```

---

## Task 2: Update .env.example with new variables

**Files:**
- Modify: `.env.example` (add OPENROUTER_MODEL_CONTEST and AIC_MODE documentation)

**Interfaces:**
- Consumes: None (static file)
- Produces: Updated `.env.example` template for team reference

- [x] **Step 1: Add OPENROUTER_MODEL_CONTEST and AIC_MODE to .env.example**

Open `.env.example` and add after existing `OPENROUTER_MODEL` line:

```
# Model to use in contest submission (AIC_MODE=contest). If not set, falls back to OPENROUTER_MODEL.
OPENROUTER_MODEL_CONTEST=

# Development mode: "test" (cheap model from OPENROUTER_MODEL) or "contest" (stronger model from OPENROUTER_MODEL_CONTEST).
# Default: "test"
AIC_MODE=test
```

- [x] **Step 2: Verify .env.example has no real API keys**

Check that all values are still placeholders (empty or "your_...").

- [x] **Step 3: Commit .env.example**

```bash
git add .env.example
git commit -m "docs: add OPENROUTER_MODEL_CONTEST and AIC_MODE documentation to .env.example"
```

---

## Task 3: Prepare for Phase 1 UI verification

**Files:**
- Modify: `.env` (local, git-ignored — person A only, done before Phase 1 verification)

**Interfaces:**
- Consumes: Existing `.env` with valid `OPENROUTER_API_KEY`
- Produces: `.env` with `OPENROUTER_MODEL_CONTEST` set to a stronger model

- [x] **Step 1: Copy a stronger model ID to OPENROUTER_MODEL_CONTEST**

Person A: In your `.env`, add or update:
```
OPENROUTER_MODEL_CONTEST=google/gemini-2.0-pro-exp-02-05
```
(or another stronger model available via OpenRouter at the time — verify it's different from OPENROUTER_MODEL)

- [x] **Step 2: Verify .env is git-ignored and has no placeholder text**

Check that your `.env` file is in `.gitignore` and contains only real values, not "your_...".

---

# UI Verification Tasks

The following tasks must be manually tested via the running application. After Tasks 1–3 (code) are complete, proceed to these:

---

## Task 4: Verify AIC_MODE=test behavior (default)

**Manual test (no code change needed after Task 1–3)**

- [x] **Step 1: Run scripts in test mode (default)**

Do NOT set `AIC_MODE` environment variable. Run:
```bash
.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "người đi bộ trên đường"
```

Expected output:
- In console logs, you should see: `[config] OpenRouter AIC_MODE=test model=google/gemini-2.5-flash (text)`
- The text "test" should clearly appear in the model selection log
- Query should complete without errors

- [x] **Step 2: Verify Gradio UI uses test model**

Start the app:
```bash
.venv\Scripts\python.exe scripts\app.py
```

Open http://127.0.0.1:7860 in your browser, go to **KIS tab**, enter a query, run it. In the console/terminal where the app is running, you should see:
- `[config] OpenRouter AIC_MODE=test model=google/gemini-2.5-flash ...`

No errors should appear.

---

## Task 5: Verify AIC_MODE=contest behavior (stronger model)

**Manual test (requires OPENROUTER_MODEL_CONTEST in .env)**

- [x] **Step 1: Run scripts in contest mode**

Set and run:
```bash
$env:AIC_MODE = "contest"; .venv\Scripts\python.exe scripts\agent\pipeline_kis.py "người đi bộ trên đường"
```

Expected output:
- In console logs, you should see: `[config] OpenRouter AIC_MODE=contest model=google/gemini-2.0-pro-exp-02-05 (text)` (or whatever stronger model you set)
- The text "contest" should clearly appear
- The model name should be **different** from the test model
- Query should complete without errors (may be slower due to stronger model)

- [x] **Step 2: Verify Gradio UI uses contest model**

Start the app with AIC_MODE=contest:
```bash
$env:AIC_MODE = "contest"; .venv\Scripts\python.exe scripts\app.py
```

Open http://127.0.0.1:7860, go to **KIS tab**, enter a query, run it. In the console:
- You should see: `[config] OpenRouter AIC_MODE=contest model=<stronger_model> ...`

The mode and model name in the log should match what you set in .env.

---

## Task 6: Verify fallback behavior (invalid AIC_MODE)

**Manual test (edge case)**

- [x] **Step 1: Run with invalid AIC_MODE**

Set and run:
```bash
$env:AIC_MODE = "invalid_mode"; .venv\Scripts\python.exe scripts\agent\pipeline_kis.py "test query"
```

Expected behavior:
- Console should show: `[config] WARNING: AIC_MODE='invalid_mode' khong hop le, dung 'test' hoac 'contest' thay the. Mac dinh: 'test'`
- System should fall back to test mode (`AIC_MODE=test`)
- Log should show the fallback model (test model)

---

## Task 7: Verify fallback behavior (missing OPENROUTER_MODEL_CONTEST)

**Manual test (edge case)**

- [x] **Step 1: Temporarily remove OPENROUTER_MODEL_CONTEST from .env**

Comment out or delete the `OPENROUTER_MODEL_CONTEST=` line in `.env`.

- [x] **Step 2: Run with AIC_MODE=contest**

Set and run:
```bash
$env:AIC_MODE = "contest"; .venv\Scripts\python.exe scripts\agent\pipeline_kis.py "test query"
```

Expected behavior:
- Console should show: `[config] WARNING: AIC_MODE=contest nhung OPENROUTER_MODEL_CONTEST trong .env trong. Dung OPENROUTER_MODEL thay the.`
- System should fall back to OPENROUTER_MODEL (test model)
- Log should show the fallback model

- [x] **Step 3: Restore OPENROUTER_MODEL_CONTEST**

Restore the value in `.env` for later use.

---

## Task 8: Verify all 3 pipelines work in both modes

**Manual test (integration check)**

- [x] **Step 1: Test KIS pipeline in test mode**

```bash
.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "người lạ vào nhà lúc đêm"
```

Should return `video_id` and `frame_id` without errors.

- [x] **Step 2: Test KIS pipeline in contest mode**

```bash
$env:AIC_MODE = "contest"; .venv\Scripts\python.exe scripts\agent\pipeline_kis.py "người lạ vào nhà lúc đêm"
```

Should return same or better result (or comparable ranking), no errors.

- [x] **Step 3: Test Q&A pipeline in both modes**

Run same query with `pipeline_qa.py` in test and contest modes — should work without errors.

- [x] **Step 4: Test TRAKE pipeline in both modes**

Run same query with `pipeline_trake.py` in test and contest modes — should work without errors.

- [x] **Step 5: Test via Gradio UI**

Start Gradio UI with default (test mode):
```bash
.venv\Scripts\python.exe scripts\app.py
```

Try KIS, Q&A, and TRAKE tabs — all should work. Check console logs show `AIC_MODE=test`.

Stop the app, restart in contest mode:
```bash
$env:AIC_MODE = "contest"; .venv\Scripts\python.exe scripts\app.py
```

Try all 3 tabs again — should work. Check console logs show `AIC_MODE=contest`.

---

## Task 9: Verify phase 1 success criteria

**Final acceptance test**

- [x] **Step 1: Confirm success criteria from PLAN.md**

According to PLAN.md, Phase 1 is complete when:
- ✅ Running `AIC_MODE=contest` shows log confirming stronger model is being used
- ✅ Not setting the environment variable behaves exactly as before (test mode)

Checklist:
- [x] When `AIC_MODE=contest`: Console clearly shows `AIC_MODE=contest` and model name is different from test model
- [x] When `AIC_MODE` not set: Console shows `AIC_MODE=test` and uses default model
- [x] No signature changes to `call_llm()` — it works exactly as before for callers
- [x] All 3 pipelines work in both modes without errors

---

# Summary

| Step | Owner | Type | Status |
|------|-------|------|--------|
| Task 1–3 | Developer (Person A) | Code | ⏳ Todo |
| Task 4–9 | User (Person A) | UI Verification | ⏳ Todo |

**Expected time:** ~30 min code + ~20 min UI testing = ~50 min total
