# AIC2026 — Session Log

> Chỉ nối thêm sau mỗi phiên, không viết lại các phiên cũ. Ghi kết quả, không ghi lại toàn bộ hội thoại.

## Session #1 — 2026-08-19
**Goal**: Xây baseline KIS + agent Q&A/TRAKE + UI human-in-the-loop trong 3 ngày còn lại trước vòng
sơ tuyển; sau đó lập tài liệu PLAN/ARCHITECTURE/SESSION_LOG để phiên sau không mất context.

### ✅ Completed
- `scripts/agent/tools/retrieve.py`: singleton nạp 177.321 keyframe / 873 video, `fast_retrieve()` +
  `fast_retrieve_for_video()`.
- `scripts/agent/pipeline_kis.py`: pipeline KIS tuyến tính, không LLM.
- `scripts/submit/build_submission.py` + `validate_submission.py`: sinh CSV (KIS/QA/TRAKE) + zip,
  validator nội bộ theo rule BTC (frame≥1, không `.mp4`, ≤100 dòng, UTF-8).
- `scripts/agent/config.py`: `call_llm()` qua LiteLLM + Gemini (`gemini/gemini-3.5-flash`), xử lý
  thinking-model cần `max_tokens≥2048`.
- `scripts/agent/tools/rewrite.py`, `ocr_lookup.py`, `answer_qa.py`: dịch query VN→EN, đọc Objects
  JSON offline, trả lời 2 tầng (objects → vision) kèm cross-check chống ảo giác.
- `scripts/agent/pipeline_qa.py`: orchestrator, tối đa 2 vòng reflection nếu confidence < 0.5.
- `scripts/agent/pipeline_trake.py`: 2 giai đoạn (chọn video → align N mốc, ràng buộc thứ tự thời gian).
- `scripts/app.py`: Gradio UI 4 tab (KIS/Q&A/TRAKE/Export) với bảng sửa tay + hàng đợi submission.
- `scripts/test_day1.py`, `test_day2_basic.py`, `test_day2_full.py`: test tích hợp thủ công (theo
  báo cáo tự thuật của phiên làm việc, chưa re-run độc lập trong phiên này).
- Chạy 1 lượt code review trên toàn bộ working-tree changes → 6 finding (xem "Quyết định chốt").
- **Fix ngay 1 lỗi bảo mật nghiêm trọng phát hiện độc lập + qua code review**: `.env.example` chứa
  API key thật (Gemini + Groq) dạng plaintext thay vì placeholder, và không nằm trong `.gitignore`
  → đã sửa thành placeholder (`your_gemini_api_key_here` / `your_groq_api_key_here`).
- Viết `PLAN.md`, `ARCHITECTURE.md`, `SESSION_LOG.md` ở gốc repo.

### 🔄 Decisions Made
- Kiến trúc **khác nhau theo dạng bài** thay vì 1 agent chung: KIS = workflow tuyến tính, Q&A =
  orchestrator-workers có trần loop, TRAKE = pipeline 2 giai đoạn cố định (không phải agent tự do).
- 1 nguồn cấu hình LLM duy nhất (`agent/config.py:call_llm()`); chỉ dùng Gemini qua LiteLLM cho tới
  giờ (multi-provider fallback bị hoãn sang Phase 5, ưu tiên thấp hơn hardening).
- Anti-hallucination cho Q&A là bắt buộc, không tuỳ chọn: mọi answer phải qua `_crosscheck_answer()`
  đối chiếu Objects JSON.
- Human-in-the-loop là thiết kế chính thức (UI luôn cho sửa tay trước khi add-to-queue), không phải
  chỉ để dự phòng.
- Chưa commit git cho toàn bộ Phase 1–3 — quyết định hoãn sang đầu Phase 4 (ưu tiên fix finding từ
  code review trước khi commit, tránh commit code có bug đã biết).

### ⏳ Next Steps (xem chi tiết ở [PLAN.md](PLAN.md) Phase 4/5)
- [x] Sửa 5 finding còn lại từ code review → đã fix hết trong Session #2.
- [x] Đồng bộ `requirements.txt` → đã pin `litellm==1.97.0`, `python-dotenv==1.2.3`.
- [x] Tạo branch, commit → đã tạo `feat/agent-pipeline`, commit theo Phase, push + mở PR.
- [ ] Đối chiếu format submission với validator chính thức BTC khi công bố (chậm nhất thứ Ba).
- [ ] Cân nhắc rotate 2 API key (Gemini, Groq) từng nằm plaintext trong `.env.example`.

### ⚠️ Blockers/Notes
- Report tự thuật `docs/BaoCao_TongHop_TrienKhai_AIC2026.md` mô tả Day1-3 là "100% PASS" nhưng phiên
  này **chưa tự chạy lại** `test_day1.py`/`test_day2_full.py` để xác nhận độc lập — chỉ đọc code tĩnh.
- BTC chưa công bố format nộp bài chính thức cuối cùng — rủi ro lớn nhất treo tới hạn chậm nhất
  thứ Ba (xem `docs/Training/AIC2026_SoTuyen_QuyTrinh_NopBai_ChamDiem.md`).
- Chỉ có 1 LLM provider (Gemini) đang wire thật; Groq/Mistral/Cerebras key vẫn là placeholder trong
  `.env.example`.

### Context for Next Session
- Branch: `main`, chưa commit gì của Phase 1–4 (tất cả untracked/modified).
- Last commit: `c41c2b9` — "Upload source code and docs" (baseline gốc, trước khi có agent/submit).
- Code chính nằm ở `scripts/agent/` (pipelines + tools) và `scripts/submit/` (CSV/ZIP + validator).
- File cấu hình bí mật: `.env` (không commit, đã có trong `.gitignore`); `.env.example` giờ chỉ chứa
  placeholder, an toàn để commit.
- Submissions thử nghiệm (test/demo) đang nằm rải trong `submissions/` — không phải bài nộp thật,
  có thể dọn khi bắt đầu Phase 5.

---

## Session #2 — 2026-08-19 (tối, ~20:00–23:00)
**Goal**: Hoàn thành Phase 4 hardening (fix toàn bộ code review finding) + commit git + bắt đầu
Phase 5 (multi-provider fallback + Kaggle GPU encoding jobs).

### ✅ Completed

**Phase 4 — Hardening (hoàn tất):**
- `98955c9` Bỏ `_enrich_hits_with_n()` thừa trong `pipeline_qa.py` — dùng `n` có sẵn từ hit.
- `a453c42` Fix dual `sys.path` import identity (`config`, `ocr_lookup`) trong `rewrite.py`/`answer_qa.py`.
- `fab8701` Guard `_df_to_submission_rows()` — try/except `int(frame_id)` thay vì crash khi ô trống.
- `b324674` Validate TRAKE frame_ids count khớp N event trước khi queue (chặn mất mốc âm thầm).
- `50d078a` + `e360649` Dịch toàn bộ comment/docstring/label UI trong `app.py` sang tiếng Việt.
- `95208ab` Pin `litellm==1.97.0`, `python-dotenv==1.2.3` trong `requirements.txt`; bỏ caveat lỗi
  thời trong `CLAUDE.md` Quick Start.
- `01ddfc7` Mark Phase 4 items done trong `PLAN.md`.
- `30513aa` Close 2 gap thêm (frame_id/TRAKE guards) phát hiện khi review lại sau commit.

**Git — đã commit:**
- Tạo branch `feat/agent-pipeline`, commit theo Phase (1→2→3→docs→hardening), push lên origin.
- 17 commit từ `24ddf2e` (`.gitignore`) đến `e360649` (dịch UI cuối).

**Phase 5 — Multi-provider fallback (hoàn tất mục này):**
- `scripts/agent/config.py`: triển khai `PROVIDER_CHAIN` (Gemini → Groq → NVIDIA NIM), áp dụng cho
  cả nhánh text lẫn vision. Key rotation trong nội bộ 1 provider (nhiều key cách nhau bằng dấu phẩy
  hoặc xuống dòng trong `.env`). Đã điền key thật cho cả 3 provider.
- `.env.example` cập nhật: hướng dẫn cú pháp nhiều key, thêm `GROQ_API_KEY`, `NVIDIA_NIM_API_KEY`,
  `MISTRAL_API_KEY`, `CEREBRAS_API_KEY` (2 cái sau để dành).

**Phase 5 — Kaggle GPU encoding jobs (khởi tạo):**
- `53e2cb0` + `3519c86` Tạo `kaggle_jobs/` với 4 job encode SOTA (ViT-L/14, SigLIP, Jina CLIP v2,
  DFN-5B) — mỗi job encode 177K keyframe bằng model khác nhau trên GPU Kaggle miễn phí.
- Cơ chế `resolve_keyframes_root()` — tự dò path mount thật thay vì hard-code.
- Tất cả job set `machine_shape: NvidiaTeslaT4` (P100 không tương thích PyTorch cu128).
- Push đợt 1 (job 01 & 02) → phát hiện 2 lỗi: path mount sai + GPU P100 không chạy được.
- `_diag/` kernel chẩn đoán trên Kaggle để xác nhận cấu trúc thư mục + GPU khả dụng.

### 🔄 Decisions Made
- Commit trước khi Phase 4 hoàn toàn xong (blocker từ Session #1) — ưu tiên an toàn code trên git
  hơn chờ hoàn hảo.
- Chọn T4 thay vì P100 cho Kaggle GPU jobs (sm_75 tương thích, P100 sm_60 không chạy PyTorch 2.10+cu128).
- Kaggle jobs là **thăm dò/ensemble**, không thay đổi baseline `clip-ViT-B-32` — chỉ tạo embedding
  bổ sung để so sánh hoặc ensemble sau nếu cải thiện accuracy.
- Multi-provider: Gemini ưu tiên 1 (miễn phí + hào phóng), Groq/NVIDIA NIM là fallback — không đổi
  thứ tự vì Gemini vẫn ổn nhất cho bài thi (hỗ trợ vision native).

### ⚠️ Blockers/Notes
- Kaggle job 01/02 đợt 1 lỗi (path mount + GPU P100) — đã sửa, cần push lại.
- Job 03 (Jina CLIP v2) chưa push đợt 1 nhưng cùng bug path, đã sửa sẵn.
- `.env` có 28 giá trị dưới `GEMINI_API_KEY` nhưng chỉ 6 key đúng format `AIzaSy...` — 22 key dạng
  `AQ.Ab8...` sẽ tự bị bỏ qua (lỗi auth), có thể gây chậm vài giây khi thi nếu 6 key thật đều
  rate-limit cùng lúc.

### Context for Next Session
- Branch: `feat/agent-pipeline` (active), đã push lên origin. PR mở về `main`.
- Last commit: `735bc7e` — "feat: establish project structure for AIC2026 Kaggle jobs" (2026-08-20 00:50).
- Phase 4: ✅ Done. Phase 5: multi-provider ✅, Kaggle jobs đang debug.
- 4 Kaggle jobs cần push lại sau fix path/GPU → xem `kaggle_jobs/README.md` cho lệnh.

---

## Session #3 — 2026-08-19 ~ 2026-08-20 (đêm, liên tục debug Kaggle jobs)
**Goal**: Debug & sửa toàn bộ lỗi của 4 Kaggle GPU encoding jobs qua nhiều vòng push/log/fix;
viết README.md cho repo.

### ✅ Completed

**Kaggle jobs — 7 vòng debug (xem chi tiết tại [`kaggle_jobs/README.md`](kaggle_jobs/README.md)):**

1. **Path mount sai** — Kaggle mount ở `/kaggle/input/datasets/<owner>/...` thay vì
   `/kaggle/input/...`. Đã sửa `resolve_keyframes_root()` tự dò.
2. **GPU P100 không chạy** — PyTorch cu128 cần sm_70+, P100 là sm_60. Ép `NvidiaTeslaT4`.
3. **Jina CLIP v2 TypeError** — `torch_dtype` phải truyền string `"float16"` cho code tuỳ biến Jina.
4. **Slug kernel lệch** — đồng bộ field `id` trong `kernel-metadata.json` cho khớp slug trên Kaggle.
5. **`BaseModelOutputWithPooling` lỗi** (job 01 & 02) — `transformers` bản mới (5.x) đổi hành vi
   `get_image_features()`. Viết `_get_image_embeds()` fallback.
6. **`clip_loss` ImportError** (job 03) — `transformers` 5.x bỏ hàm nội bộ `clip_loss`. Viết
   `_patch_missing_clip_loss()`.
7. **Double-projection** (job 01) — `_get_image_embeds()` áp `visual_projection` vô điều kiện →
   shape sai. Sửa 2 lần: lần 1 đoán sai giả định, lần 2 đổi chiến lược dựa hoàn toàn vào shape
   runtime thay vì giả định field API.

**Đổi chiến lược (Cập nhật 6):** Pin cứng `transformers==4.57.3` (job 01/02/03) và
`open_clip_torch==2.32.0` (job 04) — chặn đứng toàn bộ nhóm lỗi do thư viện đổi hành vi. Thêm
chế độ `SMOKE_TEST` cho cả 4 job (chạy 2 video × 4 ảnh trong ~1-2 phút GPU thay vì full 873 video).

**Xác nhận (Cập nhật 7):** Smoke-test job 01 **PASS** — pin version đã sửa tận gốc chuỗi lỗi,
`get_image_features()` trả thẳng `torch.Tensor` như hành vi gốc. Đã tắt `SMOKE_TEST = False`, sẵn
sàng push chạy thật.

**README.md:**
- Viết lại hoàn toàn `README.md` từ file trống — bao gồm: tổng quan, kiến trúc hệ thống, tech stack,
  cấu trúc thư mục, cài đặt & khởi chạy, sử dụng (UI + CLI), pipeline chi tiết (KIS/Q&A/TRAKE),
  Kaggle jobs, LLM provider chain, tài liệu liên quan, quy ước code, trạng thái dự án.

### 🔄 Decisions Made
- **Pin version thay vì vá API mới**: sau 3 lần đoán sai hành vi `transformers` 5.x, quyết định pin
  `4.57.3` (bản ổn định cuối cùng trước major bump) — an toàn hơn là cố tương thích API mới giữa
  lúc cần encode gấp.
- **Smoke-test trước khi chạy full**: thêm `SMOKE_TEST` mode (2 video × 4 ảnh) cho mỗi job —
  phát hiện lỗi logic trong 1-2 phút GPU thay vì 10+ phút, tiết kiệm quota.
- **Giữ nguyên các bản vá phòng hờ** (`_get_image_embeds()`, `_patch_missing_clip_loss()`) dù pin
  version đã sửa tận gốc — lớp an toàn thêm không hại gì.

### ⏳ Next Steps
- [ ] Push chạy thật job 01 (ViT-L/14) — smoke-test đã PASS.
- [ ] Smoke-test + push thật job 02 (SigLIP), 03 (Jina), 04 (DFN).
- [ ] Tải kết quả embedding SOTA về `data/extracted/features_*` khi job xong.
- [ ] Tích hợp embedding SOTA vào `scripts/index.py` (ensemble hoặc thay thế nếu cải thiện accuracy).
- [ ] Đối chiếu format submission với validator chính thức BTC (chờ BTC công bố).
- [ ] Chạy thử toàn luồng trên Codabench khi mở.
- [ ] Chuẩn bị checklist thao tác ngày thi.

### ⚠️ Blockers/Notes
- Job 02 (SigLIP), 03 (Jina), 04 (DFN) chưa chạy lại thật sau khi pin version — chỉ sửa theo lý
  thuyết + compile sạch. Khuyên bật `SMOKE_TEST = True` test trước.
- Kaggle giới hạn 2 GPU session song song — phải chạy job theo đợt (01+02 trước, rồi 03+04).
- BTC vẫn chưa công bố format nộp bài chính thức.
- PR `feat/agent-pipeline` → `main` đang mở, chưa merge.

### Context for Next Session
- Branch: `feat/agent-pipeline` (active), đã push origin.
- Last commit: `735bc7e` — Kaggle jobs structure.
- Working tree: chỉ `README.md` modified (chưa commit).
- Phase 1–4: ✅ Done. Phase 5: multi-provider ✅, Kaggle jobs đang chờ chạy thật (job 01 smoke PASS),
  3 việc còn lại (validator BTC, test Codabench, checklist ngày thi).
- Kaggle job status: 01 sẵn sàng chạy full, 02/03/04 cần smoke-test trước.
- Tài liệu repo: README.md ✅, ARCHITECTURE.md ✅, PLAN.md ✅, SESSION_LOG.md ✅.
