# So sánh baseline embedding — Phase 6

Bộ eval: 19 query (KIS=18, QA=1, TRAKE=0). Điểm = R@k đúng công thức thi (docs/Thong tin vong So tuyen AIC2026.md §2.1), CHỈ đo chất lượng retrieval — QA không chấm answer text, TRAKE chấm từng event độc lập rồi lấy trung bình (xem PLAN.md Phase 6 và docstring scripts/eval/run_eval.py để biết đầy đủ phạm vi/lý do).


## ALL (n=19)

| model | R@1 | R@5 | R@20 | R@50 | R@100 |
|---|---|---|---|---|---|
| clip_vitb32 | 0.158 | 0.263 | 0.421 | 0.579 | 0.632 |
| vitl14 | 0.158 | 0.263 | 0.368 | 0.579 | 0.737 |
| siglip | 0.421 | 0.579 | 0.737 | 0.789 | 0.895 |
| dfn | 0.263 | 0.632 | 0.684 | 0.789 | 1.000 |

## KIS (n=18)

| model | R@1 | R@5 | R@20 | R@50 | R@100 |
|---|---|---|---|---|---|
| clip_vitb32 | 0.167 | 0.278 | 0.444 | 0.611 | 0.667 |
| vitl14 | 0.167 | 0.278 | 0.389 | 0.611 | 0.722 |
| siglip | 0.444 | 0.611 | 0.778 | 0.833 | 0.944 |
| dfn | 0.278 | 0.667 | 0.722 | 0.833 | 1.000 |

## QA (n=1)

| model | R@1 | R@5 | R@20 | R@50 | R@100 |
|---|---|---|---|---|---|
| clip_vitb32 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| vitl14 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
| siglip | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| dfn | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 |
