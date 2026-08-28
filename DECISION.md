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

## 2026-08-28 — Mặc định của Hybrid/Multi-Aspect sau BẢN ĐẶC TẢ §2–§6

**Quyết định:** triển khai đủ §2–§6, nhưng 2 mặc định KHÔNG theo nguyên văn đặc tả, vì số đo thật
(18 câu KIS, đường production, `test_eval`) nói ngược lại:

1. **`SPARSE_TOP_K = 50`** (không đưa cả 500 ứng viên BM25 vào RRF). BM25 ở đây chạy trên tập từ khóa
   rất thô (tên object Faster R-CNN + caption, ~5.5K term, doc ~10 token) nên chỉ đáng tin ở đỉnh:
   `sparse_top_k` 0/20/50/100 → Final 0.656; 200/500 → 0.611. Với 50, hybrid trung tính trên bộ eval
   hiện tại mà vẫn giữ được khả năng "cứu" query nêu tên vật thể cụ thể.
2. **Multi-Aspect Prompt Expansion mặc định TẮT** (`run_kis(use_expansion=False)`). Bật lên làm
   Final tụt 0.667 → 0.644 (và 0.667 → 0.611 khi đi cùng hybrid). SigLIP được huấn luyện trên caption
   ảnh thật nên câu query gốc thường đã là caption tốt; 2 biến thể template chỉ kéo vector về trung
   bình. Cơ chế giữ nguyên, bật bằng cờ (`use_expansion=True` / `run_eval.py --expand`) để đo lại khi
   có bộ eval lớn hơn.

**Quyết định thứ 3 (thuộc về thiết kế, không phải tắt/bật):** tách `score_key` (xếp hạng) khỏi
`margin_key` (quyết định đặt cược/trải rủi ro) trong `rerank.py`. Xếp hạng theo RRF nhưng margin vẫn
đo trên cosine — vì `MARGIN_THRESHOLD=0.012` được hiệu chỉnh bằng benchmark thật trên thang cosine.

**Đánh đổi:** đặc tả yêu cầu hybrid + expansion là nền tảng cho cả 3 pipeline; ở đây expansion không
chạy mặc định nên phần "3 góc nhìn" của §3.1 chỉ tồn tại dưới dạng tuỳ chọn cho tới khi có số ủng hộ.

---

## 2026-08-28 — Kiến trúc v2 (Phase 10): vì sao lật 2 quyết định đã chốt

Chi tiết kỹ thuật → [ARCHITECTURE.md §6](ARCHITECTURE.md). Việc cần làm → [PLAN.md](PLAN.md) Phase 10.

### Lật "KIS = workflow tuyến tính, không LLM"

Quyết định gốc dựa trên giả định kiểm soát cost/latency. Hai dữ kiện tra được từ luật thi và dữ liệu
thật cho thấy giả định đó không đúng với vòng sơ tuyển:

- Vòng sơ tuyển **chấm offline theo file nộp, không giới hạn thời gian chạy**.
- Mỗi gói đề chỉ có **~42–45 truy vấn** (`THUNGHIEM-bo-de-thi/bo_de_thi.csv` 42 dòng,
  `test_eval/sotuyen1_bo_de_thi.csv` 45 dòng).

⇒ VLM rerank top-50 tốn ~2.200 lượt chấm ảnh cho **cả gói đề**, không phải cho mỗi truy vấn. Đây là
chi phí nhỏ so với đòn bẩy R@1. Phần thực sự đáng giữ của quyết định gốc — **không có vòng lặp
reflection trong KIS** — được giữ nguyên: `vlm_rerank.py` là đúng một bước một chiều, có công tắc tắt.

Chọn **Gemini 2.5 Flash Vision qua `config.py:call_llm()`** thay vì Qwen2.5-VL local vì: (a) không
chiếm VRAM — máy chỉ có 8 GB và SigLIP/SigLIP2/BGE-M3/VietOCR đã tranh nhau chỗ; (b) ~10–15 phút cho
cả gói đề thay vì 1–2 giờ; (c) đi qua `call_llm()` nên không phá quy tắc "chỉ `config.py` gọi LLM".

### Làm rõ ranh giới của "không precompute cho toàn bộ 177K keyframe"

Lệnh cấm gốc nhắm vào chi phí **SINH** nội dung bằng VLM/OCR cho 177K ảnh — vẫn giữ nguyên, vẫn cấm
(Qwen2.5-VL-3B trên 177K ảnh ≈ 74 giờ ngay cả khi có GPU). Nhưng **ENCODE văn bản đã có sẵn** là bài
toán khác hẳn: caption Vintern-1B đã nằm trên đĩa, encode bằng BGE-M3 tốn ~10–15 phút GPU.

Ranh giới mới, phát biểu tường minh để lần sau không phải tranh luận lại: **cấm sinh nội dung hàng
loạt, cho phép encode nội dung đã có.**

### Vì sao ưu tiên `refine_frame.py` lên trên tất cả

Đây không phải một cải tiến gia tăng mà là gỡ một **trần điểm**. Luật BTC quy định cửa sổ đáp án mỗi
mốc TRAKE "thường dưới 10 frame"; đo trên 400 video / 90.519 gap thì khoảng cách keyframe có trung vị
80 frame, trung bình 85,3. ⇒ P(một keyframe rơi vào cửa sổ 10 frame) ≈ 12 %.

Nghĩa là toàn bộ §5 của bản đặc tả (Coverage Pooling + DP đơn điệu + Gated VLM Verification) đang tối
ưu **hệ số nhân của một trần 0,12**. Không có hạng mục nào khác trong Phase 10 có biên độ tương đương.

### Vì sao `refine_frame` lấy tâm đoạn chứ không lấy argmax

Độ dài thật của khoảng đáp án `[s,e]` cho KIS là **ẩn số chưa xác định** — luật BTC không định nghĩa
cách dựng nó, ví dụ minh hoạ là `[500, 510]`. Lấy argmax của điểm SigLIP trên ~120 frame gần như y hệt
nhau là lấy một đỉnh nhiễu, thường nằm ở rìa đoạn. Lấy **tâm của đoạn liên tục vượt ngưỡng sau khi
làm mượt** thì đúng ở cả hai giả thuyết: nếu `[s,e]` ngắn, BTC gần như chắc chắn đặt nó quanh tâm ngữ
nghĩa của khoảnh khắc; nếu `[s,e]` dài cỡ shot, tâm đoạn cũng nằm gọn bên trong. Chọn phương án an
toàn với ẩn số thay vì cược một chiều vào một giả thuyết.

### Vì sao ASR vào RRF ở mức video chứ không mức frame

Lời nói trong video mô tả cả những thứ **không nằm trong khung hình đang chiếu**. Gán điểm ASR cho
từng frame sẽ tạo tín hiệu sai ở mức frame. Phân công đúng: **ASR trả lời "video nào", SigLIP trả lời
"frame nào"**. Cài đặt: xếp hạng video theo độ khớp ASR rồi cho mọi frame thuộc video V thừa hưởng
hạng đó — vẫn là RRF thuần trên thứ hạng, không thêm thang đo mới cần chuẩn hoá.

### Vì sao giữ heuristic đặt cược/trải rủi ro thay vì tối ưu danh mục 100 dòng

Đã cân nhắc thay `MARGIN_THRESHOLD`/`SPREAD_MAX_PER_VIDEO` bằng cực đại hoá hàm submodular
`E[Final] = (1/5)·Σ_k P(có ≥1 dòng đúng trong top-k)` — cách đó tự sinh ra cả hành vi đặt cược, trải
rủi ro lẫn NMS mà không cần ngưỡng ma thuật nào. **Chưa làm**, vì nó đòi hỏi hiệu chỉnh điểm số thành
xác suất (calibration), mà calibration trên 33 câu ground truth thì vô nghĩa. Hạng mục này mở lại được
sau khi #10.2 mở rộng bộ eval. Trước mắt chỉ dùng **bảng giá trị theo hạng** (hạng 1 → 1,00; 2–5 →
0,80; 6–20 → 0,60; 21–50 → 0,40; 51–100 → 0,20) làm kim chỉ nam phân bổ dòng bằng tay.

### Vì sao cần `model_registry.py` — ràng buộc phần cứng, không phải sở thích thiết kế

Máy chạy có **8151 MiB VRAM**. SigLIP (1,7 GB) + SigLIP2 (1,7 GB) + BGE-M3 (1,1 GB) + VietOCR không
cùng nằm vừa. Pattern singleton hiện tại (`retrieve.py`, `vlm_ocr_caption.py`, `ocr_read.py`) giữ model
sống mãi trong process — trên CPU thì chỉ tốn RAM, trên GPU thì **OOM chắc chắn** ngay khi thêm model
thứ tư. Đây là lý do hạng mục này chặn #10.4 và #10.6, không phải dọn dẹp code.
