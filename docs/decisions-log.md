# AIC2026 — Nhật ký quyết định & bài học

> Gộp từ `DECISION.md` (vì sao đã chọn thế) và `EXPERIMENT.md` (đã sai thế nào, sửa ra sao) vào
> 2026-08-31. Hai file cũ cùng thể loại nội dung và cùng tần suất đọc — chỉ mở khi cần truy nguyên
> một quyết định — nên tách đôi chỉ tạo thêm một chỗ để trôi khỏi thực tế.
>
> **Đọc file này khi:** định đảo ngược một quyết định cũ, hoặc sắp đi lại một đường debug đã từng đi.
> Không ghi tiến độ ở đây (→ [PLAN.md](../PLAN.md)), không ghi quy ước (→ [CLAUDE.md](../CLAUDE.md)),
> không ghi thiết kế hiện hành (→ [ARCHITECTURE.md](../ARCHITECTURE.md)).

---

## Phần 1 — Quyết định kiến trúc & quy trình

> Vì sao các quyết định kiến trúc/quy trình được chọn — xem [ARCHITECTURE.md](../ARCHITECTURE.md) cho
> "cái gì", [PLAN.md](../PLAN.md) cho tiến độ. Bài học lỗi cũ → [Phần 2](#phần-2--sai-lầm-đã-mắc-và-cách-sửa).

> ⚠️ **File này được dựng lại ngày 2026-08-26.** Bản gốc chưa từng lên GitHub — bị `.gitignore`
> chặn từ đầu (đã gỡ, xem lịch sử `.gitignore`) và máy chứa bản gốc đã bị reset. Nội dung dưới đây
> là tổng hợp lại từ các trích dẫn/tham chiếu tới `DECISION.md` còn sót trong
> [docs/_archive/PLAN_Lan2.md](_archive/PLAN_Lan2.md), `ARCHITECTURE.md`, và
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

Khi phát hiện `RETRIEVAL_POOL_SIZE` cần nới từ 100→500 (xem [Phần 2](#phần-2--sai-lầm-đã-mắc-và-cách-sửa) mục Phase
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
  [docs/_archive/ARCHITECTURE_Lan1.md](_archive/ARCHITECTURE_Lan1.md) nếu cần.

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

Chi tiết kỹ thuật → [ARCHITECTURE.md §6](../ARCHITECTURE.md). Việc cần làm → [PLAN.md](../PLAN.md) Phase 10.

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

---

## Phần 2 — Sai lầm đã mắc và cách sửa

> Lỗi/bài học cũ — đọc trước khi lặp lại 1 hướng debug đã từng đi qua. Vì sao các quyết định khác
> được chọn → [Phần 1](#phần-1--quyết-định-kiến-trúc--quy-trình). Tiến độ hiện tại → [PLAN.md](../PLAN.md).

> ⚠️ **File này được dựng lại ngày 2026-08-26.** Bản gốc chưa từng lên GitHub — bị `.gitignore`
> chặn từ đầu (đã gỡ) và máy chứa bản gốc đã bị reset. Nội dung dưới đây tổng hợp lại từ các sự kiện
> đã ghi log chi tiết trong [docs/_archive/PLAN_Lan2.md](_archive/PLAN_Lan2.md) và
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

## Phase 7 — `run_eval.py::score_trake` cũ không bám công thức BTC TRAKE (§2.1.3)

**Triệu chứng:** điểm TRAKE trong `docs/eval_baseline_comparison.md` lạc quan bất thường, không phân
biệt được model theo cách công thức thi làm.

**Nguyên nhân:** `score_trake` cũ retrieve **từng event độc lập trên toàn corpus** rồi lấy **trung
bình R@k của N event**. Sai 3 chỗ so với §2.1.3: (a) không có cổng video toàn câu (`v_i ≠ GT_v` → 0
cả truy vấn — chính là Giai đoạn 1 Retrieval của TRAKE, phần khó nhất, bị bỏ qua); (b) thay
`max`-trên-ứng-viên-trọn-vẹn bằng `mean`-trên-event (cấu trúc `(1/N)Σ` này là của *R-Score*, không
phải của *Final Score* `R@k = max`); (c) bỏ ràng buộc `frame_id` tăng dần (§4.2).

**Fix:** dựng danh sách **ứng viên có xếp hạng** — mỗi ứng viên = 1 `video_id` (rank theo mean score
pool của global query, mirror Giai đoạn 1) + N `frame_id` (chuỗi `frame_idx` không giảm, chọn bằng
DP sao chép từ `pipeline_trake._find_best_increasing_chain`, **không import** để giữ eval độc lập với
production). `R-Score(ứng viên) = 0` nếu video sai, ngược lại `(1/N)Σ_j I(frame_j ∈ [s_j,e_j])`.
`R@k = max` trên k ứng viên đầu. Vẫn retrieval-only, không LLM. Thêm cột `Final = (1/5)Σ R@k`.
Muốn Final Score có LLM crosscheck + đúng đường nộp → `test_eval/Test/score_pipelines.py`.

**Bài học:** khi "xấp xỉ" một công thức chấm, kiểm lại xem bước xấp xỉ có đổi *ý nghĩa* của đại lượng
không (ở đây `mean` thay `max`, và bỏ mất precondition có sức nặng nhất). Docstring có ghi "xấp xỉ"
nhưng header report vẫn tự nhận "đúng công thức thi" — cả 2 giờ đã sửa cho khớp thực tế.

## Phase 8 (Tách FE/BE) — Phase con 1: lỗi giao diện lọt lưới vì nghiệm thu toàn headless

**Triệu chứng:** chạy thử frontend Phase‑con‑1 trên trình duyệt mới lộ: (a) cột "Danh sách nộp"
(shortlist KIS) đè chữ — thứ hạng / video_id / frame / score / nút × chồng lên nhau; (b) mọi ô ảnh là
khung sọc giả, không xem được keyframe thật; (c) bấm ô ảnh trong lưới KIS mở ra màn chi tiết nhưng đó
là ảnh tĩnh — không video, dải frame lân cận không bấm được, gần như không tương tác gì ngoài 2 nút
back / thêm.

**Nguyên nhân — 3 tầng:**
1. **Có chủ đích (một phần):** plan ghi rõ "Explicitly out of scope" — ô ảnh cố tình để placeholder
   sọc, serve ảnh thật là task sau. Video *chưa từng* có trong mockup nên không nằm trong plan, không
   được dựng — dù `data/extracted/video/Videos_L*_a/*.mp4` có sẵn, không route nào serve, không thẻ
   `<video>` nào tồn tại. Class `detail-player` lấy từ mockup, mockup vẽ nó là hộp placeholder.
2. **Lỗi CSS thật, bê nguyên từ plan:** `.thumb-placeholder { width: 100% }` đặt làm con trực tiếp
   của `.shortlist-row` (`display:flex`) mà không `flex: none` → `flex-basis` nở hết cỡ, nuốt chiều
   ngang của hàng → các phần tử anh em bị bóp ~0px, chữ tràn đè nhau. Chỉ lộ ở cột shortlist 300px;
   lưới `.kis-card` dùng đúng class đó nhưng là con duy nhất của hộp aspect‑ratio cố định nên trông
   vẫn ổn → dễ bỏ sót.
3. **Lọt lưới vì verify Phase‑con‑1 100% headless:** mọi "verify" trong plan là `assert`/`print`,
   `TestClient`, hoặc `npm run build` (chỉ type‑check) — không cái nào render CSS/DOM. Plan *có* 1
   bước xem trình duyệt (Task 11 Step 3), là cổng tick checkbox PLAN.md — nhưng bị bỏ qua (đã note và
   để trống checkbox, nhưng không ai mở trình duyệt xem 60 giây).

**Điều làm sai khi "sửa" (đợt fix #2):** thêm `/api/images` + `<Thumb>` cho thumbnail thật, nhưng vẫn
để `.detail-player` là ảnh tĩnh, không thêm route video, không nối `onClick` cho dải lân cận → màn chi
tiết *trông* hoàn thiện hơn *hành xử* → mời bấm rồi hụt. Sửa bề mặt mà không thu hẹp khoảng cách kỳ
vọng, không ghi "chưa có video" lên UI.

**Bài học:**
- Skeleton dựng theo mockup: verify headless (build + đường dữ liệu API) KHÔNG thay được 1 lần mở
  trình duyệt. Bước xem trình duyệt phải là verify bắt buộc, không phải cổng phụ để tick checkbox —
  nhất là lỗi layout flex/grid mà `tsc`/`build` không bao giờ bắt.
- Khi làm media "thật hơn" ở 1 chỗ, phải rà các chỗ liền kề mà thay đổi đó tạo kỳ vọng mới (ảnh tĩnh
  trông như trình phát video) → hoặc làm nốt, hoặc ghi rõ "chưa có" ngay trên UI.
- CSS bê từ plan vào repo vẫn là code phải review: `width:100%` trên flex‑child không `flex:none` là
  lỗi kinh điển, cần bắt lúc đọc plan.

_Nguồn: phiên 2026‑08‑27, Phase 8 Phase‑con‑1
(`docs/superpowers/plans/2026-08-27-phase1-fastapi-react-frontend-skeleton.md`) + đợt fix #1–#4 ngay
sau._

## TODO — bổ sung dần

- Bài học/lỗi cụ thể trong lúc dựng 4 job Kaggle (ViT-L/14, SigLIP, Jina, DFN) ở round 1 — đã có tóm
  tắt lỗi Jina 100% NaN trong `docs/_archive/PLAN_Lan1.md` Phase 6, nhưng chưa chắc đó là toàn bộ nội
  dung từng có ở đây.
- Bất kỳ lỗi debug nào gặp phải khi chạy Dry-run contest mode (việc còn treo — xem `PLAN.md`) nên ghi
  vào đây ngay khi phát sinh, đừng để tới lúc mất máy mới tiếc.

## 2026-08-28 — Regression Guard bắt được 3 lỗi khi triển khai BẢN ĐẶC TẢ

Cả 3 đều KHÔNG lộ ra qua self-test, chỉ lộ khi chấm điểm thật 18 câu KIS qua `run_kis()`.

1. **Đo margin đặt cược trên thang RRF** → Final 0.656 → 0.633. Điểm RRF là `w/(k+rank)`: khoảng cách
   giữa các hạng cực nhỏ và đều, nên ngưỡng tương đối 5% bắt "đặt cược" sai rất nhiều (R@5 tăng nhưng
   R@20/50/100 mất). **Fix:** thêm tham số `margin_key`, mặc định vẫn là `score` (cosine).
   *Bài học: khi đổi thang điểm xếp hạng, mọi ngưỡng đã hiệu chỉnh theo thang cũ đều phải đi cùng nó.*
2. **Đưa cả 500 ứng viên BM25 vào RRF** → 0.667 → 0.611. Frame chỉ trùng 1–2 từ chung chung
   ("person", "car") ở hạng sparse ~100–500 vẫn vượt được ứng viên dense hạng 150. **Fix:**
   `SPARSE_TOP_K = 50`.
3. **`str.replace()` âm thầm không khớp khi vá file bằng script** — đoạn nối Regression Guard vào
   `score_pipelines.main()` không được áp dụng, nhưng script vẫn báo "patched" và chương trình vẫn
   chạy bình thường (chỉ là không có Guard). Phát hiện vì `--save-baseline` chạy xong mà không sinh
   file. *Bài học: vá file bằng script thì phải `assert old in s` cho TỪNG replace, hoặc dùng công cụ
   sửa file có báo lỗi khi không khớp.*

Ghi chú thêm: Temporal NMS với `min_gap=3.0s` gần như trung tính trên dữ liệu này (65% khoảng cách
keyframe < 3s nhưng GT window đã được nới sang keyframe lân cận). Cái thật sự ăn điểm khi đo ở Tầng 1
là **trần 3 dòng/video** của chế độ trải rủi ro (0.549 → 0.434 trên 33 câu) — đó là thiết kế có từ
Phase 3, chưa đụng tới ở đợt này, nhưng đáng xem lại nếu còn thời gian trước vòng thi.
### Bug nạp index 2 bản — phần còn sót ở smoke test (2026-08-31)

**Triệu chứng:** không có triệu chứng nhìn thấy được — chỉ tốn RAM và thời gian khởi động gấp đôi
khi chạy smoke test.

**Nguyên nhân:** bản sửa 2026-08-27 chuẩn hoá import về tiền tố `scripts.` **chỉ phủ `scripts/`**,
không phủ `test_eval/`. `test_smoke_tools.py` và `test_smoke_pipelines.py` vẫn đặt `scripts/` lên
`sys.path` rồi `from agent.tools.retrieve import ...` — nạp SigLIP + index hai bản suốt từ đó. Sau
đó phát hiện thêm chỗ thứ ba: `preprocess/ocr/index_ocr_es.py`.

**Bài học:** khi sửa lỗi thuộc loại "một quy ước bị vi phạm ở đâu đó", đừng kết luận đã xong theo
thư mục đang sửa — grep TOÀN repo cho chính *pattern vi phạm*, rồi mới ghi là đã xử lý. Với repo này:
`grep -rn 'sys.path.insert' --include=*.py . | grep 'scripts"'` phải luôn rỗng.

### OCR chết âm thầm vì chứng chỉ hết hạn (phát hiện 2026-08-31)

**Triệu chứng:** không có. Pipeline chạy bình thường, chỉ in một dòng CẢNH BÁO rồi đi tiếp.

**Nguyên nhân:** `ocr_read` tải config VietOCR từ `vocr.vn`, chứng chỉ SSL của site đã hết hạn →
`read_text_from_hits()` luôn trả rỗng. Cache offline `data/extracted/ocr_text_paddleocr/` cũng chưa
build. Hệ quả: OCR Direct Overwrite không bao giờ kích hoạt, gợi ý OCR không bao giờ vào prompt
Vision — một trong các trụ chống ảo giác của Q&A thực tế không tồn tại.

**Bài học:** degradation êm ái (bắt lỗi, cảnh báo, chạy tiếp) là thiết kế đúng, nhưng nó phải đi kèm
**một chỗ báo cáo trạng thái** — nếu không, tính năng chết trở thành lỗi vô hình. Một dòng cảnh báo
lẫn giữa hàng trăm dòng log không phải là chỗ báo cáo trạng thái.

### Tách file làm lộ self-test patch nhầm module (2026-08-31)

**Triệu chứng:** sau khi tách `answer_qa.py` và `pipeline_trake.py`, hai self-test đang "PASS" bỗng
fail — hoặc tệ hơn, gọi LLM thật.

**Nguyên nhân:** self-test cũ monkeypatch bằng cách gán đè biến global của chính module đó
(`call_llm = _fake`). Khi hàm được kiểm thử chuyển sang module khác, nó đọc `call_llm` của module
MỚI, nên bản giả không có tác dụng. Test vẫn "pass" ở bản cũ, nhưng vì lý do sai.

**Bài học:** monkeypatch phải nhắm vào **module chứa hàm đang chạy**, không phải module mình đang
import từ đó. Dùng `monkeypatch.setattr(module_that_owns_it, "name", fake)` của pytest thay vì gán
biến global — nó bắt lỗi này sớm và tự khôi phục.

### Sửa lỗi hành vi Pha 2 (2026-08-31)

1. **TRAKE Top-100 & Fallback `strict=False`:** Nâng `top_k_video` lên 100 và fallback `strict=False` khi chuỗi động tác nhanh xảy ra trong cùng keyframe; ưu tiên xếp hạng chuỗi strict trước relaxed. Kết quả: TRAKE Final tăng mạnh từ 0.233 lên 0.430 (+84%).
2. **Q&A Multi-Cluster Tiered Extraction:** Mở rộng từ 3 cụm lên 15 cụm (3 Full Tầng 1+2 + 12 Cheap Tầng 1 Objects JSON text LLM). Tăng độ phủ answer độc lập của từng video, giúp Q&A Final tăng từ 0.040 lên 0.360 (+0.320, gấp 9 lần).
3. **VietOCR Offline Config & Health Check:** Đóng gói YAML config và weights cục bộ `vgg_transformer.pth`, loại bỏ phụ thuộc mạng/SSL của `vocr.vn`. Thêm `ocr_health() -> tuple[bool, str]`. KIS Final tăng lên 0.652.
4. **Resilient Fail-Soft:** Bọc bảo vệ `try...except` tại tất cả các điểm gọi LLM (`rewrite_query`, `answer_from_hits`), đảm bảo pipeline không crash khi provider cạn hạn mức hoặc gặp sự cố mạng.

