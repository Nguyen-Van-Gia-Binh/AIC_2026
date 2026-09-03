# So sánh baseline embedding — Phase 6

Bộ eval: 33 query (KIS=18, QA=5, TRAKE=10). Điểm = R@k đúng công thức thi (docs/Thong tin vong So tuyen AIC2026.md §2.1), CHỈ đo chất lượng retrieval — QA không chấm answer text, TRAKE chấm từng event độc lập rồi lấy trung bình (xem PLAN.md Phase 6 và docstring scripts/eval/run_eval.py để biết đầy đủ phạm vi/lý do).


## ALL (n=33)

| model | R@1 | R@5 | R@20 | R@50 | R@100 |
|---|---|---|---|---|---|
| siglip | 0.265 | 0.386 | 0.578 | 0.624 | 0.705 |
| siglip2 | 0.189 | 0.354 | 0.513 | 0.619 | 0.674 |

## KIS (n=18)

| model | R@1 | R@5 | R@20 | R@50 | R@100 |
|---|---|---|---|---|---|
| siglip | 0.444 | 0.611 | 0.778 | 0.833 | 0.944 |
| siglip2 | 0.278 | 0.444 | 0.722 | 0.889 | 0.944 |

## QA (n=5)

| model | R@1 | R@5 | R@20 | R@50 | R@100 |
|---|---|---|---|---|---|
| siglip | 0.000 | 0.000 | 0.200 | 0.200 | 0.200 |
| siglip2 | 0.000 | 0.200 | 0.200 | 0.200 | 0.200 |

## TRAKE (n=10)

| model | R@1 | R@5 | R@20 | R@50 | R@100 |
|---|---|---|---|---|---|
| siglip | 0.075 | 0.175 | 0.408 | 0.458 | 0.525 |
| siglip2 | 0.125 | 0.267 | 0.292 | 0.342 | 0.425 |
