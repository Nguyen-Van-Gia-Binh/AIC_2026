# Phase 2 + Phase 3 Implementation Plan — Negation Rewrite Rule & Risk-Aware Ranking

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement PLAN.md Phase 2 (rewrite prompt handles negated queries) and Phase 3 (risk-aware
ranking post-processing for KIS/Q&A) — both independent of each other and of the other phases, so done
together in one pass.

**Architecture:**
- Phase 2 is a pure prompt-text addition to the existing `REWRITE_PROMPT` in
  `scripts/agent/tools/rewrite.py` — no new file, no signature change, no new dependency.
- Phase 3 adds one new tool `scripts/agent/tools/rerank.py` (pure Python, no LLM, no new dependency)
  that post-processes the `list[dict]` hits already returned by `fast_retrieve`/`fast_retrieve_for_video`.
  It is wired into `pipeline_kis.py` and `pipeline_qa.py` (both use it), not `pipeline_trake.py` (out of
  scope per PLAN.md — TRAKE's own margin/cross-check work is Phase 4).

**Tech Stack:** Pure Python (stdlib only) for `rerank.py` — no new dependency. Reuses existing
`fast_retrieve_for_video` from `scripts/agent/tools/retrieve.py`. Verification uses the project's
existing ad-hoc script convention (`.venv\Scripts\python.exe scripts\<name>.py` + `assert` + `print`) —
**this repo has no pytest / test runner configured** (see CLAUDE.md), so no step below uses pytest.

**Spec:** `PLAN.md` §"Phase 2" and §"Phase 3" (lines ~69-87 as of 2026-08-24).

## Global Constraints

- UI text and code comments are written in Vietnamese (repo-wide convention, CLAUDE.md).
- `snake_case` naming throughout, no camelCase.
- `video_id` never includes `.mp4`; `frame_id = frame_idx + 1` — never re-derive this conversion outside
  `scripts/agent/tools/retrieve.py` (already the case; Phase 3 only reorders existing dicts, never
  recomputes `frame_id`).
- Logging: plain `print()` with a `[module_name]` prefix (e.g. `[rerank]`), no logging framework.
- Don't call `litellm`/Gemini anywhere except `scripts/agent/config.py:call_llm()` — Phase 3's
  `rerank.py` must stay LLM-free per PLAN.md Phase 3 ("không cần LLM").
- Don't write submission CSV/ZIP anywhere except `scripts/submit/build_submission.py` — not touched by
  this plan.
- New single-purpose capability used by >1 pipeline → goes in `scripts/agent/tools/` (CLAUDE.md Folder
  Structure rule) — this is why `rerank.py` lives there, not inline in each pipeline.
- No `git commit`/`push` unless the user explicitly asks in this session (session-level convention
  already followed in Phase 1).

---

## Task 1: Phase 2 — Add negation-handling rule to the rewrite prompt

**Files:**
- Modify: `scripts/agent/tools/rewrite.py:23-71` (the `REWRITE_PROMPT` string)

**Interfaces:**
- Consumes: nothing new — `rewrite_query()` signature (`scripts/agent/tools/rewrite.py:74`) is
  unchanged.
- Produces: nothing new — same function, only its underlying prompt text changes.

- [x] **Step 1: Add the negation rule as a new bullet in `REWRITE_PROMPT`**

  Insert this new rule right after the existing "Preserve EXACT counts and colors..." bullet
  (`scripts/agent/tools/rewrite.py:47-49`), so the rules list reads (new bullet marked `+`):

  ```python
  - Preserve EXACT counts and colors mentioned for people/objects (e.g. "5 people", "one person wearing
      glasses", "three red hats", "yellow car") — these are strong CLIP-matchable attributes, keep them
      verbatim rather than summarizing them away
  + - If the query says something is ABSENT or NEGATED (Vietnamese "không có", "không đeo", "không mặc",
  +     English "without", "no X", "not wearing X"), do NOT keep the negation as-is in the rewritten
  +     query — CLIP matches positive visual descriptions and cannot understand logical negation, so a
  +     literal "a person without glasses" is often still matched by CLIP toward frames that DO show
  +     glasses. Instead rewrite the negated clause into what IS visibly present: either describe the
  +     actually-visible attribute in its place (e.g. "không đeo kính" -> "bare face" / "plain face, no
  +     eyewear" as part of a positive description, not as a "no X" clause), or if the object is simply
  +     not relevant to disambiguate the scene, drop it from the description entirely rather than negate
  +     it. Never output the words "no"/"without"/"không" immediately before an object name.
  - Preserve distinctive proper nouns or on-screen signage/text mentioned in the query...
  ```

- [x] **Step 2: Manual code review of the new prompt text**

  Read the edited `REWRITE_PROMPT` top to bottom once — confirm no line exceeds the existing style
  (plain English bullets, consistent indentation with the surrounding rules), and that the new bullet
  doesn't contradict rule 1 ("Output ONLY the rewritten query").

---

## Task 2: Phase 2 — Spot-check verification (real LLM calls, no ground truth needed)

**Files:**
- None modified — this is a verification-only task using the existing `rewrite.py` CLI block.

**Interfaces:**
- Consumes: `rewrite_query(query: str, feedback: str | None = None, question: str | None = None) -> str`
  from Task 1 (unchanged signature).

- [x] **Step 1: Run a throwaway negation spot-check via a one-off Python snippet**

  Run (PowerShell):
  ```
  .venv\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); from scripts.agent.tools.rewrite import rewrite_query; qs = ['Một người phụ nữ không đeo kính đang đứng nói chuyện', 'A man without a helmet riding a motorbike', 'Hai người phụ nữ, một người không đeo kính, đang ngồi đan cói']; [print(f'{q}\n  -> {rewrite_query(q)}\n') for q in qs]"
  ```

  Expected: none of the 3 printed rewritten outputs contain the literal words "no", "without", or
  "không" immediately before an object — each should describe the scene positively instead (e.g. "bare
  face" / "plain face" instead of "no glasses").

- [x] **Step 2: Note the result**

  If any output still contains a bare negation, tighten the bullet wording from Task 1 Step 1 (e.g. add
  a concrete before/after example inline) and re-run Step 1 until clean. This is a prompt-engineering
  loop, not a code bug — expect 1-2 iterations.

- [x] **Step 3 (optional, not blocking): flag the quantitative-benchmark gap**

  `queries/eval_ground_truth.json` currently has 0 queries tagged with a negation scenario, so there is
  no R@k-before/after number to report for Phase 2 (PLAN.md's literal success line asks for this). Real
  video review is needed to add such queries (per PLAN.md §0, this was assigned to the eval owner) — out
  of scope for this plan; record this gap in the PLAN.md update in Task 7.

---

## Task 3: Phase 3 — Create `rerank.py` (bet / spread post-processing)

**Files:**
- Create: `scripts/agent/tools/rerank.py`

**Interfaces:**
- Consumes: `list[dict]` hits in the exact shape `fast_retrieve`/`fast_retrieve_for_video` return
  (`scripts/agent/tools/retrieve.py:111-142`): each dict has `video_id` (str), `n` (int), `frame_idx`
  (int), `frame_id` (int), `pts_time` (float), `score` (float), `jpg_path` (str|None).
- Produces: `apply_risk_aware_ranking(hits: list[dict], top_k: int = 100, query_text: str | None = None) -> list[dict]`
  — same dict shape, reordered/re-selected, length `<= top_k`. Consumed by Task 4 and Task 5.

- [x] **Step 1: Write the file with bet-mode, spread-mode, and the dispatcher**

  ```python
  """
  rerank.py — Risk-aware re-ranking hau xu ly cho KIS/QA, chay sau khi fast_retrieve tra ve top-K.

  Y tuong (PLAN.md Phase 3): quan sat "margin" giua video ung vien manh nhat va video ung vien manh
  nhi trong danh sach hits (so sanh best score moi video).
    - Margin lon (1 video noi bat han so voi phan con lai) -> che do "dat cuoc": danh nhieu dong ket
      qua hon cho dung video do (dao sau hon trong video do bang fast_retrieve_for_video neu can), tang
      co hoi trung R@1/R@5.
    - Margin nho (khong video nao noi bat ro) -> che do "trai rui ro": gioi han so dong toi da tren 1
      video trong danh sach, ep ket qua trai rong hon nhieu video, tang co hoi trung R@50/R@100.

  Khong goi LLM (PLAN.md Phase 3: "khong can LLM"). Chi phu thuoc fast_retrieve_for_video khi can dao
  sau them trong video dang "dat cuoc" — khong tu doc/ghi index, khong doi retrieve.py.

  MARGIN_THRESHOLD / BET_VIDEO_SHARE / SPREAD_MAX_PER_VIDEO la gia tri khoi diem, CHUA co so lieu R@k
  that de hieu chinh (xem PLAN.md Blockers) — se tinh chinh lai o Phase 6 checkpoint bang benchmark
  that (scripts/test_phase3_rerank.py), khong phai doan mo hinh.

  Usage:
      from scripts.agent.tools.rerank import apply_risk_aware_ranking
      ranked = apply_risk_aware_ranking(hits, top_k=100, query_text="a red car parked on the street")
  """
  from __future__ import annotations

  import sys
  from pathlib import Path

  _ROOT = Path(__file__).resolve().parent.parent.parent
  if str(_ROOT) not in sys.path:
      sys.path.insert(0, str(_ROOT))

  # Nguong chenh lech score (cosine similarity CLIP, thuong ~0.28-0.31 cho query that — xem
  # docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md muc do luong thu
  # nghiem) de coi video #1 la "noi bat ro rang" so voi video #2.
  MARGIN_THRESHOLD = 0.012

  # Che do "dat cuoc": ti le toi da so dong (tren top_k) danh cho video noi bat nhat.
  BET_VIDEO_SHARE = 0.5

  # Che do "trai rui ro": so dong toi da cho 1 video khi khong co video nao noi bat.
  SPREAD_MAX_PER_VIDEO = 3


  def apply_risk_aware_ranking(
      hits: list[dict], top_k: int = 100, query_text: str | None = None
  ) -> list[dict]:
      """Sap xep lai hits theo chien luoc "dat cuoc" hoac "trai rui ro" tuy margin giua cac video.

      Args:
          hits: Ket qua da co tu fast_retrieve/fast_retrieve_for_video, da sap xep giam dan theo score.
          top_k: So dong toi da tra ve (gioi han submission — xem build_submission.py).
          query_text: Query da rewrite (tieng Anh) dung de dao sau them trong video "dat cuoc" khi can.
                      None = chi sap xep lai hits san co, khong goi them fast_retrieve_for_video.

      Returns:
          list[dict] cung dinh dang voi hits dau vao, do dai <= top_k.
      """
      if not hits:
          return hits

      best_score_by_video: dict[str, float] = {}
      for h in hits:
          vid = h["video_id"]
          if vid not in best_score_by_video or h["score"] > best_score_by_video[vid]:
              best_score_by_video[vid] = h["score"]

      ranked_videos = sorted(best_score_by_video.items(), key=lambda kv: -kv[1])

      if len(ranked_videos) == 1:
          margin = float("inf")
      else:
          margin = ranked_videos[0][1] - ranked_videos[1][1]

      if margin >= MARGIN_THRESHOLD:
          print(f"[rerank] margin={margin:.4f} >= {MARGIN_THRESHOLD} -> che do DAT CUOC (video={ranked_videos[0][0]})")
          return _bet_mode(hits, ranked_videos[0][0], top_k, query_text)

      print(f"[rerank] margin={margin:.4f} < {MARGIN_THRESHOLD} -> che do TRAI RUI RO")
      return _spread_mode(hits, top_k)


  def _bet_mode(hits: list[dict], top_video_id: str, top_k: int, query_text: str | None) -> list[dict]:
      n_top_slots = max(1, int(top_k * BET_VIDEO_SHARE))
      top_video_hits = [h for h in hits if h["video_id"] == top_video_id]

      if query_text and len(top_video_hits) < n_top_slots:
          from agent.tools.retrieve import fast_retrieve_for_video
          deeper = fast_retrieve_for_video(query_text, top_video_id, top_k=n_top_slots)
          seen_frame_idx = {h["frame_idx"] for h in top_video_hits}
          for d in deeper:
              if d["frame_idx"] not in seen_frame_idx:
                  top_video_hits.append(d)
                  seen_frame_idx.add(d["frame_idx"])
          top_video_hits.sort(key=lambda h: -h["score"])

      other_hits = [h for h in hits if h["video_id"] != top_video_id]
      result = top_video_hits[:n_top_slots] + other_hits
      return result[:top_k]


  def _spread_mode(hits: list[dict], top_k: int) -> list[dict]:
      per_video_count: dict[str, int] = {}
      kept: list[dict] = []
      deferred: list[dict] = []
      for h in hits:
          vid = h["video_id"]
          c = per_video_count.get(vid, 0)
          if c < SPREAD_MAX_PER_VIDEO:
              kept.append(h)
              per_video_count[vid] = c + 1
          else:
              deferred.append(h)
      result = kept + deferred
      return result[:top_k]


  # ─── CLI self-test (repo khong dung pytest — xem CLAUDE.md) ────────────────────
  if __name__ == "__main__":
      from collections import Counter

      def _fake_hit(video_id: str, i: int, score: float) -> dict:
          return {
              "video_id": video_id, "n": i, "frame_idx": i, "frame_id": i + 1,
              "pts_time": 0.0, "score": score, "jpg_path": None,
          }

      # Test 1: bet mode - video A noi bat ro rang (margin lon)
      hits_bet = (
          [_fake_hit("A", i, 0.9 - i * 0.001) for i in range(5)]
          + [_fake_hit(f"V{i}", i, 0.5 - i * 0.001) for i in range(20)]
      )
      out_bet = apply_risk_aware_ranking(hits_bet, top_k=10)
      n_a = sum(1 for h in out_bet if h["video_id"] == "A")
      assert n_a >= 5, f"Bet mode phai uu tien video A, chi thay {n_a}/10"
      print(f"[rerank] Test bet mode: OK ({n_a}/10 dong la video A)")

      # Test 2: spread mode - khong video nao noi bat (diem gan bang nhau)
      hits_spread = [
          _fake_hit(f"V{i // 10}", i, 0.5 - i * 0.0001) for i in range(50)
      ]
      out_spread = apply_risk_aware_ranking(hits_spread, top_k=30)
      counts = Counter(h["video_id"] for h in out_spread)
      assert max(counts.values()) <= SPREAD_MAX_PER_VIDEO, f"Spread mode vuot qua {SPREAD_MAX_PER_VIDEO} dong/video: {counts}"
      print(f"[rerank] Test spread mode: OK ({len(counts)} video khac nhau / {len(out_spread)} dong, max/video={max(counts.values())})")

      # Test 3: hits rong khong crash
      assert apply_risk_aware_ranking([], top_k=10) == []
      print("[rerank] Test empty input: OK")

      print("[rerank] Tat ca self-test PASS")
  ```

- [x] **Step 2: Run the self-test and confirm it fails before... — N/A, this file has no prior
      version.** Instead: run it once immediately after writing to confirm it PASSES (no red/green
      cycle possible for a brand-new pure function with inline asserts):

  Run: `.venv\Scripts\python.exe scripts\agent\tools\rerank.py`
  Expected: 4 lines ending in `[rerank] Tat ca self-test PASS`, no `AssertionError`, no traceback.

---

## Task 4: Phase 3 — Wire `rerank.py` into `pipeline_kis.py`

**Files:**
- Modify: `scripts/agent/pipeline_kis.py:27,42` (import + `run_kis` body)

**Interfaces:**
- Consumes: `apply_risk_aware_ranking(hits, top_k, query_text) -> list[dict]` from Task 3.

- [x] **Step 1: Add the import and call**

  In `scripts/agent/pipeline_kis.py`, change:
  ```python
  from agent.tools.retrieve import fast_retrieve
  ```
  to:
  ```python
  from agent.tools.retrieve import fast_retrieve
  from agent.tools.rerank import apply_risk_aware_ranking
  ```
  and change the body of `run_kis` (currently line 42):
  ```python
      results = fast_retrieve(query_text, top_k=top_k)
      return results
  ```
  to:
  ```python
      results = fast_retrieve(query_text, top_k=top_k)
      results = apply_risk_aware_ranking(results, top_k=top_k, query_text=query_text)
      return results
  ```

- [x] **Step 2: Run the existing CLI demo and confirm no crash + a `[rerank]` log line appears**

  Run: `.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "a red car parked on the street"`
  Expected: same output shape as before (10 ranked rows, submission preview), plus a new
  `[rerank] margin=... -> che do ...` line printed before the results table.

---

## Task 5: Phase 3 — Wire `rerank.py` into `pipeline_qa.py`

**Files:**
- Modify: `scripts/agent/pipeline_qa.py:26-29,68-103` (import + `run_qa` body)

**Interfaces:**
- Consumes: `apply_risk_aware_ranking(hits, top_k, query_text) -> list[dict]` from Task 3.

- [x] **Step 1: Add the import**

  Change:
  ```python
  from agent.tools.retrieve import fast_retrieve
  from agent.tools.rewrite import rewrite_query
  from agent.tools.answer_qa import answer_from_hits
  ```
  to:
  ```python
  from agent.tools.retrieve import fast_retrieve
  from agent.tools.rewrite import rewrite_query
  from agent.tools.answer_qa import answer_from_hits
  from agent.tools.rerank import apply_risk_aware_ranking
  ```

- [x] **Step 2: Track which query text produced the finally-chosen `hits`, then rerank once before
      building `results`**

  In `run_qa`, the code currently tracks `hits`/`query_en` for vong 1 and (conditionally) reassigns
  `hits = hits_v2` for vong 2 (`scripts/agent/pipeline_qa.py:83-88`). Add a `final_query_en` variable
  next to that reassignment so reranking always uses the query text matching the chosen `hits`:

  Change:
  ```python
      hits = fast_retrieve(query_en, top_k=top_k)
      print(f"[qa]   Retrieved: {len(hits)} hits, top score={hits[0]['score']:.4f}")
  ```
  to:
  ```python
      hits = fast_retrieve(query_en, top_k=top_k)
      print(f"[qa]   Retrieved: {len(hits)} hits, top score={hits[0]['score']:.4f}")
      final_query_en = query_en
  ```
  and change:
  ```python
          # Chon ket qua tot hon
          if qa_result_v2["confidence"] > qa_result["confidence"]:
              qa_result = qa_result_v2
              hits      = hits_v2
  ```
  to:
  ```python
          # Chon ket qua tot hon
          if qa_result_v2["confidence"] > qa_result["confidence"]:
              qa_result = qa_result_v2
              hits      = hits_v2
              final_query_en = query_en_v2
  ```
  Then, right before the `# ─── Build submission results ───` comment (`scripts/agent/pipeline_qa.py:90`),
  insert:
  ```python
      hits = apply_risk_aware_ranking(hits, top_k=top_k, query_text=final_query_en)
  ```

- [x] **Step 3: Run the existing CLI demo and confirm no crash + a `[rerank]` log line appears**

  Run: `.venv\Scripts\python.exe scripts\agent\pipeline_qa.py`
  Expected: same output shape as before (answer, confidence, top-5 submission rows), plus a new
  `[rerank] margin=... -> che do ...` line printed before "=== KET QUA ===".

---

## Task 6: Phase 3 — Benchmark script + real before/after comparison

**Files:**
- Create: `scripts/test_phase3_rerank.py` (ad-hoc verification script — matches the existing
  `scripts/test_day1.py`/`test_day2_*.py` convention noted in CLAUDE.md: not a pytest suite, run
  directly with the venv Python)

**Interfaces:**
- Consumes: `fast_retrieve` (`scripts/agent/tools/retrieve.py`), `apply_risk_aware_ranking`
  (Task 3), `queries/eval_ground_truth.json` (KIS + QA entries only — TRAKE entries skipped, out of
  Phase 3 scope).

- [x] **Step 1: Write the script**

  ```python
  """
  test_phase3_rerank.py — So sanh R@k truoc/sau khi ap dung apply_risk_aware_ranking (Phase 3) tren
  cac cau KIS/QA that trong queries/eval_ground_truth.json, dung DUNG duong dan production
  (scripts/agent/tools/retrieve.py, model clip_vitb32) — khac voi scripts/eval/run_eval.py (chi so
  sanh embedding baseline qua multi_index.py, khong dung retrieve.py).

  Usage:
      .venv\\Scripts\\python.exe scripts\\test_phase3_rerank.py
  """
  from __future__ import annotations

  import json
  import sys
  from pathlib import Path

  _ROOT = Path(__file__).resolve().parent.parent
  if str(_ROOT) not in sys.path:
      sys.path.insert(0, str(_ROOT))

  from scripts.agent.tools.retrieve import fast_retrieve
  from scripts.agent.tools.rerank import apply_risk_aware_ranking

  K_VALUES = [1, 5, 20, 50, 100]
  EVAL_SET_PATH = _ROOT / "queries" / "eval_ground_truth.json"


  def _rank_of_gt(hits: list[dict], gt_video_id: str, gt_start: int, gt_end: int) -> int | None:
      for i, h in enumerate(hits, start=1):
          if h["video_id"] == gt_video_id and gt_start <= h["frame_id"] <= gt_end:
              return i
      return None


  def _r_at_k(rank: int | None) -> dict[int, float]:
      return {k: (1.0 if rank is not None and rank <= k else 0.0) for k in K_VALUES}


  def main() -> None:
      eval_set = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
      queries = [q for q in eval_set if q["type"] in ("KIS", "QA")]
      print(f"[test_phase3] {len(queries)} cau KIS/QA tu {EVAL_SET_PATH}")

      before_scores, after_scores = [], []
      for q in queries:
          hits = fast_retrieve(q["text_en"], top_k=100)
          rank_before = _rank_of_gt(hits, q["gt_video_id"], q["gt_frame_start"], q["gt_frame_end"])
          before_scores.append(_r_at_k(rank_before))

          reranked = apply_risk_aware_ranking(hits, top_k=100, query_text=q["text_en"])
          rank_after = _rank_of_gt(reranked, q["gt_video_id"], q["gt_frame_start"], q["gt_frame_end"])
          after_scores.append(_r_at_k(rank_after))

          print(f"  {q['query_id']}: rank_before={rank_before}  rank_after={rank_after}")

      print("\n[test_phase3] === R@k TRUOC/SAU (trung binh tren", len(queries), "cau) ===")
      print("  k    | truoc  | sau")
      for k in K_VALUES:
          b = sum(s[k] for s in before_scores) / len(before_scores)
          a = sum(s[k] for s in after_scores) / len(after_scores)
          flag = "" if a >= b - 1e-9 else "  <-- TE DI"
          print(f"  R@{k:<4}| {b:.3f}  | {a:.3f}{flag}")


  if __name__ == "__main__":
      main()
  ```

- [x] **Step 2: Run it**

  Run: `.venv\Scripts\python.exe scripts\test_phase3_rerank.py`
  Expected: a table of R@1/5/20/50/100 before vs after, over the 23 KIS+QA eval queries. No row should
  be flagged `<-- TE DI` (worse) — this is Phase 3's literal success criterion from PLAN.md
  ("cả 2 nhóm câu đều không tệ đi").

- [x] **Step 3: If any `R@k` regresses, adjust constants and re-run**

  If a regression appears, adjust `MARGIN_THRESHOLD` and/or `BET_VIDEO_SHARE` in
  `scripts/agent/tools/rerank.py` (e.g. raise `MARGIN_THRESHOLD` so bet-mode triggers less often, or
  lower `BET_VIDEO_SHARE` so bet-mode is less aggressive when it does trigger), then re-run Step 2.
  Cap this loop at 3 iterations — if still regressing after 3 tries, fall back to `SPREAD_MAX_PER_VIDEO`
  tuning only (spread mode is the safer default) and note the remaining gap in the Task 7 PLAN.md update
  instead of continuing to iterate blind.

---

## Task 7: Update `PLAN.md` with results

**Files:**
- Modify: `PLAN.md` (Phase 2 and Phase 3 sections)

- [x] **Step 1: Mark Phase 2 done**

  Change `## Phase 2: ... (⏳ Todo)` to `(✅ Done)` and append a summary paragraph (actual wording
  depends on Task 2 results — state whether the spot-check confirmed clean negation handling, and note
  the quantitative-benchmark gap from Task 2 Step 3 explicitly, same style as the Phase 1 summary
  paragraph already in the file).

- [x] **Step 2: Mark Phase 3 done**

  Change `## Phase 3: ... (⏳ Todo)` to `(✅ Done)` and append a summary paragraph with the actual
  before/after R@k numbers from Task 6 Step 2's final run, and the final `MARGIN_THRESHOLD`/
  `BET_VIDEO_SHARE`/`SPREAD_MAX_PER_VIDEO` values used, plus a link to this plan file.

- [x] **Step 3: Do NOT commit**

  Per session convention, leave changes unstaged/uncommitted unless the user explicitly asks for a
  commit in this session.

---

## Self-Review Notes (filled in after writing the plan above)

- **Spec coverage:** Phase 2's prompt-rule requirement -> Task 1. Phase 2's success line -> Task 2
  (spot-check substitute, gap flagged since no negation ground truth exists yet). Phase 3's "post-
  processing after retrieve, bet when margin big / spread when margin small, applies to KIS+QA, no
  LLM, no other phase dependency" -> Task 3 (logic) + Task 4/5 (wiring) + Task 6 (benchmark,
  matches the literal R@1/R@5 vs R@50/R@100 comparison PLAN.md asks for).
- **Placeholder scan:** no TBD/TODO; all steps have literal code, not descriptions.
- **Type consistency:** `apply_risk_aware_ranking(hits, top_k, query_text)` signature is identical
  across Task 3 (definition), Task 4, Task 5, and Task 6 (usage). Hit dict keys match
  `fast_retrieve`'s actual return shape (`video_id`, `n`, `frame_idx`, `frame_id`, `pts_time`, `score`,
  `jpg_path`) throughout.
