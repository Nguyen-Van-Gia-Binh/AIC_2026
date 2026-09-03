# Phase 4: TRAKE — DP tăng dần + cross-check tầng 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thay bộ chọn frame "greedy, khoá cứng theo score" hiện tại của `pipeline_trake.py` bằng quy
hoạch động tìm cả chuỗi N mốc cùng lúc (tối đa tổng score, đảm bảo thứ tự thời gian không giảm), và
thêm bước cross-check tầng 3 (đối chiếu object detect sẵn, không LLM) khi 2 video ứng viên hàng đầu có
điểm sát nhau — đúng 2 việc PLAN.md Phase 4 mô tả.

**Architecture:** Toàn bộ thay đổi nằm trong `scripts/agent/pipeline_trake.py` (đúng quy ước "1 người
ôm trọn file này" của PLAN.md mục 0). Hai hàm thuần Python mới (`_find_best_increasing_chain`,
`_crosscheck_hit_count` + `_extract_keywords`) không gọi LLM, không đọc/ghi index — giống triết lý
`rerank.py` ở Phase 3 (thuật toán hậu xử lý thuần, verify bằng self-test + benchmark thật, không đoán
ngưỡng). `run_trake()` vẫn giữ nguyên chữ ký và workflow 2 giai đoạn (Retrieval rồi Alignment), chỉ đổi
**cách chọn frame trong giai đoạn 2** và **thêm 1 bước sau khi sắp xếp video**.

**Tech Stack:** Python thuần (không thêm dependency), tái dùng `agent.tools.retrieve.fast_retrieve` /
`fast_retrieve_for_video` (không đổi), `agent.tools.ocr_lookup.get_objects` (đã có, đọc Objects JSON
offline), `agent.tools.rerank.RETRIEVAL_POOL_SIZE` (hằng số đã có từ Phase 3, tái dùng — không định
nghĩa hằng số trùng lặp).

**Spec:** [PLAN.md](../../../PLAN.md) mục "Phase 4: TRAKE — ràng buộc thời gian tăng dần + cross-check
tầng 3".

## Bối cảnh / Lý do thiết kế (đọc trước khi implement)

**Vấn đề của bộ chọn frame hiện tại (`run_trake()` dòng ~91-119 bản cũ):** với mỗi event, chọn frame
điểm cao nhất trong số các frame có `frame_idx > prev_frame_idx`, rồi khoá `prev_frame_idx` lại ngay —
không bao giờ xét lại lựa chọn của event trước. Vì event đầu tiên không bị ràng buộc gì
(`prev_frame_idx = -1`), nó luôn lấy frame điểm cao nhất tuyệt đối — kể cả khi frame đó nằm rất muộn
trong video và chặn mất các event sau (event sau chỉ còn được chọn trong các frame muộn hơn nữa, thường
điểm thấp hơn nhiều). Quy hoạch động xét đồng thời cả chuỗi, có thể "hy sinh" event đầu (chọn frame điểm
thấp hơn 1 chút) để tổng điểm cả chuỗi cao hơn hẳn — xem test case cụ thể ở Task 1.

**Ràng buộc thứ tự dùng "không giảm" (`>=`) chứ không phải "tăng nghiêm ngặt" (`>`):** dữ liệu thật
trong `queries/eval_ground_truth.json` có câu (`e-trake-002`) với 2 event liên tiếp cùng
`gt_frame_start == gt_frame_end` (event "man is halfway across the street" và "man reaches the other
side" đều gán frame 13923) — tức đúng dữ liệu gán nhãn cũng chấp nhận 2 mốc trùng 1 frame khi khoảnh
khắc quá ngắn để tách biệt ở tốc độ trích keyframe hiện có. Dùng `>` nghiêm ngặt sẽ loại oan các video
đúng trong tình huống này.

**Cũng mở rộng `RETRIEVAL_POOL_SIZE` cho giai đoạn 1 (tìm video candidate):** `run_trake()` hiện gọi
`fast_retrieve(query_en, top_k=100)` để chọn ứng viên video — đúng bug pattern đã chẩn đoán và fix ở
Phase 3 (`docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md`): trần 100 có thể khiến video
đúng không lọt vào danh sách ứng viên ngay từ giai đoạn 1, trước khi DP/cross-check có cơ hội can thiệp.
Tái dùng `rerank.RETRIEVAL_POOL_SIZE=500` (đã tính chi phí gần như miễn phí ở Phase 3) thay vì lặp lại
sai lầm "trần 100" lần nữa trong cùng dự án.

**Không dùng LLM ở cross-check tầng 3** (PLAN.md: "miễn phí, không LLM") — khác với cross-check ở
`answer_qa.py` (tầng 1 CÓ gọi LLM để suy luận từ danh sách object). Ở đây chỉ đối chiếu từ khoá thô
(regex, lọc stopword ngữ pháp) với tên object detect sẵn — không gọi `call_llm()`.

## Global Constraints

- **Vietnamese comments** trong toàn bộ code mới, mật độ comment khớp phần còn lại của
  `pipeline_trake.py` (xem CLAUDE.md).
- **`snake_case`** cho mọi hàm/biến mới.
- **`frame_id = frame_idx + 1`** — không tự tính lại ở đây, luôn lấy từ dict trả về bởi
  `fast_retrieve_for_video` (đã tính sẵn ở `retrieve.py`).
- **Không có pytest trong repo này** (xem CLAUDE.md) — "test" ở mỗi Task nghĩa là 1 hàm
  `test_*()` cộng `assert`, chạy trong block `if __name__ == "__main__":` của chính
  `pipeline_trake.py`, theo đúng pattern tự-test đã dùng ở `scripts/agent/tools/rerank.py` Phase 3.
- **Không tự `git add`/`git commit`** ở bất kỳ Task nào — theo CLAUDE.md "Commit or push only when the
  user asks"; áp dụng cho toàn bộ plan này, không lặp lại ghi chú này ở từng Task.
- **Không gọi LLM** trong bất kỳ hàm mới nào của plan này (`_find_best_increasing_chain`,
  `_extract_keywords`, `_crosscheck_hit_count`) — đúng PLAN.md "miễn phí, không LLM" cho Phase 4.
- **Không đổi chữ ký `run_trake()`** — vẫn `run_trake(query_text, events, top_k_video=20,
  top_k_frame=20) -> dict` với cùng shape trả về (`results`, `best`, `n_events`), để không phá
  `build_trake_csv()` hay bất kỳ chỗ gọi nào khác.
- **Video không tìm được chuỗi hợp lệ bị loại hẳn khỏi `results`** — không trả frame sai thứ tự, không
  fallback "frame 1" (khác hành vi cũ).

---

### Task 1: Quy hoạch động chọn chuỗi mốc tăng dần

**Files:**
- Modify: `scripts/agent/pipeline_trake.py`
- Create: `scripts/test_phase4_trake.py` (benchmark thật, dùng lại ở Task 2)

**Interfaces:**
- Produces: `_find_best_increasing_chain(event_hits: list[list[dict]]) -> list[dict] | None` — hàm
  thuần, không phụ thuộc I/O, dùng lại ở Task 2 (cross-check đọc `chain[i]["video_id"]`/`["n"]`).
  Mỗi dict trong `event_hits[i]`/kết quả có đúng shape trả về bởi `fast_retrieve_for_video`:
  `video_id, n, frame_idx, frame_id, pts_time, score, jpg_path`.
- Consumes: không có phụ thuộc vào Task khác (Task đầu tiên).

- [x] **Step 1: Thêm self-test cho `_find_best_increasing_chain` (chưa implement — test sẽ fail)**

Thêm vào cuối `scripts/agent/pipeline_trake.py`, **trước** khối `# ─── CLI Demo ──` hiện có, đoạn sau
(hàm `_fake_hit` + 4 test):

```python
# ─── CLI self-test (repo khong dung pytest — xem CLAUDE.md) ────────────────────
def _fake_hit(video_id: str, frame_idx: int, score: float) -> dict:
    return {
        "video_id": video_id, "n": frame_idx, "frame_idx": frame_idx, "frame_id": frame_idx + 1,
        "pts_time": 0.0, "score": score, "jpg_path": None,
    }


def _run_self_tests() -> None:
    # Test 1: DP phai thang greedy — event 0 co frame diem cao nhat (100, 0.9) nam MUON, chan mat
    # event 1 co frame diem cao (10, 0.95) nam SOM hon. Greedy se khoa X1 (0.9) ngay lap tuc, chi con
    # Y2 (0.3) hop le cho event 1 -> tong 1.2. DP phai chon X2+Y1 = 0.8+0.95 = 1.75 (tot hon).
    event_hits_1 = [
        [_fake_hit("V", 100, 0.9), _fake_hit("V", 5, 0.8)],
        [_fake_hit("V", 10, 0.95), _fake_hit("V", 200, 0.3)],
    ]
    chain_1 = _find_best_increasing_chain(event_hits_1)
    assert chain_1 is not None, "Phai tim duoc chuoi hop le"
    total_1 = sum(h["score"] for h in chain_1)
    assert abs(total_1 - 1.75) < 1e-9, f"DP phai chon X2+Y1 (0.8+0.95=1.75), duoc {total_1}"
    assert chain_1[0]["frame_idx"] == 5 and chain_1[1]["frame_idx"] == 10, (
        f"DP phai chon frame_idx=5 roi 10, duoc {[h['frame_idx'] for h in chain_1]}"
    )
    print("[trake] Test DP thang greedy: OK (tong=1.75, tot hon greedy=1.2)")

    # Test 2: khong co chuoi hop le -> None (video bi loai)
    event_hits_2 = [
        [_fake_hit("V", 100, 0.9)],
        [_fake_hit("V", 50, 0.8)],  # frame_idx < event truoc -> khong the tang dan
    ]
    assert _find_best_increasing_chain(event_hits_2) is None, "Khong co chuoi hop le phai tra None"
    print("[trake] Test khong co chuoi hop le: OK (tra None)")

    # Test 3: 1 event duy nhat -> chon frame diem cao nhat
    event_hits_3 = [[_fake_hit("V", 10, 0.5), _fake_hit("V", 20, 0.9)]]
    chain_3 = _find_best_increasing_chain(event_hits_3)
    assert chain_3 is not None and chain_3[0]["frame_idx"] == 20, "1 event phai chon diem cao nhat"
    print("[trake] Test 1 event: OK")

    # Test 4: cho phep frame_idx BANG NHAU giua 2 event lien tiep (du lieu that co truong hop nay —
    # xem docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md)
    event_hits_4 = [[_fake_hit("V", 10, 0.5)], [_fake_hit("V", 10, 0.6)]]
    chain_4 = _find_best_increasing_chain(event_hits_4)
    assert chain_4 is not None, "Frame_idx bang nhau giua 2 event phai HOP LE (khong giam)"
    print("[trake] Test frame_idx bang nhau: OK")

    print("[trake] Tat ca self-test PASS")


if __name__ == "__main__":
    _run_self_tests()
```

- [x] **Step 2: Chạy self-test, xác nhận FAIL (hàm chưa tồn tại)**

Run: `.venv\Scripts\python.exe scripts\agent\pipeline_trake.py`
Expected: `NameError: name '_find_best_increasing_chain' is not defined`

- [x] **Step 3: Thêm import `Optional` và cài `_find_best_increasing_chain`**

Sửa dòng import ở đầu file (`from typing import Callable, Optional` — file hiện chưa import
`typing` gì cả, thêm dòng mới ngay dưới `from collections import defaultdict`):

```python
from collections import defaultdict
from typing import Optional
```

Thêm hàm sau, ngay trước `def run_trake(`:

```python
def _find_best_increasing_chain(event_hits: list[list[dict]]) -> list[dict] | None:
    """Tim chuoi 1 frame/event sao cho frame_idx KHONG GIAM qua tung event (event sau >= event
    truoc — cho phep bang nhau vi du lieu that co truong hop 2 event lien tiep trung 1 frame, xem
    docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md) va TONG score la lon nhat, bang
    quy hoach dong — thay vi greedy cu (chon diem cao nhat cho event dau tien roi khoa cung, co the
    chan mat lua chon tot hon o cac event sau, xem "Ly do thiet ke" trong plan).

    Args:
        event_hits: event_hits[i] = list ung vien (tu fast_retrieve_for_video, da sap xep giam dan
                    theo score) cho event thu i.

    Returns:
        list[dict] do dai == len(event_hits), 1 hit/event, frame_idx khong giam dan, tong score lon
        nhat co the; None neu KHONG TON TAI chuoi hop le nao (video nay bi loai hoan toan).
    """
    n = len(event_hits)
    if n == 0 or any(not candidates for candidates in event_hits):
        return None

    NEG_INF = float("-inf")
    # dp[i][j] = tong score lon nhat cua chuoi ket thuc bang ung vien j cua event i
    dp: list[list[float]] = [[NEG_INF] * len(candidates) for candidates in event_hits]
    back: list[list[Optional[int]]] = [[None] * len(candidates) for candidates in event_hits]

    for j, hit in enumerate(event_hits[0]):
        dp[0][j] = hit["score"]

    for i in range(1, n):
        for j, hit in enumerate(event_hits[i]):
            for k, prev_hit in enumerate(event_hits[i - 1]):
                if prev_hit["frame_idx"] > hit["frame_idx"]:
                    continue  # phai khong giam (>=), khong duoc lui ve truoc
                if dp[i - 1][k] == NEG_INF:
                    continue
                candidate_score = dp[i - 1][k] + hit["score"]
                if candidate_score > dp[i][j]:
                    dp[i][j] = candidate_score
                    back[i][j] = k

    last = n - 1
    best_j, best_score = None, NEG_INF
    for j, s in enumerate(dp[last]):
        if s > best_score:
            best_score, best_j = s, j
    if best_j is None or best_score == NEG_INF:
        return None

    chain: list[Optional[dict]] = [None] * n
    j = best_j
    for i in range(last, -1, -1):
        chain[i] = event_hits[i][j]
        j = back[i][j]
    return chain  # type: ignore[return-value]
```

- [x] **Step 4: Chạy lại self-test, xác nhận PASS**

Run: `.venv\Scripts\python.exe scripts\agent\pipeline_trake.py`
Expected: 4 dòng `OK` + `[trake] Tat ca self-test PASS`, sau đó demo CLI cũ vẫn chạy tiếp bình thường
(chưa nối dây vào `run_trake()` ở bước này — demo vẫn dùng hành vi cũ).

- [x] **Step 5: Nối `_find_best_increasing_chain` vào `run_trake()`, dùng `RETRIEVAL_POOL_SIZE`**

Sửa import ở đầu file:

```python
from agent.tools.retrieve import fast_retrieve, fast_retrieve_for_video
from agent.tools.rewrite import rewrite_query
from agent.tools.rerank import RETRIEVAL_POOL_SIZE
```

Trong `run_trake()`, đổi dòng:

```python
    all_hits = fast_retrieve(query_en, top_k=100)
```

thành:

```python
    all_hits = fast_retrieve(query_en, top_k=RETRIEVAL_POOL_SIZE)
```

Thay toàn bộ vòng lặp giai đoạn 2 (từ `for vid in top_videos:` tới hết phần gán `video_results.append`
cũ, đúng đoạn dòng ~91-119 bản gốc) bằng:

```python
    for vid in top_videos:
        event_hits = [fast_retrieve_for_video(eq, vid, top_k=top_k_frame) for eq in event_queries_en]
        chain = _find_best_increasing_chain(event_hits)
        if chain is None:
            print(f"[trake]   {vid}: khong tim duoc chuoi moc tang dan hop le -> loai")
            continue

        video_results.append({
            "video_id":  vid,
            "frame_ids": [h["frame_id"] for h in chain],
            "score":     sum(h["score"] for h in chain) / len(chain),
            "chain":     chain,  # giu hit day du (co "n") de cross-check tang 3 dung — khong vao CSV
        })
```

- [x] **Step 6: Chạy demo CLI có sẵn, xác nhận frame_id tăng dần và không lỗi**

Run: `.venv\Scripts\python.exe scripts\agent\pipeline_trake.py`
Expected: self-test PASS như Step 4, tiếp theo demo in ra `Frame IDs:` là danh sách không giảm dần
(vd. `[120, 340, 512, 890]` — thứ tự tăng, không còn trường hợp lặp "frame 1" fallback), không có
traceback.

- [x] **Step 7: Viết benchmark thật cho TRAKE (baseline mới sau DP)**

Tạo file mới `scripts/test_phase4_trake.py`:

```python
"""
test_phase4_trake.py — Benchmark that cho pipeline_trake.py (Phase 4: DP tang dan + cross-check
tang 3) tren cac cau TRAKE that trong queries/eval_ground_truth.json.

Metric (khac KIS/QA — TRAKE la 1 phuong an tron ven cho ca chuoi N moc, khong phai 1 dong/moc):
  - video_rank:      video co gt_video_id dung nam o hang thu may trong results (None = khong xuat
                      hien trong top_k_video ung vien).
  - events_matched:  CHI tinh cho cac cau video #1 (best) DUNG — trong so do, bao nhieu event co
                      frame_id du doan nam trong [gt_frame_start, gt_frame_end] cua chinh event do,
                      DUNG THU TU (khop tung phan tu cua danh sach du doan voi danh sach that).

Usage:
    .venv\\Scripts\\python.exe scripts\\test_phase4_trake.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.agent.pipeline_trake import run_trake

EVAL_SET_PATH = _ROOT / "queries" / "eval_ground_truth.json"


def _rank_of_video(results: list[dict], gt_video_id: str) -> int | None:
    for i, r in enumerate(results, start=1):
        if r["video_id"] == gt_video_id:
            return i
    return None


def main() -> None:
    eval_set = json.loads(EVAL_SET_PATH.read_text(encoding="utf-8"))
    queries = [q for q in eval_set if q["type"] == "TRAKE"]
    print(f"[test_phase4] {len(queries)} cau TRAKE tu {EVAL_SET_PATH}")

    n_video_top1 = 0
    n_video_found_any_rank = 0
    total_events = 0
    total_events_matched = 0

    for q in queries:
        events_text = [ev["text_en"] for ev in q["events"]]
        out = run_trake(q["text_en"], events_text, top_k_video=20, top_k_frame=20)
        results = out["results"]

        rank = _rank_of_video(results, q["gt_video_id"])
        top1_ok = rank == 1
        n_video_top1 += int(top1_ok)
        n_video_found_any_rank += int(rank is not None)

        events_matched = 0
        if top1_ok:
            predicted = results[0]["frame_ids"]
            for fid, ev in zip(predicted, q["events"]):
                lo, hi = sorted((ev["gt_frame_start"], ev["gt_frame_end"]))
                if lo <= fid <= hi:
                    events_matched += 1
        total_events += len(q["events"])
        total_events_matched += events_matched

        print(f"  {q['query_id']}: video_rank={rank}  events_matched={events_matched}/{len(q['events'])}"
              f"  (gt_video={q['gt_video_id']})")

    n = len(queries)
    print("\n[test_phase4] === Tom tat ===")
    print(f"  Video dung hang #1:            {n_video_top1}/{n}")
    print(f"  Video xuat hien (bat ky hang): {n_video_found_any_rank}/{n}")
    print(f"  Event frame dung (trong cac cau video #1 dung): {total_events_matched}/{total_events}")


if __name__ == "__main__":
    main()
```

- [x] **Step 8: Chạy benchmark, ghi lại số liệu baseline (sau DP, trước cross-check)**

Run: `.venv\Scripts\python.exe scripts\test_phase4_trake.py`
Expected: không traceback; in ra 4 dòng (1/query) + tóm tắt 3 dòng. Ghi lại 3 con số tóm tắt — dùng làm
mốc so sánh "không tệ đi" ở Task 2 Step 6.

---

### Task 2: Cross-check tầng 3 (object detection, không LLM) khi top-2 video sát điểm

**Files:**
- Modify: `scripts/agent/pipeline_trake.py`

**Interfaces:**
- Consumes: `_find_best_increasing_chain` (Task 1) — mỗi `video_results[i]["chain"]` là list hit đầy đủ
  (`video_id`, `n`, ...) do Task 1 gắn vào.
- Produces: `_extract_keywords(text: str) -> set[str]`, `_crosscheck_hit_count(chain: list[dict],
  keywords: set[str]) -> int` — không dùng ở Task nào khác trong plan này, nhưng đặt tên đủ rõ để tái
  dùng sau nếu cần (vd. Phase 5 OCR).

- [x] **Step 1: Thêm self-test cho `_extract_keywords` (chưa implement — test sẽ fail)**

Thêm vào `_run_self_tests()` (nối tiếp sau test 4 của Task 1, trước dòng
`print("[trake] Tat ca self-test PASS")`):

```python
    # Test 5: trich keyword tho — giu danh tu chi doi tuong (khop ten object), loai stopword ngu phap
    kws = _extract_keywords("A man cutting the ribbon with his colleagues")
    assert "man" in kws and "ribbon" in kws and "colleagues" in kws, f"Thieu keyword: {kws}"
    assert "the" not in kws and "his" not in kws and "with" not in kws, f"Con sot stopword: {kws}"
    print("[trake] Test extract keywords: OK")

    # Test 6: _crosscheck_hit_count khong crash voi keyword rong / chain rong
    assert _crosscheck_hit_count([], set()) == 0
    assert _crosscheck_hit_count([], {"car"}) == 0
    print("[trake] Test crosscheck rong: OK")
```

- [x] **Step 2: Chạy self-test, xác nhận FAIL**

Run: `.venv\Scripts\python.exe scripts\agent\pipeline_trake.py`
Expected: `NameError: name '_extract_keywords' is not defined`

- [x] **Step 3: Cài `_extract_keywords` + `_crosscheck_hit_count` + hằng số ngưỡng**

Thêm import ở đầu file (nối tiếp các import hiện có):

```python
import re

from agent.tools.ocr_lookup import get_objects
```

Thêm hằng số + 2 hàm mới, ngay sau `_find_best_increasing_chain` và trước `def run_trake(`:

```python
# Nguong chenh lech trake_score (trung binh cosine similarity qua N event) giua video #1 va #2 de coi
# la "chua du ro rang, can cross-check bang object detection" — cung thang do voi
# rerank.MARGIN_THRESHOLD (~0.012, xem scripts/agent/tools/rerank.py). Diem khoi dau, se tinh chinh o
# Phase 6 khi co benchmark rong hon (xem PLAN.md "Blockers").
TRAKE_CROSSCHECK_MARGIN = 0.012

# Tu loai khoi keyword khi doi chieu voi object detect duoc — chi loai tu ngu phap, GIU LAI danh tu chi
# doi tuong (man/woman/car/...) vi do chinh la thu can khop voi ten object (Person/Car/...).
_STOPWORDS = frozenset({
    "a", "an", "the", "of", "in", "on", "at", "to", "and", "or", "is", "are", "was", "were",
    "with", "this", "that", "these", "those", "his", "her", "their", "its", "for", "from",
    "by", "as", "be", "being", "been", "has", "have", "had", "it", "he", "she", "they",
    "just", "while", "first", "moment", "view",
})


def _extract_keywords(text: str) -> set[str]:
    """Tach tu khoa tho tu mo ta (khong LLM) de doi chieu voi ten object detect duoc — loc stopword
    ngu phap, giu tu >= 3 ky tu."""
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in _STOPWORDS}


def _crosscheck_hit_count(chain: list[dict], keywords: set[str]) -> int:
    """Dem so keyword co it nhat 1 object detect duoc (gop tu toan bo frame trong chain) chua no —
    khong goi LLM, chi doc Objects JSON co san (ocr_lookup.get_objects)."""
    if not keywords or not chain:
        return 0
    all_objects: set[str] = set()
    for hit in chain:
        vid = hit.get("video_id", "")
        n = hit.get("n")
        if vid and n is not None:
            all_objects.update(o.lower() for o in get_objects(vid, int(n)))
    return sum(1 for kw in keywords if any(kw in obj for obj in all_objects))
```

- [x] **Step 4: Chạy lại self-test, xác nhận PASS**

Run: `.venv\Scripts\python.exe scripts\agent\pipeline_trake.py`
Expected: 6 dòng `OK` + `[trake] Tat ca self-test PASS`.

- [x] **Step 5: Nối cross-check vào `run_trake()` sau khi sắp xếp video_results**

Trong `run_trake()`, ngay sau dòng `video_results.sort(key=lambda x: x["score"], reverse=True)`, thêm:

```python
    if len(video_results) >= 2:
        margin = video_results[0]["score"] - video_results[1]["score"]
        if margin < TRAKE_CROSSCHECK_MARGIN:
            keywords = _extract_keywords(query_text + " " + " ".join(events))
            hits0 = _crosscheck_hit_count(video_results[0]["chain"], keywords)
            hits1 = _crosscheck_hit_count(video_results[1]["chain"], keywords)
            print(f"[trake]   Cross-check top-2 (margin={margin:.4f} < {TRAKE_CROSSCHECK_MARGIN}): "
                  f"{video_results[0]['video_id']}={hits0} keyword-hit vs "
                  f"{video_results[1]['video_id']}={hits1}")
            if hits1 > hits0:
                video_results[0], video_results[1] = video_results[1], video_results[0]
                print(f"[trake]   -> Doi cho: {video_results[0]['video_id']} len #1")
```

- [x] **Step 6: Chạy lại benchmark, so sánh với baseline Task 1 Step 8, xác nhận không tệ đi**

Run: `.venv\Scripts\python.exe scripts\test_phase4_trake.py`
Expected: 3 số tóm tắt (video #1 đúng / video xuất hiện / event khớp) **>= baseline Task 1**, không có
câu nào bị đổi từ đúng sang sai. Nếu tệ đi: kiểm tra log `[trake]   Cross-check top-2 ...` cho từng câu
bị ảnh hưởng — nếu `TRAKE_CROSSCHECK_MARGIN` đang bắt quá nhiều cặp video biên (margin gần ngưỡng nhưng
video #1 gốc vẫn đúng), hạ ngưỡng xuống (vd 0.008) và chạy lại; tối đa 3 lần điều chỉnh trước khi coi là
cần thiết kế lại (theo đúng tinh thần "verify bằng số thật, không đoán" đã áp dụng ở Phase 3).

- [x] **Step 7: Cập nhật PLAN.md Phase 4 với số liệu benchmark thật**

Trong `PLAN.md`, đổi `## Phase 4: ... (⏳ Todo)` thành `(✅ Done)`, thêm đoạn "Đã làm:" mô tả 2 thay đổi
(DP + cross-check), số liệu benchmark thật từ Step 6 (3 số tóm tắt), và link tới file plan này:
`[docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md](docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md)`.

---

## Self-Review Notes

- **Spec coverage:** PLAN.md Phase 4 liệt kê đúng 2 việc — (1) DP tìm chuỗi tăng dần (Task 1), (2)
  cross-check tầng 3 khi top-2 sát điểm (Task 2). Success line "frame_id luôn tăng dần" được đảm bảo
  bằng cấu trúc DP (ràng buộc không giảm là điều kiện transition, không phải hậu kiểm); "benchmark TRAKE
  không tệ đi" được đo bằng `test_phase4_trake.py` ở cả 2 Task.
- **Placeholder scan:** không còn `TODO`/"tương tự Task N" — mọi step có code đầy đủ, copy-paste được.
- **Type consistency:** `_find_best_increasing_chain` (Task 1) trả `list[dict] | None`, đúng type được
  Task 2 dùng (`video_results[i]["chain"]`); `_crosscheck_hit_count` nhận đúng `chain: list[dict]` này.
  `run_trake()` giữ nguyên chữ ký và shape trả về (`results`/`best`/`n_events`) — không phá chỗ gọi từ
  `build_submission.py` demo hay `app.py` (TRAKE UI tab, nếu có, chưa nằm trong scope plan này vì
  PLAN.md Phase 4 chỉ mô tả thay đổi trong `pipeline_trake.py`).
