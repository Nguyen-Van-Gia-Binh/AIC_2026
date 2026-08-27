# So sánh baseline embedding — Phase 6/7

Bộ eval: 33 query (KIS=18, QA=5, TRAKE=10). `Final` = (1/5)·Σ R@k (con số BTC xếp hạng, docs/Thong tin vong So tuyen AIC2026.md §2.2). **Bake-off retrieval-only, KHÔNG LLM:**
- **KIS** — đúng công thức §2.1.1.
- **QA** — CHỈ retrieval, KHÔNG chấm answer (a_i = GT_a của §2.1.2); cột QA là trần retrieval, không phải R-Score QA. Final Score QA thật → test_eval/Test/score_pipelines.py.
- **TRAKE** — proxy §2.1.3: ứng viên (video + N frame, chuỗi tăng dần) có xếp hạng + cổng video + max-trên-ứng-viên; KHÔNG có LLM crosscheck.

(Xem PLAN.md Phase 6/7 + docstring test_eval/Eval/run_eval.py để biết đầy đủ phạm vi/lý do.)


## ALL (n=33)

| model | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|
| clip_vitb32 | 0.136 | 0.207 | 0.298 | 0.389 | 0.419 | **0.290** |
| siglip | 0.295 | 0.457 | 0.624 | 0.654 | 0.715 | **0.549** |
| siglip2 | 0.227 | 0.475 | 0.604 | 0.694 | 0.755 | **0.551** |
| dfn | 0.265 | 0.477 | 0.586 | 0.616 | 0.737 | **0.536** |
| jina | 0.258 | 0.389 | 0.419 | 0.540 | 0.571 | **0.435** |

## KIS (n=18)

| model | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|
| clip_vitb32 | 0.167 | 0.278 | 0.444 | 0.611 | 0.667 | **0.433** |
| siglip | 0.389 | 0.611 | 0.833 | 0.889 | 1.000 | **0.744** |
| siglip2 | 0.222 | 0.611 | 0.722 | 0.889 | 1.000 | **0.689** |
| dfn | 0.278 | 0.667 | 0.833 | 0.833 | 1.000 | **0.722** |
| jina | 0.278 | 0.500 | 0.556 | 0.778 | 0.833 | **0.589** |

## QA (n=5)

| model | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|
| clip_vitb32 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** |
| siglip | 0.000 | 0.000 | 0.200 | 0.200 | 0.200 | **0.120** |
| siglip2 | 0.200 | 0.200 | 0.600 | 0.600 | 0.600 | **0.440** |
| dfn | 0.200 | 0.200 | 0.200 | 0.400 | 0.600 | **0.320** |
| jina | 0.200 | 0.200 | 0.200 | 0.200 | 0.200 | **0.200** |

## TRAKE (n=10)

| model | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|
| clip_vitb32 | 0.150 | 0.183 | 0.183 | 0.183 | 0.183 | **0.177** |
| siglip | 0.275 | 0.408 | 0.458 | 0.458 | 0.458 | **0.412** |
| siglip2 | 0.250 | 0.367 | 0.392 | 0.392 | 0.392 | **0.358** |
| dfn | 0.275 | 0.275 | 0.333 | 0.333 | 0.333 | **0.310** |
| jina | 0.250 | 0.283 | 0.283 | 0.283 | 0.283 | **0.277** |
