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
- Người D cài thử `pip install easyocr` trên máy sẽ làm Phase 5 **trước** ngày bắt đầu — lần đầu chạy
  EasyOCR tự tải model, tốn vài phút, không nên để việc này rơi vào lúc đang code.
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

## Phase 1: Nền tảng — `AIC_MODE=test|contest` (⏳ Todo)

Thêm 1 biến môi trường chọn model LLM theo chế độ (rẻ lúc dev, mạnh hơn lúc nộp thật), theo đúng
pattern đã có của `AIC_RETRIEVE_MODEL`. Không đổi `call_llm()` signature. Làm trước tiên vì không
chặn/không bị chặn bởi bất kỳ phase nào khác.

Success: chạy `AIC_MODE=contest` thấy log xác nhận model mạnh hơn được dùng; không set biến môi
trường thì hành vi y hệt hiện tại.

## Phase 2: Query rewrite — thêm rule xử lý phủ định (⏳ Todo)

Thêm đúng 1 rule vào prompt rewrite hiện có: khi query nói "không có"/"without" một vật/hành động,
diễn giải lại thành mô tả cái ĐANG hiện diện thay vì giữ nguyên câu phủ định (CLIP khớp mô tả dương
tính, không hiểu phủ định logic). Không mở rộng thêm chuẩn hoá ngữ pháp hay bước keyword — phần đó
coi như đã có sẵn trong prompt hiện tại, xem [DECISION.md](DECISION.md).

Success: bộ câu test có phủ định trong `eval_ground_truth.json` (cần bổ sung — xem mục 0) cải thiện
R@k so với trước khi thêm rule.

## Phase 3: Risk-aware ranking & budget allocation (⏳ Todo)

Thêm 1 bước hậu xử lý sau khi retrieve: nếu 1 video nổi bật rõ so với các video còn lại (margin lớn),
"đặt cược" nhiều dòng kết quả hơn vào đúng video đó; nếu không có video nào nổi bật rõ, trải kết quả
ra nhiều video hơn để giảm rủi ro chọn sai hoàn toàn. Áp dụng cho cả KIS và Q&A. Không phụ thuộc Phase
nào khác, không cần LLM.

Success: so sánh R@1/R@5 (đặt cược) và R@50/R@100 (trải rủi ro) trước/sau trên `eval_ground_truth.json`,
cả 2 nhóm câu đều không tệ đi.

## Phase 4: TRAKE — ràng buộc thời gian tăng dần + cross-check tầng 3 (⏳ Todo)

Hai việc làm nối tiếp trên cùng 1 file (`pipeline_trake.py`), nên để 1 người phụ trách xuyên suốt:

1. **Ràng buộc tăng dần đáng tin cậy hơn**: thay vì chọn từng mốc độc lập rồi hy vọng thứ tự đúng,
   tìm cả chuỗi N mốc cùng lúc sao cho vừa tăng dần vừa tổng điểm cao nhất (quy hoạch động); video nào
   không tìm được chuỗi hợp lệ thì loại hẳn, không trả về kết quả sai thứ tự.
2. **Cross-check tầng 3** (sau khi (1) xong): khi 2 video ứng viên hàng đầu có điểm sát nhau, dùng
   danh sách object đã detect sẵn (miễn phí, không LLM) đối chiếu với từ khoá trong mô tả sự kiện để
   chọn đúng video hơn — tái dùng logic cross-check đã có ở nhánh Q&A.

Success: chạy lại ví dụ demo có sẵn trong `pipeline_trake.py`, xác nhận `frame_id` trả về luôn tăng
dần; benchmark TRAKE trên `eval_ground_truth.json` (cần có câu TRAKE trước — xem mục 0) không tệ đi.

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

Success: nộp đợt 4 với cả 5 cải tiến đã qua benchmark xác nhận không regress so với đợt 1.

---

## Blockers / Risks

- **Ngưỡng margin ở Phase 3/4 chưa có số liệu để hiệu chỉnh** cho tới khi Phase 0 (mở rộng
  `eval_ground_truth.json`, đặc biệt câu TRAKE) hoàn tất — đây là việc chuẩn bị ưu tiên cao nhất, có
  thể chặn benchmark thật của Phase 4 nếu làm chậm.
- **Rotation key Gemini vẫn chưa nhớ trạng thái key đã cạn quota giữa các lần khởi động** (bài học
  đợt 1, xem [EXPERIMENT.md](EXPERIMENT.md)) — chưa có Phase nào ở trên xử lý việc này; cân nhắc thêm
  nếu còn thời gian sau Phase 6, không bắt buộc cho đợt 4.
- **EasyOCR (Phase 5) là dependency mới hoàn toàn** — rủi ro cài đặt/tải model lần đầu chậm hơn dự
  kiến trên máy nào đó trong nhóm; đã đưa vào mục chuẩn bị ngày 1 để giảm rủi ro này.
