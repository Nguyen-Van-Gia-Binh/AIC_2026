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
- [ ] Sửa 5 finding còn lại từ code review (bug hiệu năng `_enrich_hits_with_n`, crash tiềm ẩn
      `_df_to_submission_rows` khi frame_id trống, mất token TRAKE âm thầm, import `config` 2
      identity, comment tiếng Anh trong `app.py`).
- [ ] Đồng bộ `requirements.txt` với dependency thật đang dùng (`litellm`, `python-dotenv`).
- [ ] Tạo branch, commit toàn bộ Phase 1–4 (hiện toàn bộ vẫn ở trạng thái uncommitted trên `main`).
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
