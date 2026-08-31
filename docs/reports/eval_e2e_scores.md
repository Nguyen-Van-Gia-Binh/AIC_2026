# Final Score BTC end-to-end — test_eval/Test/score_pipelines.py

Chạy trọn pipeline production (retrieve + rerank + DP + LLM answer/crosscheck) rồi chấm đúng §2.1–2.2. `Final` = (1/5)·Σ R@k. **Cảnh báo:** QA đi qua vision LLM nên điểm dao động giữa các lần chạy (chạy 2–3 lần lấy khoảng); `run_trake` mặc định `top_k_video=20` nên `results` ≤ 20 hàng → R@50 = R@100 = R@20 cho TRAKE.

## Lần chạy 2026-08-31 — CHỈ nhóm KIS (`--types kis`)

Lần chạy này **không phủ QA và TRAKE**, nên dòng `ALL` ở đây trùng `KIS` và không so sánh được
với dòng `ALL` của lần chạy trước (n=33). Chạy sau `_preserve_recall_tail` (xem `rerank.py`).

| nhóm | n | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|---|
| KIS | 18 | 0.389 | 0.611 | 0.722 | 0.889 | 1.000 | **0.722** |

## Lần chạy trước — đủ 3 nhóm (n=33), trước `_preserve_recall_tail`

| nhóm | n | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|---|
| ALL | 33 | 0.298 | 0.419 | 0.538 | 0.568 | 0.598 | **0.484** |
| KIS | 18 | 0.389 | 0.611 | 0.722 | 0.778 | 0.833 | **0.667** |
| QA | 5 | 0.200 | 0.200 | 0.200 | 0.200 | 0.200 | **0.200** |
| TRAKE | 10 | 0.183 | 0.183 | 0.375 | 0.375 | 0.375 | **0.298** |
