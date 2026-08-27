# Final Score BTC end-to-end — test_eval/Test/score_pipelines.py

Chạy trọn pipeline production (retrieve + rerank + DP + LLM answer/crosscheck) rồi chấm đúng §2.1–2.2. `Final` = (1/5)·Σ R@k. **Cảnh báo:** QA đi qua vision LLM nên điểm dao động giữa các lần chạy (chạy 2–3 lần lấy khoảng); `run_trake` mặc định `top_k_video=20` nên `results` ≤ 20 hàng → R@50 = R@100 = R@20 cho TRAKE.

| nhóm | n | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|---|
| ALL | 33 | 0.106 | 0.182 | 0.273 | 0.364 | 0.394 | **0.264** |
| KIS | 18 | 0.167 | 0.278 | 0.444 | 0.611 | 0.667 | **0.433** |
| QA | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | **0.000** |
| TRAKE | 10 | 0.050 | 0.100 | 0.100 | 0.100 | 0.100 | **0.090** |
