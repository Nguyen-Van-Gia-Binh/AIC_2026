# AIC2026 — Project Plan

> Cách đọc file này: mỗi Phase là một cột mốc lớn. Trong phiên làm việc mới, đọc
> Phase nào đang 🔄/⏳ và mục Blockers trước, đó là việc cần làm tiếp theo.
> Chi tiết "làm thế nào" không ghi ở đây — xem [ARCHITECTURE.md](ARCHITECTURE.md)
> và code. File này chỉ nối thêm / tick checkbox qua từng phiên, không viết lại.

## Lịch sử

**Lần 1 (Phase 1–4, xong ~19/8/2026)** — chi tiết đầy đủ ở
[docs/_archive/PLAN_Lan1.md](docs/_archive/PLAN_Lan1.md). Dựng nền tảng: retrieval CLIP
`clip-ViT-B-32` + 3 pipeline KIS/QA/TRAKE tuyến tính, agent LLM layer, Gradio UI 4 tab, submission
CSV/ZIP builder + validator, 1 đợt hardening theo code review. Nộp đợt 1: **5.6/10** — nguyên nhân
chính không phải embedding yếu mà là **cạn quota Gemini free-tier** giữa lúc thi.

**Lần 2 (Phase 1–6 round 2, 22/8→04/09/2026)** — chi tiết đầy đủ ở
[docs/_archive/PLAN_Lan2.md](docs/_archive/PLAN_Lan2.md). Team 4 người, 5 cải tiến chạy song song
sau bài học đợt 1:

- **Phase 1** `AIC_MODE=test|contest` — chọn model LLM theo chế độ, rẻ lúc dev/mạnh lúc nộp thật.
- **Phase 2** Rewrite thêm rule xử lý phủ định ("không có X" → mô tả dương tính cho CLIP).
- **Phase 3** Risk-aware ranking (`rerank.py`) — "đặt cược" khi 1 video nổi bật rõ, "trải rủi ro"
  khi không; benchmark cuối R@100 tăng 0.522→0.565 trên 23 câu KIS+QA, không regression.
- **Phase 4** TRAKE: DP tìm chuỗi mốc tăng dần điểm cao nhất + cross-check tầng 3 bằng object
  detect khi 2 video top sát điểm.
- **Phase 5** OCR on-demand (PaddleOCR) cho Q&A cần đọc chữ/số, chỉ chạy khi câu hỏi cần và chỉ
  trên vài ảnh candidate tốt nhất.
- **Phase 6** Checkpoint benchmark (bộ eval mở rộng lên 33 câu: 18 KIS + 5 QA + 10 TRAKE) — xác
  nhận không regression toàn bộ Phase 3–5. **Còn 2 việc chưa xong khi archive** (carry-forward
  xuống dưới): Dry-run contest mode, Freeze 03/09.
- Đồng thời đổi kiến trúc LLM: bỏ multi-provider fallback (Gemini/Groq/NVIDIA) của lần 1, chuyển
  sang **1 provider OpenRouter duy nhất** (`OPENROUTER_API_KEY`/`OPENROUTER_MODEL`/
  `OPENROUTER_MODEL_CONTEST`).

**Cập nhật 2026-08-26 — [docs/decisions-log.md](docs/decisions-log.md)/[docs/decisions-log.md](docs/decisions-log.md) đã dựng lại:**
2 file này chưa từng thật sự lên GitHub — bị chặn bởi `.gitignore` từ đầu (đã gỡ khỏi `.gitignore`),
và máy chứa bản gốc đã bị reset trước khi kịp phát hiện. Đã tổng hợp lại nội dung có thể suy ra được
từ các trích dẫn còn sót trong `docs/_archive/PLAN_Lan2.md`/`ARCHITECTURE.md`/
`docs/superpowers/plans/` — **không phải nguyên văn bản gốc**, cả 2 file đều ghi rõ banner + mục TODO
cho phần chưa dựng lại được. Link trong 2 file archive giờ trỏ đúng, không còn chết.

## Việc carry-forward từ Lần 2 (chưa xong khi archive 2026-08-26)

- [ ] **Dry-run contest mode** — chạy trọn cả 3 pipeline (KIS/QA/TRAKE) với `AIC_MODE=contest`,
  xác nhận model mạnh hơn (`OPENROUTER_MODEL_CONTEST`) thật sự được dùng và hệ thống không chậm/lỗi
  bất thường trước khi nộp. Runbook đầy đủ ở cuối Phase 6 trong
  [docs/_archive/PLAN_Lan2.md](docs/_archive/PLAN_Lan2.md).
- [ ] **Freeze 03/09** — mốc quy trình của round 2 (không merge thay đổi mới, chỉ sửa lỗi chặn) —
  xác nhận lại còn áp dụng hay đã lùi lịch trước khi coi round 2 thật sự đóng.

## Phase 7: Sửa chấm điểm eval khớp BTC + gom `tests/`

Cơ chế chấm điểm so model/phương án chưa bám đúng công thức BTC (§2.1–2.2); test/eval nằm rải rác.

- [X] **Nới khoảng ground truth** — `tests/eval/widen_gt_windows.py` (mới): mọi entry
  `gt_frame_start == gt_frame_end` (KIS/QA/event TRAKE) nới ra keyframe lân cận từ `map-keyframes`.
  Đã chạy (27 khoảng). **Cần dò tay lại** — vài khoảng còn rộng do keyframe thưa.
- [X] **Fix `score_trake` trong `run_eval.py`** — bỏ cách cũ (mean-trên-event, không cổng video,
  không thứ tự). Giờ: dựng ứng viên (video + N frame, chuỗi `frame_idx` không giảm bằng DP) có xếp
  hạng → cổng video (`v ≠ GT` → 0) → `R@k = max` trên k ứng viên đầu. Vẫn retrieval-only, không LLM.
  Thêm cột `Final` = (1/5)Σ R@k. Header report viết lại trung thực từng loại.
- [X] **Harness end-to-end mới** — `tests/e2e/score_pipelines.py`: chạy `run_kis/run_qa/run_trake`
  production → Final Score BTC thật, **QA có chấm answer** (`answer_matches`, substring 2 chiều so với
  `gt_answers`). Cờ `--types/--limit/--no-rewrite/--self-test`. Ghi `docs/reports/eval_e2e_scores.md`.
- [X] **Schema** `gt_answer` (string) → `gt_answers` (list) — 5 câu QA + file draft + `EVAL_GUIDE.md`.
- [X] **Gom `tests/`** (đổi từ `queries/`): `Test/` (harness đường production: `test_phase3–6`,
  `score_pipelines`, `test_smoke_tools`/`test_smoke_pipelines` gộp từ `test_day*`), `Eval/`
  (`run_eval`/`multi_index`/`lookup_frame`/`widen_gt_windows` + ground truth + `EVAL_GUIDE.md`),
  `README.md` ở gốc. `git mv` giữ lịch sử; `retrieve.py` repoint import `multi_index` sang vị trí mới.
- [X] **Chạy lại `run_eval.py` đủ 5 model** + `score_pipelines.py` cho QA/TRAKE (cần API key) sau khi
  user dò tay xong ground truth — cập nhật `docs/reports/eval_baseline_comparison.md` / `docs/reports/eval_e2e_scores.md`.

## Phase 8: Tách Frontend/Backend — FastAPI + React (vòng sau)

Bối cảnh đầy đủ: `docs/superpowers/specs/2026-08-27-multiagent-chat-architecture-design.md`.
Roadmap 4 phase con (thứ tự do user chốt 2026-08-27): 1) khung FastAPI + frontend React theo mockup
Claude Design (plan: `docs/superpowers/plans/2026-08-27-phase1-fastapi-react-frontend-skeleton.md`)
2) LangGraph AI graph 3) nối Agent Backend hoàn chỉnh vào frontend mới 4) pytest suite.

- [X] Phase con 1 — khung FastAPI (`scripts/api/`) + frontend React (`frontend/`) theo mockup
  (xem plan link ở trên). Backend bridge sang `run_kis/run_qa/run_trake` + `build_submission.py`,
  giữ 2 luật single-call-site (LLM chỉ ở `config.py:call_llm()`, ghi CSV/ZIP chỉ ở
  `build_submission.py`). Frontend 4 màn KIS/Q&A/TRAKE/Hàng đợi chạy dữ liệu thật qua proxy Vite;
  màn Chat để nút disabled (Phase con 2). Gradio `scripts/app.py` đã chuyển vào `docs/_archive/app_gradio.py`.
- [X] Phase con 1.5 — parity với UI Gradio + luồng xem video kiểm chứng keyframe (KIS).
  Plan: `C:\Users\admin\.claude\plans\rustling-bouncing-eclipse.md`. Sửa lỗi thiếu
  `get_keyframe_path`/`get_neighbor_frames` trong `retrieve.py` (backend không khởi động được);
  thêm router `scripts/api/routers/videos.py` (`GET /api/videos/{id}` kèm Range + `/meta` fps);
  frontend: chip gợi ý rewrite (KIS/QA/TRAKE), thanh kéo top-k, đổi font sang Be Vietnam Pro
  (offline, `@fontsource`), sửa padding/goc textarea (lỗi "chữ dính sát"), ô sửa tay frame_id
  (KIS shortlist + TRAKE mỗi mốc), `VideoVerifier` (tua theo frame + phím tắt) thay ảnh tĩnh ở
  màn chi tiết keyframe.
- [ ] Phase con 1.6 — làm lại UI KIS theo góp ý: (1) bỏ panel "Danh sách nộp" bên trái — lưới kết
  quả chính là danh sách nộp, kéo thả card trực tiếp trên lưới để đổi thứ hạng, nút × để loại;
  (2) Query ID + "Thêm vào hàng đợi" gom thành thanh nổi `position: fixed` góc dưới-phải; (3) trong
  màn video, nút đổi thành "Cập nhật vị trí #N với frame hiện tại" — ghi đè frame/thời gian đang tua
  vào đúng card đó (không tạo dòng mới); (4) dải luớt TOÀN BỘ keyframe của video (cuộn ngang,
  `GET /api/keyframes/{id}/all` + `get_all_frames` trong `retrieve.py`) thay dải ±5, và ô nhập
  `pts_time`/`frame_id` trong bảng metadata để nhảy nhanh (Enter / nút ⏩).
- [ ] Phase con 1.7 — làm lại UI Q&A theo cùng khuôn KIS: header 3 vùng compact (mô tả cảnh + chip
  rewrite | câu hỏi + đáp án chung tự đồng bộ mọi card | slider top-k + Run + độ tin cậy/số vòng);
  lưới kết quả full-width là danh sách nộp (card có nhãn đáp án); màn soi video riêng
  `QaKeyframeDetail` (video + dải keyframe + nhảy nhanh + ô đáp án frame + nút ⭐ đặt Rank #1 / 🌐 áp
  đáp án cho toàn bộ / ✓ cập nhật frame); widget "🚀 Chốt & Thêm vào hàng đợi" nổi cố định góc
  dưới-phải, phím tắt Ctrl/Cmd+Enter. Không cần đổi backend (dùng lại `qa/run`, `keyframes/{id}/all`,
  `videos/{id}/meta`).
- [ ] Phase con 1.8 — làm lại UI TRAKE theo cùng khuôn: header 2 cột (mô tả tổng quát + chip rewrite |
  danh sách khoảnh khắc đánh số 1..N) + thanh điều khiển (slider top-k video 3–10 + Run TRAKE); kết quả
  là các thẻ video xếp dọc, kéo-thả (drag handle ⋮⋮) hoặc nút ▲/▼ để đổi thứ tự ưu tiên, mỗi thẻ có
  nút "🚀 Nộp riêng video này"; thân thẻ = dải timeline N mốc (thumbnail + ô sửa `frame_id` + `pts_time`
  quy đổi, viền đỏ + ⚠️ khi lệch thứ tự `frame_k > frame_{k+1}`); bấm 1 mốc → màn soi video riêng
  `TrakeKeyframeDetail` (video + dải keyframe + nhảy nhanh, hiện frame mốc trước/sau, nút "✓ Cập nhật
  frame cho Mốc này"); widget "🚀 Chốt & Nộp vào hàng đợi" nổi cố định góc dưới-phải (ghi nhận đúng
  thứ tự thẻ đã sắp), phím tắt Ctrl/Cmd+Enter. Không đổi backend (dùng lại `trake/run`,
  `keyframes/{id}/all`, `videos/{id}/meta`).
- [ ] Phase con 1.9 — màn Chat Mock-First (GĐ1 của spec `2026-08-28-chat-screen-ui-design.md`): bật
  tab Chat, dựng toàn bộ UI hội thoại đa tác vụ với **fixture tĩnh 3 kịch bản** (KIS `L21_V001` /
  Q&A `L22_V001` / TRAKE `L25_V001`, dùng `video_id`+`frame_idx` thật) — `src/mock/chatScenarios.ts`
  (`pickScenario` heuristic keyword + `buildAssistantMessage`, có nhận diện "lượt tiếp nối"). Rich
  Card: `AgentTraceAccordion` + `KisResultCards` / `QaResultBanner` (sửa đáp án) / `TrakeSequenceView`
  (sửa `frame_id` + ⚠️ lệch thứ tự). Bấm thumbnail → `ChatDrawer` trượt phải dùng chung
  `VideoVerifier` (thêm phím `A`/`D` = ±1 frame) + dải keyframe; "📌 Cập nhật Frame … vào vị trí #k"
  → card cập nhật + nhãn "Đã chỉnh sửa"; "📥 Chốt vào Hàng đợi nộp" → `api.addToQueue` + toast. KIS/
  Q&A/TRAKE tab giữ nguyên. Không đổi backend. GĐ2 chỉ đổi `buildAssistantMessage` → `api.chatMessage`.
- [ ] Phase con 2 — AI Graph (LangGraph)
- [ ] Phase con 3 — nối Agent Backend hoàn chỉnh vào frontend
- [ ] Phase con 4 — pytest suite + hoàn thiện end-to-end

Đánh dấu `[x]` cho Phase con 1 chỉ sau khi Task 11 Step 3 (walkthrough end-to-end trên trình duyệt)
thật sự chạy qua.

## Phase 9: Bản đặc tả kiểm soát chất lượng thuật toán (2026-08-28)

Triển khai BẢN ĐẶC TẢ §2–§6. Mọi bước mới đều có công tắc bật/tắt để đo trước–sau.

- [x] **§2 Hybrid Retrieval** — `tools/sparse_index.py` (BM25 trên Objects JSON + caption, cache
  `data/extracted/bm25_index/`, build 1 lần ~3.5 phút: 171.819 doc / 5.539 term), `tools/fusion.py`
  (RRF k=60, w=0.75/0.25), `retrieve.hybrid_retrieve()`. Chưa build cache → tự chạy dense-only.
- [x] **§3 KIS** — `tools/query_expand.py` (Multi-Aspect, template tất định),
  `tools/temporal_nms.py` (Δt ≥ 3s), `rerank.py` (+NMS, +trần 50% cho video đặt cược, tách
  `score_key` cho xếp hạng khỏi `margin_key` cho quyết định đặt cược). Bonus OCR/caption 0.15/0.07
  đã có sẵn từ trước.
- [x] **§4 Q&A** — `pipeline_qa.answer_by_video_cluster()` (mỗi video trong top-3 cụm có answer
  riêng, hết cảnh "1 đáp án của video top-1 gán cho cả 100 dòng"); `answer_qa.canonicalize_answer()`
  + `ocr_direct_answer()` + cổng chống ảo giác (`is_non_answer`).
- [x] **§5 TRAKE** — Multi-Event Coverage Pooling, DP tăng NGHIÊM NGẶT, cổng 2 tầng (rule miễn phí
  cho cả 20 video → LLM chỉ khi margin #1–#2 ≤ 0.02, tối đa 3 video). Trước đây gọi LLM cho tất cả
  candidate.
- [x] **§6 Regression Guard** — Tầng 1: `run_eval.py --hybrid/--expand/--nms/--strict-dp/
  --coverage-pool`. Tầng 2: `score_pipelines.py --save-baseline` + tự cảnh báo khi Final tụt > 0.01
  (thoát code 1).
- [ ] **Chốt baseline E2E đầy đủ** — `score_pipelines.py --save-baseline` (cả 3 loại) để các lần sau
  có mốc so sánh.

Số đo (xem [docs/decisions-log.md](docs/decisions-log.md) để biết vì sao chọn mặc định như hiện tại).

---

## Phase 10: Kiến trúc v2 — GPU, định vị dưới keyframe, hybrid 4-leg (chốt 2026-08-28)

Cơ sở đo đạc và lý do → [ARCHITECTURE.md §6](ARCHITECTURE.md#6-kiến-trúc-v2-phase-10--chốt-2026-08-28).
Xếp theo lợi ích/chi phí. Mọi hạng mục đều phải có công tắc bật/tắt và đo trước–sau bằng Regression
Guard của Phase 9.

| # | Hạng mục | Lợi ích kỳ vọng | Chi phí | File động đến |
|---|----------|-----------------|---------|---------------|
| 0 | torch bản CUDA | **chặn đứng mọi thứ dưới** | 1 buổi | `.venv-gpu/`, `requirements.txt` |
| 1 | `refine_frame.py` | TRAKE 0,12 → có thể 0,5–0,7 | 1–2 ngày | tool mới, `pipeline_trake.py`, `pipeline_kis.py` |
| 2 | Mở rộng ground truth | mọi số đo sau đó mới đáng tin | 1–2 ngày, không cần GPU | `tests/eval/` |
| 3 | `model_registry.py` | điều kiện cần của #4,#6 (8 GB VRAM) | 1 ngày | tool mới, `retrieve.py`, `ocr_read.py`, `vlm_ocr_caption.py` |
| 4 | `vlm_rerank.py` cho KIS | đòn bẩy R@1 lớn nhất còn lại | 1 ngày | tool mới, `pipeline_kis.py` |
| 5 | 3 cải tiến Q&A | Q&A phải đúng cả 3 yếu tố, sai sót nhân nhau | 0,5 ngày, **không cần GPU** | `pipeline_qa.py`, `answer_qa.py` |
| 6 | `text_index.py` (BGE-M3) | leg thứ 3+4 của hybrid | 2 ngày | tool mới, `fusion.py`, `retrieve.py` |
| 7 | Phân bổ 100 dòng theo bảng giá trị hạng | 0 chi phí, thuần xếp lại | 0,5 ngày | `rerank.py`, `temporal_nms.py` |
| 8 | Ensemble `features_dfn` + `features_jina` | **0 GPU** — đã precompute sẵn trên đĩa | 0,5 ngày | `retrieve.py`, `fusion.py` |
| 9 | Khử hubness (QB-Norm / Dual-Softmax) | thường +2–5 R@1, không cần train | 1 ngày | `retrieve.py` |

### 10.0 — [ ] CHẶN ĐỨNG: chuyển sang torch bản CUDA

Máy có **RTX 5050 Laptop 8151 MiB, driver 592.82** nhưng venv cài `torch 2.13.0+cpu` — GPU chưa từng
được dùng. RTX 5050 là Blackwell (sm_120), **bắt buộc** wheel `cu128`/`cu129`; bản `+cpu` và các bản
CUDA cũ đều không nhận card này.

- [ ] Dựng `.venv-gpu/` **song song**, không đụng `.venv/` đang chạy được
- [ ] `pip install torch --index-url https://download.pytorch.org/whl/cu129`
- [ ] Xác minh `torch.cuda.is_available()` và `torch.cuda.get_device_capability()` ra `(12, 0)`
- [ ] Xác minh SigLIP so400m chạy được fp16 trên GPU và đo throughput thật (ảnh/giây)
- [ ] **Xác minh riêng rủi ro đã biết**: `paddlepaddle` (CPU thuần, KHÔNG `-gpu`) + VietOCR (GPU) +
      torch-CUDA cùng một process không gây `WinError 127` — xem [docs/decisions-log.md](docs/decisions-log.md).
      Torch chạy CUDA làm rủi ro DLL này **tăng**, không giảm.
- [ ] Chỉ khi cả 5 mục trên xanh mới đổi `.venv/` chính

### 10.1 — [ ] `tools/refine_frame.py` — định vị dưới mức keyframe

Hạng mục có lợi ích lớn nhất trong toàn Phase: gỡ trần 0,12 của TRAKE (xem ARCHITECTURE.md §6.1).

- [ ] `refine(video_id, frame_idx_center, query_text, half_window=None) -> frame_idx`
- [ ] Decode dải frame gốc từ `data/extracted/video/**/{video_id}.mp4` ở fps thật (đọc fps từ
      `map-keyframes/{video_id}.csv`, **không đoán 30fps** — dữ liệu thật có 25.0 / 26.44 / 29.97 / 30.0)
- [ ] `half_window` mặc định = nửa gap keyframe cục bộ (trung vị 80 frame ⇒ ~±40)
- [ ] Encode SigLIP theo batch, chấm với `query_text`
- [ ] **Làm mượt (moving average ~15 frame) rồi lấy TÂM đoạn liên tục vượt ngưỡng — KHÔNG argmax**
      (lý do → ARCHITECTURE.md §6.4)
- [ ] Nối vào `pipeline_trake.py` sau DP (cho từng mốc của 1–3 video ứng viên đầu)
- [ ] Nối vào `pipeline_kis.py` cho top-20 dòng, sau `rerank`, trước `build_submission`
- [ ] Công tắc `AIC_REFINE=0|1` (mặc định 0 cho tới khi đo xong), theo tiền lệ `AIC_RETRIEVE_MODEL`
- [ ] Đo trước–sau bằng `score_pipelines.py --types trake`

### 10.2 — [ ] Mở rộng ground truth (33 câu là quá ít để tin bất kỳ số đo nào)

Mọi tham số hiện tại (`w_dense=0,75`, `k=60`, `Δ≤0,02`, `partial_ratio≥85`, `MARGIN_THRESHOLD`,
`SPREAD_MAX_PER_VIDEO`) đang chốt trên 33 mẫu — sai số lấy mẫu ở cỡ đó lớn hơn hầu hết mức cải thiện
định đo. Regression Guard chạy trên 33 câu là guard giả. **Hai bộ, hai mục đích khác nhau:**

- [ ] **Bộ tổng hợp (tinh chỉnh tham số, cần nhiều mẫu)** — lấy caption Vintern của một keyframe làm
      query, chính keyframe đó là đáp án. Hàng nghìn câu miễn phí. Ghi rõ trong `EVAL_GUIDE.md` rằng
      bộ này **lệch phân phối** so với query BTC (caption máy sinh ≠ mô tả người viết) nên chỉ dùng
      để so sánh tương đối giữa hai cấu hình, **không** để báo cáo điểm tuyệt đối.
- [ ] **Bộ nhãn tay (kiểm chứng cuối, cần đúng phân phối)** — dùng đề `THUNGHIEM-bo-de-thi` (42 câu) +
      `sotuyen1_bo_de_thi.csv` (45 câu); VLM đề xuất ứng viên, người duyệt qua UI. Mục tiêu 150–300 câu.
- [ ] Bổ sung breakdown theo loại truy vấn (KIS/QA/TRAKE) vào `run_eval.py`

### 10.3 — [ ] `tools/model_registry.py` — quản lý vòng đời model cho 8 GB VRAM

SigLIP (1,7 GB) + SigLIP2 (1,7 GB) + BGE-M3 (1,1 GB) + VietOCR **không cùng nằm vừa 8 GB**. Pattern
singleton hiện tại ở `retrieve.py`/`vlm_ocr_caption.py`/`ocr_read.py` giữ model sống mãi trong process
⇒ thêm bất kỳ model nào cũng OOM.

- [ ] `acquire(name)` / `release(name)`, giải phóng model ít dùng nhất + `torch.cuda.empty_cache()`
- [ ] Ngân sách VRAM đọc từ env, mặc định chừa ~1 GB cho phân mảnh
- [ ] Chuyển 3 module singleton hiện có sang registry, **giữ nguyên chữ ký hàm public**
- [ ] Chế độ kép: UI chỉ giữ SigLIP thường trú; đường sinh bài nộp chạy batch nhiều giai đoạn

### 10.4 — [ ] `tools/vlm_rerank.py` — VLM rerank top-50 cho KIS

Lật quyết định "KIS không LLM" (ARCHITECTURE.md §6.4). Dùng **Gemini 2.5 Flash Vision qua
`config.py:call_llm()`** — không chiếm VRAM, không phá quy tắc "chỉ config.py gọi LLM".

- [ ] Chấm từng ứng viên "ảnh khớp mô tả tới mức nào, 0–10", trộn với điểm RRF
- [ ] ~2.200 lượt ảnh/gói đề (44 truy vấn × 50) — chạy song song có giới hạn, có retry
- [ ] Công tắc `AIC_VLM_RERANK=0|1`, mặc định 0
- [ ] **Không** thêm vòng lặp reflection — đúng một bước một chiều
- [ ] Đo chi phí API thật cho 1 gói đề trước khi bật cho bài nộp

### 10.5 — [ ] Ba cải tiến Q&A (rẻ nhất, không cần GPU)

Q&A phải đúng **cả** video, frame **và** answer nên sai sót nhân nhau.

- [ ] **Ghép câu HỎI vào truy vấn retrieval** — câu hỏi chứa thông tin thị giác ("người phụ nữ mặc
      váy đỏ", "cầm ly") hiện đang bị vứt đi, chỉ mô tả sự kiện được dùng để tìm
- [ ] **Tái xếp hạng frame theo đáp án đã sinh** — sinh đáp án trước, rồi xếp lại frame theo "frame
      này có chứng minh được đáp án không", đẩy frame trúng cửa sổ đáp án lên đầu
- [ ] **Phòng hộ biến thể đáp án trên các dòng** — cùng video, các dòng mang biến thể khác nhau
      ("15" / "mười lăm" / "15 người"). BTC khớp **theo ngữ nghĩa** (luật §2.1.2) nên lợi ích có thể
      nhỏ, nhưng chi phí bằng 0. Xếp biến thể tự tin nhất lên trước theo bảng giá trị hạng (#7).

### 10.6 — [ ] `tools/text_index.py` — leg dense-text (caption) + leg ASR (mức video)

- [ ] Encode 177K caption Vintern-1B bằng **BGE-M3** (~10–15 phút GPU) → `rank_caption(d)` mức frame
- [ ] Encode segment ASR PhoWhisper → xếp hạng **VIDEO** → mọi frame của video V thừa hưởng
      `rank_asr(V)` (lý do phải ở mức video, không mức frame → ARCHITECTURE.md §6.4)
- [ ] Mở rộng `fusion.reciprocal_rank_fusion()` lên 4 số hạng, trọng số cấu hình được
- [ ] Đo xem sparse-từ-vựng của BGE-M3 có thay được BM25 tự viết trong `sparse_index.py` không —
      nếu hơn thì bỏ bớt một hệ thống, nếu không thì giữ cả hai
- [ ] Cân nhắc trọng số RRF **thích ứng theo loại query** thay vì cố định 0,75/0,25: query có
      chữ/số trong ngoặc kép → nghiêng sparse; query có tên riêng/địa danh → nghiêng ASR; query tả
      cảnh thuần thị giác → nghiêng dense

### 10.7 — [ ] Phân bổ 100 dòng theo bảng giá trị hạng

Không tốn compute, chỉ là xếp lại. Bảng giá trị: hạng 1 → 1,00; 2–5 → 0,80; 6–20 → 0,60; 21–50 →
0,40; 51–100 → 0,20 (ARCHITECTURE.md §6.1).

- [ ] Dồn công sức vào dòng 1–20 (phải là 20 giả thuyết **thực sự khác nhau**); dòng 21–100 là vé số
- [ ] **Đồng chỉnh `SPREAD_MAX_PER_VIDEO` + `MIN_TIME_GAP` của NMS cùng lúc với #10.1**: hai tham số
      này hiện mặc định giả thuyết "cửa sổ `[s,e]` dài" — một ẩn số chưa xác định. `refine_frame` nâng
      `q` (xác suất frame trúng cửa sổ) lên, và chỉ khi `q` cao thì việc rải rộng mới đúng.
      **Không chỉnh riêng lẻ từng tham số.**

### 10.8 — [ ] Ensemble backbone dense (0 chi phí GPU)

`data/extracted/features_dfn/` và `features_jina/` **đã precompute xong** và đang nằm không.

- [ ] RRF giữa siglip + dfn (+ jina) cho KIS; đo từng tổ hợp bằng `run_eval.py`
- [ ] Chỉ giữ tổ hợp nào thật sự hơn baseline 1 model trên bộ GT đã mở rộng ở #10.2
- [ ] Lưu ý RAM: mỗi ma trận 177K × 1152 float32 ≈ 800 MB — nạp nhiều backbone cùng lúc cần đi qua
      `model_registry` (#10.3) hoặc dùng memmap

### 10.9 — [ ] Khử hubness (QB-Norm / Dual-Softmax)

Trong không gian SigLIP tồn tại ảnh "hub" gần với **mọi** query và chiếm chỗ top-k của mọi truy vấn.
Chuẩn hoá điểm theo một querybank dựng sẵn (từ caption có sẵn) thường được +2–5 R@1, **không cần train**.

- [ ] Dựng querybank từ caption Vintern (mẫu ngẫu nhiên vài nghìn câu)
- [ ] Cài QB-Norm và/hoặc Dual-Softmax ở `retrieve.py`, công tắc riêng
- [ ] Đo trước–sau; hạng mục này thuần thực nghiệm, bỏ nếu không thấy hơn

### Việc chưa xếp lịch (đã bàn, chưa chọn làm)

- **Tăng dày keyframe offline cho toàn dataset** — encode lại ở mật độ dày hơn (mỗi 5–10 frame).
  Giải quyết cùng vấn đề với #10.1 nhưng ở tầng index, tốn ~40 phút GPU/backbone cộng chi phí decode
  toàn bộ video. Đã chọn đi hướng tinh chỉnh runtime (#10.1) trước vì rẻ hơn nhiều lần.
- **Ước lượng độ dài `[s,e]` thật của KIS** — ẩn số quan trọng nhất còn lại; luật BTC không định
  nghĩa. Nếu moi được từ kết quả vòng 1 hoặc phản hồi BTC thì chốt được ngay cả #10.1 lẫn #10.7.

---

## Pha chuẩn hoá repo (2026-08-31) — ✅ XONG

Chuẩn hoá cấu trúc/tài liệu, **bảo toàn hành vi tuyệt đối**. Spec:
[docs/superpowers/specs/2026-08-31-repo-standardization-design.md](docs/superpowers/specs/2026-08-31-repo-standardization-design.md).
Nghiệm thu bằng `tests/e2e/golden_kis_snapshot.py --check` (digest `81448536a4f1245f`) sau mỗi bước.

- [x] `scripts/` về đúng 4 bucket: `agent` / `api` / `submit` / `offline`
- [x] Tách `retrieve.py` → `index_store` + `retrieve` + `hybrid` + `frames`
- [x] Tách `answer_qa.py` → `qa_prompts` + `qa_classify` + `qa_normalize`
- [x] Tách DP của TRAKE → `tools/trake_align.py`
- [x] `ocr_lookup.py` → `objects_lookup.py` (tên cũ nói dối: nó không làm OCR)
- [x] `test_eval/` → `tests/{unit,eval,e2e,data}` + `conftest.py`
- [x] Self-test → `tests/unit/` (pytest, 59 test / 124 assert, ~10s, không cần data/API)
- [x] Gộp `DECISION.md` + `EXPERIMENT.md` → `docs/decisions-log.md`; `docs/` chia 8 nhóm
- [x] Sửa bug nạp index 2 bản còn sót ở 3 chỗ (`test_smoke_tools`, `test_smoke_pipelines`, `index_ocr_es`)

---

## Pha 2 — Sửa lỗi hành vi (CHƯA LÀM, ưu tiên theo thứ tự)

> Cố ý tách khỏi pha chuẩn hoá: mỗi mục dưới đây **đổi hành vi**, nên phải chạy
> `golden_kis_snapshot.py --save` chốt mốc mới sau khi sửa xong từng mục.

### P2.1 — [ ] `_QA_MODEL_TAG` mặc định đang là `siglip`, mọi tài liệu ghi `siglip2`

`index_store.py` đặt mặc định Q&A là `siglip`, trong khi `pipeline_qa.py` docstring, ARCHITECTURE và
bake-off đều nói `siglip2`. Bake-off 33 query: **QA Final siglip2 = 0.440 vs siglip = 0.120**. Thay
đổi này lọt vào ở commit `ab0ab32` — nhiều khả năng là tai nạn merge, không phải quyết định.
**Đây là chênh lệch lớn nhất còn lại trong hệ thống.**

### P2.2 — [ ] TRAKE `top_k_video=20` khoá cứng R@50 = R@100 = R@20

`results` ≤ 20 dòng nên 2 trong 5 hạng của Final Score bị khoá ở giá trị hạng 20. Mở rộng lên 100
**không tốn một lượt LLM nào** (giai đoạn 2 chỉ là nhân ma trận trong 1 video + DP O(N·K²); cổng LLM
vẫn chỉ mở cho top-3). Món rẻ nhất trong danh sách.

### P2.3 — [ ] `strict_monotonic` loại thẳng video thay vì hạ tiêu chuẩn

`chain is None` → `continue`, video biến mất hoàn toàn. Nhưng keyframe cách nhau ~2,5–3 s, còn một
chuỗi động tác nhanh (giậm nhảy → qua xà → tiếp đất) có thể gói trong <3 s ⇒ hai mốc rơi vào **cùng
một keyframe** ⇒ video đúng bị loại vì lấy mẫu thưa, không phải vì sai. Đã có sẵn `strict=False`;
nên rơi về đó thay vì bỏ video.

### P2.4 — [ ] `_bet_mode` chấm điểm ứng viên đào sâu khiến chúng không bao giờ lọt top-100

Ứng viên đào sâu được gán `W_DENSE/(RRF_K + len(hits) + 1 + i)` ≈ 0.0013369, thấp hơn **mọi** ứng
viên trong pool 500 (ứng viên tệ nhất ≈ 0.0013393). Với pool=500 > top_k=100, chúng không bao giờ
xuất hiện — trong khi vẫn tốn một lượt encode + nhân ma trận mỗi query. Ý tưởng đặt cược đúng; cách
gán điểm làm nó chết lâm sàng.

### P2.5 — [ ] OCR chết hoàn toàn

`ocr_read` tải config VietOCR từ `vocr.vn` — **chứng chỉ SSL đã hết hạn**. Cache offline
`data/extracted/ocr_text_paddleocr/` cũng **chưa build**. Hệ quả: OCR Direct Overwrite không bao giờ
kích hoạt, gợi ý OCR không bao giờ vào prompt Vision, `rerank_by_ocr` chỉ còn khớp caption. Cần pin
config VietOCR về máy (hoặc build cache offline) trước ngày thi.

### P2.6 — [ ] Q&A chỉ trích answer riêng cho 3 cụm video đầu

`MAX_ANSWER_CLUSTERS = 3`, nên ~97/100 dòng mang `best_answer` của video **khác**. Với luật "sai
answer = 0 điểm dòng đó", R@20/R@50/R@100 của Q&A bị khoá vào 3 video đầu — khớp đúng với QA e2e
phẳng 0.200 ở mọi k. Hướng rẻ: các cụm ngoài top-3 chỉ chạy Tầng 1 (objects, 1 lượt text LLM).

### P2.7 — [ ] `MARGIN_THRESHOLD = 0.012` hiệu chỉnh trên thang đo của model đã retire

Comment tự khai là hiệu chỉnh trên cosine CLIP (~0,28–0,31), nhưng CLIP đã retire và cosine SigLIP
thực tế ~0,05–0,15. Đo thật trong phiên 2026-08-31 cho thấy margin điển hình 0,0039–0,0528 ⇒ ngưỡng
tuyệt đối 0,012 khiến chế độ ĐẶT CƯỢC bật ở phần lớn truy vấn. Quét lại bằng `tests/eval/run_eval.py`
(0 chi phí API).

### P2.8 — [ ] Production đang import từ `tests/`

`agent/tools/index_store.py` nạp `multi_index` từ `tests/eval/` — code chạy thật phụ thuộc code test.
Chuyển `multi_index.py` (+ `MODEL_REGISTRY`) vào `scripts/agent/tools/` và để `tests/eval/` import
ngược lại.

---

## Blockers / Risks

- **⛔ Độ dài thật của khoảng đáp án `[s,e]` cho KIS là ẩn số** — luật BTC không định nghĩa cách dựng
  nó; ví dụ minh hoạ trong luật là `[500, 510]` (11 frame), nhưng mục TRAKE lại *lưu ý thêm* rằng
  cửa sổ của TRAKE "rất ngắn, dưới 10 frame", ngụ ý cửa sổ KIS dài hơn. Ẩn số này chi phối trực tiếp
  `MIN_TIME_GAP` của Temporal NMS, `SPREAD_MAX_PER_VIDEO`, và việc `refine_frame` có cần bật cho KIS
  hay không. Hiện đang thiết kế **an toàn ở cả hai giả thuyết** (lấy tâm đoạn, không lấy argmax) —
  nhưng nếu moi được con số thật từ kết quả vòng 1 hoặc phản hồi BTC thì chốt được ngay cả Phase 10.1
  lẫn 10.7. **Ưu tiên tìm dữ kiện này.**
- **⛔ Xung đột DLL `paddlepaddle` × `torch-CUDA` trên Windows chưa được kiểm chứng lại sau khi đổi
  torch** — rủi ro đã xác nhận ở [docs/decisions-log.md](docs/decisions-log.md) (WinError 127, `cudnn_cnn64_9.dll`).
  Chuyển torch sang bản CUDA làm rủi ro này **tăng**. Đây là lý do Phase 10.0 bắt buộc dựng
  `.venv-gpu/` song song và xác minh trước, không nâng cấp thẳng `.venv/` đang chạy được.
- **Mọi tham số hiện tại đang chốt trên 33 câu ground truth** — sai số lấy mẫu ở cỡ đó lớn hơn hầu
  hết mức cải thiện định đo, nên Regression Guard của Phase 9 hiện là guard giả. Xem Phase 10.2.
- **Single LLM provider (OpenRouter)** — lần 2 đã bỏ multi-provider fallback (Gemini/Groq/NVIDIA)
  của lần 1 để đơn giản hoá, đổi lại mất lớp dự phòng khi rate-limit đúng lúc thi (chính là nguyên
  nhân mất điểm ở đợt 1). Cân nhắc lại trước round 3 nếu còn phụ thuộc 1 provider duy nhất.
- **Rotation key chưa nhớ trạng thái quota giữa các lần khởi động** (bài học đợt 1) — chưa Phase
  nào ở lần 2 xử lý việc này.
- **`docs/decisions-log.md` (gộp từ `DECISION.md`+`EXPERIMENT.md`, 2026-08-31) vừa dựng lại (2026-08-26) từ dữ liệu gián tiếp, không phải bản
  gốc** — máy cũ chứa bản thật đã bị reset. Xem mục TODO cuối mỗi file cho phần chưa dựng lại được;
  bổ sung dần khi nhớ ra hoặc gặp bài học/quyết định mới — đừng để mất máy lần nữa mới ghi lại.
- **2 việc Dry-run/Freeze của lần 2 chưa xác nhận đã xong** — xem mục carry-forward ở trên.
