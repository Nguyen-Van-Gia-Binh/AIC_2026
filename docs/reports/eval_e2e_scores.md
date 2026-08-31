# Final Score BTC end-to-end — tests/e2e/score_pipelines.py

Chạy trọn pipeline production (retrieve + rerank + DP + LLM answer/crosscheck) rồi chấm đúng §2.1–2.2. `Final` = (1/5)·Σ R@k. **Cảnh báo:** QA đi qua vision LLM nên điểm dao động giữa các lần chạy (chạy 2–3 lần lấy khoảng); `run_trake` mặc định `top_k_video=20` nên `results` ≤ 20 hàng → R@50 = R@100 = R@20 cho TRAKE.

| nhóm | n | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|---|
| ALL | 38 | 0.283 | 0.467 | 0.526 | 0.605 | 0.658 | **0.508** |
| KIS | 23 | 0.348 | 0.609 | 0.652 | 0.783 | 0.870 | **0.652** |
| QA | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** |
| TRAKE | 10 | 0.275 | 0.375 | 0.500 | 0.500 | 0.500 | **0.430** |
