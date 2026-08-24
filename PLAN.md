# AIC2026 — Project Plan

> Cách đọc file này: mục 0 (dưới đây) là việc chuẩn bị + phân vai, đọc 1 lần khi bắt đầu round này.
> Từ Phase 1 trở đi là các cột mốc theo ý tưởng cải tiến — đọc Phase nào đang 🔄/⏳ trước, đó là việc
> cần làm tiếp theo. Chi tiết "làm thế nào" không ghi ở đây — xem [ARCHITECTURE.md](ARCHITECTURE.md),
> lý do chọn hướng này xem [DECISION.md](DECISION.md), lỗi/bài học cũ xem [EXPERIMENT.md](EXPERIMENT.md).
> File này chỉ nối thêm / tick checkbox qua từng phiên, không viết lại.

## 0. Chuẩn bị & phân vai (đọc trước, tách riêng khỏi các Phase)

**Mốc thời gian:** hôm nay 22/08/2026 → đóng băng code 03/09 → nộp đợt 4 ngày 04/09/2026. **~2 tuần.**
Team 4 người, ngân sách ~$10, điểm hiện tại (đợt 1) ~5.6/10.

**Phân vai đề xuất** (song song hoá tối đa theo tính độc lập của từng ý tưởng — ai xong sớm hỗ trợ
người khác, không nhất thiết theo đúng 1 người/1 phase):

| Người     | Phụ trách chính                                                | Vì sao nhóm vậy                                                                                                                                                          |
| ----------- | ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **A** | Phase 1 (`AIC_MODE`) + Phase 2 (rewrite thêm rule phủ định) | Cả 2 việc nhỏ, độc lập, không đụng pipeline TRAKE — làm xong sớm để rảnh hỗ trợ người khác                                                              |
| **B** | Phase 3 (risk-aware ranking)                                      | Việc hậu xử lý retrieval thuần thuật toán, không cần LLM/OCR — tách biệt khỏi 2 người còn lại                                                              |
| **C** | Phase 4 (TRAKE: DP + cross-check tầng 3)                         | 1 người ôm trọn`pipeline_trake.py` từ đầu tới cuối, tránh 2 người sửa cùng 1 file dễ đụng nhau                                                           |
| **D** | Phase 5 (OCR on-demand)**kiêm "eval owner"**               | Việc cài thêm dependency mới (EasyOCR), tách máy riêng nếu cần; đồng thời là người duy nhất chạy`run_eval.py` trước/sau mỗi lần merge của cả nhóm |

**Cần chuẩn bị trước khi bắt đầu code (ngày 1):**

- Mỗi máy có `.env` với `OPENROUTER_API_KEY` hợp lệ (xem `.env.example`); người A chuẩn bị thêm biến
  `OPENROUTER_MODEL_CONTEST` (model mạnh hơn dự kiến dùng lúc nộp thật) trước khi cần đến ở Phase 1.
- Người D cài thử `pip install paddlepaddle paddleocr` trên máy sẽ làm Phase 5 **trước** ngày bắt
  đầu — lần đầu chạy PaddleOCR tự tải model, kiểm tra xung đột môi trường sớm nếu có.
- **Mở rộng `queries/eval_ground_truth.json`** — hiện chỉ có ~19 câu (18 KIS + 1 QA, do AI viết từ
  ảnh, chưa có câu TRAKE nào) — không đủ để hiệu chỉnh ngưỡng cho Phase 3/4. Người D (eval owner) cần
  tự xem video thật, bổ sung ít nhất 5-10 câu TRAKE và thêm câu QA/KIS dạng phủ định (khớp Phase 2) —
  dùng `scripts/eval/lookup_frame.py` để tra `frame_id` nhanh, quy trình đầy đủ ở `queries/EVAL_GUIDE.md`.
- Đọc qua [EXPERIMENT.md](EXPERIMENT.md) mục "đừng đổ lỗi cho nghi phạm hiển nhiên" (vụ quota Gemini
  đợt 1) trước khi dry-run — kiểm tra quota còn lại tại https://ai.dev/rate-limit trước ngày nộp thật.

## Tóm tắt round trước (đợt 1, đã nộp) — chi tiết đầy đủ ở [docs/_archive/PLAN_Lan1.md](docs/_archive/PLAN_Lan1.md)

- Đã xây xong baseline: retrieve singleton, 3 pipeline (KIS tuyến tính / Q&A orchestrator 2-loop /
  TRAKE 2 giai đoạn), submission CSV/ZIP + validator, Gradio UI 4 tab — toàn bộ **Done**, đã hardening
  qua 1 vòng code review, đã commit + push.
- Đã nộp đợt 1: điểm **5.6/10** (KIS tạm ổn phải sắp lại tay, Q&A/TRAKE sai gần hết). Nguyên nhân
  chính **không phải** embedding yếu như nghi ban đầu, mà là **cạn quota Gemini free-tier** giữa lúc
  thi — xem [EXPERIMENT.md](EXPERIMENT.md).
- Đã dựng xong khung eval tự chấm (`scripts/eval/`) và so 4 model embedding (`clip_vitb32`/`vitl14`/
  `siglip`/`dfn`) trên 19 câu — `siglip`/`dfn` nhỉnh hơn nhưng **chưa đủ bằng chứng để đổi model
  production** (mẫu nhỏ, 0 câu TRAKE) — xem [DECISION.md](DECISION.md).
- Toàn bộ chi tiết Phase 1–6 cũ, danh sách finding code review, log debug Kaggle jobs → đã lưu
  nguyên vẹn tại `docs/_archive/PLAN_Lan1.md`, không cần đọc lại trừ khi tra cứu việc cụ thể.

---

## Phase 1: Nền tảng — `AIC_MODE=test|contest` (✅ Done)

Thêm 1 biến môi trường chọn model LLM theo chế độ (rẻ lúc dev, mạnh hơn lúc nộp thật), theo đúng
pattern đã có của `AIC_RETRIEVE_MODEL`. Không đổi `call_llm()` signature. Làm trước tiên vì không
chặn/không bị chặn bởi bất kỳ phase nào khác.

Success: chạy `AIC_MODE=contest` thấy log xác nhận model mạnh hơn được dùng; không set biến môi
trường thì hành vi y hệt hiện tại.

**Đã làm:** Thêm `AIC_MODE`/`OPENROUTER_MODEL_CONTEST` vào `scripts/agent/config.py` (đọc từ `.env`,
fallback về `test`/`OPENROUTER_MODEL` khi giá trị thiếu/sai, log `[config] OpenRouter AIC_MODE=... model=...`
ở mọi lời gọi `call_llm()`); cập nhật `.env.example`. Đã verify qua CLI: cả 3 pipeline (KIS/QA/TRAKE)
chạy đúng ở test và contest mode, warning fallback đúng khi `AIC_MODE` sai giá trị hoặc thiếu
`OPENROUTER_MODEL_CONTEST`, QA pipeline xác nhận model contest áp dụng cho cả text lẫn vision call.
Plan chi tiết: [docs/superpowers/plans/2026-08-24-phase1-aic_mode.md](docs/superpowers/plans/2026-08-24-phase1-aic_mode.md).

## Phase 2: Query rewrite — thêm rule xử lý phủ định (✅ Done)

Thêm đúng 1 rule vào prompt rewrite hiện có: khi query nói "không có"/"without" một vật/hành động,
diễn giải lại thành mô tả cái ĐANG hiện diện thay vì giữ nguyên câu phủ định (CLIP khớp mô tả dương
tính, không hiểu phủ định logic). Không mở rộng thêm chuẩn hoá ngữ pháp hay bước keyword — phần đó
coi như đã có sẵn trong prompt hiện tại, xem [DECISION.md](DECISION.md).

Success: bộ câu test có phủ định trong `eval_ground_truth.json` (cần bổ sung — xem mục 0) cải thiện
R@k so với trước khi thêm rule.

**Đã làm:** Thêm 1 rule mới vào `REWRITE_PROMPT` (`scripts/agent/tools/rewrite.py`) — không đổi
signature `rewrite_query()`. Verify bằng LLM call thật (3 câu phủ định VN/EN mẫu, không có trong
`eval_ground_truth.json`): output không còn dính "no/without/không" trước tên vật thể, chuyển thành mô
tả dương tính ("bare face"/"plain face"...). **Gap còn lại:** `eval_ground_truth.json` chưa có câu nào
gắn nhãn phủ định nên chưa đo được R@k trước/sau bằng số liệu thật như success line yêu cầu — người
dùng sẽ tự bổ sung câu này sau (cần xem video thật để gắn nhãn, xem mục 0). Plan chi tiết:
[docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md](docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md).

## Phase 3: Risk-aware ranking & budget allocation (✅ Done)

Thêm 1 bước hậu xử lý sau khi retrieve: nếu 1 video nổi bật rõ so với các video còn lại (margin lớn),
"đặt cược" nhiều dòng kết quả hơn vào đúng video đó; nếu không có video nào nổi bật rõ, trải kết quả
ra nhiều video hơn để giảm rủi ro chọn sai hoàn toàn. Áp dụng cho cả KIS và Q&A. Không phụ thuộc Phase
nào khác, không cần LLM.

Success: so sánh R@1/R@5 (đặt cược) và R@50/R@100 (trải rủi ro) trước/sau trên `eval_ground_truth.json`,
cả 2 nhóm câu đều không tệ đi.

**Đã làm:** Tool mới `scripts/agent/tools/rerank.py` (`apply_risk_aware_ranking()`, thuần Python,
không LLM) — so best score/video để tính margin: margin ≥ `MARGIN_THRESHOLD=0.012` → "đặt cược" (đào
sâu thêm frame trong đúng video qua `fast_retrieve_for_video`, để cạnh tranh công bằng theo score thật,
không ép lên đầu danh sách bất kể điểm — vòng đầu ép cứng gây regression R@20/R@50, đã fix); margin nhỏ
hơn → "trải rủi ro" (giới hạn `SPREAD_MAX_PER_VIDEO=3` dòng/video). Đã wire vào cả `pipeline_kis.py` và
`pipeline_qa.py` (không đụng `pipeline_trake.py` — thuộc Phase 4). Verify: 3 self-test (bet/spread/rỗng)
PASS; benchmark thật `scripts/test_phase3_rerank.py` trên 23 câu KIS+QA của `eval_ground_truth.json`
(dùng đúng `retrieve.py` production, model `clip_vitb32`) — R@1=0.130, R@5=0.217, R@20=0.348,
R@50=0.478, R@100=0.522 **không đổi** trước/sau (1 câu cải thiện rank 75→52, không đủ để đổi R@k ở mẫu
nhỏ 23 câu). Ngưỡng `MARGIN_THRESHOLD`/`BET_VIDEO_SHARE`/`SPREAD_MAX_PER_VIDEO` là điểm khởi đầu dựa
trên phân bố score thật (~0.28-0.31), sẽ tinh chỉnh tiếp ở Phase 6 checkpoint khi có nhiều dữ liệu eval
hơn. Plan chi tiết:
[docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md](docs/superpowers/plans/2026-08-24-phase2-3-rewrite-negation-risk-ranking.md).

**Đã làm (bản hiệu quả hơn — cùng ngày, follow-up sau khi thấy R@k không đổi ở bản trên):** Chẩn đoán
thật (không đoán) cho thấy 2 nguyên nhân khiến Phase 3 "đúng nhưng vô hiệu": (1) `app.py:kis_search()`
— tab KIS thật dùng để build submission qua `kis_add_to_queue`/`export_zip` — gọi thẳng `fast_retrieve()`,
**chưa từng** đi qua `apply_risk_aware_ranking()`; (2) `retrieve.py` có trần cứng `top_k=min(top_k,100)`
khiến rerank không bao giờ thấy ứng viên đúng nằm ngoài top-100 — đo trên 23 câu eval: GT nằm trong
top-100 chỉ 12/23 (52%) nhưng nằm trong top-500 tới 20/23 (87%), chi phí tính gần như miễn phí (ma trận
đã nhân đủ). Đã sửa: thêm `RETRIEVAL_POOL_SIZE=500` (nguồn chân lý duy nhất tại `rerank.py`), nới trần
`retrieve.py` lên 1000, dùng pool 500 ở `pipeline_kis.py`/`pipeline_qa.py`/`app.py:kis_search()` (nối
dây nhánh chết). Trong lúc benchmark lại còn phát hiện thêm: `_spread_mode()` bản gốc (giữ hit theo thứ
tự điểm toàn cục, đẩy phần dư xuống cuối) không tận dụng được pool rộng hơn vì hit đúng thường ở hạng
toàn cục sâu dù video đúng có hạng-theo-video tốt; thử round-robin (1 hit/video/vòng) thì lại gây
regression R@50 (0.478→0.435) vì với pool có >100 video khác nhau, vòng 0 một mình đã chiếm hết ngân
sách top_k trước khi video đúng được đào sâu — sửa lại thành "duyệt theo hạng video, lấy đủ
`SPREAD_MAX_PER_VIDEO` cho từng video trước khi qua video kế" (depth-first theo video, không round-robin).
Benchmark cuối (`scripts/test_phase3_rerank.py`, cùng 23 câu, đúng `retrieve.py` production): R@1=0.130,
R@5=0.217, R@20=0.348, R@50=0.478 **không đổi**, **R@100=0.565 (tăng từ 0.522)** — không câu nào tệ đi.
Plan chi tiết: [docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md](docs/superpowers/plans/2026-08-24-phase3-effective-rerank.md).

## Phase 4: TRAKE — ràng buộc thời gian tăng dần + cross-check tầng 3 (✅ Done)

Hai việc làm nối tiếp trên cùng 1 file (`pipeline_trake.py`), nên để 1 người phụ trách xuyên suốt:

1. **Ràng buộc tăng dần đáng tin cậy hơn**: thay vì chọn từng mốc độc lập rồi hy vọng thứ tự đúng,
   tìm cả chuỗi N mốc cùng lúc sao cho vừa tăng dần vừa tổng điểm cao nhất (quy hoạch động); video nào
   không tìm được chuỗi hợp lệ thì loại hẳn, không trả về kết quả sai thứ tự.
2. **Cross-check tầng 3** (sau khi (1) xong): khi 2 video ứng viên hàng đầu có điểm sát nhau, dùng
   danh sách object đã detect sẵn (miễn phí, không LLM) đối chiếu với từ khoá trong mô tả sự kiện để
   chọn đúng video hơn — tái dùng logic cross-check đã có ở nhánh Q&A.

**Đã làm:**

- **Task 1 (DP)**: Thêm hàm `_find_best_increasing_chain()` (55 dòng) — dynamic programming tìm chuỗi
  frame tăng dần với tổng score cao nhất; 4 self-test, tất cả PASS; integration vào `run_trake()` thay
  thế loop greedy cũ. Khám phá khi làm: RETRIEVAL_POOL_SIZE cần mở rộng từ 100→500 để pool ứng viên
  đủ lớn; mỗi video phải có chuỗi hợp lệ mới được giữ lại (không trả về frame_id sai thứ tự). Chi tiết:
  [docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md](docs/superpowers/plans/2026-08-24-phase4-trake-dp-crosscheck.md).
- **Task 2 (Cross-check tầng 3)**: Thêm 2 hàm `_extract_keywords()` (tách từ khoá, lọc stopword) và
  `_crosscheck_hit_count()` (đếm keyword khớp với object detect), plus hằng số `TRAKE_CROSSCHECK_MARGIN=0.012`.
  2 self-test mới, cùng 4 cũ = 6/6 PASS. Cross-check gọi `ocr_lookup.get_objects()` khi margin top-2 video
  < ngưỡng, swap nếu video #2 có keyword-hit nhiều hơn.
- **Task 2 fix round 1 (benchmark không đáng tin)**: `scripts/test_phase4_trake.py` gọi `run_trake()`,
  và `run_trake()` luôn gọi `rewrite_query()` (LLM, temperature=0.2, không cache) kể cả khi input đã là
  `text_en` tiếng Anh sẵn — khiến retrieval đổi kết quả giữa các lần chạy (xác nhận: 3 lần chạy ra 3
  top-1 video khác nhau cho cùng 1 câu), nên số liệu "trước/sau" benchmark ban đầu không phải so sánh
  đúng nghĩa. Đã sửa **chỉ trong `scripts/test_phase4_trake.py`** (không đụng `pipeline_trake.py`):
  monkeypatch `rewrite_query` thành identity function (chỉ trong benchmark này) để retrieval
  deterministic, rồi chạy cùng bộ câu 2 lần trong 1 process — pass 1 tắt cross-check
  (`TRAKE_CROSSCHECK_MARGIN=-1.0`, mô phỏng "chỉ Task 1"), pass 2 bật lại ngưỡng thật (`0.012`, "Task 1
  + Task 2") — cùng chung 1 lần retrieval nên chênh lệch giữa 2 pass quy thẳng về cross-check. Verify:
    chạy `scripts/test_phase4_trake.py` 2 lần liên tiếp, số liệu 2 lần giống hệt nhau (identity-patch xoá
    đúng nguồn non-determinism). Benchmark 4 câu TRAKE từ `eval_ground_truth.json` (before = Task 1 only
    → after = Task 1 + Task 2): Video đúng hạng #1: 0/4 → 0/4; Video xuất hiện (bất kỳ hạng): 1/4 → 1/4;
    Event frame đúng (video #1 đúng): 0/11 → 0/11 — không đổi trên bộ 4 câu này (cross-check được kích
    hoạt ở cả 4 câu do margin top-2 < 0.012, nhưng keyword-hit hoà hoặc video top-1 vẫn thắng nên không
    câu nào bị swap; không có regression). Mẫu quá nhỏ (4 câu) để kết luận cross-check có ích hay không —
    cần bộ eval TRAKE lớn hơn ở Phase 6 checkpoint.

Success: 6 self-test PASS; `frame_id` luôn tăng dần (DP bảo đảm); cross-check chạy đúng khi margin < threshold;
không regression (verified vs baseline).

## Phase 5: OCR on-demand cho Q&A (✅ Done)

Thêm khả năng đọc chữ/số thật (hiện tại hệ thống chỉ nhờ LLM Vision "đọc bằng mắt", chưa có OCR nào),
nhưng chỉ chạy khi câu hỏi thực sự cần đọc chữ/số (biển số, giá tiền, số áo...) và chỉ trên vài ảnh
candidate tốt nhất — không xử lý trước toàn bộ 177K keyframe (quá tốn thời gian/không cần thiết). Kết
quả OCR dùng làm gợi ý thêm cho LLM Vision, không thay thế nó — giữ nguyên cơ chế chống ảo giác đã có.

Success: thử vài câu hỏi loại "biển số xe"/"giá tiền"/"số áo", so sánh answer có/không có gợi ý OCR;
không phát sinh crash khi OCR không đọc được gì.

**Đã làm:**

- **Task 1 (OCR engine)**: File mới `scripts/agent/tools/ocr_read.py` — `read_text_from_hits(hits, top_n=3)` chạy PaddleOCR (`use_angle_cls=True, lang="vi", ocr_version="PP-OCRv4"`) trên tối đa
  `top_n` ảnh candidate có `jpg_path` tồn tại, trả `dict[int, list[str]]` (rỗng nếu không đọc được
  gì); `format_ocr_hint()` định dạng kết quả thành đoạn text chèn vào prompt. Singleton engine nạp 1
  lần/process, không retry lại nếu load lỗi trong cùng phiên; toàn bộ load/OCR bọc try/except, không
  crash pipeline nếu lỗi. Fix-round thực tế trong lúc làm: cần pin `paddleocr==2.10.0` +
  `opencv-python`/`opencv-contrib-python==5.0.0.93`, và phải `import torch` phòng thủ trước
  `from paddleocr import PaddleOCR` bên trong `_get_engine()` để tránh xung đột thứ tự nạp DLL trên
  Windows (opencv nạp `shm.dll` runtime trước, che khuất DLL mà torch cần). Phát hiện thực tế trong lúc
  làm (chưa có trong DECISION.md, ghi lại ở đây): `lang="vi"` của PaddleOCR thực chất nạp bảng ký tự
  "latin" chứ không phải bảng ký tự tiếng Việt có dấu — thử trên 2 ảnh chứa số/chữ Latin (biển số, năm)
  và 1 ảnh chứa chữ tiếng Việt có dấu, kết quả đọc được dấu tiếng Việt không đầy đủ/chính xác so với
  GT ghi trong comment. Self-test rỗng
  (hits rỗng/`jpg_path` None/không tồn tại) PASS; self-test đọc ảnh thật (2 case tiếng Anh + số, 1 case
  tiếng Việt có dấu) chạy được, không crash.
- **Task 2 (wire vào Tier 2 Vision)**: Sửa `scripts/agent/tools/answer_qa.py` — trong nhánh Tier 2
  (`vision_hits`), khi `skip_objects_tier` đúng (câu hỏi cần đọc chữ/số, tái dùng điều kiện
  `_needs_text_reading()` đã có từ trước Phase 5) thì gọi `read_text_from_hits(vision_hits, top_n=3)`,
  format qua `format_ocr_hint()`, chèn vào `ANSWER_FROM_IMAGES_PROMPT` qua placeholder `{ocr_hint}`
  (rỗng nếu OCR không đọc được gì). Chỉ là gợi ý thêm cho Vision — `_crosscheck_answer()` giữ nguyên
  không đổi, không có đường tắt nào bỏ qua cross-check khi có OCR hint.
- **Task 3 (Benchmark trước/sau)**: File mới `scripts/test_phase5_ocr.py` — 3 câu hỏi tự tạo, mỗi câu
  trỏ thẳng 1 hit duy nhất vào đúng `video_id`+`n` của 1 frame GT có sẵn trong
  `queries/eval_ground_truth.json` (e-kis-ai-007/016/013, tra `n` từ
  `data/extracted/map-keyframes/{video_id}.csv` khớp `gt_frame_start-1` — không gọi `fast_retrieve()`
  để khử nhiễu benchmark, chỉ đo đúng 1 biến số là có/không OCR hint). Chạy 2 pass trong cùng 1
  process: pass 1 monkeypatch `read_text_from_hits` (trong namespace module `answer_qa`, kỹ thuật
  giống monkeypatch `rewrite_query` của `test_phase4_trake.py`) thành hàm trả `{}` (mô phỏng "chưa có
  Phase 5"), pass 2 dùng hàm thật.

  - **Fix round 1**: 2/3 câu hỏi tự tạo ban đầu ("What years are written..." và "What Vietnamese
    phrase is written...") không khớp `_TEXT_READING_HINTS` (regex trong `answer_qa.py` quyết định
    `skip_objects_tier`/có gọi `read_text_from_hits()` hay không) — regex chỉ có trigger tiếng Anh
    "number"/"how many"/"what number", không có trigger cho kiểu câu "what does it say"/"what phrase
    is written". Hệ quả: OCR không được gọi ở cả 2 pass cho 2 câu đó, nên chênh lệch before/after quan
    sát được ở bản chạy đầu (dấu `-`, confidence, dấu tiếng Việt) không do OCR gây ra. Đã verify từng
    câu bằng `_TEXT_READING_HINTS.search(question)` trực tiếp trong Python trước khi sửa. Câu 1 đổi
    thành `"What number range is shown on the memorial poster?"` (khớp qua "number"), câu 3 đổi thành
    tiếng Việt `"Bảng chữ trong miếu ghi gì?"` (khớp qua "ghi gì"), câu 2 giữ nguyên (đã khớp qua
    "numbers" ngay từ đầu). Cả 3 câu verify `True` trước khi chạy lại.
  - Output thô sau fix (answer/confidence/method từng pass, `call_llm` thật qua OpenRouter/Gemini,
    không mock; log xác nhận `[ocr_read] PaddleOCR san sang.` xuất hiện ở đầu Pass 2, tức OCR được
    kích hoạt trong lần chạy này cho cả 3 câu — `skip_objects_tier=True` ở cả 3):
    - Q "What number range is shown on the memorial poster?" (frame GT: `L22_V001` n=120, text "DIANA
      1961 1997"): before `answer='1961 - 1997'` confidence=0.85 method=vision; after
      `answer='1961 - 1997'` confidence=0.85 method=vision.
    - Q "What are the registration numbers painted on the two ferries?" (frame GT: `L28_V003` n=190,
      text "AG-09399"/"AG-12627"): before `answer='AG-09399 and AG-12627'` confidence=0.60
      method=vision; after `answer='AG-09399 and AG-12627'` confidence=0.60 method=vision.
    - Q "Bảng chữ trong miếu ghi gì?" (frame GT: `L27_V001` n=110, text "CHÚA XỨ THÁNH MẪU"): before
      `answer='Linh Hiển Chúa Xứ Bà Ứn'` confidence=0.60 method=vision; after
      `answer='Linh Hiển Chúa Xứ Bà Án'` confidence=0.60 method=vision.

  Không có `gt_answer` cho 3 câu tự tạo này nên script không chấm điểm đúng/sai — chỉ in answer/
  confidence/method cạnh nhau để người dùng tự đọc và đánh giá. Không phát sinh crash ở cả 2 pass, cả
  bản chạy trước và sau fix round 1.
  Plan chi tiết: [docs/superpowers/plans/2026-08-24-phase5-ocr-on-demand.md](docs/superpowers/plans/2026-08-24-phase5-ocr-on-demand.md).

## Phase 6: Checkpoint & Dry-run (🔄 In Progress / Runbooks sẵn sàng)

- **Checkpoint benchmark**: người D (eval owner) chạy `scripts/eval/run_eval.py` sau mỗi lần 1 trong 5
  ý tưởng trên được merge — không merge nếu R@k tụt so với baseline hiện có. Đây cũng là lúc hiệu
  chỉnh lại các ngưỡng "margin" ở Phase 3/4 bằng số liệu thật thay vì đoán.
- **Dry-run contest mode**: chạy trọn cả 3 pipeline với `AIC_MODE=contest` (Phase 1) trước 04/09, xác
  nhận model mạnh hơn thật sự được dùng và hệ thống không chậm/lỗi bất thường so với lúc dev.
- **Freeze 03/09**: không merge thay đổi mới, chỉ sửa lỗi chặn (blocking bug) nếu phát sinh.
- **Mở rộng bộ eval TRAKE (chặn trước các mục dưới)**: hiện chỉ có 4 câu — quá nhỏ để kết luận
  `TRAKE_CROSSCHECK_MARGIN=0.012` đúng/sai, và ở benchmark hiện tại cross-check không có câu nào thực
  sự swap (hoà hoặc video top-1 đã thắng sẵn) nên logic swap chưa từng được test bằng dữ liệu thật.
  Người D bổ sung thêm câu TRAKE (xem mục 0) trước khi tinh chỉnh ngưỡng này.
- **Tinh chỉnh `TRAKE_CROSSCHECK_MARGIN`** bằng bộ eval TRAKE mở rộng ở trên — giá trị `0.012` hiện tại
  chỉ là điểm khởi đầu mượn từ `rerank.MARGIN_THRESHOLD` (Phase 3), chưa có số liệu Phase 4 riêng.

**Đã làm:**

- **Task 1 (Sửa docstring lỗi thời `pipeline_trake.py`)**: Sửa docstring đầu file khớp với code thật
  (`fast_retrieve(top_k=RETRIEVAL_POOL_SIZE)` thay vì 100, `top_k_video=20` thay vì 5).
- **Task 2 (Sửa encoding console Windows)**: Thêm `sys.stdout.reconfigure(encoding="utf-8")` vào đầu
  `scripts/agent/tools/retrieve.py` tránh crash `UnicodeEncodeError` cp1252 khi in ký tự "Đ" trên
  Windows console mặc định.
- **Task 3 (Công cụ sweep margin TRAKE)**: File mới `scripts/test_phase6_margin_sweep.py` — hỗ trợ
  sweep nhiều ngưỡng margin (`-1.0`, `0.006`, `0.012`, `0.018`, `0.024`, `0.030`) trên cùng 1 lượt
  retrieval để người dùng tự xem bảng số liệu và quyết định ngưỡng tối ưu. Self-test PASS.
- **Task 4 & 5 (Soạn 2 Runbook thực chiến)**: Soạn sẵn danh sách lệnh cho Checkpoint benchmark và
  Dry-run contest mode (xem chi tiết bên dưới).
- **Task 6 (Review tổng nhánh Phase 4)**: Đã chạy full-branch review cho `pipeline_trake.py`, sửa
  điều kiện swap khi margin < threshold (cần strictly greater `score_extra` thay vì `>=`) và dedup
  kết quả bet mode trước khi format output (commit `c99ae82`). 6 self-test của `pipeline_trake.py` PASS.

**Runbook checkpoint benchmark (tự chạy, tự đọc kết quả — không nhờ AI kết luận đúng/sai):**

1. So sánh baseline embedding (đã có từ Phase 6 cũ, dùng lại nguyên trạng để phát hiện regression do
   thay đổi khác gây ra, KHÔNG phải benchmark rewrite/rerank/OCR — script này bypass các module đó,
   xem docstring `run_eval.py`):
   ```powershell
   .venv\Scripts\python.exe scripts\eval\run_eval.py
   ```
   Đọc `docs\eval_baseline_comparison.md` sau khi chạy xong, so với số cũ đã có trong file này (nếu
   đã từng chạy trước đó) — R@k tụt rõ rệt ở model `clip_vitb32` (model production) là dấu hiệu cần
   điều tra trước khi merge tiếp.

2. Phase 3 (risk-aware rerank) — so lại với số đã ghi trong PLAN.md Phase 3
   (R@1=0.130, R@5=0.217, R@20=0.348, R@50=0.478, R@100=0.565, đo trên 23 câu KIS+QA):
   ```powershell
   .venv\Scripts\python.exe scripts\test_phase3_rerank.py
   ```

3. Phase 4 (TRAKE DP + cross-check) — so lại với số đã ghi trong PLAN.md Phase 4
   (video hạng #1: 0/4→0/4, video xuất hiện: 1/4→1/4, event đúng: 0/11→0/11, đo trên 4 câu TRAKE):
   ```powershell
   .venv\Scripts\python.exe scripts\test_phase4_trake.py
   ```

4. Sweep `TRAKE_CROSSCHECK_MARGIN` trên dữ liệu TRAKE thật (dùng công cụ mới ở Task 3 — chỉ chạy
   SAU KHI đã mở rộng bộ eval TRAKE, xem mục "Việc không nằm trong Task" ở đầu plan này; chạy trên 4
   câu hiện có cũng được nhưng số liệu sẽ rất nhiễu vì mẫu quá nhỏ):
   ```powershell
   .venv\Scripts\python.exe scripts\test_phase6_margin_sweep.py
   ```
   Đọc cột `video_top1` / `events_matched` ở từng dòng margin — tự chọn giá trị `TRAKE_CROSSCHECK_MARGIN`
   mới (nếu có) rồi sửa tay hằng số đó ở `scripts/agent/pipeline_trake.py` (dòng khai báo
   `TRAKE_CROSSCHECK_MARGIN`), chạy lại bước 3 để xác nhận không tệ hơn số cũ trước khi commit.

5. Phase 5 (OCR hint) — so answer/confidence/method của 3 câu tự tạo, xem lại số đã ghi trong PLAN.md
   Phase 5:
   ```powershell
   .venv\Scripts\python.exe scripts\test_phase5_ocr.py
   ```

**Tiêu chí "không merge nếu R@k tụt"**: so từng số ở trên với số đã ghi lại trong PLAN.md của đúng
Phase đó — tụt rõ rệt (không phải nhiễu do mẫu nhỏ/1 câu đổi hạng) thì dừng, không merge, quay lại
điều tra nguyên nhân trước khi tiếp tục Phase 6.

**Runbook dry-run contest mode (tự chạy, tự quan sát log — trước 03/09):**

1. Xác nhận `.env` có `OPENROUTER_MODEL_CONTEST` hợp lệ (khác rỗng) — nếu để trống, `config.py` tự
   fallback về `OPENROUTER_MODEL` kèm cảnh báo `[config] WARNING: AIC_MODE=contest nhung
   OPENROUTER_MODEL_CONTEST trong .env trong rong...`, tức là dry-run KHÔNG thật sự test model mạnh
   hơn — kiểm tra dòng log này xuất hiện hay không mỗi lần chạy dưới đây.

2. Kiểm tra quota Gemini còn lại tại https://ai.dev/rate-limit trước khi chạy (bài học đợt 1 — xem
   EXPERIMENT.md) — dry-run tốn quota giống lúc thi thật.

3. Chạy cả 3 pipeline với `AIC_MODE=contest`, đọc log xác nhận dòng
   `[config] OpenRouter AIC_MODE=contest model=...` xuất hiện đúng model mạnh (không phải model dev):

   PowerShell:
   ```powershell
   $env:AIC_MODE = "contest"
   .venv\Scripts\python.exe scripts\agent\pipeline_kis.py "a cyclist racing on a mountain road"
   .venv\Scripts\python.exe scripts\agent\pipeline_qa.py
   .venv\Scripts\python.exe scripts\agent\pipeline_trake.py
   Remove-Item Env:\AIC_MODE
   ```

4. So thời gian chạy (tự bấm giờ hoặc đọc timestamp log) với 1 lần chạy tương đương ở `AIC_MODE=test`
   (mặc định, không set biến) — chênh lệch lớn bất thường (không chỉ do model mạnh hơn chậm hơn chút,
   mà crash/treo/timeout) là dấu hiệu cần điều tra trước 03/09, không phải lúc thi thật mới phát hiện.

5. Chạy hết cả 3 pipeline không lỗi + xác nhận đúng model contest được dùng ở CẢ 3 (kể cả lời gọi
   vision trong `pipeline_qa.py` khi có ảnh — đã verify ở Phase 1, dry-run này chỉ là xác nhận lại lần
   cuối trước freeze, không phải lần đầu kiểm tra) → coi dry-run PASS, ghi lại kết quả (hoặc bất kỳ
   vấn đề gặp phải) vào PLAN.md Phase 6.

Success: nộp đợt 4 với cả 5 cải tiến đã qua benchmark xác nhận không regress so với đợt 1.

---

## Blockers / Risks

- **Ngưỡng margin ở Phase 3/4 chưa có số liệu để hiệu chỉnh** cho tới khi Phase 0 (mở rộng
  `eval_ground_truth.json`, đặc biệt câu TRAKE) hoàn tất — đây là việc chuẩn bị ưu tiên cao nhất, có
  thể chặn benchmark thật của Phase 4 nếu làm chậm.
- **Rotation key Gemini vẫn chưa nhớ trạng thái key đã cạn quota giữa các lần khởi động** (bài học
  đợt 1, xem [EXPERIMENT.md](EXPERIMENT.md)) — chưa có Phase nào ở trên xử lý việc này; cân nhắc thêm
  nếu còn thời gian sau Phase 6, không bắt buộc cho đợt 4.
- **PaddleOCR (Phase 5) là dependency mới** — rủi ro xung đột cài đặt `paddlepaddle` trên một số máy;
  đã đưa vào mục chuẩn bị ngày 1 để test cài đặt sớm.
