# tests/ — Kiểm thử & Đánh giá

Nơi tập trung mọi thứ để **kiểm thử** hệ thống và **đo / so sánh** chất lượng theo đúng công thức
chấm điểm của BTC (`docs/rules/Thong tin vong So tuyen AIC2026.md` §2.1–2.2:
`R-Score` → `R@k = max_{i≤k}` → `Final Score = (1/5) Σ_k R@k`, `k ∈ {1,5,20,50,100}`).

## Ba tầng — chạy cái nào, khi nào

| Thư mục | Cần gì | Tất định? | Chạy khi nào |
|---|---|---|---|
| **`unit/`** | không cần `data/`, không cần API key | **Có** | **Mọi lần sửa code.** `pytest tests/unit` — ~10 giây |
| **`eval/`** | cần `data/extracted/` | **Có** | So sánh backbone embedding, đo thuật toán retrieval |
| **`e2e/`** | cần `data/` + `OPENROUTER_API_KEY` | Không¹ | Trước khi nộp bài, hoặc khi cần Final Score thật |

¹ **Một ngoại lệ quan trọng:** `e2e/golden_kis_snapshot.py` **tất định** và **không cần API key** —
`run_kis()` không gọi LLM. Nó là lưới regression cho toàn bộ đường KIS production:

```
.venv\Scripts\python.exe tests\e2e\golden_kis_snapshot.py --check
```

Chạy `--check` sau **mọi** refactor. Một lượt gọi phủ `index_store` → `retrieve` → `hybrid` →
`sparse_index` → `fusion` → `rerank` → `temporal_nms` → `ocr_read`. Lệch dù một dòng nghĩa là hành
vi đã đổi — không phải nhiễu. Đổi hành vi **có chủ đích** thì chốt mốc mới bằng `--save`.

> Vì sao cần nó bên cạnh `eval/run_eval.py`: `run_eval.py` chạy trên `eval/multi_index.py`, mà module
> đó **cố ý không import** `retrieve.py`. Nó không hề chạm tầng production — dùng một mình thì không
> phát hiện được regression do refactor.

## Quy ước viết test

- Khối có `assert` → `tests/unit/` dưới dạng hàm pytest. **Không** để trong `if __name__ == "__main__"`.
- Khối `__main__` chỉ dành cho CLI demo/công cụ (in kết quả cho người đọc, hoặc cần `data/`/API key).
- Monkeypatch phải nhắm vào **module sở hữu hàm đang chạy**, dùng fixture `monkeypatch` của pytest —
  không gán đè biến global. Patch nhầm module làm test "pass" vì lý do sai (xem `docs/decisions-log.md`).
- Test cần `data/` mà vẫn muốn nằm trong `unit/` thì tự `pytest.mark.skipif` khi thiếu dữ liệu
  (xem `unit/test_asr_lookup.py`) — để `pytest tests/unit` luôn xanh trên máy chỉ có source.

Ground truth (`eval/eval_ground_truth.json`) là bộ **hand-label tự chấm** (một người xem video rồi
ghi `video_id` + khoảng `frame_id` đúng), **không phải đề thi chính thức của BTC**. Quy trình ghi:
[`eval/EVAL_GUIDE.md`](eval/EVAL_GUIDE.md).

## `e2e/` — harness đường production

| File | Dùng để | Lệnh |
|---|---|---|
| `score_pipelines.py` | **Final Score BTC thật** end-to-end cho KIS/QA/TRAKE. KIS: `I(video ∧ frame∈[s,e])`; QA: thêm `answer_matches(answer, gt_answers)` (§2.1.2); TRAKE: cổng video + `(1/N)Σ I(frame_j∈[s_j,e_j])` (§2.1.3). Ghi `docs/reports/eval_e2e_scores.md`. | `.venv\Scripts\python.exe tests\e2e\score_pipelines.py --types kis,qa,trake` |
| `test_phase3_rerank.py` | R@k KIS/QA **trước/sau** risk-aware rerank (Phase 3), qua `retrieve.py` production | `.venv\Scripts\python.exe tests\e2e\test_phase3_rerank.py` |
| `test_phase4_trake.py` | TRAKE **trước/sau** LLM cross-check tầng 3 (Phase 4), 2-pass deterministic | `.venv\Scripts\python.exe tests\e2e\test_phase4_trake.py` |
| `test_phase5_ocr.py` | Answer QA **trước/sau** OCR on-demand (Phase 5, `answer_qa.py` Tier 2) | `.venv\Scripts\python.exe tests\e2e\test_phase5_ocr.py` |
| `test_phase6_margin_sweep.py` | Quét `TRAKE_CROSSCHECK_MARGIN` ở nhiều giá trị, in bảng để người tự chọn | `.venv\Scripts\python.exe tests\e2e\test_phase6_margin_sweep.py [--self-test]` |
| `test_smoke_tools.py` | Smoke test tool nền tảng (`fast_retrieve`, `objects_lookup`, `call_llm`, `rewrite_query`) sau khi setup | `.venv\Scripts\python.exe tests\e2e\test_smoke_tools.py` |
| `test_smoke_pipelines.py` | Smoke test 3 pipeline + `build_submission` + `validate_submission` (ghi CSV `smoke-*` vào `submissions/`) | `.venv\Scripts\python.exe tests\e2e\test_smoke_pipelines.py` |

`answer_matches` (trong `score_pipelines.py`): chuẩn hoá (casefold + gộp whitespace + bỏ dấu câu/nháy
2 đầu) rồi khớp nếu answer sinh ra **trùng / chứa / là con** của bất kỳ phần tử `gt_answers`.

## `eval/` — bake-off backbone embedding (retrieval-only, không LLM)

| File | Dùng để | Lệnh |
|---|---|---|
| `run_eval.py` | So `clip_vitb32` vs `vitl14`/`siglip`/`dfn`/… bằng R@k + `Final`. KIS đúng §2.1.1; QA **chỉ retrieval** (không chấm answer — dùng `score_pipelines.py` cho việc đó); TRAKE proxy §2.1.3 (ứng viên có xếp hạng + cổng video + DP thứ tự, không LLM). Ghi `docs/reports/eval_baseline_comparison.md`. | `.venv\Scripts\python.exe tests\eval\run_eval.py [--models clip_vitb32,siglip]` |
| `multi_index.py` | Index loader + text encoder cho từng model (features `.npy` từ `kaggle_jobs/`). Cố ý **không** import `index.py`/`retrieve.py`. | `.venv\Scripts\python.exe tests\eval\multi_index.py clip_vitb32` (smoke) |
| `lookup_frame.py` | CLI tra `frame_id` từ `(video_id, giây)` khi ghi ground truth | `.venv\Scripts\python.exe tests\eval\lookup_frame.py L21_V001 25.0` |
| `widen_gt_windows.py` | Nới các khoảng `gt_frame_start == gt_frame_end` (1 frame — quá chặt) ra keyframe lân cận từ `map-keyframes`; in bảng before→after để dò tay lại | `.venv\Scripts\python.exe tests\eval\widen_gt_windows.py [--dry-run]` |
| `eval_ground_truth.json` | Bộ ground truth hand-label (KIS/QA/TRAKE). Schema: xem `EVAL_GUIDE.md`. | — |
| `eval_ground_truth_thunghiem_draft.json` | Bản nháp ground truth cho vòng thử nghiệm | — |
| `EVAL_GUIDE.md` | Quy trình + schema ghi ground truth (gồm `gt_answers` cho QA) | — |

## File dữ liệu dùng chung (`tests/data/`)

| File | Là gì |
|---|---|
| `sample_queries.json` | Query mẫu (không phải đề chính thức) — dùng khi test thủ công |
| `sotuyen1_bo_de_thi.csv` | Gói đề BTC sơ tuyển đợt 1 (sinh từ `scripts/offline/shards/generate_sotuyen1_csv.py`) |
| `sotuyen2_bo_de_thi.csv` | Gói đề BTC sơ tuyển đợt 2 (sinh từ `scripts/offline/shards/generate_sotuyen2_csv.py`) |
| `thunghiem_bo_de_thi.csv` | Gói đề BTC vòng thử nghiệm |
