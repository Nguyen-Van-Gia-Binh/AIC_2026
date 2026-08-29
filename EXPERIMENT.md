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
