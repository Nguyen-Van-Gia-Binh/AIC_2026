# AIC2026 — Project Plan

> Cách đọc file này: mỗi Phase là một cột mốc lớn. Trong phiên làm việc mới, đọc
> Phase nào đang 🔄/⏳ và mục Blockers trước, đó là việc cần làm tiếp theo.
> Chi tiết "làm thế nào" không ghi ở đây — xem [ARCHITECTURE.md](ARCHITECTURE.md)
> và code. File này chỉ nối thêm / tick checkbox qua từng phiên, không viết lại.

## Phase 1: Nền tảng Retrieval & Submission Engine (✅ Done)
- [x] `scripts/agent/tools/retrieve.py` — singleton index, `fast_retrieve`, `fast_retrieve_for_video`
- [x] `scripts/agent/pipeline_kis.py` — pipeline KIS tuyến tính (không LLM)
- [x] `scripts/submit/build_submission.py` — sinh CSV KIS/QA/TRAKE + zip
- [x] `scripts/submit/validate_submission.py` — validator nội bộ (encoding, .mp4, frame≥1, ≤100 dòng)
- [x] `scripts/test_day1.py` — test tích hợp end-to-end Day 1

Success: retrieve → CSV → zip → validator PASS chạy được end-to-end trên dữ liệu thật.

## Phase 2: Agent đa phương thức cho Q&A + TRAKE (✅ Done)
- [x] `scripts/agent/config.py` — `call_llm()` qua LiteLLM + Gemini (`gemini/gemini-3.5-flash`)
- [x] `scripts/agent/tools/rewrite.py` — dịch/tối ưu query VN→EN cho CLIP, hỗ trợ `feedback`
- [x] `scripts/agent/tools/ocr_lookup.py` — đọc Objects JSON offline (Faster R-CNN)
- [x] `scripts/agent/tools/answer_qa.py` — trả lời 2 tầng (objects → vision) + cross-check chống ảo giác
- [x] `scripts/agent/pipeline_qa.py` — orchestrator, tối đa 2 vòng reflection (`MAX_AGENT_LOOPS=2`)
- [x] `scripts/agent/pipeline_trake.py` — 2 giai đoạn (chọn video → align N mốc theo world-model tuần tự)
- [x] `scripts/test_day2_basic.py`, `scripts/test_day2_full.py`

Success: `run_qa()` và `run_trake()` chạy hết pipeline, sinh được CSV hợp lệ.

## Phase 3: Gradio UI Human-in-the-loop (✅ Done)
- [x] `scripts/app.py` — 4 tab: KIS / Q&A / TRAKE / Export, có bảng sửa tay + hàng đợi submission

Success: thao tác search → sửa kết quả trên UI → add to queue → export zip chạy được thủ công.

## Phase 4: Hardening trước ngày thi (✅ Done)
Việc phát sinh từ code review (2026-08-19) + rà soát thủ công — ưu tiên theo mức rủi ro điểm số/bảo mật:

- [x] **[BẢO MẬT — đã fix]** `.env.example` chứa key thật (Gemini + Groq) thay vì placeholder, và
      không nằm trong `.gitignore` → đã thay bằng placeholder. **Cần làm thêm:** cân nhắc
      rotate 2 key đó ở Google/Groq console vì đã tồn tại ở dạng plaintext trên máy một thời gian.
- [x] `scripts/agent/pipeline_qa.py:_enrich_hits_with_n` build lại toàn bộ lookup
      `(video_id, frame_idx)->n` bằng `.iterrows()` trên cả `_META` (~177K dòng) mỗi lần gọi Q&A,
      dù `fast_retrieve`/`fast_retrieve_for_video` đã trả sẵn `n` trong mỗi hit — đã bỏ hẳn hàm này,
      dùng `n` có sẵn từ hit.
- [x] `scripts/app.py:_df_to_submission_rows` gọi `int(r["frame_id"])` không try/except — nếu user
      xóa trống ô `frame_id` trên bảng Gradio rồi bấm "Add to Queue" thì `int(nan)` crash cả app
      thay vì báo lỗi thân thiện như chỗ khác trong file. Đã bọc try/except + thông báo ⚠️.
- [x] `scripts/app.py` (TRAKE tab) — `trake_add_to_queue` lọc âm thầm token không phải số nguyên
      khi parse `frame_ids` (`"40530 | 40727 | 40895"`), có thể làm mất 1 event mà không cảnh báo,
      dẫn tới submit thiếu mốc so với N event của câu hỏi. Đã validate đủ N phần tử, chặn + báo lỗi
      nếu thiếu.
- [x] `scripts/agent/config.py` bị import theo 2 identity khác nhau (`config` từ `rewrite.py`/
      `answer_qa.py` qua `sys.path` trỏ vào `scripts/agent`, và `agent.config` từ `pipeline_qa.py`
      qua `sys.path` trỏ vào `scripts`) → module bị load/khởi tạo 2 lần, state tách rời. Đã chuẩn hóa
      import path về 1 kiểu duy nhất (`from agent.config import ...`, chỉ thêm `scripts/` vào
      `sys.path`) — cùng lúc fix luôn `ocr_lookup.py` bị dính bug tương tự.
- [x] Comment/docstring trong `scripts/app.py` viết bằng tiếng Anh, vi phạm quy ước
      "UI text và code comment viết tiếng Việt" ghi trong `CLAUDE.md`. Đã dịch lại sang tiếng Việt
      (toàn file — banner section, docstring hàm, comment inline).
- [x] `requirements.txt` chưa liệt kê `litellm`, `python-dotenv` (đang comment "chưa cài" dù đã cài
      và đang dùng thật trong `config.py`) → clone máy mới / môi trường Kaggle sẽ thiếu dependency.
      Đã pin đúng version thật từ `.venv` (`litellm==1.97.0`, `python-dotenv==1.2.3`), bỏ luôn đoạn
      caveat lỗi thời trong `CLAUDE.md` Quick Start.
- [x] Toàn bộ Phase 1–3 hiện chưa hề commit (tất cả nằm ở trạng thái `??`/`M` trên `main`, chưa có
      branch riêng). Đã tạo branch `feat/agent-pipeline`, commit theo từng Phase, push lên origin,
      mở PR về `main`.

Success: code review PASS lại (0 finding mức cao), `requirements.txt` cài lại từ đầu chạy được app,
toàn bộ thay đổi đã nằm trong git history trên 1 branch.

**Phát sinh thêm (chưa nằm trong phạm vi Phase 4 gốc, để dành xét sau):** ngoài comment/docstring,
`scripts/app.py` còn một số label tiếng Anh trong status message runtime (vd. "Method:",
"Confidence:", "Best:", "Frames:", "ZIP:", "Path:", "Validate: PASS/FAIL") — cùng vi phạm quy ước
Vietnamese-UI-text nhưng là text hiển thị runtime chứ không phải comment/docstring, nên không nằm
trong phạm vi mục đã duyệt ở trên. Cần quyết định có dịch nốt hay không ở phiên sau.

## Phase 5: Sẵn sàng thi (⏳ Todo)
- [ ] Đối chiếu format CSV/ZIP hiện tại với validator chính thức của BTC trên Codabench khi có (hạn
      BTC công bố: chậm nhất thứ Ba) — `build_submission.py`/`validate_submission.py` hiện dựa trên
      hiểu biết tay, chưa test với validator thật.
- [ ] Multi-provider LiteLLM fallback (Groq/Mistral/Cerebras) — hiện chỉ có Gemini
      (`scripts/agent/config.py`), single point of failure nếu Gemini rate-limit đúng lúc thi.
      Chỉ làm nếu Phase 4 xong sớm — không đánh đổi thời gian của Phase 4.
- [ ] Chạy thử toàn bộ luồng (KIS + Q&A + TRAKE) trên tài khoản thi thử thật khi Codabench mở, không
      chỉ trên `test_day1.py`/`test_day2_full.py`.
- [ ] Chuẩn bị sẵn checklist thao tác Gradio UI cho người vận hành ngày thi (search → rà soát →
      sửa tay nếu sai → add to queue → export) để không lúng túng lúc thi thật.

Success: nộp thử 1 zip lên Codabench (nếu có tài khoản thi thử) và được chấp nhận không lỗi format.

---

## Blockers / Risks
- **Thời hạn BTC công bố format nộp bài chính thức** (chậm nhất thứ Ba) — `build_submission.py`
  đang implement theo suy đoán từ tài liệu, có thể phải sửa gấp nếu BTC công bố khác.
- **Single LLM provider (Gemini)** — nếu bị rate-limit/downtime đúng lúc thi, `pipeline_qa.py` và
  `answer_qa.py` không có fallback, toàn bộ Q&A pipeline dừng.
- **Chưa commit git** — rủi ro mất code nếu máy gặp sự cố trước ngày thi (xem Phase 4 mục cuối).
- **Chưa test load thật** — chưa rõ latency `run_qa`/`run_trake` (gọi Gemini nhiều lần) có đủ nhanh
  để rà soát tay trong thời gian thi hay không.
