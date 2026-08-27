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

**Cập nhật 2026-08-26 — [DECISION.md](DECISION.md)/[EXPERIMENT.md](EXPERIMENT.md) đã dựng lại:**
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

## Phase 7: Sửa chấm điểm eval khớp BTC + gom `test_eval/`

Cơ chế chấm điểm so model/phương án chưa bám đúng công thức BTC (§2.1–2.2); test/eval nằm rải rác.

- [X] **Nới khoảng ground truth** — `test_eval/Eval/widen_gt_windows.py` (mới): mọi entry
  `gt_frame_start == gt_frame_end` (KIS/QA/event TRAKE) nới ra keyframe lân cận từ `map-keyframes`.
  Đã chạy (27 khoảng). **Cần dò tay lại** — vài khoảng còn rộng do keyframe thưa.
- [X] **Fix `score_trake` trong `run_eval.py`** — bỏ cách cũ (mean-trên-event, không cổng video,
  không thứ tự). Giờ: dựng ứng viên (video + N frame, chuỗi `frame_idx` không giảm bằng DP) có xếp
  hạng → cổng video (`v ≠ GT` → 0) → `R@k = max` trên k ứng viên đầu. Vẫn retrieval-only, không LLM.
  Thêm cột `Final` = (1/5)Σ R@k. Header report viết lại trung thực từng loại.
- [X] **Harness end-to-end mới** — `test_eval/Test/score_pipelines.py`: chạy `run_kis/run_qa/run_trake`
  production → Final Score BTC thật, **QA có chấm answer** (`answer_matches`, substring 2 chiều so với
  `gt_answers`). Cờ `--types/--limit/--no-rewrite/--self-test`. Ghi `docs/eval_e2e_scores.md`.
- [X] **Schema** `gt_answer` (string) → `gt_answers` (list) — 5 câu QA + file draft + `EVAL_GUIDE.md`.
- [X] **Gom `test_eval/`** (đổi từ `queries/`): `Test/` (harness đường production: `test_phase3–6`,
  `score_pipelines`, `test_smoke_tools`/`test_smoke_pipelines` gộp từ `test_day*`), `Eval/`
  (`run_eval`/`multi_index`/`lookup_frame`/`widen_gt_windows` + ground truth + `EVAL_GUIDE.md`),
  `README.md` ở gốc. `git mv` giữ lịch sử; `retrieve.py` repoint import `multi_index` sang vị trí mới.
- [X] **Chạy lại `run_eval.py` đủ 5 model** + `score_pipelines.py` cho QA/TRAKE (cần API key) sau khi
  user dò tay xong ground truth — cập nhật `docs/eval_baseline_comparison.md` / `docs/eval_e2e_scores.md`.

## Phase 8: Tách Frontend/Backend — FastAPI + React (vòng sau)

Bối cảnh đầy đủ: `docs/superpowers/specs/2026-08-27-multiagent-chat-architecture-design.md`.
Roadmap 4 phase con (thứ tự do user chốt 2026-08-27): 1) khung FastAPI + frontend React theo mockup
Claude Design (plan: `docs/superpowers/plans/2026-08-27-phase1-fastapi-react-frontend-skeleton.md`)
2) LangGraph AI graph 3) nối Agent Backend hoàn chỉnh vào frontend mới 4) pytest suite.

- [X] Phase con 1 — khung FastAPI (`scripts/api/`) + frontend React (`frontend/`) theo mockup
  (xem plan link ở trên). Backend bridge sang `run_kis/run_qa/run_trake` + `build_submission.py`,
  giữ 2 luật single-call-site (LLM chỉ ở `config.py:call_llm()`, ghi CSV/ZIP chỉ ở
  `build_submission.py`). Frontend 4 màn KIS/Q&A/TRAKE/Hàng đợi chạy dữ liệu thật qua proxy Vite;
  màn Chat để nút disabled (Phase con 2). Gradio `scripts/app.py` giữ nguyên làm fallback.
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
- [ ] Phase con 2 — AI Graph (LangGraph)
- [ ] Phase con 3 — nối Agent Backend hoàn chỉnh vào frontend
- [ ] Phase con 4 — pytest suite + hoàn thiện end-to-end

Đánh dấu `[x]` cho Phase con 1 chỉ sau khi Task 11 Step 3 (walkthrough end-to-end trên trình duyệt)
thật sự chạy qua.

---

## Blockers / Risks

- **Single LLM provider (OpenRouter)** — lần 2 đã bỏ multi-provider fallback (Gemini/Groq/NVIDIA)
  của lần 1 để đơn giản hoá, đổi lại mất lớp dự phòng khi rate-limit đúng lúc thi (chính là nguyên
  nhân mất điểm ở đợt 1). Cân nhắc lại trước round 3 nếu còn phụ thuộc 1 provider duy nhất.
- **Rotation key chưa nhớ trạng thái quota giữa các lần khởi động** (bài học đợt 1) — chưa Phase
  nào ở lần 2 xử lý việc này.
- **`DECISION.md`/`EXPERIMENT.md` vừa dựng lại (2026-08-26) từ dữ liệu gián tiếp, không phải bản
  gốc** — máy cũ chứa bản thật đã bị reset. Xem mục TODO cuối mỗi file cho phần chưa dựng lại được;
  bổ sung dần khi nhớ ra hoặc gặp bài học/quyết định mới — đừng để mất máy lần nữa mới ghi lại.
- **2 việc Dry-run/Freeze của lần 2 chưa xác nhận đã xong** — xem mục carry-forward ở trên.
