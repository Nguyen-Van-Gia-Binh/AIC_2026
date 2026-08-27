# AIC2026 — Experiment / Lessons Log

> Lỗi/bài học cũ — đọc trước khi lặp lại 1 hướng debug đã từng đi qua. Vì sao các quyết định khác
> được chọn → [DECISION.md](DECISION.md). Tiến độ hiện tại → [PLAN.md](PLAN.md).

> ⚠️ **File này được dựng lại ngày 2026-08-26.** Bản gốc chưa từng lên GitHub — bị `.gitignore`
> chặn từ đầu (đã gỡ) và máy chứa bản gốc đã bị reset. Nội dung dưới đây tổng hợp lại từ các sự kiện
> đã ghi log chi tiết trong [docs/_archive/PLAN_Lan2.md](docs/_archive/PLAN_Lan2.md) và
> `docs/superpowers/plans/` — **không phải nguyên văn bản gốc**. Bổ sung thêm khi nhớ ra chi tiết
> khác hoặc gặp bài học mới.

## Đợt 1 (nộp trước 22/8/2026): đừng đổ lỗi cho nghi phạm hiển nhiên

**Triệu chứng:** nộp đợt 1 chỉ được 5.6/10 — KIS tạm ổn (phải sắp lại tay), Q&A/TRAKE sai gần hết.

**Nghi phạm ban đầu (sai):** embedding CLIP `clip-ViT-B-32` yếu, cần đổi model retrieval ngay.

**Nguyên nhân thật:** **cạn quota Gemini free-tier giữa lúc thi** — không phải embedding. Bài học:
kiểm tra quota/rate-limit thật (https://ai.dev/rate-limit) trước khi kết luận lỗi nằm ở model/thuật
toán, đặc biệt khi hệ thống phụ thuộc LLM gọi nhiều lần liên tục trong thời gian ngắn (đúng kịch bản
thi). Vì lý do này, mọi runbook dry-run ở round 2 đều có bước "kiểm tra quota trước khi chạy".

_Nguồn: `docs/_archive/PLAN_Lan2.md` mục 0 + "Tóm tắt round trước"; tựa đề gốc suy luận lại từ chỗ
`PLAN.md` trích "Đọc qua EXPERIMENT.md mục 'đừng đổ lỗi cho nghi phạm hiển nhiên' (vụ quota Gemini
đợt 1) trước khi dry-run"._

## Round 2 — Phase 3: rerank "đúng nhưng vô hiệu" (2 nguyên nhân im lặng)

**Triệu chứng:** implement xong `apply_risk_aware_ranking()`, self-test PASS, nhưng benchmark thật
trên `eval_ground_truth.json` cho R@k **không đổi** so với trước khi có rerank — như thể tính năng
chưa từng chạy.

**2 nguyên nhân thật (tìm bằng cách chẩn đoán trực tiếp, không đoán):**
1. `app.py:kis_search()` — đường thật dùng để build submission qua `kis_add_to_queue`/`export_zip` —
   gọi thẳng `fast_retrieve()`, **chưa từng** đi qua `apply_risk_aware_ranking()`. Rerank tồn tại
   trong code nhưng không được wire vào đường đi thật của UI.
2. `retrieve.py` có trần cứng `top_k=min(top_k, 100)` — rerank không bao giờ thấy được ứng viên đúng
   nếu nó nằm ngoài top-100. Đo thật: ground truth chỉ nằm trong top-100 ở 12/23 câu (52%), nhưng nằm
   trong top-500 ở 20/23 câu (87%) — chi phí tính gần như miễn phí vì ma trận score đã nhân đủ.

**Bài học:** 1 tính năng self-test PASS không đồng nghĩa đã có tác dụng trên đường đi thật — cần đo
trên chính pipeline/UI người dùng thật sự chạm vào, không chỉ unit test cô lập. Fix: thêm
`RETRIEVAL_POOL_SIZE=500` làm nguồn chân lý duy nhất, nới trần `retrieve.py` lên 1000, nối dây
`app.py:kis_search()`.

_Nguồn: `docs/_archive/PLAN_Lan2.md` Phase 3, đoạn "Đã làm (bản hiệu quả hơn...)"._

## Round 2 — Phase 4: benchmark TRAKE không đáng tin vì non-determinism ẩn

**Triệu chứng:** chạy `test_phase4_trake.py` nhiều lần cho cùng 1 câu, ra top-1 video **khác nhau**
giữa các lần chạy — số liệu "trước/sau cross-check" không phải so sánh hợp lệ (vì retrieval tự nó
đã đổi kết quả, không phải do cross-check).

**Nguyên nhân:** `run_trake()` luôn gọi `rewrite_query()` (LLM thật, `temperature=0.2`, không cache)
kể cả khi input đã sẵn là `text_en` tiếng Anh — không cần rewrite thêm.

**Fix — chỉ trong benchmark script, không đụng code production:** monkeypatch `rewrite_query` thành
identity function bên trong `test_phase4_trake.py`, chạy 2 pass trong cùng 1 process (tắt cross-check
→ bật cross-check) để đảm bảo cả 2 pass dùng chung 1 kết quả retrieval, chênh lệch đo được quy thẳng
về đúng biến số đang test (cross-check), không lẫn nhiễu từ rewrite ngẫu nhiên.

**Bài học:** khi benchmark trước/sau 1 thay đổi, phải kiểm tra toàn bộ pipeline có nguồn ngẫu nhiên
nào khác (LLM temperature > 0, không cache) đang chạy giữa 2 lần đo — nếu có, phải khử nhiễu nó trước,
nếu không con số "cải thiện/không cải thiện" đo được là vô nghĩa.

_Nguồn: `docs/_archive/PLAN_Lan2.md` Phase 4, đoạn "Task 2 fix round 1"._

## Round 2 — Phase 5: benchmark OCR ban đầu không kích hoạt được OCR ở 2/3 câu

**Triệu chứng:** chạy benchmark trước/sau OCR hint, thấy answer/confidence lệch giữa 2 pass — tưởng
là do OCR, nhưng thực ra 2/3 câu hỏi tự tạo không hề kích hoạt nhánh gọi `read_text_from_hits()`.

**Nguyên nhân:** `_TEXT_READING_HINTS` (regex quyết định `skip_objects_tier`) chỉ có trigger tiếng Anh
kiểu "number"/"how many"/"what number" — câu hỏi dạng "what does it say"/"what phrase is written"
không khớp regex này, nên OCR không được gọi ở cả 2 pass cho 2/3 câu.

**Fix:** verify từng câu bằng `_TEXT_READING_HINTS.search(question)` trực tiếp trong Python trước khi
tin benchmark, sửa lại câu hỏi để thật sự khớp trigger, chạy lại.

**Bài học:** khi benchmark 1 tính năng có điều kiện kích hoạt (gate/regex/threshold), phải xác nhận
gate đó thật sự bật ở ca test — không chỉ nhìn output khác nhau rồi kết luận do tính năng.

_Nguồn: `docs/_archive/PLAN_Lan2.md` Phase 5, đoạn "Fix round 1"._

## Round 2 — Phase 5: xung đột thứ tự nạp DLL Windows (PaddleOCR + torch)

**Triệu chứng:** `from paddleocr import PaddleOCR` bên trong `_get_engine()` gây lỗi liên quan tới
DLL trên Windows nếu không cẩn thận thứ tự import.

**Nguyên nhân:** OpenCV (dependency của PaddleOCR) nạp `shm.dll` runtime trước, che khuất DLL mà
`torch` cần nạp sau đó.

**Fix:** thêm `import torch` phòng thủ **trước** dòng `from paddleocr import PaddleOCR`, đảm bảo
torch nạp DLL của nó trước khi opencv kịp che khuất. Đồng thời cần pin đúng version
(`paddleocr==2.10.0`, `opencv-python`/`opencv-contrib-python==5.0.0.93`) — version khác từng gây lỗi.

_Nguồn: `docs/_archive/PLAN_Lan2.md` Phase 5, đoạn "Task 1 (OCR engine)"._

## TODO — bổ sung dần

- Bài học/lỗi cụ thể trong lúc dựng 4 job Kaggle (ViT-L/14, SigLIP, Jina, DFN) ở round 1 — đã có tóm
  tắt lỗi Jina 100% NaN trong `docs/_archive/PLAN_Lan1.md` Phase 6, nhưng chưa chắc đó là toàn bộ nội
  dung từng có ở đây.
- Bất kỳ lỗi debug nào gặp phải khi chạy Dry-run contest mode (việc còn treo — xem `PLAN.md`) nên ghi
  vào đây ngay khi phát sinh, đừng để tới lúc mất máy mới tiếc.
