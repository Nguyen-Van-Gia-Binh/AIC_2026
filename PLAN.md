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

- [X] **BTC đã công bố hướng dẫn nộp bài chính thức (2026-08-20)** — đã lưu đầy đủ vào
  [docs/Thong tin vong So tuyen AIC2026.md](<docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>) §4
  và [.agents/skills/submission/SKILL.md](.agents/skills/submission/SKILL.md). Đối chiếu code thật
  với tài liệu này phát hiện 2 lỗi xác nhận (cả 2 đều "im lặng" — `validate_submission.py` từng
  PASS dù dính lỗi) — **đã fix cả 2 (2026-08-20)**:
  - [X] `build_submission.py:build_zip_submission` từng nén CSV thẳng vào gốc ZIP — đã sửa
    `arcname` thành `f"submission/{csv_path.name}"` + thêm kiểm tra thư mục này vào `validate_zip()`.
  - [X] `build_kis_csv`/`build_qa_csv`/`build_trake_csv` từng tự ghép tên file `f"{query_id}_kis.csv"`
    — đã đổi 3 hàm nhận thẳng tên file đích (`filename`, giữ nguyên tên BTC cấp, tự đổi đuôi
    `.txt`/không đuôi → `.csv`), khớp yêu cầu BTC giữ nguyên tên gốc.
  - [X] (mức thấp hơn) `validate_csv_file`/`validate_zip` phần `qa` từng chưa kiểm tra answer ≤ 100
    ký tự — đã thêm kiểm tra (dùng chung qua `_validate_rows`, áp dụng cho cả đường CSV lẫn ZIP).
  Đã cập nhật `app.py` (placeholder ô Query ID sang đúng chuẩn `query-1-kis`) và
  [.agents/skills/submission/SKILL.md](.agents/skills/submission/SKILL.md) (xoá TODO, sửa mô tả
  TRAKE CSV từng sai — thực tế 1 dòng = 1 phương án trọn vẹn cho cả N mốc, không phải 1 dòng/event).
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
- [ ] **Lịch thi chính thức đã có (xem [docs/Thong tin vong So tuyen AIC2026.md](<docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>) §5)**:
  Vòng thử nghiệm mở 08:00 20/8 → đóng 19:30 21/8; **Sơ tuyển đợt 1 mở đúng lúc đó (19:30 21/8),
  đóng 22:30 21/8** — chỉ 3 tiếng. Không có khoảng đệm giữa 2 vòng. Toàn bộ Phase 5 phải xong
  TRƯỚC 19:30 21/8, không phải "khi nào tiện".
- [ ] Chạy thử toàn bộ luồng (KIS + Q&A + TRAKE) trên tài khoản thi thử thật trong cửa sổ Vòng thử
  nghiệm (08:00 20/8–19:30 21/8), không chỉ trên `test_day1.py`/`test_day2_full.py` — đây là cơ hội
  DUY NHẤT tập dượt trước khi Sơ tuyển đợt 1 (tính điểm thật) mở.
  **Đã có đề thật để chạy việc này (2026-08-20):** `data/raw/THUNGHIEM-bo-de-thi.zip` — 24 câu hỏi
  thô (18 KIS + 3 QA + 3 TRAKE), tên file khớp với "Vòng thử nghiệm" đang mở → nhiều khả năng đây
  chính là đề thử của BTC, không phải bộ tự tạo. Ưu tiên chạy đúng 24 câu này qua toàn bộ luồng thật
  (Gradio UI → sửa tay → export zip → nộp thử) trước khi dùng lại chúng làm ngữ liệu cho bộ eval
  Phase 6 — đây mới là "cơ hội DUY NHẤT" nói ở trên, không phải bài tập giả lập.
- [X] Chuẩn bị sẵn checklist thao tác Gradio UI cho người vận hành ngày thi (search → rà soát →
  sửa tay nếu sai → add to queue → export) để không lúng túng trong cửa sổ 3 tiếng của Sơ tuyển
  đợt 1 — đã viết [docs/Checklist Van Hanh Ngay Thi.md](<docs/Checklist%20Van%20Hanh%20Ngay%20Thi.md>)
  (chuẩn bị trước giờ G, luồng thao tác từng loại truy vấn, quy trình export/nộp tối đa 3 lần, xử
  lý sự cố nhanh, bảng tra nút/ô trên UI). Còn thiếu: chạy thử thật để kiểm chứng checklist này
  đúng với luồng thật trên tài khoản thi (mục ngay dưới).

- [X] **[LỖI NGHIÊM TRỌNG — đã fix, phát hiện tình cờ khi dựng Phase 6, 2026-08-20]**
  `scripts/index.py:build_index()` tính `jpg_path` sai cho **toàn bộ 177.321 keyframe** (đã chạy
  thật `python scripts/index.py` để xác nhận, không đoán — trước fix in ra
  `Số keyframe đã có ảnh jpg thật: 0`). Nguyên nhân: code giả định
  `data/extracted/keyframes/{video_id}/{n}.jpg`, nhưng dữ liệu thật (đủ 10 batch L21–L30 từ
  2026-08-20) lồng thêm 1 cấp thư mục batch: `data/extracted/keyframes/{batch}/{video_id}/{n}.jpg`
  (xác nhận đúng cho cả 10/10 batch bằng `ls` thật, kể cả L23 — batch cũ nhất). Hệ quả: Gradio UI
  (`app.py`) không hiển thị được bất kỳ ảnh preview nào ở bước rà soát tay — đúng bước ARCHITECTURE.md
  coi là thiết kế cốt lõi, đúng lúc Vòng thử nghiệm đang mở. Đã sửa: thử đường dẫn lồng batch trước,
  fallback về đường dẫn phẳng cũ nếu không thấy (phòng máy khác còn cấu trúc cũ) — verify lại bằng
  `python scripts/index.py`: `n_with_jpg` từ 0 → 177321.

Success: nộp thử 1 zip trong Vòng thử nghiệm và được chấp nhận không lỗi format, trước 19:30 21/8.

## Phase 6: Nâng cấp retrieval baseline + bộ eval tự chấm (⏳ Todo — chạy song song, KHÔNG chặn Phase 5)

> Track thăm dò (Mặt trận 1 — xem ADVISOR.md), ưu tiên thấp hơn việc còn lại của Phase 5 (chạy thử
> nộp thật trong Vòng thử nghiệm). Chỉ dồn lực chính vào đây sau khi việc đó xong hoặc không còn chặn.
> `data/extracted/` có đủ **4/5** bộ feature DÙNG ĐƯỢC (`clip-features-32` + `features_vitl14`/
> `features_siglip`/`features_dfn`). **`features_jina` đã giải nén (873 file `.npy`) nhưng LỖI NGHIÊM
> TRỌNG — XÁC NHẬN THẬT (2026-08-20): 100% NaN** (cả 873/873 file, mọi giá trị cùng 1 bit pattern
> float16 `0x7FFF` — bug encode-time thật trên Kaggle, nghi do chạy `torch_dtype="float16"` trên GPU
> với vision tower EVA+RoPE dễ overflow fp16, KHÔNG phải lỗi giải nén/transfer. Chi tiết + hướng debug
> → `kaggle_jobs/README.md` mục "Cập nhật 8"). Đã thêm entry `"jina"` + `_build_jina_encoder()` +
> patch `_patch_missing_clip_loss()` vào `scripts/eval/multi_index.py` — code encoder đã xác nhận
> chạy đúng qua smoke-test (text vector không NaN), CHỈ dữ liệu `.npy` nguồn bị hỏng. Đã thêm fail-loud
> check NaN chung ở `load_feature_index()` để không âm thầm ra `score=nan`. **`jina` KHÔNG dùng được
> cho tới khi chạy lại job `03_jina` trên Kaggle** (đã ghi cảnh báo + hướng sửa trong
> `kaggle_jobs/03_jina/main.py`) và giải nén lại — không phải việc ưu tiên trước Sơ tuyển đợt 1.
> **Lưu ý dung lượng đĩa đã đổi** — không còn 88GB trống như ghi trước đây; do tải thêm nhiều file
> `Videos_L*.zip` (~50GB+) vào `data/raw/` nên ổ C hiện chỉ còn **~31GB trống (94% đầy)**. Không ảnh
> hưởng trực tiếp Phase 6 (feature `.npy` đã giải nén xong, nhỏ), nhưng cần dọn trước khi tải/giải nén
> thêm gì lớn: `data/raw/Videos_L24_a.zip`/`L25_a.zip`/`L26_a-d.zip`/`L27_a.zip`/`L30_a.zip` đang giữ
> trùng cả `.zip` gốc lẫn bản đã giải nén (~52GB) — xoá `.zip` sau khi xác nhận folder giải nén đủ, như
> đã làm đúng với `L23`. `data/extracted/keyframes/` đủ dữ liệu thật (10 batch L21–L30, 177.321 keyframe).
>
> **Phát hiện mới (2026-08-20): `data/raw/THUNGHIEM-bo-de-thi.zip`** — bộ đề thi thử thật (tên khớp
> với Vòng thử nghiệm đang mở), 24 file câu hỏi thô (18 KIS + 3 QA + 3 TRAKE), tiếng Việt, **chỉ có
> câu hỏi, không có đáp án** (đúng bản chất — team tự tìm). Nguồn ngữ liệu tốt hơn hẳn tự bịa cho bộ
> eval bên dưới — xem mục ground-truth. Quan trọng hơn: nhiều khả năng đây chính là đề cho việc "chạy
> thử nộp thật trong Vòng thử nghiệm" còn thiếu ở Phase 5 — ưu tiên dùng ngay cho việc đó trước.
>
> **Tiện ích/khung code đã dựng xong (2026-08-20)** — xem `scripts/eval/` (`multi_index.py`,
> `run_eval.py`, `lookup_frame.py`) + `queries/EVAL_GUIDE.md`/`eval_ground_truth.json`. Đã smoke-test
> 4/5 model tag (`clip_vitb32`/`vitl14`/`siglip`/`dfn`) chạy được, `clip_vitb32` đối chiếu khớp
> 100% với `scripts/agent/tools/retrieve.py` (cùng video_id/frame_id/score). `jina` đã smoke-test
> xong (encoder code đúng) nhưng phát hiện dữ liệu nguồn `features_jina/` hỏng 100% NaN — xem khối
> đầu Phase 6. Việc còn thiếu: ground truth thật (`eval_ground_truth.json` mới có 19 câu, cần thêm) —
> việc của người, không code được.

- [ ] **Dựng bộ eval có ground truth thật, tự chấm bằng đúng công thức thi (R@{1,5,20,50,100})** —
  điều kiện tiên quyết để so sánh baseline khách quan, nếu không sẽ chỉ so bằng cảm tính. AI cố vấn
  không tự tạo được ground truth (không xem được nội dung video thật) — người trong team cần tự xem
  video thật và ghi lại `(video_id, frame_id)` đúng cho từng câu hỏi tự đặt. **Quy trình + schema đã
  viết sẵn ở [queries/EVAL_GUIDE.md](queries/EVAL_GUIDE.md)**, dùng
  `scripts/eval/lookup_frame.py <video_id> <giây>` để tra `frame_id` nhanh thay vì tự tính tay.
  - **Có sẵn 24 câu hỏi thật** (`data/raw/THUNGHIEM-bo-de-thi.zip`, xem khối phát hiện mới đầu Phase 6)
    — dùng làm LÕI của bộ eval thay vì tự bịa toàn bộ, vì đây đúng văn phong/độ khó BTC ra đề (đã thấy
    sẵn ví dụ đánh đố tự nhiên: 1 câu QA hỏi tên xã "tại thời điểm đó" ở Khánh Hòa — dễ dính bẫy sáp
    nhập/đổi tên địa giới; 1 câu TRAKE nấu ăn cần phân 4 mốc rất sát nhau). Vẫn phải tự xem video thật
    để gán `(video_id, frame_id)` cho từng câu — zip chỉ có câu hỏi, không có đáp án.
  - Đề xuất cỡ mẫu: ~30 câu KIS + 10 QA + 10 TRAKE (đủ để so sánh có ý nghĩa mà không tốn quá nhiều
    thời gian ghi tay); chọn video trải đều 10 batch trong `data/extracted/keyframes/` (L21–L30). 24
    câu thật ở trên mới có 18 KIS + 3 QA + 3 TRAKE — KIS gần đủ ngay, QA/TRAKE cần tự đặt thêm ~7 câu
    mỗi loại nữa cho đủ cỡ mẫu và đủ tin cậy khi so sánh riêng từng loại.
  - Trải phổ độ khó, không chỉ toàn "lắt léo": giữ một số câu dễ (đối tượng/màu/hành động rõ) làm
    sanity check hệ thống chưa hỏng, phần còn lại mới dồn vào các dạng đánh đố bên dưới.
  - Dạng câu hỏi lắt léo nên có trong bộ test: đối tượng nhỏ/khuất một phần khung hình; nhiều đối
    tượng giống nhau chỉ khác 1 chi tiết (màu áo, số áo, loại xe); hành động rất ngắn giữa video dài;
    mô tả phụ thuộc thứ tự thời gian ("trước khi X thì Y" — quan trọng riêng cho TRAKE); câu hỏi đếm
    số lượng (QA — dễ sai vì phần đếm nằm ở vision LLM, không phải retrieval); câu phủ định/loại trừ
    ("cảnh không có người"); câu tiếng Việt có từ địa phương/viết tắt (kiểm tra `rewrite.py` dịch có
    giữ đúng ý); ảnh dễ đánh lừa CLIP (phản chiếu gương, ảnh lồng trong ảnh/màn hình TV trong khung).
- [ ] So baseline: clip-ViT-B-32 hiện tại + vitl14/siglip/dfn (4/4 dùng được) trên cùng bộ eval trên,
  đo đúng công thức R@{1,5,20,50,100} — không dùng metric khác để kết quả phản ánh đúng cách BTC
  chấm. `jina` tạm loại khỏi vòng so sánh — dữ liệu `.npy` hỏng 100% NaN, cần chạy lại job Kaggle
  trước (xem khối đầu Phase 6), không chặn việc so 4 model còn lại. **Script đo đã xong: `scripts/eval/run_eval.py`** (đọc `eval_ground_truth.json`,
  in bảng + ghi `docs/eval_baseline_comparison.md`) — chỉ còn chờ ground truth ở mục trên rồi chạy
  `python scripts\eval\run_eval.py`. Phạm vi đã chốt: chỉ đo retrieval (video_id + frame trong
  `[s,e]`), KHÔNG chấm answer text QA, TRAKE chấm từng event độc lập rồi lấy trung bình — chi tiết lý
  do xem docstring `run_eval.py`.
  **Cơ chế so sánh KHÔNG cần web/UI riêng** — 1 script offline thuần, không gọi LLM, không đụng
  `scripts/index.py`/`retrieve.py`. Nếu sau đó muốn xem trực quan vài case cụ thể model mạnh vẫn sai
  (debug định tính, không phải ra quyết định), dùng lại `scripts/app.py` (Gradio) có sẵn — trỏ tạm
  `FEATURES_DIR` sang model khác để search bằng tay — không cần dựng thêm công cụ web mới cho việc này.
  **Đã chạy thử thật (2026-08-20)** — `eval_ground_truth.json` có 19 câu (18 KIS do AI cố vấn tự viết
  sau khi trực tiếp xem ảnh keyframe thật + 1 QA đếm số), `run_eval.py` chạy hết cả 4 model, ra
  `docs/eval_baseline_comparison.md`: `siglip`/`dfn` vượt rõ `clip_vitb32` ở mọi ngưỡng R@k (VD R@100
  KIS: 0.667 baseline vs 0.944 siglip vs 1.000 dfn). **CHƯA đủ tin cậy để quyết định** — mẫu còn nhỏ
  (18/~30-50 mục tiêu), 0 câu TRAKE, và câu hỏi+đáp án cùng do AI viết từ 1 ảnh nên dễ "dễ" hơn câu
  thật (xem văn phong tự nhiên ở 24 câu `THUNGHIEM-bo-de-thi.zip`) — chỉ là tín hiệu sớm ủng hộ hướng
  đầu tư tiếp, không đổi lịch "không swap model trước đợt 1" ở dưới. Việc còn lại: câu QA/TRAKE thật +
  câu phủ định/từ địa phương — để người tự làm (không AI viết được đáng tin cho 2 dạng này).
- [ ] Cân nhắc ensemble/fusion nhiều model thay vì chọn 1 — kiến trúc lưu embedding `.npy` tách riêng
  theo từng model nên rank-fusion khả thi mà không phá `retrieve.py`, nhưng đây là quyết định kiến
  trúc mới — chỉ làm SAU khi bộ eval chứng minh fusion thắng rõ single-model tốt nhất, không làm vì
  "trực giác nhiều model chắc tốt hơn".
- [ ] **KHÔNG đổi model sản xuất trước Sơ tuyển đợt 1 (19:30 21/8)** — không còn đủ thời gian validate
  an toàn (chưa có bộ eval, chưa test QA/TRAKE với embedding mới). Giữ `clip-ViT-B-32` cho đợt 1. Dùng
  đúng khoảng 21/8→28/8 (giữa đợt 1 và đợt 2, ~1 tuần — dài hơn hẳn khoảng đệm bằng 0 trước đợt 1) làm
  cửa sổ kiểm định + swap nếu có bằng chứng thắng rõ ràng. Giữ nguyên `data/extracted/clip-features-32/`
  cũ (không xoá, không ghi đè `FEATURES_DIR`) để luôn rollback được nếu model mới phát sinh vấn đề.
- [X] Kiểm tra dung lượng đĩa trống trước khi giải nén — đã xác nhận **không phải vấn đề tại thời
  điểm đó** (88GB trống / 476GB, 3 zip feature chỉ ~927MB tổng, đã giải nén xong cả 3, không cần dọn
  zip nguồn). **Cập nhật 2026-08-20 (cùng ngày, sau khi tải thêm video):** số liệu này đã cũ — xem
  khối đầu Phase 6 ("Lưu ý dung lượng đĩa đã đổi" + "Phát hiện mới") để biết trạng thái hiện tại
  (~31GB trống, Jina đã chạy xong).

Success: có bộ eval ground-truth thật + bảng so sánh R@{1,5,20,50,100} của ≥3 baseline, quyết định
model cho Sơ tuyển đợt 2 dựa trên bằng chứng đo được, có đường rollback nếu cần.

---

## Blockers / Risks

- **Deadline cứng: Sơ tuyển đợt 1 mở 19:30 21/8/2026, chỉ 3 tiếng (đóng 22:30 21/8)** — và Vòng thử
  nghiệm (cơ hội tập dượt duy nhất) đóng đúng lúc đó, không có khoảng đệm. Mọi việc ở Phase 5 phải
  xong trước mốc này. Xem [docs/Thong tin vong So tuyen AIC2026.md](<docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>) §5.
- **BTC đã công bố format nộp bài chính thức (2026-08-20)** — không còn là suy đoán. 2 lỗi format
  xác nhận trong `build_submission.py` (thư mục `submission/` trong ZIP, tên file CSV) **đã fix**
  — xem Phase 5 mục đầu. Vẫn cần chạy thử nộp thật 1 zip trong Vòng thử nghiệm để xác nhận hệ
  thống BTC chấp nhận, không chỉ dựa vào validator nội bộ.
- **Single LLM provider (Gemini)** — đã hết, có fallback 3 tầng + key rotation (xem Phase 5), cả 3
  provider đều có key thật trong `.env`.
- **Chưa test load thật** — chưa rõ latency `run_qa`/`run_trake` (gọi Gemini nhiều lần) có đủ nhanh
  để rà soát tay trong thời gian thi hay không.
