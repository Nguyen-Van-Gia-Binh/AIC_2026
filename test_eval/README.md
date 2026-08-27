# Test & Eval

Nơi tập trung mọi thứ để **kiểm thử** hệ thống và **đo / so sánh** chất lượng theo đúng công thức
chấm điểm của BTC (`docs/Thong tin vong So tuyen AIC2026.md` §2.1–2.2:
`R-Score` → `R@k = max_{i≤k}` → `Final Score = (1/5) Σ_k R@k`, `k ∈ {1,5,20,50,100}`).

Thư mục này (trước đây là `queries/`) có 2 nhánh, khác nhau ở chỗ **có đi qua đường production hay
không**:

| | `Test/` | `Eval/` |
|---|---|---|
| Chạy qua `scripts/agent/*` (retrieve + rerank + DP + LLM)? | **Có** — đúng cái sẽ nộp | **Không** — chỉ cosine trên embedding đã encode |
| Cần API key? | **Có** (`OPENROUTER_API_KEY`, hoặc `GEMINI_API_KEY` khi `AIC_MODE=test`) | Không |
| Deterministic? | Không (QA/TRAKE có biến thiên LLM — chạy 2–3 lần) | Có |
| Dùng để | Ước lượng Final Score thật, xác nhận không regression khi đổi pipeline | Chọn backbone embedding (clip_vitb32 / vitl14 / siglip / dfn / …) |

Ground truth (`Eval/eval_ground_truth.json`) là bộ **hand-label tự chấm** (một người xem video rồi
ghi `video_id` + khoảng `frame_id` đúng), **không phải đề thi chính thức của BTC**. Quy trình ghi:
[`Eval/EVAL_GUIDE.md`](Eval/EVAL_GUIDE.md).

---

## `Test/` — harness đường production

| File | Dùng để | Lệnh |
|---|---|---|
| `score_pipelines.py` | **Final Score BTC thật** end-to-end cho KIS/QA/TRAKE. KIS: `I(video ∧ frame∈[s,e])`; QA: thêm `answer_matches(answer, gt_answers)` (§2.1.2); TRAKE: cổng video + `(1/N)Σ I(frame_j∈[s_j,e_j])` (§2.1.3). Ghi `docs/eval_e2e_scores.md`. | `.venv\Scripts\python.exe test_eval\Test\score_pipelines.py --types kis,qa,trake` |
| `test_phase3_rerank.py` | R@k KIS/QA **trước/sau** risk-aware rerank (Phase 3), qua `retrieve.py` production | `.venv\Scripts\python.exe test_eval\Test\test_phase3_rerank.py` |
| `test_phase4_trake.py` | TRAKE **trước/sau** LLM cross-check tầng 3 (Phase 4), 2-pass deterministic | `.venv\Scripts\python.exe test_eval\Test\test_phase4_trake.py` |
| `test_phase5_ocr.py` | Answer QA **trước/sau** OCR on-demand (Phase 5, `answer_qa.py` Tier 2) | `.venv\Scripts\python.exe test_eval\Test\test_phase5_ocr.py` |
| `test_phase6_margin_sweep.py` | Quét `TRAKE_CROSSCHECK_MARGIN` ở nhiều giá trị, in bảng để người tự chọn | `.venv\Scripts\python.exe test_eval\Test\test_phase6_margin_sweep.py [--self-test]` |
| `test_smoke_tools.py` | Smoke test tool nền tảng (`fast_retrieve`, `ocr_lookup`, `call_llm`, `rewrite_query`) sau khi setup | `.venv\Scripts\python.exe test_eval\Test\test_smoke_tools.py` |
| `test_smoke_pipelines.py` | Smoke test 3 pipeline + `build_submission` + `validate_submission` (ghi CSV `smoke-*` vào `submissions/`) | `.venv\Scripts\python.exe test_eval\Test\test_smoke_pipelines.py` |

`answer_matches` (trong `score_pipelines.py`): chuẩn hoá (casefold + gộp whitespace + bỏ dấu câu/nháy
2 đầu) rồi khớp nếu answer sinh ra **trùng / chứa / là con** của bất kỳ phần tử `gt_answers`.

## `Eval/` — bake-off backbone embedding (retrieval-only, không LLM)

| File | Dùng để | Lệnh |
|---|---|---|
| `run_eval.py` | So `clip_vitb32` vs `vitl14`/`siglip`/`dfn`/… bằng R@k + `Final`. KIS đúng §2.1.1; QA **chỉ retrieval** (không chấm answer — dùng `score_pipelines.py` cho việc đó); TRAKE proxy §2.1.3 (ứng viên có xếp hạng + cổng video + DP thứ tự, không LLM). Ghi `docs/eval_baseline_comparison.md`. | `.venv\Scripts\python.exe test_eval\Eval\run_eval.py [--models clip_vitb32,siglip]` |
| `multi_index.py` | Index loader + text encoder cho từng model (features `.npy` từ `kaggle_jobs/`). Cố ý **không** import `index.py`/`retrieve.py`. | `.venv\Scripts\python.exe test_eval\Eval\multi_index.py clip_vitb32` (smoke) |
| `lookup_frame.py` | CLI tra `frame_id` từ `(video_id, giây)` khi ghi ground truth | `.venv\Scripts\python.exe test_eval\Eval\lookup_frame.py L21_V001 25.0` |
| `widen_gt_windows.py` | Nới các khoảng `gt_frame_start == gt_frame_end` (1 frame — quá chặt) ra keyframe lân cận từ `map-keyframes`; in bảng before→after để dò tay lại | `.venv\Scripts\python.exe test_eval\Eval\widen_gt_windows.py [--dry-run]` |
| `eval_ground_truth.json` | Bộ ground truth hand-label (KIS/QA/TRAKE). Schema: xem `EVAL_GUIDE.md`. | — |
| `eval_ground_truth_thunghiem_draft.json` | Bản nháp ground truth cho vòng thử nghiệm | — |
| `EVAL_GUIDE.md` | Quy trình + schema ghi ground truth (gồm `gt_answers` cho QA) | — |

## File dữ liệu dùng chung (gốc `test_eval/`)

| File | Là gì |
|---|---|
| `sample_queries.json` | Query mẫu (không phải đề chính thức) — dùng khi test thủ công |
| `sotuyen1_bo_de_thi.csv` | Gói đề BTC sơ tuyển đợt 1 (sinh từ `scripts/generate_sotuyen1_csv.py`) |
| `thunghiem_bo_de_thi.csv` | Gói đề BTC vòng thử nghiệm |
