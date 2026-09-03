# Phase 1 Implementation Plan — FastAPI Backend + React/Vite Frontend Skeleton

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Decouple the UI from Gradio. Stand up a FastAPI backend (`scripts/api/`) that bridges to the
existing `scripts/agent/*` pipelines and `scripts/submit/*` (no pipeline logic rewritten, only wrapped),
and a React + Vite frontend (`frontend/`) that reimplements the 6 operative screens from the approved
Claude Design mockup (`AIC2026 Mockups.dc.html`, project
`https://claude.ai/design/p/d59ebed7-77b7-4266-8dc5-1b56a720b234`) with **real data** from the backend.
`scripts/app.py` (Gradio) is left untouched and stays the fallback UI until this replaces it.

**Explicitly out of scope for Phase 1** (later phases per the roadmap agreed with the user):

- Any LangGraph / AI-router / multi-agent graph logic (Phase 2).
- A working Chat screen (mockup screen `1f`) — the rail nav gets a disabled placeholder entry only.
- Real keyframe thumbnails — both the mockup and this plan intentionally keep image tiles as the
  striped CSS placeholder (mockup's own words: *"Ô ảnh là placeholder sọc — thả keyframe thật vào
  sau"*); wiring real `jpg_path` image serving is a separate later task, not part of this skeleton.
- pytest — approved only for Phase 4; this plan's verification uses the repo's existing convention
  (ad-hoc script + `assert`/`print`, or FastAPI's `TestClient` which ships with `fastapi`/`starlette`,
  not pytest).

**Architecture:**

- Backend: `scripts/api/` (new, sibling to `scripts/agent/` and `scripts/submit/`) — FastAPI app,
  Pydantic schemas, an in-memory (RAM dict) session queue store, and 4 routers (kis, qa, trake, queue)
  that each import and call the existing pipeline entry points directly. It must keep both hard
  single-call-site rules from CLAUDE.md: only `scripts/agent/config.py:call_llm()` calls the LLM (the
  routers never call it directly — they call `rewrite_query`/`run_qa`/`run_trake`, which internally use
  `call_llm()`), and only `scripts/submit/build_submission.py` writes CSV/ZIP (the export router calls
  its `build_*_csv`/`build_zip_submission` functions, never writes a file itself).
- Frontend: `frontend/` (new, Node/npm isolated here) — Vite + React + TypeScript. No React Router (the
  4 modes are simple client-state tab switches, not distinct URLs — matches the mockup's rail-nav
  behavior). No new drag-and-drop dependency — the shortlist reorder (mockup `1b`) is native HTML5
  drag events, transliterated directly from the mockup's own `onDragStart/onDragEnter/onDragOver/ onDragEnd` logic (already present in `AIC2026 Mockups.dc.html`, so this is a known-working algorithm,
  not new design). Styling ports `ds-organic.css`'s tokens/components verbatim plus one small
  app-layout stylesheet — no Tailwind/CSS-in-JS added.
- Dev wiring: Vite dev server proxies `/api/*` to the FastAPI dev server (`vite.config.ts`), so the
  browser only ever talks to one origin in dev — CORS middleware is added on the backend too, as a
  fallback for direct-port access while developing, but the proxy is the primary mechanism.
- Session/queue state: a `session_id` (UUID) generated client-side via `crypto.randomUUID()`, persisted
  in `localStorage`, sent as a URL path segment to the queue/export endpoints. Backend keeps queues in
  a plain `dict[str, list]` in `scripts/api/state.py` — no database (per the approved architecture spec,
  `docs/superpowers/specs/2026-08-27-multiagent-chat-architecture-design.md` §3).

**Tech Stack:**

- Backend: `fastapi`, `uvicorn[standard]` (new — added to `requirements.txt` in Task 1). Pydantic ships
  with FastAPI, no separate pin needed. `fastapi.testclient.TestClient` is used for verification
  (needs `httpx`, already present transitively via `litellm`) — not pytest.
- Frontend: Node.js + npm (assume an LTS Node is already installed — Task 7 Step 0 checks this and
  stops with an explicit message if not, rather than trying to install Node itself). `vite`,
  `react`, `react-dom`, `typescript` — installed via the standard Vite scaffold command, no extra
  frontend dependency beyond that scaffold.

**Spec:** `PLAN.md` (Phase 7, to be named/linked in Task 12) and
`docs/superpowers/specs/2026-08-27-multiagent-chat-architecture-design.md` §2–§3 (this plan implements
only the "khung FastAPI cơ bản + bridge" + "frontend mới theo mockup" slice of that spec — not the
LangGraph/chat parts, per the user's reordered roadmap).

## Global Constraints

- UI text and code comments in the **Python backend** (`scripts/api/`) are written in Vietnamese
  (repo-wide convention, CLAUDE.md) — same density as `scripts/agent/tools/rerank.py`.
- **Carve-out for the frontend:** TypeScript/React code uses `camelCase` (JS/React convention:
  `useState`, `onClick`, etc. are camelCase and not renameable), not `snake_case` — CLAUDE.md's
  `snake_case` rule was written for the Python codebase; this plan treats it as scoped there and does
  not try to force `snake_case` onto TSX. User-facing text inside the frontend (labels, buttons,
  status messages) IS in Vietnamese, matching the repo-wide UI-text rule. Flagged again in Self-Review.
- `video_id` never includes `.mp4`; `frame_id = frame_idx + 1` is derived ONLY in
  `scripts/agent/tools/retrieve.py` (Task 2 adds one more function there, still deriving it the same
  way, never recomputing it elsewhere — the API layer and frontend only ever pass the field through).
- Don't call `litellm`/Gemini anywhere except `scripts/agent/config.py:call_llm()` — the new routers
  call existing pipeline/tool functions (`rewrite_query`, `run_qa`, `run_trake`), never `call_llm()`
  directly.
- Don't write submission CSV/ZIP anywhere except `scripts/submit/build_submission.py` — the export
  router only calls its functions, never opens a file itself.
- `MAX_AGENT_LOOPS` cap: unaffected — `run_qa`/`run_trake` already enforce it internally; the API layer
  adds no new loops.
- New single-purpose backend capability → `scripts/api/` (new top-level bucket under `scripts/`,
  alongside `scripts/agent/` and `scripts/submit/` — see CLAUDE.md Folder Structure, already updated).
- No `git commit`/`push` unless the user explicitly asks in this session.
- Human-in-the-loop review gate is preserved: every screen requires an explicit "Thêm vào hàng đợi" /
  "Chốt đáp án" action before a query enters the queue, and Export is a separate explicit action — no
  automatic submission anywhere in this plan.

---

## Task 1: Backend skeleton — FastAPI app, schemas, in-memory state

**Files:**

- Modify: `requirements.txt` (add `fastapi`, `uvicorn[standard]`)
- Create: `scripts/api/__init__.py` (empty)
- Create: `scripts/api/schemas.py`
- Create: `scripts/api/state.py`
- Create: `scripts/api/main.py`

**Interfaces:**

- Produces: `app` (FastAPI instance) importable as `scripts.api.main:app`, mounted with CORS + a
  `/api/health` endpoint. Consumed by Task 3–6 (routers) and by `uvicorn` at dev time.

- [x] **Step 1: Add dependencies**

  Append to `requirements.txt` (after the existing entries, before the Phase 6 eval-only comment
  block):

  ```
  fastapi==0.115.6
  uvicorn[standard]==0.34.0
  ```

  Then install: `.venv\Scripts\python.exe -m pip install fastapi==0.115.6 "uvicorn[standard]==0.34.0"`
- [x] **Step 2: Write `scripts/api/schemas.py`**

  ```python
  """
  schemas.py — Pydantic request/response models cho scripts/api/.

  Chi mo ta shape HTTP (JSON) — KHONG chua business logic. Cac field khop voi dict tra ve tu
  scripts/agent/pipeline_kis.py / pipeline_qa.py / pipeline_trake.py / agent/tools/retrieve.py, TRU
  jpg_path — co tinh KHONG lo ra ngoai API o Phase 1 (man hinh dung placeholder soc dung theo mockup,
  xem PHASE1 plan header "Explicitly out of scope" — serve anh that la viec cua phase sau).
  """
  from __future__ import annotations

  from pydantic import BaseModel


  class RewriteRequest(BaseModel):
      query: str
      question: str | None = None
      max_n: int = 3


  class RewriteResponse(BaseModel):
      candidates: list[str]


  class Hit(BaseModel):
      video_id: str
      frame_id: int
      frame_idx: int
      pts_time: float
      score: float


  class NeighborFrame(BaseModel):
      video_id: str
      frame_id: int
      frame_idx: int
      pts_time: float


  class KisSearchRequest(BaseModel):
      query: str
      top_k: int = 20


  class KisSearchResponse(BaseModel):
      hits: list[Hit]


  class QaRunRequest(BaseModel):
      query: str
      question: str | None = None
      top_k: int = 20
      query_en: str | None = None


  class QaHit(Hit):
      answer: str


  class QaRunResponse(BaseModel):
      hits: list[QaHit]
      answer: str
      confidence: float
      n_loops: int


  class TrakeRunRequest(BaseModel):
      query: str
      events: list[str]
      top_k_video: int = 5
      query_en: str | None = None


  class TrakeCandidate(BaseModel):
      video_id: str
      frame_ids: list[int]
      score: float


  class TrakeRunResponse(BaseModel):
      candidates: list[TrakeCandidate]
      n_events: int


  class QueueRowIn(BaseModel):
      query_id: str
      query_type: str  # "kis" | "qa" | "trake"
      rows: list[dict]  # shape phu thuoc query_type — xem state.py
      answer: str | None = None  # chi dung khi query_type == "qa"


  class QueueRowOut(QueueRowIn):
      pass


  class ExportResponse(BaseModel):
      zip_path: str
      valid: bool
      csv_count: int
      errors: list[str]
  ```
- [x] **Step 3: Write `scripts/api/state.py`**

  ```python
  """
  state.py — Session state trong RAM cho backend API (Phase 1 skeleton).

  KHONG dung database (xem CLAUDE.md / docs/superpowers/specs/2026-08-27-...-design.md §3) — moi
  session (session_id do frontend tu sinh, xem frontend/src/session.ts) co 1 danh sach cac query da
  "Them vao hang doi", giu trong dict toan cuc trong tien trinh backend. Mat khi restart backend —
  chap nhan duoc o Phase 1 (chua can persist qua nhieu lan chay).

  Thread-safety: uvicorn dev (1 worker) chay cac route FastAPI dong bo (khong co await xen giua luc
  sua dict trong file nay) -> khong co race dieu kien thuc su. Neu sau nay chay nhieu worker/process,
  phai doi sang store khac.
  """
  from __future__ import annotations

  from typing import Any

  _QUEUES: dict[str, list[dict[str, Any]]] = {}


  def get_queue(session_id: str) -> list[dict[str, Any]]:
      return _QUEUES.setdefault(session_id, [])


  def add_to_queue(session_id: str, item: dict[str, Any]) -> None:
      """Them 1 query vao hang doi — neu query_id da ton tai thi THAY THE (giong scripts/app.py cu)."""
      queue = get_queue(session_id)
      queue[:] = [q for q in queue if q["query_id"] != item["query_id"]]
      queue.append(item)


  def remove_from_queue(session_id: str, query_id: str) -> bool:
      queue = get_queue(session_id)
      before = len(queue)
      queue[:] = [q for q in queue if q["query_id"] != query_id]
      return len(queue) < before


  def clear_queue(session_id: str) -> None:
      _QUEUES[session_id] = []
  ```
- [x] **Step 4: Write `scripts/api/main.py`**

  ```python
  """
  main.py — FastAPI app entrypoint cho backend AIC2026 (Phase 1 skeleton).

  Chay:  .venv\\Scripts\\python.exe -m uvicorn scripts.api.main:app --reload --port 8000
  Mo:    http://127.0.0.1:8000/api/health

  Nap san index + model CLIP luc khoi dong (giong scripts/app.py) de request search dau tien khong
  phai cho load model.
  """
  from __future__ import annotations

  import sys
  from pathlib import Path

  _ROOT = Path(__file__).resolve().parent.parent.parent
  if str(_ROOT) not in sys.path:
      sys.path.insert(0, str(_ROOT))

  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware

  from scripts.agent.tools.retrieve import preload

  app = FastAPI(title="AIC2026 Backend API")

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
      allow_methods=["*"],
      allow_headers=["*"],
  )


  @app.on_event("startup")
  def _on_startup() -> None:
      print("[api] Nap index + CLIP model (mot lan)...")
      preload()
      print("[api] San sang.")


  @app.get("/api/health")
  def health() -> dict:
      return {"status": "ok"}
  ```

  (Routers are added to this file in Tasks 3–6, one `app.include_router(...)` line each — kept out of
  this step because they don't exist yet.)
- [x] **Step 5: Verify — app imports and starts, health check responds**

  Run:

  ```
  .venv\Scripts\python.exe -c "from fastapi.testclient import TestClient; from scripts.api.main import app; c = TestClient(app); r = c.get('/api/health'); assert r.status_code == 200 and r.json() == {'status': 'ok'}, r.text; print('[verify] health OK:', r.json())"
  ```

  Expected: `[verify] health OK: {'status': 'ok'}`, no traceback. Note: this does NOT trigger
  `preload()` (that only runs under `with TestClient(app) as c:` / real `uvicorn` — fine for this
  step, Task 6's full smoke test uses the `with` form so startup actually runs).

---

## Task 2: Add `get_neighbor_frames()` to `scripts/agent/tools/retrieve.py`

**Files:**

- Modify: `scripts/agent/tools/retrieve.py` (append one new function)

**Interfaces:**

- Produces: `get_neighbor_frames(video_id: str, frame_idx: int, window: int = 5) -> list[dict]`.
  Consumed by Task 3's KIS router (mockup screen `1c`'s "frame lân cận" strip).

- [x] **Step 1: Append the function** (after `fast_retrieve_for_video`, before the `if __name__ == "__main__":` block)

  ```python
  def get_neighbor_frames(video_id: str, frame_idx: int, window: int = 5) -> list[dict]:
      """Tra ve toi da 2*window+1 keyframe LIEN TIEP (theo frame_idx) trong CUNG 1 video, xung quanh
      frame_idx duoc chi dinh — dung cho man chi tiet keyframe (dai frame lan can, mockup man 1c).
      Khong tinh score (khong phai ket qua truy van) — chi tra ve video_id/frame_id/frame_idx/pts_time.
      """
      _ensure_loaded()
      mask = _META["video_id"] == video_id
      if not mask.any():
          return []
      local_meta = _META[mask].sort_values("frame_idx").reset_index(drop=True)
      pos = local_meta.index[local_meta["frame_idx"] == frame_idx]
      if len(pos) == 0:
          return []
      center = pos[0]
      lo = max(0, center - window)
      hi = min(len(local_meta), center + window + 1)
      results = []
      for _, row in local_meta.iloc[lo:hi].iterrows():
          fidx = int(row["frame_idx"])
          results.append({
              "video_id": row["video_id"],
              "frame_idx": fidx,
              "frame_id": fidx + 1,
              "pts_time": float(row["pts_time"]),
          })
      return results
  ```
- [x] **Step 2: Verify against real data**

  Run:

  ```
  .venv\Scripts\python.exe -c "from scripts.agent.tools.retrieve import fast_retrieve, get_neighbor_frames; h = fast_retrieve('a person walking on the street', top_k=1)[0]; n = get_neighbor_frames(h['video_id'], h['frame_idx'], window=5); assert len(n) >= 1; assert any(f['frame_idx'] == h['frame_idx'] for f in n); assert [f['frame_idx'] for f in n] == sorted(f['frame_idx'] for f in n); print(f'[verify] {len(n)} neighbor frames, center present, sorted OK')"
  ```

  Expected: `[verify] N neighbor frames, center present, sorted OK`, no `AssertionError`/traceback.

---

## Task 3: KIS + rewrite + neighbor-frames router

**Files:**

- Create: `scripts/api/routers/__init__.py` (empty)
- Create: `scripts/api/routers/kis.py`
- Modify: `scripts/api/main.py` (register the router)

**Interfaces:**

- Consumes: `run_kis` (`scripts/agent/pipeline_kis.py`), `rewrite_query_candidates`
  (`scripts/agent/tools/rewrite.py`), `get_neighbor_frames` (Task 2).
- Produces: `POST /api/rewrite`, `POST /api/kis/search`, `GET /api/keyframes/{video_id}/neighbors`.

- [x] **Step 1: Write `scripts/api/routers/kis.py`**

  ```python
  """
  routers/kis.py — Bridge sang HTTP cho rewrite + KIS search + frame lan can (man chi tiet keyframe).
  KHONG chua logic retrieval/rerank — chi goi thang cac ham co san.
  """
  from __future__ import annotations

  from fastapi import APIRouter, HTTPException

  from scripts.agent.pipeline_kis import run_kis
  from scripts.agent.tools.rewrite import rewrite_query_candidates
  from scripts.agent.tools.retrieve import get_neighbor_frames
  from scripts.api.schemas import (
      RewriteRequest, RewriteResponse, KisSearchRequest, KisSearchResponse, Hit, NeighborFrame,
  )

  router = APIRouter(prefix="/api", tags=["kis"])

  _HIT_KEYS = {"video_id", "frame_id", "frame_idx", "pts_time", "score"}


  def _strip_extra(hits: list[dict]) -> list[dict]:
      """Bo cac key khong thuoc schema (vd. jpg_path, n) truoc khi ep kieu Pydantic."""
      return [{k: v for k, v in h.items() if k in _HIT_KEYS} for h in hits]


  @router.post("/rewrite", response_model=RewriteResponse)
  def rewrite(req: RewriteRequest) -> RewriteResponse:
      if not req.query.strip():
          raise HTTPException(400, "query rong")
      candidates = rewrite_query_candidates(req.query, max_n=req.max_n, question=req.question)
      return RewriteResponse(candidates=candidates)


  @router.post("/kis/search", response_model=KisSearchResponse)
  def kis_search(req: KisSearchRequest) -> KisSearchResponse:
      if not req.query.strip():
          raise HTTPException(400, "query rong")
      hits = run_kis(req.query, top_k=req.top_k)
      return KisSearchResponse(hits=[Hit(**h) for h in _strip_extra(hits)])


  @router.get("/keyframes/{video_id}/neighbors", response_model=list[NeighborFrame])
  def keyframe_neighbors(video_id: str, frame_idx: int, window: int = 5) -> list[NeighborFrame]:
      frames = get_neighbor_frames(video_id, frame_idx, window=window)
      return [NeighborFrame(**f) for f in frames]
  ```
- [x] **Step 2: Register the router in `scripts/api/main.py`**

  Append at the end of the file:

  ```python
  from scripts.api.routers import kis  # noqa: E402

  app.include_router(kis.router)
  ```
- [x] **Step 3: Verify against real data (startup + endpoints, via `TestClient` context manager so
  `preload()` actually runs)**

  Run:

  ```
  .venv\Scripts\python.exe -c "
  from fastapi.testclient import TestClient
  from scripts.api.main import app
  with TestClient(app) as c:
      r = c.post('/api/kis/search', json={'query': 'a red car parked on the street', 'top_k': 5})
      assert r.status_code == 200, r.text
      hits = r.json()['hits']
      assert len(hits) == 5 and all('.mp4' not in h['video_id'] for h in hits), hits
      print('[verify] kis/search OK,', len(hits), 'hits, top score=', hits[0]['score'])
      h0 = hits[0]
      r2 = c.get(f\"/api/keyframes/{h0['video_id']}/neighbors\", params={'frame_idx': h0['frame_idx'], 'window': 3})
      assert r2.status_code == 200, r2.text
      print('[verify] neighbors OK,', len(r2.json()), 'frames')
  "
  ```

  Expected: two `[verify] ... OK` lines, no traceback. (Skips `/api/rewrite` here — it costs a real LLM
  call; Task 6's full smoke test exercises it once, end-to-end.)

---

## Task 4: Q&A router

**Files:**

- Create: `scripts/api/routers/qa.py`
- Modify: `scripts/api/main.py` (register the router)

**Interfaces:**

- Consumes: `run_qa` (`scripts/agent/pipeline_qa.py`).
- Produces: `POST /api/qa/run`.

- [x] **Step 1: Write `scripts/api/routers/qa.py`**

  ```python
  """
  routers/qa.py — Bridge pipeline_qa sang HTTP.
  """
  from __future__ import annotations

  from fastapi import APIRouter, HTTPException

  from scripts.agent.pipeline_qa import run_qa
  from scripts.api.schemas import QaRunRequest, QaRunResponse, QaHit

  router = APIRouter(prefix="/api", tags=["qa"])

  _QA_HIT_KEYS = {"video_id", "frame_id", "frame_idx", "pts_time", "score", "answer"}


  @router.post("/qa/run", response_model=QaRunResponse)
  def qa_run(req: QaRunRequest) -> QaRunResponse:
      if not req.query.strip():
          raise HTTPException(400, "query rong")
      out = run_qa(req.query, question=req.question, top_k=req.top_k, query_en=req.query_en)
      hits = [QaHit(**{k: v for k, v in h.items() if k in _QA_HIT_KEYS}) for h in out["results"]]
      return QaRunResponse(
          hits=hits, answer=out["answer"], confidence=out["confidence"], n_loops=out["n_loops"],
      )
  ```
- [x] **Step 2: Register in `scripts/api/main.py`**

  ```python
  from scripts.api.routers import qa  # noqa: E402

  app.include_router(qa.router)
  ```
- [x] **Step 3: Verify against real data**

  Run:

  ```
  .venv\Scripts\python.exe -c "
  from fastapi.testclient import TestClient
  from scripts.api.main import app
  with TestClient(app) as c:
      r = c.post('/api/qa/run', json={'query': 'Mot nguoi dang phat bieu truoc dam dong, mac ao trang', 'question': \"What color is the speaker's shirt?\", 'top_k': 10})
      assert r.status_code == 200, r.text
      body = r.json()
      assert body['answer'] and 0.0 <= body['confidence'] <= 1.0 and len(body['hits']) <= 10
      print('[verify] qa/run OK, answer=', repr(body['answer']), 'confidence=', body['confidence'])
  "
  ```

  Expected: `[verify] qa/run OK, answer=... confidence=...`, no traceback. This makes real LLM calls
  (needs `OPENROUTER_API_KEY` in `.env`, `AIC_MODE=test` recommended to keep it cheap).

---

## Task 5: TRAKE router

**Files:**

- Create: `scripts/api/routers/trake.py`
- Modify: `scripts/api/main.py` (register the router)

**Interfaces:**

- Consumes: `run_trake` (`scripts/agent/pipeline_trake.py`).
- Produces: `POST /api/trake/run`.

- [x] **Step 1: Write `scripts/api/routers/trake.py`**

  ```python
  """
  routers/trake.py — Bridge pipeline_trake sang HTTP.
  """
  from __future__ import annotations

  from fastapi import APIRouter, HTTPException

  from scripts.agent.pipeline_trake import run_trake
  from scripts.api.schemas import TrakeRunRequest, TrakeRunResponse, TrakeCandidate

  router = APIRouter(prefix="/api", tags=["trake"])


  @router.post("/trake/run", response_model=TrakeRunResponse)
  def trake_run(req: TrakeRunRequest) -> TrakeRunResponse:
      if not req.query.strip():
          raise HTTPException(400, "query rong")
      if not req.events:
          raise HTTPException(400, "can it nhat 1 event")
      out = run_trake(req.query, req.events, top_k_video=req.top_k_video, query_en=req.query_en)
      candidates = [TrakeCandidate(**c) for c in out["results"]]
      return TrakeRunResponse(candidates=candidates, n_events=out["n_events"])
  ```
- [x] **Step 2: Register in `scripts/api/main.py`**

  ```python
  from scripts.api.routers import trake  # noqa: E402

  app.include_router(trake.router)
  ```
- [x] **Step 3: Verify against real data**

  Run:

  ```
  .venv\Scripts\python.exe -c "
  from fastapi.testclient import TestClient
  from scripts.api.main import app
  events = ['athlete running toward the bar during approach run', 'athlete jumping over the high bar at peak', 'athlete landing on the mat after clearing']
  with TestClient(app) as c:
      r = c.post('/api/trake/run', json={'query': 'An athlete performing a high jump in a stadium competition', 'events': events, 'top_k_video': 3})
      assert r.status_code == 200, r.text
      body = r.json()
      assert body['n_events'] == 3
      print('[verify] trake/run OK,', len(body['candidates']), 'candidates')
      if body['candidates']:
          print('  best:', body['candidates'][0])
  "
  ```

  Expected: `[verify] trake/run OK, N candidates`, no traceback. Makes real LLM crosscheck calls (same
  cost note as Task 4).

---

## Task 6: Queue + export router, and the full end-to-end backend smoke test

**Files:**

- Create: `scripts/api/routers/queue.py`
- Modify: `scripts/api/main.py` (register the router)
- Create: `scripts/api/_smoke_test.py` (persistent smoke script — matches the existing
  `test_eval/Test/test_smoke_*.py` convention, run directly with the venv Python, not pytest)

**Interfaces:**

- Consumes: `state.py` (Task 1), `build_kis_csv`/`build_qa_csv`/`build_trake_csv`/
  `build_zip_submission` (`scripts/submit/build_submission.py`), `validate_file`
  (`scripts/submit/validate_submission.py`).
- Produces: `GET/POST/DELETE /api/queue/{session_id}[...]`, `POST /api/export/{session_id}`.

- [x] **Step 1: Write `scripts/api/routers/queue.py`**

  ```python
  """
  routers/queue.py — Hang doi submission trong RAM + export ZIP.

  Export bridge sang scripts/submit/build_submission.py (noi DUY NHAT duoc phep ghi CSV/ZIP submission
  — xem CLAUDE.md) va scripts/submit/validate_submission.py — khong tu ghi file o day.
  """
  from __future__ import annotations

  from fastapi import APIRouter, HTTPException

  from scripts.api import state
  from scripts.api.schemas import QueueRowIn, QueueRowOut, ExportResponse
  from scripts.submit.build_submission import (
      build_kis_csv, build_qa_csv, build_trake_csv, build_zip_submission,
  )
  from scripts.submit.validate_submission import validate_file

  router = APIRouter(prefix="/api", tags=["queue"])


  @router.get("/queue/{session_id}", response_model=list[QueueRowOut])
  def get_queue(session_id: str) -> list[QueueRowOut]:
      return [QueueRowOut(**q) for q in state.get_queue(session_id)]


  @router.post("/queue/{session_id}/add", response_model=list[QueueRowOut])
  def add_to_queue(session_id: str, item: QueueRowIn) -> list[QueueRowOut]:
      state.add_to_queue(session_id, item.model_dump())
      return [QueueRowOut(**q) for q in state.get_queue(session_id)]


  @router.delete("/queue/{session_id}/{query_id}", response_model=list[QueueRowOut])
  def remove_from_queue(session_id: str, query_id: str) -> list[QueueRowOut]:
      if not state.remove_from_queue(session_id, query_id):
          raise HTTPException(404, f"khong tim thay query_id={query_id}")
      return [QueueRowOut(**q) for q in state.get_queue(session_id)]


  @router.delete("/queue/{session_id}", response_model=list[QueueRowOut])
  def clear_queue(session_id: str) -> list[QueueRowOut]:
      state.clear_queue(session_id)
      return []


  @router.post("/export/{session_id}", response_model=ExportResponse)
  def export_zip(session_id: str) -> ExportResponse:
      queue = state.get_queue(session_id)
      if not queue:
          raise HTTPException(400, "Hang doi rong")

      csv_files = []
      errors: list[str] = []
      for item in queue:
          qid, qtype, rows = item["query_id"], item["query_type"], item["rows"]
          try:
              if qtype == "kis":
                  hits = [{"video_id": r["video_id"], "frame_id": r["frame_id"]} for r in rows]
                  csv_files.append(build_kis_csv(qid, hits))
              elif qtype == "qa":
                  hits = [{"video_id": r["video_id"], "frame_id": r["frame_id"],
                           "answer": r.get("answer", item.get("answer", ""))} for r in rows]
                  csv_files.append(build_qa_csv(qid, hits))
              elif qtype == "trake":
                  csv_files.append(build_trake_csv(qid, rows))
              else:
                  errors.append(f"{qid}: query_type khong hop le '{qtype}'")
          except Exception as e:
              errors.append(f"{qid}: {e}")

      if not csv_files:
          raise HTTPException(500, "Khong tao duoc CSV nao:\n" + "\n".join(errors))

      zip_path = build_zip_submission(csv_files, tag="frontend")
      valid = validate_file(zip_path)
      return ExportResponse(zip_path=str(zip_path), valid=valid, csv_count=len(csv_files), errors=errors)
  ```
- [x] **Step 2: Register in `scripts/api/main.py`**

  ```python
  from scripts.api.routers import queue  # noqa: E402

  app.include_router(queue.router)
  ```
- [x] **Step 3: Write `scripts/api/_smoke_test.py` — full end-to-end backend check**

  ```python
  """
  _smoke_test.py — Kiem tra toan bo backend API mot luot: KIS -> QA -> TRAKE -> queue -> export -> validate.
  Khong phai pytest (repo khong dung pytest o Phase 1 — xem CLAUDE.md) — script doc lap, chay tay.

  Usage:
      .venv\\Scripts\\python.exe scripts\\api\\_smoke_test.py

  Can OPENROUTER_API_KEY that (goi LLM that qua rewrite/qa/trake) va data/ da giai nen san.
  """
  from __future__ import annotations

  import sys
  from pathlib import Path

  _ROOT = Path(__file__).resolve().parent.parent.parent
  if str(_ROOT) not in sys.path:
      sys.path.insert(0, str(_ROOT))

  from fastapi.testclient import TestClient
  from scripts.api.main import app

  SESSION = "smoke-test-session"


  def main() -> None:
      with TestClient(app) as c:
          r = c.get("/api/health")
          assert r.status_code == 200
          print("[smoke] health OK")

          r = c.post("/api/kis/search", json={"query": "a red car parked on the street", "top_k": 5})
          assert r.status_code == 200, r.text
          kis_hits = r.json()["hits"]
          assert len(kis_hits) == 5
          print(f"[smoke] kis/search OK ({len(kis_hits)} hits)")

          r = c.post("/api/queue/" + SESSION + "/add", json={
              "query_id": "smoke-kis", "query_type": "kis",
              "rows": [{"video_id": h["video_id"], "frame_id": h["frame_id"]} for h in kis_hits[:3]],
          })
          assert r.status_code == 200, r.text
          print("[smoke] queue add (kis) OK")

          r = c.post("/api/qa/run", json={
              "query": "Mot nguoi dang phat bieu truoc dam dong, mac ao trang",
              "question": "What color is the speaker's shirt?", "top_k": 10,
          })
          assert r.status_code == 200, r.text
          qa_body = r.json()
          print(f"[smoke] qa/run OK (answer={qa_body['answer']!r}, confidence={qa_body['confidence']:.2f})")

          r = c.post("/api/queue/" + SESSION + "/add", json={
              "query_id": "smoke-qa", "query_type": "qa", "answer": qa_body["answer"],
              "rows": [{"video_id": h["video_id"], "frame_id": h["frame_id"], "answer": qa_body["answer"]}
                       for h in qa_body["hits"][:3]],
          })
          assert r.status_code == 200, r.text
          print("[smoke] queue add (qa) OK")

          events = [
              "athlete running toward the bar during approach run",
              "athlete jumping over the high bar at peak",
              "athlete landing on the mat after clearing",
          ]
          r = c.post("/api/trake/run", json={
              "query": "An athlete performing a high jump in a stadium competition",
              "events": events, "top_k_video": 3,
          })
          assert r.status_code == 200, r.text
          trake_body = r.json()
          print(f"[smoke] trake/run OK ({len(trake_body['candidates'])} candidates)")

          if trake_body["candidates"]:
              best = trake_body["candidates"][0]
              r = c.post("/api/queue/" + SESSION + "/add", json={
                  "query_id": "smoke-trake", "query_type": "trake",
                  "rows": [{"video_id": best["video_id"], "frame_ids": best["frame_ids"]}],
              })
              assert r.status_code == 200, r.text
              print("[smoke] queue add (trake) OK")

          r = c.get("/api/queue/" + SESSION)
          assert r.status_code == 200 and len(r.json()) >= 2, r.text
          print(f"[smoke] queue GET OK ({len(r.json())} queries queued)")

          r = c.post("/api/export/" + SESSION)
          assert r.status_code == 200, r.text
          export_body = r.json()
          print(f"[smoke] export OK: {export_body['zip_path']} (valid={export_body['valid']}, "
                f"csv_count={export_body['csv_count']})")
          assert export_body["valid"], export_body["errors"]

          r = c.delete("/api/queue/" + SESSION)
          assert r.status_code == 200 and r.json() == []
          print("[smoke] queue clear OK")

      print("\n[smoke] TAT CA BUOC PASS")


  if __name__ == "__main__":
      main()
  ```
- [x] **Step 4: Run it**

  Run: `.venv\Scripts\python.exe scripts\api\_smoke_test.py`

  Expected: a sequence of `[smoke] ... OK` lines ending in `[smoke] TAT CA BUOC PASS`, no
  `AssertionError`/traceback. A real ZIP appears under `submissions/` (tag `frontend`) — inspect it
  once by hand to confirm the `submission/` subfolder + 3 CSVs (`smoke-kis.csv`, `smoke-qa.csv`,
  `smoke-trake.csv`) look right, same as any other manual submission would.

---

## Task 7: Frontend bootstrap — Vite + React shell, dev proxy, ported design tokens

**Files:**

- Create: `frontend/` (via Vite scaffold command, then edited)
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/styles/organic.css`
- Create: `frontend/src/styles/app.css`
- Create: `frontend/src/session.ts`
- Create: `frontend/src/api/client.ts`
- Modify: `frontend/src/App.tsx`, `frontend/src/main.tsx`

**Interfaces:**

- Produces: the running shell (rail nav + empty main panel) and the shared `api` client object used
  by every screen component in Tasks 8–11.

- [x] **Step 0: Verify Node is installed** — run `node -v` and `npm -v`. If either fails, STOP and
  tell the user to install Node.js 20 LTS first — this plan does not install Node itself.
- [x] **Step 1: Scaffold the project**

  From the repo root:

  ```
  npm create vite@latest frontend -- --template react-ts
  cd frontend
  npm install
  cd ..
  ```
- [x] **Step 2: Add the dev proxy — `frontend/vite.config.ts`**

  ```ts
  import { defineConfig } from "vite";
  import react from "@vitejs/plugin-react";

  // Proxy /api/* sang backend FastAPI (127.0.0.1:8000) — trinh duyet chi thay 1 origin luc dev,
  // khong can dua vao CORS lam co che chinh (van bat CORS o backend lam du phong — xem main.py).
  export default defineConfig({
    plugins: [react()],
    server: {
      proxy: {
        "/api": "http://127.0.0.1:8000",
      },
    },
  });
  ```
- [x] **Step 3: Port design tokens — `frontend/src/styles/organic.css`**

  Copy the full content of the mockup project's `ds-organic.css` (already fetched in this session)
  verbatim into this file — it is the exact `:root` token set (`--color-bg`, `--color-accent`,
  `--font-heading`, `--radius-*`, `--shadow-*`, ...) plus the `.btn/.card/.tag/.table/.dialog/.input`
  component classes the screens in Tasks 8–11 use. No changes needed, it's plain CSS with no
  framework dependency.
- [x] **Step 4: Write the app-layout stylesheet — `frontend/src/styles/app.css`**

  ```css
  /* app.css — Bo cuc rieng cua app (rail nav, luoi ket qua, panel...), dung tren nen token/component
     cua organic.css (bien --color-*, --radius-*, --shadow-*, class .btn/.card/.tag/.table). */

  .app-shell { display: flex; height: 100vh; background: var(--color-bg); color: var(--color-text); }

  .rail {
    width: 88px; flex: none; display: flex; flex-direction: column; align-items: center; gap: 8px;
    padding: 16px 0; background: var(--color-surface); border-right: 1px solid var(--color-divider);
  }
  .rail-logo {
    width: 40px; height: 40px; border-radius: 999px; background: var(--color-accent);
    color: var(--color-bg); display: grid; place-items: center; font-family: var(--font-heading);
    margin-bottom: 8px;
  }
  .rail-item {
    width: 64px; padding: 9px 0; border-radius: 999px; text-align: center;
    font: 600 11px var(--font-body); color: color-mix(in srgb, var(--color-text) 65%, transparent);
    background: none; border: none; cursor: pointer;
  }
  .rail-item.active { background: var(--color-accent); color: var(--color-bg); }
  .rail-item:disabled { opacity: 0.4; cursor: not-allowed; }

  .main-panel { flex: 1; min-width: 0; overflow: auto; padding: 24px 28px; }
  .screen { display: flex; flex-direction: column; gap: 16px; max-width: 1180px; }

  .topbar { display: flex; gap: 10px; }
  .search-input { flex: 1; }
  .status-line { font-size: 12.5px; color: color-mix(in srgb, var(--color-text) 60%, transparent); white-space: pre-wrap; }

  .kis-empty { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 60px 0; text-align: center; }
  .kis-body { display: flex; gap: 20px; align-items: flex-start; }
  .shortlist-panel { width: 300px; flex: none; background: var(--color-neutral-100); border-radius: var(--radius-lg); padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .shortlist-row { display: flex; align-items: center; gap: 8px; padding: 8px; border-radius: var(--radius-md); border: 1px solid var(--color-divider); cursor: grab; }
  .shortlist-row.dragging { background: var(--color-accent-100); border-color: var(--color-accent-400); }
  .shortlist-meta { flex: 1; min-width: 0; }
  .remove-btn { background: none; border: none; cursor: pointer; color: color-mix(in srgb, var(--color-text) 40%, transparent); }

  .kis-grid { flex: 1; display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
  .kis-card { position: relative; border-radius: var(--radius-md); overflow: hidden; border: 1px solid var(--color-divider); aspect-ratio: 16/10; cursor: pointer; }
  .kis-card:hover { border-color: var(--color-accent); box-shadow: var(--shadow-md); }
  .card-rank, .card-score { position: absolute; top: 6px; font-size: 10px; padding: 2px 7px; border-radius: 999px; background: color-mix(in srgb, var(--color-bg) 90%, transparent); }
  .card-rank { left: 6px; }
  .card-score { right: 6px; }
  .card-caption { position: absolute; bottom: 0; left: 0; right: 0; display: flex; justify-content: space-between; padding: 5px 8px; font-size: 10px; background: color-mix(in srgb, var(--color-bg) 92%, transparent); }

  .thumb-placeholder {
    width: 100%; height: 100%; min-height: 60px;
    background: repeating-linear-gradient(135deg, var(--color-neutral-200) 0 8px, var(--color-neutral-300) 8px 16px);
    display: flex; align-items: center; justify-content: center;
  }

  .detail-header { display: flex; align-items: center; gap: 10px; }
  .detail-body { display: flex; flex-direction: column; gap: 14px; }
  .detail-player { height: 360px; border-radius: var(--radius-lg); }
  .detail-strip { display: flex; gap: 8px; }
  .strip-frame { flex: 1; aspect-ratio: 16/10; border-radius: var(--radius-sm); display: flex; align-items: flex-end; justify-content: center; font-size: 10px; }
  .strip-frame.current { outline: 2px solid var(--color-accent); }
  .detail-meta { display: flex; flex-direction: column; gap: 4px; font-size: 12px; }
  .detail-meta > div { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid var(--color-divider); }

  .qa-body { display: flex; gap: 18px; }
  .qa-frame { flex: 1; height: 260px; border-radius: var(--radius-lg); }
  .qa-side { width: 280px; flex: none; display: flex; flex-direction: column; gap: 10px; }
  .answer-input { font: 400 20px var(--font-heading); }
  .confidence-bar { height: 8px; border-radius: 999px; background: var(--color-neutral-300); overflow: hidden; }
  .confidence-bar div { height: 100%; background: var(--color-accent-2); }

  .queue-header { display: flex; align-items: center; justify-content: space-between; }
  .queue-header > div { display: flex; gap: 8px; }
  ```
- [x] **Step 5: Write `frontend/src/session.ts`**

  ```ts
  // session.ts — sinh 1 session_id (UUID) luu trong localStorage, dung chung cho toan bo query
  // hang doi cua trinh duyet nay (xem scripts/api/state.py o backend).
  const KEY = "aic_session_id";

  export function getSessionId(): string {
    let id = localStorage.getItem(KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(KEY, id);
    }
    return id;
  }
  ```
- [x] **Step 6: Write `frontend/src/api/client.ts`**

  ```ts
  // client.ts — wrapper fetch() goi backend qua proxy /api/* (xem vite.config.ts).
  export type Hit = {
    video_id: string;
    frame_id: number;
    frame_idx: number;
    pts_time: number;
    score: number;
  };

  export type QaHit = Hit & { answer: string };

  export type NeighborFrame = {
    video_id: string;
    frame_id: number;
    frame_idx: number;
    pts_time: number;
  };

  export type TrakeCandidate = {
    video_id: string;
    frame_ids: number[];
    score: number;
  };

  export type QueueRow = {
    query_id: string;
    query_type: "kis" | "qa" | "trake";
    rows: Record<string, unknown>[];
    answer?: string | null;
  };

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(`/api${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`${res.status} ${res.statusText}: ${body}`);
    }
    return res.json() as Promise<T>;
  }

  export const api = {
    rewrite: (query: string, question?: string) =>
      request<{ candidates: string[] }>("/rewrite", {
        method: "POST",
        body: JSON.stringify({ query, question }),
      }),

    kisSearch: (query: string, top_k = 20) =>
      request<{ hits: Hit[] }>("/kis/search", {
        method: "POST",
        body: JSON.stringify({ query, top_k }),
      }),

    keyframeNeighbors: (video_id: string, frame_idx: number, window = 5) =>
      request<NeighborFrame[]>(
        `/keyframes/${video_id}/neighbors?frame_idx=${frame_idx}&window=${window}`
      ),

    qaRun: (query: string, question: string, top_k = 20, query_en?: string) =>
      request<{ hits: QaHit[]; answer: string; confidence: number; n_loops: number }>("/qa/run", {
        method: "POST",
        body: JSON.stringify({ query, question, top_k, query_en }),
      }),

    trakeRun: (query: string, events: string[], top_k_video = 5, query_en?: string) =>
      request<{ candidates: TrakeCandidate[]; n_events: number }>("/trake/run", {
        method: "POST",
        body: JSON.stringify({ query, events, top_k_video, query_en }),
      }),

    getQueue: (sessionId: string) => request<QueueRow[]>(`/queue/${sessionId}`),

    addToQueue: (sessionId: string, row: QueueRow) =>
      request<QueueRow[]>(`/queue/${sessionId}/add`, {
        method: "POST",
        body: JSON.stringify(row),
      }),

    removeFromQueue: (sessionId: string, queryId: string) =>
      request<QueueRow[]>(`/queue/${sessionId}/${queryId}`, { method: "DELETE" }),

    clearQueue: (sessionId: string) => request<QueueRow[]>(`/queue/${sessionId}`, { method: "DELETE" }),

    exportZip: (sessionId: string) =>
      request<{ zip_path: string; valid: boolean; csv_count: number; errors: string[] }>(
        `/export/${sessionId}`,
        { method: "POST" }
      ),
  };
  ```
- [x] **Step 7: Replace `frontend/src/main.tsx`**

  ```tsx
  import { StrictMode } from "react";
  import { createRoot } from "react-dom/client";
  import App from "./App";
  import "./styles/organic.css";
  import "./styles/app.css";

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
  ```
- [x] **Step 8: Replace `frontend/src/App.tsx` with the rail-nav shell (screens are stubbed until
  Tasks 8–11 add them)**

  ```tsx
  import { useState } from "react";

  type Mode = "chat" | "kis" | "qa" | "trake" | "queue";

  const MODES: { id: Mode; label: string; disabled?: boolean }[] = [
    { id: "chat", label: "Chat", disabled: true },
    { id: "kis", label: "KIS" },
    { id: "qa", label: "Q&A" },
    { id: "trake", label: "TRAKE" },
    { id: "queue", label: "Hàng đợi" },
  ];

  export default function App() {
    const [mode, setMode] = useState<Mode>("kis");

    return (
      <div className="app-shell">
        <nav className="rail">
          <div className="rail-logo">AIC</div>
          {MODES.map((m) => (
            <button
              key={m.id}
              className={`rail-item ${mode === m.id ? "active" : ""}`}
              disabled={m.disabled}
              title={m.disabled ? "Sắp có ở Phase 2/3 (AI Graph)" : undefined}
              onClick={() => setMode(m.id)}
            >
              {m.label}
            </button>
          ))}
        </nav>
        <main className="main-panel">
          <p className="status-line">Màn "{mode}" sẽ được thêm ở Task tiếp theo.</p>
        </main>
      </div>
    );
  }
  ```
- [x] **Step 9: Verify — dev server starts, shell renders**

  Terminal 1: `.venv\Scripts\python.exe -m uvicorn scripts.api.main:app --port 8000` (leave running).
  Terminal 2: `cd frontend; npm run dev` — open the printed `http://localhost:5173/` URL in a browser.

  Expected: page loads with the cream background, a left rail showing "AIC" + Chat (greyed
  out)/KIS/Q&A/TRAKE/Hàng đợi, KIS highlighted by default, clicking a mode updates the placeholder
  text, no red errors in the browser devtools console. Stop both processes after confirming (Ctrl+C).

---

## Task 8: KIS screen (mockup `1a`/`1b`/`1c`) wired to the backend

**Files:**

- Create: `frontend/src/screens/KisScreen.tsx`
- Create: `frontend/src/components/KeyframeDetail.tsx`
- Modify: `frontend/src/App.tsx` (render `KisScreen` for `mode === "kis"`)

**Interfaces:**

- Consumes: `api.kisSearch`, `api.keyframeNeighbors`, `api.addToQueue`, `getSessionId()` (Task 7).

- [x] **Step 1: Write `frontend/src/components/KeyframeDetail.tsx`**

  ```tsx
  import { useEffect, useState } from "react";
  import { api, Hit, NeighborFrame } from "../api/client";

  // Man chi tiet 1 keyframe (mockup 1c): dai frame lan can trong cung video + nut them vao shortlist.
  export default function KeyframeDetail({
    hit, onBack, onAddToShortlist,
  }: {
    hit: Hit;
    onBack: () => void;
    onAddToShortlist: (h: Hit) => void;
  }) {
    const [neighbors, setNeighbors] = useState<NeighborFrame[]>([]);

    useEffect(() => {
      api.keyframeNeighbors(hit.video_id, hit.frame_idx, 5).then(setNeighbors).catch(() => setNeighbors([]));
    }, [hit.video_id, hit.frame_idx]);

    return (
      <div className="screen detail-screen">
        <div className="detail-header">
          <button className="btn btn-secondary" onClick={onBack}>← Về kết quả</button>
          <span className="mono tag">{hit.video_id} · frame {hit.frame_id}</span>
          <span className="mono tag tag-accent-2">score {hit.score.toFixed(4)}</span>
        </div>
        <div className="detail-body">
          <div className="detail-player thumb-placeholder">
            <span className="text-muted">keyframe {hit.video_id} #{hit.frame_id}</span>
          </div>
          <div className="detail-strip">
            {neighbors.map((n) => (
              <div
                key={n.frame_id}
                className={`strip-frame thumb-placeholder ${n.frame_id === hit.frame_id ? "current" : ""}`}
              >
                <span className="mono">{n.frame_id}</span>
              </div>
            ))}
          </div>
          <div className="detail-meta">
            <div><span>video_id</span><span className="mono">{hit.video_id}</span></div>
            <div><span>frame_id</span><span className="mono">{hit.frame_id}</span></div>
            <div><span>pts_time</span><span className="mono">{hit.pts_time.toFixed(1)}s</span></div>
          </div>
          <button className="btn btn-primary btn-block" onClick={() => onAddToShortlist(hit)}>
            Thêm vào danh sách
          </button>
        </div>
      </div>
    );
  }
  ```
- [x] **Step 2: Write `frontend/src/screens/KisScreen.tsx`**

  ```tsx
  import { useState } from "react";
  import { api, Hit, QueueRow } from "../api/client";
  import { getSessionId } from "../session";
  import KeyframeDetail from "../components/KeyframeDetail";

  type ShortlistItem = Hit & { _key: string };

  export default function KisScreen() {
    const [query, setQuery] = useState("");
    const [topK] = useState(20);
    const [hits, setHits] = useState<Hit[]>([]);
    const [status, setStatus] = useState("");
    const [loading, setLoading] = useState(false);
    const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);
    // Toa do dong dang keo (drag) trong shortlist — logic reorder giong het mockup 1b (onDragStart/
    // onDragEnter/onDragOver/onDragEnd), chuyen tu JS thuan sang React state.
    const [dragFrom, setDragFrom] = useState<number | null>(null);
    const [detail, setDetail] = useState<Hit | null>(null);
    const [queryId, setQueryId] = useState("");

    async function runSearch() {
      if (!query.trim()) {
        setStatus("⚠️ Nhập query trước khi tìm.");
        return;
      }
      setLoading(true);
      try {
        const { hits } = await api.kisSearch(query, topK);
        setHits(hits);
        setShortlist(hits.slice(0, 5).map((h, i) => ({ ...h, _key: `${h.video_id}-${h.frame_id}-${i}` })));
        setStatus(`✅ Tìm thấy ${hits.length} kết quả | điểm cao nhất = ${hits[0]?.score.toFixed(4) ?? "-"}`);
      } catch (e) {
        setStatus(`❌ Lỗi: ${(e as Error).message}`);
      } finally {
        setLoading(false);
      }
    }

    function reorderShortlist(from: number, to: number) {
      if (from === to) return;
      setShortlist((list) => {
        const next = list.slice();
        const [item] = next.splice(from, 1);
        next.splice(to, 0, item);
        return next;
      });
    }

    function removeFromShortlist(key: string) {
      setShortlist((list) => list.filter((h) => h._key !== key));
    }

    async function addToQueue() {
      if (shortlist.length === 0) {
        setStatus("⚠️ Chưa có kết quả để thêm.");
        return;
      }
      const qid = queryId.trim() || "kis-query-001";
      const row: QueueRow = {
        query_id: qid,
        query_type: "kis",
        rows: shortlist.map((h) => ({ video_id: h.video_id, frame_id: h.frame_id })),
      };
      await api.addToQueue(getSessionId(), row);
      setStatus(`✅ Đã thêm ${qid} (${shortlist.length} dòng) vào hàng đợi.`);
    }

    if (detail) {
      return (
        <KeyframeDetail
          hit={detail}
          onBack={() => setDetail(null)}
          onAddToShortlist={(h) => {
            setShortlist((list) => [...list, { ...h, _key: `${h.video_id}-${h.frame_id}-${list.length}` }]);
            setDetail(null);
          }}
        />
      );
    }

    return (
      <div className="screen kis-screen">
        <div className="topbar">
          <input
            className="input search-input"
            placeholder="VD: một người đang phát biểu tại cuộc họp báo ngoài trời, phía sau có logo màu xanh…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runSearch()}
          />
          <button className="btn btn-primary" onClick={runSearch} disabled={loading}>
            {loading ? "Đang tìm…" : "Tìm"}
          </button>
        </div>
        <p className="status-line">{status}</p>

        {hits.length === 0 ? (
          <div className="kis-empty">
            <h2>Bạn cần tìm ảnh nào?</h2>
            <p className="text-muted">
              Mô tả cảnh bằng tiếng Việt hoặc tiếng Anh. Nhấn Tìm để truy vấn qua chỉ mục CLIP.
            </p>
          </div>
        ) : (
          <div className="kis-body">
            <aside className="shortlist-panel">
              <h4>Danh sách nộp</h4>
              <p className="text-muted">Kéo để đổi thứ tự — hạng 1 là đáp án chính khi nộp.</p>
              <div className="shortlist-list">
                {shortlist.map((h, i) => (
                  <div
                    key={h._key}
                    className={`shortlist-row ${dragFrom === i ? "dragging" : ""}`}
                    draggable
                    onDragStart={() => setDragFrom(i)}
                    onDragEnter={() => dragFrom !== null && reorderShortlist(dragFrom, i)}
                    onDragOver={(e) => e.preventDefault()}
                    onDragEnd={() => setDragFrom(null)}
                  >
                    <span className="mono rank">{i + 1}</span>
                    <div className="thumb-placeholder" />
                    <div className="shortlist-meta">
                      <div className="mono">{h.video_id}</div>
                      <div className="mono text-muted">frame {h.frame_id} · {h.pts_time.toFixed(1)}s</div>
                    </div>
                    <span className="mono score">{h.score.toFixed(4)}</span>
                    <button className="remove-btn" onClick={() => removeFromShortlist(h._key)}>×</button>
                  </div>
                ))}
              </div>
              <div className="field">
                <label>Query ID (giữ nguyên tên BTC cấp)</label>
                <input className="input" placeholder="VD: query-1-kis" value={queryId} onChange={(e) => setQueryId(e.target.value)} />
              </div>
              <button className="btn btn-primary btn-block" onClick={addToQueue}>Thêm vào hàng đợi</button>
            </aside>

            <div className="kis-grid">
              {hits.map((h, i) => (
                <div key={`${h.video_id}-${h.frame_id}`} className="kis-card" onClick={() => setDetail(h)}>
                  <div className="thumb-placeholder" />
                  <span className="mono card-rank">#{i + 1}</span>
                  <span className="mono card-score">{h.score.toFixed(3)}</span>
                  <div className="card-caption">
                    <span>{h.video_id}</span>
                    <span className="text-muted">{h.frame_id}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }
  ```
- [x] **Step 3: Wire into `App.tsx`**

  Add `import KisScreen from "./screens/KisScreen";` and replace the placeholder body with:

  ```tsx
  <main className="main-panel">
    {mode === "kis" && <KisScreen />}
    {mode !== "kis" && <p className="status-line">Màn "{mode}" sẽ được thêm ở Task tiếp theo.</p>}
  </main>
  ```
- [x] **Step 4: Manual verification** (backend + frontend dev servers both running, per Task 7 Step 9)

  In the browser: type a query (e.g. "a red car parked on the street") into the KIS search box,
  press Enter. Expected: status line shows a result count + top score; a 4-column grid of striped
  placeholder cards appears with rank/score/video_id/frame_id captions; the left "Danh sách nộp"
  panel shows 5 draggable rows. Drag row 2 onto row 1 — confirm the order swaps. Click a grid card —
  confirm the detail view opens showing a neighbor-frame strip with the clicked frame outlined, and
  "← Về kết quả" returns to the grid. Type a Query ID and click "Thêm vào hàng đợi" — confirm the
  status line acknowledges it (verified against the queue itself in Task 11).

---

## Task 9: Q&A screen (mockup `1e`) wired to the backend

**Files:**

- Create: `frontend/src/screens/QaScreen.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**

- Consumes: `api.qaRun`, `api.addToQueue`.

- [x] **Step 1: Write `frontend/src/screens/QaScreen.tsx`**

  ```tsx
  import { useState } from "react";
  import { api, QaHit, QueueRow } from "../api/client";
  import { getSessionId } from "../session";

  export default function QaScreen() {
    const [query, setQuery] = useState("");
    const [question, setQuestion] = useState("");
    const [topK] = useState(20);
    const [hits, setHits] = useState<QaHit[]>([]);
    const [answer, setAnswer] = useState("");
    const [confidence, setConfidence] = useState(0);
    const [status, setStatus] = useState("");
    const [loading, setLoading] = useState(false);
    const [queryId, setQueryId] = useState("");

    async function run() {
      if (!query.trim()) {
        setStatus("⚠️ Nhập query trước.");
        return;
      }
      setLoading(true);
      try {
        const out = await api.qaRun(query, question || query, topK);
        setHits(out.hits);
        setAnswer(out.answer);
        setConfidence(out.confidence);
        setStatus(`✅ Độ tin cậy: ${(out.confidence * 100).toFixed(0)}% | Số vòng: ${out.n_loops}`);
      } catch (e) {
        setStatus(`❌ Lỗi: ${(e as Error).message}`);
      } finally {
        setLoading(false);
      }
    }

    async function addToQueue() {
      if (hits.length === 0) {
        setStatus("⚠️ Chưa có kết quả.");
        return;
      }
      const qid = queryId.trim() || "qa-query-001";
      const row: QueueRow = {
        query_id: qid,
        query_type: "qa",
        answer,
        rows: hits.map((h) => ({ video_id: h.video_id, frame_id: h.frame_id, answer })),
      };
      await api.addToQueue(getSessionId(), row);
      setStatus(`✅ Đã thêm ${qid} (${hits.length} dòng) vào hàng đợi.`);
    }

    return (
      <div className="screen qa-screen">
        <div className="field">
          <label>Mô tả cảnh (để tìm kiếm)</label>
          <textarea className="input" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <div className="field">
          <label>Câu hỏi cụ thể</label>
          <textarea className="input" value={question} onChange={(e) => setQuestion(e.target.value)} />
        </div>
        <button className="btn btn-primary" onClick={run} disabled={loading}>
          {loading ? "Đang chạy…" : "Run Q&A"}
        </button>
        <p className="status-line">{status}</p>

        {hits.length > 0 && (
          <div className="qa-body">
            <div className="qa-frame thumb-placeholder">
              <span className="mono">{hits[0].video_id} · {hits[0].frame_id}</span>
            </div>
            <div className="qa-side">
              <label>Đáp án (sửa được)</label>
              <input className="input answer-input" value={answer} onChange={(e) => setAnswer(e.target.value)} />
              <div className="confidence-bar"><div style={{ width: `${confidence * 100}%` }} /></div>
              <div className="field">
                <label>Query ID</label>
                <input className="input" placeholder="VD: query-2-qa" value={queryId} onChange={(e) => setQueryId(e.target.value)} />
              </div>
              <button className="btn btn-primary btn-block" onClick={addToQueue}>Chốt đáp án</button>
            </div>
          </div>
        )}
      </div>
    );
  }
  ```
- [x] **Step 2: Wire into `App.tsx`** — add `import QaScreen from "./screens/QaScreen";` and
  `{mode === "qa" && <QaScreen />}`.
- [x] **Step 3: Manual verification** — enter a scene description + question (e.g. from
  `pipeline_qa.py`'s own CLI demo), click Run Q&A. Expected: status line shows confidence/n_loops,
  an editable answer box appears with a confidence bar, editing the answer box updates its value,
  "Chốt đáp án" acknowledges via the status line.

---

## Task 10: TRAKE screen (mockup `1d`) wired to the backend

**Files:**

- Create: `frontend/src/screens/TrakeScreen.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**

- Consumes: `api.trakeRun`, `api.addToQueue`.

- [x] **Step 1: Write `frontend/src/screens/TrakeScreen.tsx`**

  ```tsx
  import { useState } from "react";
  import { api, TrakeCandidate, QueueRow } from "../api/client";
  import { getSessionId } from "../session";

  export default function TrakeScreen() {
    const [globalQuery, setGlobalQuery] = useState("");
    const [eventsText, setEventsText] = useState("");
    const [topKVideo] = useState(5);
    const [candidates, setCandidates] = useState<TrakeCandidate[]>([]);
    const [status, setStatus] = useState("");
    const [loading, setLoading] = useState(false);
    const [queryId, setQueryId] = useState("");

    function parseEvents(): string[] {
      return eventsText.split("\n").map((e) => e.trim()).filter(Boolean);
    }

    async function run() {
      const events = parseEvents();
      if (!globalQuery.trim() || events.length === 0) {
        setStatus("⚠️ Cần global query và ít nhất 1 event.");
        return;
      }
      setLoading(true);
      try {
        const out = await api.trakeRun(globalQuery, events, topKVideo);
        setCandidates(out.candidates);
        const best = out.candidates[0];
        setStatus(best
          ? `✅ Tốt nhất: ${best.video_id} | frame_ids: ${best.frame_ids.join(", ")}`
          : "⚠️ Không tìm được chuỗi hợp lệ.");
      } catch (e) {
        setStatus(`❌ Lỗi: ${(e as Error).message}`);
      } finally {
        setLoading(false);
      }
    }

    async function addToQueue() {
      const best = candidates[0];
      if (!best) {
        setStatus("⚠️ Chưa có kết quả.");
        return;
      }
      const qid = queryId.trim() || "trake-query-001";
      const row: QueueRow = {
        query_id: qid,
        query_type: "trake",
        rows: [{ video_id: best.video_id, frame_ids: best.frame_ids }],
      };
      await api.addToQueue(getSessionId(), row);
      setStatus(`✅ Đã thêm ${qid} vào hàng đợi.`);
    }

    return (
      <div className="screen trake-screen">
        <div className="field">
          <label>Mô tả tổng quát chuỗi sự kiện</label>
          <textarea className="input" value={globalQuery} onChange={(e) => setGlobalQuery(e.target.value)} />
        </div>
        <div className="field">
          <label>Danh sách khoảnh khắc (mỗi dòng 1 khoảnh khắc, theo thứ tự)</label>
          <textarea className="input" rows={6} value={eventsText} onChange={(e) => setEventsText(e.target.value)} />
        </div>
        <button className="btn btn-primary" onClick={run} disabled={loading}>
          {loading ? "Đang chạy…" : "Run TRAKE"}
        </button>
        <p className="status-line">{status}</p>

        {candidates.length > 0 && (
          <>
            <table className="table">
              <thead><tr><th>video_id</th><th>frame_ids</th><th>score</th></tr></thead>
              <tbody>
                {candidates.map((c) => (
                  <tr key={c.video_id}>
                    <td className="mono">{c.video_id}</td>
                    <td className="mono">{c.frame_ids.join(" | ")}</td>
                    <td className="mono">{c.score.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="field">
              <label>Query ID</label>
              <input className="input" placeholder="VD: query-3-trake" value={queryId} onChange={(e) => setQueryId(e.target.value)} />
            </div>
            <button className="btn btn-primary" onClick={addToQueue}>Thêm vào hàng đợi</button>
          </>
        )}
      </div>
    );
  }
  ```
- [x] **Step 2: Wire into `App.tsx`** — add `import TrakeScreen from "./screens/TrakeScreen";` and
  `{mode === "trake" && <TrakeScreen />}`.
- [x] **Step 3: Manual verification** — paste the global query + 3 events from `pipeline_trake.py`'s
  own CLI demo, click Run TRAKE. Expected: status line names the best video + frame_ids, a table
  lists all candidates sorted by score, "Thêm vào hàng đợi" acknowledges via the status line.

---

## Task 11: Queue/Export screen (mockup `1g`) + full end-to-end walkthrough

**Files:**

- Create: `frontend/src/screens/QueueScreen.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**

- Consumes: `api.getQueue`, `api.clearQueue`, `api.exportZip`.

- [x] **Step 1: Write `frontend/src/screens/QueueScreen.tsx`**

  ```tsx
  import { useEffect, useState } from "react";
  import { api, QueueRow } from "../api/client";
  import { getSessionId } from "../session";

  export default function QueueScreen() {
    const [queue, setQueue] = useState<QueueRow[]>([]);
    const [status, setStatus] = useState("");
    const sessionId = getSessionId();

    async function refresh() {
      const q = await api.getQueue(sessionId);
      setQueue(q);
    }

    useEffect(() => {
      refresh();
    }, []);

    async function doExport() {
      try {
        const out = await api.exportZip(sessionId);
        setStatus(
          `${out.valid ? "✅" : "⚠️"} ZIP: ${out.zip_path} | ${out.csv_count} CSV | ${out.valid ? "Hợp lệ" : "Có lỗi"}` +
          (out.errors.length ? `\n${out.errors.join("\n")}` : "")
        );
      } catch (e) {
        setStatus(`❌ Lỗi: ${(e as Error).message}`);
      }
    }

    async function doClear() {
      await api.clearQueue(sessionId);
      await refresh();
      setStatus("🗑️ Hàng đợi đã được xoá.");
    }

    return (
      <div className="screen queue-screen">
        <div className="queue-header">
          <h3>Hàng đợi nộp</h3>
          <div>
            <button className="btn btn-secondary" onClick={refresh}>🔄 Refresh</button>
            <button className="btn btn-secondary" onClick={doClear}>🗑️ Xoá hàng đợi</button>
            <button className="btn btn-primary" onClick={doExport}>📦 Export ZIP</button>
          </div>
        </div>
        <table className="table">
          <thead><tr><th>query_id</th><th>loại</th><th>dòng</th></tr></thead>
          <tbody>
            {queue.map((q) => (
              <tr key={q.query_id}>
                <td className="mono">{q.query_id}</td>
                <td className="mono tag">{q.query_type.toUpperCase()}</td>
                <td className="mono">{q.rows.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <pre className="status-line">{status}</pre>
      </div>
    );
  }
  ```
- [x] **Step 2: Wire into `App.tsx`** — add `import QueueScreen from "./screens/QueueScreen";` and
  `{mode === "queue" && <QueueScreen />}`. At this point every mode in `MODES` (except the disabled
  `chat`) renders a real screen — remove the now-unused fallback placeholder line entirely.
- [x] **Step 3: Full end-to-end manual walkthrough** (both dev servers running, submissions/queue
  empty — call `api.clearQueue` via the Queue screen first if not)

  1. KIS: search a query, drag-reorder the shortlist, add it to the queue with a query ID.
  2. Q&A: run a query+question, edit the answer, add it to the queue.
  3. TRAKE: run a query+events, add the best candidate to the queue.
  4. Queue screen: click Refresh — confirm all 3 queries appear with correct type/row counts. Click
     Export ZIP — confirm a "✅ ZIP: ..." message with `valid=true`. Open `submissions/` and confirm the
     newest ZIP contains a `submission/` folder with 3 correctly-named-per-your-query-IDs CSVs.
  5. Click Xoá hàng đợi, Refresh — confirm the table is empty again.

  This is the Phase 1 acceptance check — if all 5 steps pass with no console errors and no backend
  tracebacks, the skeleton is functionally complete.

---

## Task 12: Docs — real Quick Start commands, ignore rules, PLAN.md entry

**Files:**

- Modify: `CLAUDE.md` (Quick Start section)
- Modify: `.gitignore`, `.claudeignore`
- Modify: `PLAN.md` (Phase 7)

- [x] **Step 1: Add real run commands to CLAUDE.md's Quick Start**

  Append two lines to the "Daily commands" block:

  ```
  .venv\Scripts\python.exe -m uvicorn scripts.api.main:app --reload --port 8000   # backend API, http://127.0.0.1:8000/api/health
  cd frontend; npm run dev                                                        # frontend dev server, http://localhost:5173
  ```

  And one line near the `test_eval` smoke-test commands:

  ```
  .venv\Scripts\python.exe scripts\api\_smoke_test.py               # backend API end-to-end smoke test (KIS/QA/TRAKE/queue/export)
  ```
- [x] **Step 2: Ignore frontend build artifacts**

  Add to `.gitignore`:

  ```
  frontend/node_modules/
  frontend/dist/
  ```

  Add to `.claudeignore` (same two lines) — large generated trees, no reason for either tool to load
  them into context.
- [x] **Step 3: Update PLAN.md**

  Rename the `## Phase 7: (chưa đặt tên — chờ scope)` section to name this work, e.g.:

  ```
  ## Phase 7: Tách Frontend/Backend — FastAPI + React (vòng sau)

  Bối cảnh đầy đủ: `docs/superpowers/specs/2026-08-27-multiagent-chat-architecture-design.md`.
  Roadmap 4 phase con (thứ tự do user chốt 2026-08-27): 1) khung FastAPI + frontend React theo mockup
  Claude Design (plan: `docs/superpowers/plans/2026-08-27-phase1-fastapi-react-frontend-skeleton.md`)
  2) LangGraph AI graph 3) nối Agent Backend hoàn chỉnh vào frontend mới 4) pytest suite.

  - [ ] Phase 1 — khung FastAPI + frontend React (xem plan link ở trên)
  - [ ] Phase 2 — AI Graph (LangGraph)
  - [ ] Phase 3 — nối Agent Backend hoàn chỉnh vào frontend
  - [ ] Phase 4 — pytest suite + hoàn thiện end-to-end
  ```

  Mark the Phase 1 checkbox `[x]` only after Task 11 Step 3's walkthrough has actually passed.
- [x] **Step 4: Do NOT commit** — per session convention, leave changes unstaged unless the user
  explicitly asks for a commit in this session.

---

## Self-Review Notes (filled in after writing the plan above)

- **Spec coverage:** User's roadmap line "Backend chỉ cần khung FastAPI cơ bản + mock endpoints hoặc
  bridge tạm... để UI hoạt động" → Tasks 1–6 (chose the bridge option throughout, not mock data, since
  the real pipelines were already reusable with zero rewriting). "Dựng frontend mới theo mockup" →
  Tasks 7–11 (6 of the mockup's 7 screens: `1a/1b/1c` in Task 8, `1d` in Task 10, `1e` in Task 9, `1g`
  in Task 11; `1f` Chat intentionally left as a disabled nav stub, out of scope per the roadmap).
  "Tách Backend/Frontend độc lập" → the `scripts/api/` + `frontend/` split with a dev proxy, no shared
  process. CLAUDE.md's just-updated Tech Stack/Folder Structure → referenced, not re-done, in this plan.
- **Placeholder scan:** no TBD/TODO in code; every step has literal, complete file contents. The one
  intentional "placeholder" is the striped CSS thumbnail — that mirrors the mockup's own explicit
  design choice, not an unfinished plan step (called out twice: architecture header + Task 8).
- **Type consistency:** `Hit`/`QaHit`/`NeighborFrame`/`TrakeCandidate` field names match exactly what
  `fast_retrieve`/`run_kis`/`run_qa`/`run_trake`/`get_neighbor_frames` actually return (verified by
  reading the real source in this session, not assumed) on both the Pydantic side (`schemas.py`) and
  the TypeScript side (`api/client.ts`) — kept in sync by hand since Phase 1 has no codegen step; a
  future phase could add one, not required for a 4-endpoint skeleton.
  `jpg_path` and `n` are deliberately dropped at the API boundary (`_strip_extra` / explicit key
  allow-lists) rather than passed through, per the "no image serving yet" scope decision.
- **Naming-convention carve-out flagged twice:** Global Constraints and this section both note that
  `frontend/` uses camelCase (JS/React convention), not the repo's Python `snake_case` rule — worth
  the repeat since CLAUDE.md's rule reads as repo-wide if not read carefully against this plan.
- **Ambiguities resolved without asking (within the scope the user already handed off):** package
  manager = npm (Vite's own default, no reason to add pnpm/yarn); TypeScript over plain JS (matches a
  "real" frontend, not a throwaway prototype); no React Router (modes are tab-switches, not distinct
  URLs — nothing in the mockup implies shareable per-screen URLs); no drag-and-drop library (the
  mockup's own vanilla-JS reorder algorithm was already known-correct and is directly portable to
  React state); Vite dev-proxy over running two fully separate CORS'd origins (fewer moving parts for
  local dev, CORS middleware kept as a fallback, not the primary mechanism).
