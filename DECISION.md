# AIC2026 — Decision Log

> Vì sao các quyết định kiến trúc/quy trình được chọn — xem [ARCHITECTURE.md](ARCHITECTURE.md) cho
> "cái gì", [PLAN.md](PLAN.md) cho tiến độ. Bài học lỗi cũ → [EXPERIMENT.md](EXPERIMENT.md).

> ⚠️ **File này được dựng lại ngày 2026-08-26.** Bản gốc chưa từng lên GitHub — bị `.gitignore`
> chặn từ đầu (đã gỡ, xem lịch sử `.gitignore`) và máy chứa bản gốc đã bị reset. Nội dung dưới đây
> là tổng hợp lại từ các trích dẫn/tham chiếu tới `DECISION.md` còn sót trong
> [docs/_archive/PLAN_Lan2.md](docs/_archive/PLAN_Lan2.md), `ARCHITECTURE.md`, và
> `docs/superpowers/plans/`/`.superpowers/sdd/` (ghi chú làm việc cục bộ, chưa từng commit) — **không
> phải nguyên văn bản gốc**, chỉ là suy luận lại nội dung từ ngữ cảnh xung quanh. Bổ sung/sửa lại nếu
> nhớ ra chi tiết khác. Mục nào chưa có nguồn rõ để dựng lại được để trống, đánh dấu TODO.

## Round 2 (22/8 → 04/09/2026)

### Model production — đổi sang siglip (KIS/TRAKE) + siglip2 (Q&A) (2026-08-28)

Benchmark 33 query (18 KIS, 5 QA, 10 TRAKE) trải rộng 27 video, công thức BTC
Final = (1/5)·Σ R@{1,5,20,50,100}:

| Model       | ALL   | KIS       | QA-retrieval  | TRAKE     |
|-------------|-------|-----------|---------------|-----------|
| siglip2     | 0.551 | 0.689     | **0.440** 🥇  | 0.358     |
| siglip      | 0.549 | **0.744** 🥇 | 0.120      | **0.412** 🥇 |
| dfn         | 0.536 | 0.722     | 0.320         | 0.310     |
| clip_vitb32 | 0.290 | 0.433     | 0.000         | 0.177     |

Quyết định:
- **KIS/TRAKE → siglip**: tối ưu visual spotting (R@100 KIS=1.000, TRAKE +357% vs baseline).
- **Q&A → siglip2**: tối ưu VLM reasoning/OCR context (gấp 3.7× siglip v1 ở QA-retrieval).
- **clip-features-32 đã xoá vĩnh viễn** — không có đường rollback về clip_vitb32.
- Quyết định này thay thế mục "Model production — chưa đổi khỏi `clip_vitb32`" bên dưới.

_Nguồn: benchmark 33 query từ `test_eval/Eval/run_eval.py`, kết quả ghi ở đầu phiên 2026-08-28._

### OCR on-demand (Phase 5) — chọn PaddleOCR, không phải EasyOCR

Chốt ngày 2026-08-24 (commit `6838fd1`). Ban đầu có 1 lần lỡ commit nhầm hướng EasyOCR lẫn vào commit
Phase 4 rồi phải revert — **đây chỉ là revert nhầm lẫn, không phải đổi ý** giữa 2 lib; PaddleOCR vẫn là
lựa chọn đã chốt xuyên suốt.

**Tradeoff đã biết và chấp nhận từ đầu** (không phải bug phát sinh sau): `PaddleOCR(lang="vi")` thực
chất nạp bảng ký tự "latin", không phải bảng tiếng Việt có dấu đầy đủ — OCR đọc tốt cho số/chữ Latin
(biển số, giá tiền, năm) nhưng không đáng tin cho chữ tiếng Việt có dấu. Vì vậy quyết định: **OCR chỉ
là gợi ý phụ (hint) cho LLM Vision, không thay thế/không phải nguồn trả lời chính thức** — cơ chế
cross-check chống ảo giác ở tầng Vision giữ nguyên, không có đường tắt nào bỏ qua nó khi có OCR hint.

_Nguồn: `.superpowers/sdd/2026-08-24-phase5-ocr-on-demand/{progress,task-1-brief,task-1-report}.md`
(ghi chú làm việc cục bộ), `docs/_archive/PLAN_Lan2.md` Phase 5._

### Query rewrite phủ định (Phase 2) — chỉ thêm 1 rule, không mở rộng chuẩn hoá ngữ pháp

Khi thêm rule xử lý phủ định ("không có X" → mô tả dương tính cho CLIP), quyết định **không** mở rộng
thêm bước chuẩn hoá ngữ pháp hay tách keyword riêng — cho rằng phần đó "đã có sẵn trong prompt hiện
tại", giữ thay đổi tối thiểu.

_Nguồn: `docs/_archive/PLAN_Lan2.md` Phase 2 ("Không mở rộng thêm chuẩn hoá ngữ pháp hay bước keyword
— phần đó coi như đã có sẵn trong prompt hiện tại, xem DECISION.md")._

### Risk-aware ranking (Phase 3) — không đổi thuật toán bet/spread gốc khi mở rộng pool

Khi phát hiện `RETRIEVAL_POOL_SIZE` cần nới từ 100→500 (xem [EXPERIMENT.md](EXPERIMENT.md) mục Phase
3), quyết định chỉ đổi input pool + nối lại 1 điểm wiring còn thiếu (`app.py:kis_search()`), **không**
viết lại thuật toán bet/spread đang có — rủi ro thấp hơn, đúng tinh thần "ưu tiên workflow đơn giản
nhất" đã thống nhất trong `CLAUDE.md`.

_Nguồn: `docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md:260-263`._

### Model production — chưa đổi khỏi `clip_vitb32`

Kế thừa từ round 1: dù `siglip`/`dfn` cho R@k nhỉnh hơn `clip_vitb32` trên bộ eval, **chưa đủ bằng
chứng để đổi model production** (mẫu nhỏ, thiếu câu TRAKE lúc đánh giá) — giữ `clip_vitb32` làm mặc
định, có đường rollback nếu cần. Round 2 không có phase nào lật lại quyết định này.

_Nguồn: `docs/_archive/PLAN_Lan1.md` Phase 6, nhắc lại ở `docs/_archive/PLAN_Lan2.md` "Tóm tắt round
trước"._

### Phase 7 — 2 harness chấm điểm tách rời, không gộp làm một

`run_eval.py` giữ **retrieval-only, không LLM, deterministic** (bake-off backbone: cần nhanh, chạy
được không API key, lặp lại y hệt để so 5 model). Chấm answer QA (§2.1.2) và LLM crosscheck TRAKE
**bắt buộc** phải gọi LLM → tách sang `test_eval/Test/score_pipelines.py` (chậm, cần API key, QA có
biến thiên giữa các lần chạy). Không nhét answer-scoring vào `run_eval.py` vì sẽ phá cả 3 tính chất
trên mà lợi ích (answer phụ thuộc chủ yếu vào LLM, không phải backbone) thì nhỏ.

### Phase 7 — gom `queries/` → `test_eval/` với 2 nhánh `Test/` (đường production) vs `Eval/` (không LLM)

Ranh giới "có đi qua `scripts/agent/*` hay không" đã có sẵn trong repo (`scripts/eval/` vs
`scripts/test_phase*.py`) nhưng nằm rải rác. Gom về 1 chỗ, đặt tên nhánh theo đúng ranh giới đó để
người đọc biết ngay harness nào cần API key / có biến thiên. Tên thư mục dùng `test_eval` (snake_case)
thay vì `Test & Eval` — dấu cách và `&` làm vỡ lệnh shell/PowerShell ở mọi chỗ tham chiếu.
`test_day1/2_*.py` gộp thành `test_smoke_{tools,pipelines}.py` (bản chất là smoke test, không phải
"ngày").

### TODO — chưa dựng lại được, cần bạn xác nhận

- **Vì sao đổi từ multi-provider LLM fallback (Gemini→Groq→NVIDIA NIM) sang 1 provider OpenRouter
  duy nhất** — thấy rõ trong code (`scripts/agent/config.py`, xem lịch sử `PLAN.md` mục Blockers) là
  đã đổi thật, nhưng không tìm được lý do bằng chữ ở đâu trong repo. Có thể là đơn giản hoá code,
  chi phí, hoặc lý do khác — điền lại khi nhớ ra.
- Lý do chọn ngưỡng cụ thể `MARGIN_THRESHOLD=0.012` / `TRAKE_CROSSCHECK_MARGIN=0.012` (ngoài việc dựa
  trên phân bố score thật ~0.28-0.31 đã ghi trong `PLAN_Lan2.md`) — nếu có cân nhắc sâu hơn, ghi lại.
- Các quyết định kiến trúc round-1 (`ARCHITECTURE.md` dòng 97 nói "kể cả các quyết định của
  round-1" từng nằm ở đây) — chưa dựng lại được, có thể tham khảo thêm
  [docs/_archive/ARCHITECTURE_Lan1.md](docs/_archive/ARCHITECTURE_Lan1.md) nếu cần.
