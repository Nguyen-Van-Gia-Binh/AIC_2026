# AIC2026 — Project Plan

> Cách đọc file này: mỗi Phase là một cột mốc lớn. Trong phiên làm việc mới, đọc
> Phase nào đang 🔄/⏳ và mục Blockers trước, đó là việc cần làm tiếp theo.
> Chi tiết "làm thế nào" không ghi ở đây — xem [ARCHITECTURE.md](ARCHITECTURE.md)
> và code. File này chỉ nối thêm / tick checkbox qua từng phiên, không viết lại.

## Phase 1: Nền tảng Retrieval & Submission Engine (✅ Done)

- [X] `scripts/agent/tools/retrieve.py` — singleton index, `fast_retrieve`, `fast_retrieve_for_video`
- [X] `scripts/agent/pipeline_kis.py` — pipeline KIS tuyến tính (không LLM)
- [X] `scripts/submit/build_submission.py` — sinh CSV KIS/QA/TRAKE + zip
- [X] `scripts/submit/validate_submission.py` — validator nội bộ (encoding, .mp4, frame≥1, ≤100 dòng)
- [X] `scripts/test_day1.py` — test tích hợp end-to-end Day 1

Success: retrieve → CSV → zip → validator PASS chạy được end-to-end trên dữ liệu thật.

## Phase 2: Agent đa phương thức cho Q&A + TRAKE (✅ Done)

- [X] `scripts/agent/config.py` — `call_llm()` qua LiteLLM + Gemini (`gemini/gemini-3.5-flash`)
- [X] `scripts/agent/tools/rewrite.py` — dịch/tối ưu query VN→EN cho CLIP, hỗ trợ `feedback`
- [X] `scripts/agent/tools/ocr_lookup.py` — đọc Objects JSON offline (Faster R-CNN)
- [X] `scripts/agent/tools/answer_qa.py` — trả lời 2 tầng (objects → vision) + cross-check chống ảo giác
- [X] `scripts/agent/pipeline_qa.py` — orchestrator, tối đa 2 vòng reflection (`MAX_AGENT_LOOPS=2`)
- [X] `scripts/agent/pipeline_trake.py` — 2 giai đoạn (chọn video → align N mốc theo world-model tuần tự)
- [X] `scripts/test_day2_basic.py`, `scripts/test_day2_full.py`

Success: `run_qa()` và `run_trake()` chạy hết pipeline, sinh được CSV hợp lệ.

## Phase 3: Gradio UI Human-in-the-loop (✅ Done)

- [X] `scripts/app.py` — 4 tab: KIS / Q&A / TRAKE / Export, có bảng sửa tay + hàng đợi submission

Success: thao tác search → sửa kết quả trên UI → add to queue → export zip chạy được thủ công.

## Phase 4: Hardening trước ngày thi (✅ Done)

Việc phát sinh từ code review (2026-08-19) + rà soát thủ công — ưu tiên theo mức rủi ro điểm số/bảo mật:

- [X] **[BẢO MẬT — đã fix]** `.env.example` chứa key thật (Gemini + Groq) thay vì placeholder, và
  không nằm trong `.gitignore` → đã thay bằng placeholder. **Cần làm thêm:** cân nhắc
  rotate 2 key đó ở Google/Groq console vì đã tồn tại ở dạng plaintext trên máy một thời gian.
- [X] `scripts/agent/pipeline_qa.py:_enrich_hits_with_n` build lại toàn bộ lookup
  `(video_id, frame_idx)->n` bằng `.iterrows()` trên cả `_META` (~177K dòng) mỗi lần gọi Q&A,
  dù `fast_retrieve`/`fast_retrieve_for_video` đã trả sẵn `n` trong mỗi hit — đã bỏ hẳn hàm này,
  dùng `n` có sẵn từ hit.
- [X] `scripts/app.py:_df_to_submission_rows` gọi `int(r["frame_id"])` không try/except — nếu user
  xóa trống ô `frame_id` trên bảng Gradio rồi bấm "Add to Queue" thì `int(nan)` crash cả app
  thay vì báo lỗi thân thiện như chỗ khác trong file. Đã bọc try/except + thông báo ⚠️.
- [X] `scripts/app.py` (TRAKE tab) — `trake_add_to_queue` lọc âm thầm token không phải số nguyên
  khi parse `frame_ids` (`"40530 | 40727 | 40895"`), có thể làm mất 1 event mà không cảnh báo,
  dẫn tới submit thiếu mốc so với N event của câu hỏi. Đã validate đủ N phần tử, chặn + báo lỗi
  nếu thiếu.
- [X] `scripts/agent/config.py` bị import theo 2 identity khác nhau (`config` từ `rewrite.py`/
  `answer_qa.py` qua `sys.path` trỏ vào `scripts/agent`, và `agent.config` từ `pipeline_qa.py`
  qua `sys.path` trỏ vào `scripts`) → module bị load/khởi tạo 2 lần, state tách rời. Đã chuẩn hóa
  import path về 1 kiểu duy nhất (`from agent.config import ...`, chỉ thêm `scripts/` vào
  `sys.path`) — cùng lúc fix luôn `ocr_lookup.py` bị dính bug tương tự.
- [X] Comment/docstring trong `scripts/app.py` viết bằng tiếng Anh, vi phạm quy ước
  "UI text và code comment viết tiếng Việt" ghi trong `CLAUDE.md`. Đã dịch lại sang tiếng Việt
  (toàn file — banner section, docstring hàm, comment inline).
- [X] `requirements.txt` chưa liệt kê `litellm`, `python-dotenv` (đang comment "chưa cài" dù đã cài
  và đang dùng thật trong `config.py`) → clone máy mới / môi trường Kaggle sẽ thiếu dependency.
  Đã pin đúng version thật từ `.venv` (`litellm==1.97.0`, `python-dotenv==1.2.3`), bỏ luôn đoạn
  caveat lỗi thời trong `CLAUDE.md` Quick Start.
- [X] Toàn bộ Phase 1–3 hiện chưa hề commit (tất cả nằm ở trạng thái `??`/`M` trên `main`, chưa có
  branch riêng). Đã tạo branch `feat/agent-pipeline`, commit theo từng Phase, push lên origin,
  mở PR về `main`.

Success: code review PASS lại (0 finding mức cao), `requirements.txt` cài lại từ đầu chạy được app,
toàn bộ thay đổi đã nằm trong git history trên 1 branch.

**Phát sinh thêm (đã fix):** ngoài comment/docstring, `scripts/app.py` còn nhiều label tiếng Anh
trong status message runtime + label component UI (status Q&A/TRAKE/Export, tên tab, checkbox
auto-translate, "rows"→"dòng", v.v.) — đã dịch nốt toàn bộ sang tiếng Việt theo yêu cầu, giữ lại
các loanword kỹ thuật đã dùng nhất quán trong toàn repo (`video_id`, `query`, `ZIP`, `CSV`,
`keyframe`, `Submission`, `Top-k`) và giữ nguyên các placeholder ví dụ tiếng Anh ở tab TRAKE (mô tả
cảnh cho CLIP search cần tiếng Anh — xem mục "Notable constraints" CLAUDE.md).

## Phase 5: Sẵn sàng thi (⏳ Todo)

- [ ] Đối chiếu format CSV/ZIP hiện tại với validator chính thức của BTC trên Codabench khi có (hạn
  BTC công bố: chậm nhất thứ Ba) — `build_submission.py`/`validate_submission.py` hiện dựa trên
  hiểu biết tay, chưa test với validator thật.
- [X] Multi-provider LiteLLM fallback — `scripts/agent/config.py:PROVIDER_CHAIN` (Gemini ưu tiên 1
  → Groq fallback 2 → NVIDIA NIM fallback 3), áp dụng cho cả nhánh text lẫn vision, tự chuyển
  provider khi gặp lỗi 429/rate-limit/quota hoặc bất kỳ lỗi nào khác; provider thiếu API key trong
  `.env` tự bị bỏ qua. Đã điền đủ key thật cho cả 3 provider trong `.env`. Đồng thời thêm key
  rotation trong nội bộ 1 provider (`GEMINI_API_KEY` giờ nhận nhiều key, mỗi dòng 1 key trong dấu
  ngoặc kép — xem `.env.example`): hiện `.env` có 28 giá trị dưới `GEMINI_API_KEY`, nhưng chỉ 6
  đúng định dạng Gemini API key thật (`AIzaSy...`); 22 dòng còn lại dạng `AQ.Ab8...` do người dùng
  cung cấp nhưng KHÔNG đúng định dạng Gemini API key (giống token OAuth/phiên hơn) — đã cảnh báo,
  người dùng xác nhận cứ để vậy; code sẽ tự bỏ qua (lỗi auth) và rớt key kế tiếp nên không crash,
  chỉ cần lưu ý nếu cả 6 key AIzaSy thật đều bị rate-limit cùng lúc thì sẽ mất thêm vài giây thử
  22 key không hợp lệ trước khi rớt sang Groq. **Cần làm thêm:** test tay qua Gradio UI (không cần
  script CLI); cân nhắc dọn bớt 22 key `AQ.Ab8...` không hợp lệ nếu thấy log bị ồn khi thi.
- [ ] Chạy thử toàn bộ luồng (KIS + Q&A + TRAKE) trên tài khoản thi thử thật khi Codabench mở, không
  chỉ trên `test_day1.py`/`test_day2_full.py`.
- [ ] Chuẩn bị sẵn checklist thao tác Gradio UI cho người vận hành ngày thi (search → rà soát →
  sửa tay nếu sai → add to queue → export) để không lúng túng lúc thi thật.

Success: nộp thử 1 zip lên Codabench (nếu có tài khoản thi thử) và được chấp nhận không lỗi format.

---

## Blockers / Risks

- **Thời hạn BTC công bố format nộp bài chính thức** (chậm nhất thứ Ba) — `build_submission.py`
  đang implement theo suy đoán từ tài liệu, có thể phải sửa gấp nếu BTC công bố khác.
- **Single LLM provider (Gemini)** — đã hết, có fallback 3 tầng + key rotation (xem Phase 5), cả 3
  provider đều có key thật trong `.env`.
- **Chưa commit git** — rủi ro mất code nếu máy gặp sự cố trước ngày thi (xem Phase 4 mục cuối).
- **Chưa test load thật** — chưa rõ latency `run_qa`/`run_trake` (gọi Gemini nhiều lần) có đủ nhanh
  để rà soát tay trong thời gian thi hay không.
