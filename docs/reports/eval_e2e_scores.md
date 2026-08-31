# Final Score BTC end-to-end — tests/e2e/score_pipelines.py

Chạy trọn pipeline production (retrieve + rerank + DP + LLM answer/crosscheck) rồi chấm đúng §2.1–2.2. `Final` = (1/5)·Σ R@k. **Cảnh báo:** QA đi qua vision LLM nên điểm dao động giữa các lần chạy (chạy 2–3 lần lấy khoảng); `run_trake` mặc định `top_k_video=20` nên `results` ≤ 20 hàng → R@50 = R@100 = R@20 cho TRAKE.

| nhóm | n | R@1 | R@5 | R@20 | R@50 | R@100 | **Final** |
|---|---|---|---|---|---|---|---|
| ALL | 38 | 0.237 | 0.412 | 0.465 | 0.544 | 0.623 | **0.456** |
| KIS | 23 | 0.348 | 0.565 | 0.652 | 0.783 | 0.870 | **0.643** |
| QA | 5 | 0.000 | 0.000 | 0.000 | 0.000 | 0.200 | **0.040** |
| TRAKE | 10 | 0.100 | 0.267 | 0.267 | 0.267 | 0.267 | **0.233** |
