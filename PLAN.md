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

## Phase 5: OCR on-demand cho Q&A (⏳ Todo)

Thêm khả năng đọc chữ/số thật (hiện tại hệ thống chỉ nhờ LLM Vision "đọc bằng mắt", chưa có OCR nào),
nhưng chỉ chạy khi câu hỏi thực sự cần đọc chữ/số (biển số, giá tiền, số áo...) và chỉ trên vài ảnh
candidate tốt nhất — không xử lý trước toàn bộ 177K keyframe (quá tốn thời gian/không cần thiết). Kết
quả OCR dùng làm gợi ý thêm cho LLM Vision, không thay thế nó — giữ nguyên cơ chế chống ảo giác đã có.

Success: thử vài câu hỏi loại "biển số xe"/"giá tiền"/"số áo", so sánh answer có/không có gợi ý OCR;
không phát sinh crash khi OCR không đọc được gì.

## Phase 6: Checkpoint & Dry-run (⏳ Todo, sau khi Phase 1–5 xong)

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
- **Chạy review tổng toàn nhánh cho Phase 4** (`superpowers:requesting-code-review` hoặc tương đương) —
  phiên làm Phase 4 (subagent-driven) đã review từng Task riêng lẻ (cả 2 sạch, 1 finding fix round đã
  giải quyết) nhưng bỏ qua bước review toàn nhánh cuối cùng theo yêu cầu dừng sớm của người dùng; nên
  chạy 1 lần trước khi freeze 03/09 để bắt các vấn đề nằm ngoài phạm vi từng Task riêng lẻ. Kế hoạch +
  ledger còn giữ tại `.superpowers/sdd/2026-08-24-phase4-trake-dp-crosscheck/` để resume nếu cần.
- **Sửa docstring lỗi thời ở `pipeline_trake.py`** dòng đầu file — vẫn ghi `fast_retrieve(100)` dù code
  thật đã đổi thành `RETRIEVAL_POOL_SIZE` (500) từ Task 1 Phase 4 — cosmetic, không chặn gì.
- **Lỗi encoding console Windows**: chạy bất kỳ script nào import `scripts/agent/tools/retrieve.py`
  trên console mặc định (code page cp1252) sẽ crash `UnicodeEncodeError` ở dòng in "ĐANG DÙNG MODEL"
  (ký tự "Đ") — phải set `PYTHONIOENCODING=utf-8` mới chạy được. Lỗi có từ trước Phase 4, không phải do
  Phase 4 gây ra, nhưng ảnh hưởng bất kỳ ai chạy script trên máy Windows mặc định — nên sửa (vd.
  `sys.stdout.reconfigure(encoding="utf-8")` ở đầu `retrieve.py`, hoặc đổi log sang không dấu) trước
  ngày nộp thật để tránh crash bất ngờ lúc demo/dry-run.

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
