# Phase 3 Effective Rerank Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Làm Phase 3 (risk-aware ranking) tạo ra khác biệt đo được thật, bằng cách (a) nối `apply_risk_aware_ranking()` vào đúng nhánh mà người dùng thật sự dùng để build submission (`app.py` tab KIS hiện đang KHÔNG gọi rerank — nhánh chết), và (b) nới rộng candidate pool nội bộ trước khi rerank (100 → 500) vì chi phí tính gần như miễn phí và chẩn đoán thực tế cho thấy đây là nút thắt lớn nhất.

**Architecture:** Không đổi thuật toán bet/spread hiện có trong `rerank.py` — chỉ đổi (1) nguồn dữ liệu đưa vào rerank (pool rộng hơn, 1 hằng số mới `RETRIEVAL_POOL_SIZE` đặt tại `rerank.py` làm nguồn chân lý duy nhất) và (2) điểm nối dây còn thiếu (`app.py:kis_search`). Vẫn giữ nguyên format `list[dict]` hits và vẫn cắt về đúng `top_k` submission ở bước cuối cùng trong `apply_risk_aware_ranking()`.

**Tech Stack:** Python/.venv, pandas/numpy (không đổi), không LLM.

**Spec:** [PLAN.md](../../../PLAN.md) Phase 3 (đã ✅ Done nhưng benchmark cho thấy R@k không đổi trước/sau —
mục tiêu lần này là sửa để có cải thiện đo được thật). Diagnostic findings dưới đây là lý do cho plan
này, thay thế phần "Đã làm" trước của Phase 3 chỉ ở khía cạnh hiệu quả, không phủ nhận công đúng.

## Diagnostic Findings (chạy trong phiên làm việc này, không phải giả định)

Chạy chẩn đoán trên 23 câu KIS+QA của `queries/eval_ground_truth.json` qua đúng `fast_retrieve()`
production (model `clip_vitb32`):

- GT nằm trong top-100: **12/23 (52%)**
- GT nằm trong top-300: **17/23 (74%)**
- GT nằm trong top-500: **20/23 (87%)**
- 3 câu còn lại (`e-qa-ai-002/003/004`) KHÔNG tìm thấy GT dù ở top-500 — giới hạn thật của CLIP
  embedding (hoặc cần OCR — Phase 5), ngoài phạm vi Phase 3, không cố sửa ở đây.

Nguyên nhân kỹ thuật:

1. `scripts/agent/tools/retrieve.py:125` có `top_k = min(top_k, 100)` — trần cứng khiến
   `apply_risk_aware_ranking()` không bao giờ thấy được ứng viên đúng nằm ngoài top-100, dù chi phí
   tính gần như miễn phí (`scores = _MATRIX @ q_vec` đã nhân toàn bộ 177K keyframe; chỉ khác ở
   `argsort` cắt bao nhiêu phần tử).
2. `scripts/app.py:kis_search()` — tab KIS thật mà người dùng dùng để tìm rồi bấm "thêm vào queue"
   (`kis_add_to_queue` → `export_zip` → `build_kis_csv`, đây MỚI là đường build submission thật, không
   phải `scripts/submit/build_submission.py` chỉ có demo CLI riêng) — gọi thẳng `fast_retrieve()`,
   **không** đi qua `pipeline_kis.run_kis()`. Vì vậy `apply_risk_aware_ranking()` **chưa bao giờ chạy**
   trong luồng build submission KIS thật qua UI — đây là lý do chính Phase 3 "không hiệu quả" dù code
   đúng và có self-test pass: code nằm ở nhánh không ai gọi tới.

## Global Constraints

- `.venv\Scripts\python.exe` cho mọi lệnh chạy — không activate venv.
- Comment/log tiếng Việt, `snake_case`, prefix `[module_name]` cho mọi `print()`.
- `frame_id = frame_idx + 1` chỉ tính trong `retrieve.py` — không re-derive ở nơi khác.
- Không gọi LLM mới trong rerank/pool logic (Phase 3 vẫn "không cần LLM").
- Submission cuối cùng vẫn phải ≤ 100 dòng/query — `apply_risk_aware_ranking()` đã tự cắt `[:top_k]` ở
  cuối, các Task dưới không được bỏ bước này hay tự ý trả hits chưa qua rerank.
- Không dùng pytest — verify bằng chạy trực tiếp `.venv\Scripts\python.exe` + print/assert, theo đúng
  quy ước ad-hoc script hiện có (`scripts/test_*.py`).

---

### Task 1: Thêm `RETRIEVAL_POOL_SIZE` (nguồn chân lý duy nhất) + nới trần cứng trong retrieve.py

**Files:**
- Modify: `scripts/agent/tools/rerank.py` (thêm constant sau 3 constant hiện có)
- Modify: `scripts/agent/tools/retrieve.py:125`

**Interfaces:**
- Produces: `RETRIEVAL_POOL_SIZE: int = 500` (module-level trong `agent.tools.rerank`), Task 2/3/4 import
  từ đây — không hard-code lại con số này ở nơi khác.

- [x] **Step 1: Thêm constant vào `rerank.py`**

Chèn ngay sau dòng `SPREAD_MAX_PER_VIDEO = 3`:

```python
# So ung vien tho can lay tu fast_retrieve TRUOC KHI rerank/cat ve top_k submission. Lon hon han so voi
# top_k thuc te (thuong 100) vi chan doan thuc te tren eval_ground_truth.json cho thay GT frame chi nam
# trong top-100 o 12/23 cau nhung nam trong top-500 o 20/23 cau (xem
# docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md) — trong khi chi phi tinh gan nhu mien
# phi (fast_retrieve da nhan full ma tran 177K keyframe, chi argsort cat nhieu hon).
RETRIEVAL_POOL_SIZE = 500
```

- [x] **Step 2: Nới trần cứng trong `retrieve.py`**

Sửa dòng 125 từ:
```python
    top_k = min(top_k, 100)
```
thành:
```python
    top_k = min(top_k, 1000)  # tran an toan, KHONG phai gia tri mac dinh — xem rerank.RETRIEVAL_POOL_SIZE
```

- [x] **Step 3: Verify**

Run:
```
.venv\Scripts\python.exe -c "from scripts.agent.tools.retrieve import fast_retrieve; r = fast_retrieve('a person walking', top_k=500); print(len(r))"
```
Expected: in ra `500` (trước đây bị kẹp về `100`).

---

### Task 2: Nới pool trong `pipeline_kis.py`

**Files:** Modify `scripts/agent/pipeline_kis.py`

**Interfaces:**
- Consumes: `apply_risk_aware_ranking(hits, top_k, query_text)` (đã có), `RETRIEVAL_POOL_SIZE: int` (Task 1).

- [x] **Step 1: Sửa import + `run_kis()`**

```python
from agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE
```

```python
def run_kis(query_text: str, top_k: int = 100) -> list[dict]:
    """..."""
    pool_size = max(top_k, RETRIEVAL_POOL_SIZE)
    results = fast_retrieve(query_text, top_k=pool_size)
    print(f"[kis] Lay {len(results)} ung vien tho (pool={pool_size}), rerank cat ve top_k={top_k}")
    results = apply_risk_aware_ranking(results, top_k=top_k, query_text=query_text)
    return results
```

- [x] **Step 2: Verify**

Run: `.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "a red car parked on the street"`
Expected: log có dòng `[kis] Lay 500 ung vien tho (pool=500)...`, output cuối vẫn ≤ `top_k` dòng.

---

### Task 3: Nới pool trong `pipeline_qa.py` (vòng 1 + vòng 2)

**Files:** Modify `scripts/agent/pipeline_qa.py`

**Interfaces:**
- Consumes: `RETRIEVAL_POOL_SIZE` (Task 1), import cùng dòng với `apply_risk_aware_ranking` đã có sẵn.

- [x] **Step 1: Sửa import**

```python
from agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE
```

- [x] **Step 2: Sửa 2 lời gọi `fast_retrieve` (vòng 1 và vòng 2)**

Vòng 1 (ngay sau `query_en = rewrite_query(...)`):
```python
    pool_size = max(top_k, RETRIEVAL_POOL_SIZE)
    hits = fast_retrieve(query_en, top_k=pool_size)
```

Vòng 2 (giữ nguyên `pool_size` đã tính ở trên, không tính lại):
```python
        hits_v2 = fast_retrieve(query_en_v2, top_k=pool_size)
```

Không đổi `answer_from_hits(question, hits, top_n=5)` — hàm này chỉ lấy `top_n` phần tử đầu của
`hits`, vốn luôn là điểm cao nhất bất kể pool dài bao nhiêu (fast_retrieve luôn trả về đã sort giảm dần).

- [x] **Step 3: Verify**

Run: `.venv\Scripts\python.exe scripts\agent\pipeline_qa.py`
Expected: vẫn ra answer hợp lệ như trước, log cho thấy pool 500 được dùng, `[rerank]` log ở cuối vẫn in ra.

---

### Task 4: Nối rerank vào `app.py:kis_search()` — sửa nhánh chết (quan trọng nhất)

**Files:** Modify `scripts/app.py`

**Interfaces:**
- Consumes: `apply_risk_aware_ranking`, `RETRIEVAL_POOL_SIZE` từ `agent.tools.rerank`.

- [x] **Step 1: Sửa `kis_search()`**

Thay đoạn hiện tại:
```python
    hits = fast_retrieve(query_used, top_k=int(top_k))
```
thành:
```python
    from agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE
    pool_size = max(int(top_k), RETRIEVAL_POOL_SIZE)
    hits = fast_retrieve(query_used, top_k=pool_size)
    hits = apply_risk_aware_ranking(hits, top_k=int(top_k), query_text=query_used)
```
Giữ nguyên toàn bộ phần gallery/df/status phía sau (`_hits_to_gallery(hits)`, `_hits_to_df(hits)`, ...) —
không đổi vì `hits` vẫn cùng format, chỉ khác nội dung/thứ tự.

- [x] **Step 2: Verify qua UI thật**

Run: `.venv\Scripts\python.exe scripts\app.py`, mở `http://127.0.0.1:7860`, tab KIS, nhập 1 câu query,
bấm tìm. Xác nhận terminal in `[rerank] margin=...`. Đây là bước đầu tiên Phase 3 thật sự cần mở UI để
verify — vì đây chính là nhánh trước đó chưa từng được kiểm qua UI.

---

### Task 5: Cập nhật `scripts/test_phase3_rerank.py` để phản ánh pool mới

**Files:** Modify `scripts/test_phase3_rerank.py`

**Interfaces:**
- Consumes: `RETRIEVAL_POOL_SIZE` (Task 1).

- [x] **Step 1: Sửa import + vòng lặp so sánh**

```python
from scripts.agent.tools.rerank import apply_risk_aware_ranking, RETRIEVAL_POOL_SIZE
```

```python
    for q in queries:
        hits_before = fast_retrieve(q["text_en"], top_k=100)  # hanh vi CU: chi top-100, khong rerank
        rank_before = _rank_of_gt(hits_before, q["gt_video_id"], q["gt_frame_start"], q["gt_frame_end"])
        before_scores.append(_r_at_k(rank_before))

        hits_pool = fast_retrieve(q["text_en"], top_k=RETRIEVAL_POOL_SIZE)  # hanh vi MOI: pool rong hon
        reranked = apply_risk_aware_ranking(hits_pool, top_k=100, query_text=q["text_en"])
        rank_after = _rank_of_gt(reranked, q["gt_video_id"], q["gt_frame_start"], q["gt_frame_end"])
        after_scores.append(_r_at_k(rank_after))

        print(f"  {q['query_id']}: rank_before={rank_before}  rank_after={rank_after}")
```

- [x] **Step 2: Chạy benchmark**

Run: `.venv\Scripts\python.exe scripts\test_phase3_rerank.py`
Ghi lại bảng R@k trước/sau đầy đủ.

- [x] **Step 3: Nếu có R@k nào TỆ ĐI, chẩn đoán + sửa, chạy lại (tối đa 3 vòng)**

Lần này kỳ vọng không chỉ "không đổi" mà thực sự CẢI THIỆN R@20/R@50/R@100 (do diagnostic cho thấy
GT-trong-pool tăng từ 12/23 lên 17-20/23). Nếu R@1/R@5 giảm (do pool rộng hơn kéo thêm nhiễu vào margin
tính toán), cân nhắc giảm `RETRIEVAL_POOL_SIZE` hoặc tăng `MARGIN_THRESHOLD` một chút — sửa tại
`rerank.py`, không sửa logic `_bet_mode`/`_spread_mode`.

---

### Task 6: Cập nhật PLAN.md

**Files:** Modify `PLAN.md` (mục Phase 3)

- [x] **Step 1: Thêm đoạn "Đã làm (bản hiệu quả hơn)"**

Nối thêm sau đoạn "Đã làm" hiện có của Phase 3 (không xoá đoạn cũ — giữ lịch sử), tóm tắt: lý do cần
plan này (nhánh `app.py:kis_search` bị bỏ qua rerank), `RETRIEVAL_POOL_SIZE=500`, số liệu benchmark mới
từ Task 5, link tới file plan này.

- [x] **Step 2: Không commit**

Theo quy ước "chỉ commit khi được yêu cầu" — dừng lại sau khi sửa file, không `git add`/`git commit`.

---

## Self-Review Notes

- **Spec coverage:** Diagnostic Findings → Task 1 (root cause: trần cứng retrieve.py) + Task 4 (root
  cause: nhánh app.py chết) đều có task riêng giải quyết trực tiếp. Benchmark cập nhật ở Task 5 đo lại
  đúng bằng chứng đã dùng để lập plan.
- **No placeholders:** mọi step đều có code cụ thể, không có "TODO"/"tương tự Task N".
- **Type/signature consistency:** `apply_risk_aware_ranking(hits, top_k, query_text)` giữ nguyên chữ ký
  xuyên suốt Task 2-5; `RETRIEVAL_POOL_SIZE` chỉ định nghĩa 1 lần ở `rerank.py` (Task 1), mọi nơi khác
  import chứ không hard-code lại — tránh lệch giá trị giữa các file như CLAUDE.md DRY yêu cầu.
- **Không đổi thuật toán bet/spread hiện có** — rủi ro thấp, chỉ đổi input pool + 1 điểm wiring còn
  thiếu, đúng tinh thần "ưu tiên workflow đơn giản nhất" của CLAUDE.md/DECISION.md.
