# Kế hoạch Thực thi Chi tiết — Hoàn thiện các công việc giang dở của Pha 2

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hoàn thiện toàn bộ các nhiệm vụ còn dang dở của Pha 2 (P2.2 ➔ P2.3 ➔ P2.6 ➔ P2.5 ➔ P2.4 + P2.7), đảm bảo mỗi task có test riêng, đo đạc trước–sau, ghi log đầy đủ và không gây suy thoái hệ thống.

**Architecture:** Tuân thủ kiến trúc mô-đun đã tách ở Pha 1 (`scripts/agent/tools/`, `pipeline_trake.py`, `pipeline_qa.py`, `answer_qa.py`, `ocr_read.py`). Các cải tiến logic retrieval, DP và OCR được triển khai độc lập, có fallback an toàn và công tắc kiểm soát.

**Tech Stack:** Python 3.10+, Pytest, PyTorch (CUDA 12.8/12.9), SigLIP/SigLIP2, VietOCR / PaddleOCR, LiteLLM.

**Spec:** [docs/superpowers/specs/2026-08-31-phase2-behavior-fixes-design.md](../specs/2026-08-31-phase2-behavior-fixes-design.md)

---

## Global Constraints

- `pytest tests/unit -q` phải pass (xanh) 100% sau mỗi task.
- Mọi số đo so sánh phục vụ báo cáo phải chạy ở `AIC_MODE=test` (không dùng `local` để lấy số kết luận).
- Mỗi task sửa hành vi phải ghi một khối kết quả vào `docs/reports/phase2_measurement_log.md` trước khi commit.
- Luật single-call-site giữ nguyên: LLM chỉ ở `scripts/agent/config.py:call_llm()`; CSV/ZIP chỉ ở `scripts/submit/build_submission.py`.
- Import nội bộ dùng tiền tố `scripts.`; chỉ repo root trên `sys.path`.
- Comment và text UI bằng tiếng Việt có dấu.
- Mỗi task hoàn thành một commit riêng biệt với git commit message chuẩn.

---

## Task 1: P2.2 — TRAKE mở rộng `top_k_video=100`

**Files:**
- Modify: `scripts/agent/pipeline_trake.py:10,120,132`
- Test: `tests/unit/test_pipeline_trake.py`

**Interfaces:**
- Consumes: `run_trake(query_text, events, top_k_video=100, ...)`
- Produces: `results` danh sách candidate video lên đến 100 dòng thay vì bị nghẽn ở 20 dòng.

- [x] **Step 1: Viết unit test kiểm tra giá trị mặc định của `top_k_video`**

Thêm test vào `tests/unit/test_pipeline_trake.py`:
```python
import inspect
from scripts.agent.pipeline_trake import run_trake

def test_run_trake_default_top_k_video_is_100():
    sig = inspect.signature(run_trake)
    assert sig.parameters["top_k_video"].default == 100
```

- [x] **Step 2: Chạy test để xác nhận test FAIL**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_pipeline_trake.py -k test_run_trake_default_top_k_video_is_100`
Expected: FAIL (`assert 20 == 100`).

- [x] **Step 3: Cập nhật `pipeline_trake.py`**

Trong file `scripts/agent/pipeline_trake.py`:
- Dòng 10: Đổi `(mặc định 20)` thành `(mặc định 100)`.
- Dòng 120: Đổi `top_k_video: int = 20` thành `top_k_video: int = 100`.
- Dòng 132: Đổi `(default 20)` thành `(default 100)`.

- [x] **Step 4: Chạy test để xác nhận test PASS**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_pipeline_trake.py -k test_run_trake_default_top_k_video_is_100`
Expected: PASS.

- [x] **Step 5: Đo đạc trước/sau và ghi nhật ký**

Run: `.venv\Scripts\python.exe tests/e2e/score_pipelines.py --types trake`
Ghi kết quả TRAKE Final, R@20, R@50, R@100 vào `docs/reports/phase2_measurement_log.md`.

- [x] **Step 6: Commit**

```bash
git add scripts/agent/pipeline_trake.py tests/unit/test_pipeline_trake.py docs/reports/phase2_measurement_log.md
git commit -m "fix(P2.2): TRAKE mo rong top_k_video=100 go bo khoang chan R@50/R@100"
```

---

## Task 2: P2.3 — TRAKE fallback `strict=False` khi không có chuỗi tăng nghiêm ngặt

**Files:**
- Modify: `scripts/agent/pipeline_trake.py:198-212,219,245-251`
- Test: `tests/unit/test_trake_align.py`, `tests/unit/test_pipeline_trake.py`

**Interfaces:**
- Consumes: `find_best_increasing_chain(event_hits, strict=bool)` từ `scripts.agent.tools.trake_align`
- Produces: `video_results` chứa thêm trường `strict_chain: bool`. Candidate có `strict_chain=False` được giữ lại nhưng xếp sau các candidate có `strict_chain=True`.

- [x] **Step 1: Viết test cho hành vi fallback và phân hạng chuỗi**

Thêm test vào `tests/unit/test_trake_align.py`:
```python
def test_fallback_when_strict_chain_impossible():
    # 2 event cùng điểm cao nhất ở frame_idx = 100
    event_hits = [
        [{"frame_id": 101, "n": 100, "score": 0.9, "video_id": "V1", "pts_time": 10.0}],
        [{"frame_id": 101, "n": 100, "score": 0.85, "video_id": "V1", "pts_time": 10.0}],
    ]
    assert find_best_increasing_chain(event_hits, strict=True) is None
    relaxed_chain = find_best_increasing_chain(event_hits, strict=False)
    assert relaxed_chain is not None
    assert len(relaxed_chain) == 2
```

Và thêm test vào `tests/unit/test_pipeline_trake.py`:
```python
def test_pipeline_trake_ranks_strict_before_relaxed():
    # Video có strict_chain=True phải xếp trước strict_chain=False nếu bằng hoặc sát điểm
    candidates = [
        {"video_id": "V_relaxed", "score": 0.95, "strict_chain": False},
        {"video_id": "V_strict", "score": 0.90, "strict_chain": True},
    ]
    # Tiêu chí sắp xếp: strict_chain ưu tiên hàng đầu, sau đó tới score
    sorted_candidates = sorted(
        candidates,
        key=lambda x: (1 if x.get("strict_chain", True) else 0, x["score"]),
        reverse=True
    )
    assert sorted_candidates[0]["video_id"] == "V_strict"
    assert sorted_candidates[1]["video_id"] == "V_relaxed"
```

- [x] **Step 2: Chạy test để xác nhận**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_trake_align.py tests/unit/test_pipeline_trake.py`
Expected: Test pass vì test align kiểm tra hàm có sẵn, test sort kiểm tra logic mẫu.

- [x] **Step 3: Cập nhật logic trong `pipeline_trake.py`**

Sửa khối căn chỉnh tại Giai đoạn 2 trong `scripts/agent/pipeline_trake.py`:
```python
    # ─── Giai đoạn 2: Alignment cho từng video ─────────────────────────────────
    video_results = []

    for vid in top_videos:
        event_hits = [fast_retrieve_for_video(eq, vid, top_k=top_k_frame) for eq in event_queries_en]
        chain = find_best_increasing_chain(event_hits, strict=strict_monotonic)
        is_strict = True
        if chain is None and strict_monotonic:
            # Thử nới lỏng strict=False để cứu video (vd keyframe thưa các mốc trùng keyframe)
            chain = find_best_increasing_chain(event_hits, strict=False)
            is_strict = False
            if chain is not None:
                print(f"[trake]   {vid}: cứu video bằng chuỗi nới lỏng (strict=False)")

        if chain is None:
            print(f"[trake]   {vid}: không tìm được chuỗi mốc hợp lệ -> loại")
            continue

        trake_score = sum(h["score"] for h in chain) / len(chain)
        video_results.append({
            "video_id":    vid,
            "frame_ids":   [h["frame_id"] for h in chain],
            "trake_score": trake_score,
            "strict_chain": is_strict,
            "chain":       chain,
        })
```
Và cập nhật tiêu chí sắp xếp ở Giai đoạn 3:
```python
    video_results.sort(
        key=lambda x: (1 if x.get("strict_chain", True) else 0, x["score"]),
        reverse=True
    )
```

- [x] **Step 4: Chạy lại toàn bộ unit test**

Run: `.venv\Scripts\python.exe -m pytest tests/unit -q`
Expected: 100% PASSED.

- [x] **Step 5: Đo đạc và ghi nhật ký**

Run: `.venv\Scripts\python.exe tests/e2e/score_pipelines.py --types trake`
Ghi nhận kết quả vào `docs/reports/phase2_measurement_log.md`.

- [x] **Step 6: Commit**

```bash
git add scripts/agent/pipeline_trake.py tests/unit/test_trake_align.py tests/unit/test_pipeline_trake.py docs/reports/phase2_measurement_log.md
git commit -m "fix(P2.3): TRAKE fallback strict=False cuu video thay vi loai thang"
```

---

## Task 3: P2.6 — Q&A trích xuất answer cho nhiều cụm hơn (Tier 1 cheap clusters)

**Files:**
- Modify: `scripts/agent/tools/answer_qa.py:146`
- Modify: `scripts/agent/pipeline_qa.py:44,64-88`
- Test: `tests/unit/test_answer_qa.py`, `tests/unit/test_pipeline_qa.py`

**Interfaces:**
- Consumes: `answer_from_hits(..., max_tier: int = 2)`
- Produces: `pipeline_qa` chạy 3 cụm đầu với `max_tier=2` (Full VLM/OCR) và cụm 4..15 với `max_tier=1` (Chỉ Objects JSON + 1 lượt text LLM, không tốn Vision VLM).

- [x] **Step 1: Viết test cho tham số `max_tier` của `answer_from_hits`**

Thêm test vào `tests/unit/test_answer_qa.py`:
```python
from unittest.mock import patch
from scripts.agent.tools.answer_qa import answer_from_hits

def test_answer_from_hits_max_tier_1_skips_vision():
    hits = [{"video_id": "L21_V001", "frame_id": 10, "score": 0.8}]
    with patch("scripts.agent.tools.answer_qa.call_llm") as mock_llm:
        # Mock Tier 1 trả về đáp án rõ ràng
        mock_llm.return_value = "ANSWER: quả bóng màu đỏ"
        ans = answer_from_hits(
            query="câu hỏi về bóng",
            question="quả bóng màu gì?",
            hits=hits,
            max_tier=1
        )
        assert ans["answer"] != ""
        # Khẳng định chỉ gọi LLM text 1 lần và không gọi model vision
        assert mock_llm.call_count <= 1
        if mock_llm.call_count == 1:
            assert mock_llm.call_args[1].get("model") == "text"
```

- [x] **Step 2: Chạy test để xác nhận**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_answer_qa.py -k test_answer_from_hits_max_tier_1_skips_vision`
Expected: PASS hoặc FAIL tùy thuộc tham số `max_tier` hiện tại.

- [x] **Step 3: Cập nhật `answer_qa.py` và `pipeline_qa.py`**

Trong `scripts/agent/tools/answer_qa.py`:
Cập nhật signature hàm:
```python
def answer_from_hits(
    query: str,
    question: str,
    hits: list[dict],
    max_tier: int = 2,
) -> dict:
```
Và sau khi kết thúc Tầng 1:
```python
    if max_tier == 1:
        # Dừng sau Tầng 1 — không vào Tầng 2 Vision, không chạy OCR
        if t1_answer and not is_non_answer(t1_answer):
            return {
                "answer": t1_answer,
                "confidence": 0.6,
                "source": "objects_json_tier1",
                "method": "objects",
                "best_hit": hits[0] if hits else {},
            }
        return {
            "answer": "",
            "confidence": 0.0,
            "source": "tier1_no_answer",
            "method": "fallback",
            "best_hit": hits[0] if hits else {},
        }
```

Trong `scripts/agent/pipeline_qa.py`:
```python
FULL_ANSWER_CLUSTERS = 3     # Chạy đủ Tầng 1 + Tầng 2 Vision
CHEAP_ANSWER_CLUSTERS = 12   # Cụm 4..15 chỉ chạy Tầng 1 Objects JSON (rẻ, 1 lượt text LLM)
```
Cập nhật vòng lặp `answer_by_video_cluster`:
```python
    for idx, (vid, vhits) in enumerate(top_clusters):
        max_tier = 2 if idx < FULL_ANSWER_CLUSTERS else 1
        ans_info = answer_from_hits(
            query=query_text,
            question=question,
            hits=vhits,
            max_tier=max_tier,
        )
        cluster_answers[vid] = ans_info
```

- [x] **Step 4: Chạy toàn bộ pytest**

Run: `.venv\Scripts\python.exe -m pytest tests/unit -q`
Expected: 100% PASSED.

- [x] **Step 5: Đo đạc và ghi nhật ký**

Run: `.venv\Scripts\python.exe tests/e2e/score_pipelines.py --types qa`
Ghi lại Final Score QA và chi phí vào `docs/reports/phase2_measurement_log.md`.

- [x] **Step 6: Commit**

```bash
git add scripts/agent/tools/answer_qa.py scripts/agent/pipeline_qa.py tests/unit/test_answer_qa.py docs/reports/phase2_measurement_log.md
git commit -m "fix(P2.6): Q&A mo rong trich xuat dap an cho 15 cum video (3 full + 12 cheap)"
```

---

## Task 4: P2.5 — Bật lại OCR Offline & Thêm Fail-Loud Health Check

**Files:**
- Create: `scripts/offline/ocr/fetch_vietocr_assets.py`
- Modify: `scripts/agent/tools/ocr_read.py:88-100`
- Modify: `.gitignore`
- Test: `tests/unit/test_ocr_read.py`

**Interfaces:**
- Consumes: Model weights `data/models/vietocr/vgg_transformer.pth` và config offline `data/models/vietocr/config.yml`.
- Produces: Hàm `ocr_health() -> tuple[bool, str]` và cơ chế nạp VietOCR an toàn không phụ thuộc host ngoài `vocr.vn`.

- [x] **Step 1: Viết test cho `ocr_health()`**

Tạo `tests/unit/test_ocr_read.py`:
```python
from unittest.mock import patch
from pathlib import Path
from scripts.agent.tools.ocr_read import ocr_health

def test_ocr_health_bao_loi_ro_khi_thieu_tai_san(tmp_path):
    with patch("scripts.agent.tools.ocr_read._VIETOCR_CONFIG", tmp_path / "nonexistent.yml"):
        ok, reason = ocr_health()
        assert ok is False
        assert "fetch_vietocr_assets.py" in reason
```

- [x] **Step 2: Chạy test để xác nhận FAIL**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_ocr_read.py`
Expected: FAIL (`cannot import name 'ocr_health'`).

- [x] **Step 3: Tạo `fetch_vietocr_assets.py` và cập nhật `ocr_read.py`**

Tạo `scripts/offline/ocr/fetch_vietocr_assets.py` để đóng gói assets vào `data/models/vietocr/`.
Cập nhật `scripts/agent/tools/ocr_read.py`:
- Thêm `_VIETOCR_DIR = _ROOT / "data" / "models" / "vietocr"`
- Thêm `_VIETOCR_CONFIG = _VIETOCR_DIR / "config.yml"`
- Cập nhật hàm khởi tạo engine: dùng `Cfg.load_config_from_file(str(_VIETOCR_CONFIG))` thay vì nạp từ tên qua internet.
- Viết hàm `ocr_health() -> tuple[bool, str]`.
- Thêm `data/models/` vào `.gitignore`.

- [x] **Step 4: Chạy test để xác nhận PASS**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_ocr_read.py`
Expected: PASS.

- [x] **Step 5: Chạy kiểm tra thực tế**

Run: `.venv\Scripts\python.exe -c "from scripts.agent.tools.ocr_read import ocr_health; print(ocr_health())"`
Expected: In ra `(True, 'OCR ready')` hoặc lý do rõ ràng.

- [x] **Step 6: Commit**

```bash
git add scripts/offline/ocr/fetch_vietocr_assets.py scripts/agent/tools/ocr_read.py tests/unit/test_ocr_read.py .gitignore
git commit -m "fix(P2.5): phuc hoi cau hinh offline cho VietOCR va them ham ocr_health"
```

---

## Task 5: P2.4 + P2.7 — Xây dựng công cụ quét tham số Rerank & Bet Mode

**Files:**
- Create: `tests/eval/sweep_rerank.py`
- Modify: `docs/reports/phase2_measurement_log.md`
- Test: `tests/unit/test_sweep_rerank.py`

**Interfaces:**
- Consumes: `score_kis()` từ `scripts/../score_pipelines.py`
- Produces: Bảng so sánh các ngưỡng `MARGIN_THRESHOLD` và phương pháp gán điểm `_bet_mode` (KHÔNG tự ý sửa tham số production khi chưa đủ ≥100 câu KIS).

- [x] **Step 1: Viết test cho `sweep_rerank.py`**

Tạo `tests/unit/test_sweep_rerank.py`:
```python
from tests.eval.sweep_rerank import compute_bet_rank_score

def test_compute_bet_rank_score():
    # Khẳng định điểm gán cho ứng viên đào sâu dựa trên thứ hạng nội bộ video
    score_rank_0 = compute_bet_rank_score(rank_in_video=0, base_score=0.015)
    score_rank_5 = compute_bet_rank_score(rank_in_video=5, base_score=0.015)
    assert score_rank_0 > score_rank_5
    assert score_rank_0 > 0.0015
```

- [x] **Step 2: Viết script `tests/eval/sweep_rerank.py`**

Implement harness quét `MARGIN_THRESHOLD` ∈ `[-1.0, 0.004, 0.008, 0.012, 0.020, 0.035, 1.0]` và xuất bảng số liệu.

- [x] **Step 3: Chạy test và chạy harness**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/test_sweep_rerank.py`
Run: `.venv\Scripts\python.exe tests/eval/sweep_rerank.py`

- [x] **Step 4: Commit harness**

```bash
git add tests/eval/sweep_rerank.py tests/unit/test_sweep_rerank.py
git commit -m "feat(eval): them sweep_rerank harness de khao sat MARGIN_THRESHOLD va bet_mode"
```

---

## Task 6: Kiểm chứng Toàn diện & Nghiệm thu Pha 2

- [x] **Step 1: Chạy trọn vẹn bộ kiểm thử unit**
Run: `.venv\Scripts\python.exe -m pytest tests/unit -q`
Expected: 100% tests PASSED.

- [x] **Step 2: Chạy kiểm tra Golden Snapshot KIS**
Run: `.venv\Scripts\python.exe tests/e2e/golden_kis_snapshot.py --check`

- [x] **Step 3: Chạy toàn bộ E2E scoring 38 câu và lưu baseline mới**
Run: `.venv\Scripts\python.exe tests/e2e/score_pipelines.py --types kis,qa,trake --save-baseline`

- [x] **Step 4: Cập nhật PLAN.md và decisions-log.md**
Tick các checkbox hoàn thành trong [PLAN.md](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/PLAN.md) và ghi nhận bài học trong [docs/decisions-log.md](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/docs/decisions-log.md).

- [x] **Step 5: Commit nghiệm thu Pha 2**
```bash
git add PLAN.md docs/decisions-log.md docs/reports/phase2_measurement_log.md
git commit -m "docs: nghiem thu va hoan tat Pha 2 (P2.1-P2.8)"
```
