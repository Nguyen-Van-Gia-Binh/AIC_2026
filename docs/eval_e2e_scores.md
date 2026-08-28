# Final Score BTC end-to-end — test_eval/Test/score_pipelines.py

Chạy trọn pipeline production (retrieve + rerank + DP + LLM answer/crosscheck) rồi chấm đúng §2.1–2.2. `Final` = (1/5)·Σ R@k. **Cảnh báo:** QA đi qua vision LLM nên điểm dao động giữa các lần chạy (chạy 2–3 lần lấy khoảng); `run_trake` mặc định `top_k_video=20` nên `results` ≤ 20 hàng → R@50 = R@100 = R@20 cho TRAKE.

| nhóm | n | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|---|
| ALL | 33 | 0.298 | 0.439 | 0.538 | 0.568 | 0.598 | **0.488** |
| KIS | 18 | 0.389 | 0.611 | 0.722 | 0.778 | 0.833 | **0.667** |
| QA | 5 | 0.200 | 0.200 | 0.200 | 0.200 | 0.200 | **0.200** |
| TRAKE | 10 | 0.183 | 0.250 | 0.375 | 0.375 | 0.375 | **0.312** |
