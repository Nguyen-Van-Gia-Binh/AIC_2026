# So sánh baseline embedding — Phase 6/7

Bộ eval: 33 query (KIS=18, QA=5, TRAKE=10). `Final` = (1/5)·Σ R@k (con số BTC xếp hạng, docs/Thong tin vong So tuyen AIC2026.md §2.2). **Bake-off retrieval-only, KHÔNG LLM:**
- **KIS** — đúng công thức §2.1.1.
- **QA** — CHỈ retrieval, KHÔNG chấm answer (a_i = GT_a của §2.1.2); cột QA là trần retrieval, không phải R-Score QA. Final Score QA thật → test_eval/Test/score_pipelines.py.
- **TRAKE** — proxy §2.1.3: ứng viên (video + N frame, chuỗi tăng dần) có xếp hạng + cổng video + max-trên-ứng-viên; KHÔNG có LLM crosscheck.

(Xem PLAN.md Phase 6/7 + docstring test_eval/Eval/run_eval.py để biết đầy đủ phạm vi/lý do.)


**Tuỳ chọn thuật toán đang bật:** `hybrid, expand, nms, strict_dp, coverage_pool`


## ALL (n=33)

| model | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|
| siglip | 0.295 | 0.386 | 0.485 | 0.545 | 0.606 | **0.464** |

## KIS (n=18)

| model | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|
| siglip | 0.389 | 0.500 | 0.611 | 0.722 | 0.778 | **0.600** |

## QA (n=5)

| model | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|
| siglip | 0.000 | 0.000 | 0.000 | 0.000 | 0.200 | **0.040** |

## TRAKE (n=10)

| model | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|
| siglip | 0.275 | 0.375 | 0.500 | 0.500 | 0.500 | **0.430** |
