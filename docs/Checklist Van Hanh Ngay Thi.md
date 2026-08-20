# Checklist vận hành Gradio UI — ngày thi (Sơ tuyển đợt 1)

> Dành cho người trực tiếp thao tác `scripts/app.py` trong cửa sổ thi thật (Sơ tuyển đợt 1: **19:30
> → 22:30, 21/8/2026 — chỉ 3 tiếng, không có khoảng đệm** với Vòng thử nghiệm kết thúc ngay trước
> đó). Mục tiêu: không lúng túng, không mất điểm vì thao tác sai chứ không phải vì retrieval yếu.
> Tham chiếu format nộp bài đầy đủ: [Thong tin vong So tuyen AIC2026.md](<Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>)
> §4. Tham chiếu thao tác export code: [SKILL.md](<../.agents/skills/submission/SKILL.md>).

## Phase 0 — Chuẩn bị trước giờ G (làm trong Vòng thử nghiệm, không phải lúc 19:30)

- [ ] `.venv` cài đủ dependency, `.env` có API key thật cho cả 3 provider (Gemini/Groq/NVIDIA).
- [ ] Dữ liệu (`data/`) đã giải nén đủ — batch hiện có + batch mới nếu BTC cấp thêm trước giờ thi.
- [ ] Đã chạy `scripts/app.py` thử ít nhất 1 lần thành công **trước** 19:30, ghi nhớ thời gian load
      index + CLIP model lúc khởi động (vài chục giây, tùy máy) — để không bị bất ngờ mất thời gian
      chờ ngay đầu giờ thi.
- [ ] Trình duyệt đã đăng nhập sẵn tài khoản thi BTC cấp (giữ session, tránh phải đăng nhập lại
      giữa giờ).
- [ ] Biết trước nơi BTC sẽ gửi/đăng gói truy vấn (`query-N-kis.txt`, `query-N-qa.txt`,
      `query-N-trake.txt`) và cách mở nhanh (Notepad/VSCode) — không mất thời gian tìm chỗ tải.
- [ ] Nếu đội có ≥ 2 người: phân vai rõ — 1 người thao tác UI, 1 người đọc/chuẩn bị câu truy vấn kế
      tiếp + theo dõi đồng hồ + đối chiếu checklist. Pipeline hoá để tiết kiệm giây.
- [ ] Restart máy/app 1 lần trước giờ G để đảm bảo state sạch, RAM trống.

## Nguyên tắc chung — nhớ trước khi bắt đầu

- **Thứ tự dòng trong bảng kết quả quyết định điểm.** Final Score = trung bình R@{1,5,20,50,100};
  phương án tin cậy nhất phải nằm ở **dòng đầu tiên**, không phải chỉ cần "có mặt trong 100 dòng".
- **Add to Queue với cùng Query ID sẽ GHI ĐÈ** mục cũ (không cộng dồn) — cứ sửa lại rồi Add lại
  thoải mái, không sợ bị nhân đôi.
- **Query ID phải khớp CHÍNH XÁC** tên file gốc BTC cấp, bỏ đuôi `.txt` (vd. file
  `query-1-kis.txt` → gõ `query-1-kis`) — copy tên file, đừng gõ tay để tránh lỗi chính tả. Sai tên
  gần như chắc chắn nghĩa là truy vấn đó không được chấm.
- **Q&A và TRAKE cho phép gõ tiếng Việt trực tiếp** — 2 pipeline này tự dịch VN→EN nội bộ trước khi
  đưa vào CLIP. Riêng tab **KIS dùng pipeline tuyến tính không tự dịch** — phải để checkbox
  "🌐 Tự động dịch VN→EN" bật (mặc định đã bật) nếu gõ tiếng Việt ở đây.
- **Tối đa 3 lần nộp/gói truy vấn, chỉ lần CUỐI CÙNG tính điểm** (Private LB, 100% đáp án). Public
  Leaderboard lúc thi chỉ tính trên 50% đáp án → có nhiễu, đừng hoảng vì điểm Public thấp.

## Phase 1 — Vòng lặp xử lý từng truy vấn (lặp lại cho mỗi file BTC cấp)

### 🔍 Tab KIS — Tìm kiếm văn bản

1. Mở file `query-N-kis.txt`, đọc mô tả sự kiện.
2. Dán vào ô **"Mô tả cảnh cần tìm"** (tiếng Việt OK, để nguyên checkbox tự dịch).
3. Bấm **🔍 Search** (hoặc Enter trong ô).
4. Rà soát gallery ảnh — đối chiếu bằng mắt candidate top có khớp mô tả không.
5. Nếu sai: thử viết lại mô tả cụ thể hơn, tăng Top-k để tìm xa hơn trong danh sách, hoặc tắt
   auto-dịch và tự gõ thẳng tiếng Anh (CLIP mạnh nhất với tiếng Anh).
6. Sửa tay trên bảng nếu cần — **kéo dòng đúng nhất lên trên cùng**, xoá dòng rác.
7. Gõ **Query ID** = tên file gốc bỏ đuôi (`query-1-kis`).
8. Bấm **➕ Add to Submission Queue**, xác nhận thông báo ✅ đúng số dòng mong đợi.

### ❓ Tab Q&A — Trả lời câu hỏi

1. Mở file `query-N-qa.txt`, tách mô tả cảnh và câu hỏi cụ thể.
2. Dán mô tả cảnh vào **"Mô tả cảnh (để tìm kiếm)"**, câu hỏi vào **"Câu hỏi cụ thể"** (tiếng Việt
   OK — không cần tick gì thêm).
3. Bấm **🤖 Run Q&A Pipeline** — chờ (LLM chạy 1–2 vòng reflection, xem "Số vòng" trong status để
   biết đã chạy mấy vòng; có thể chậm hơn nếu provider ưu tiên bị rate-limit rồi tự fallback).
4. Rà soát ô **"💡 Câu trả lời"** — đọc kỹ, **sửa tay nếu nghi LLM đoán sai/ảo giác**, đối chiếu
   gallery frame nổi bật để xác nhận bằng mắt.
5. Rà soát bảng Top-100 — sắp xếp để frame đúng nhất lên dòng đầu, như KIS.
6. Lưu ý: ô "Câu trả lời" là **giá trị DUY NHẤT áp dụng cho mọi dòng** khi export — chỉ cần sửa
   đúng 1 lần trong ô đó, không cần sửa từng dòng riêng.
7. Gõ Query ID (`query-2-qa`), bấm **➕ Add to Queue**.

### 🎬 Tab TRAKE — Chuỗi sự kiện

1. Mở file `query-N-trake.txt`, đọc mô tả tổng quát chuỗi sự kiện + danh sách N mốc cần định vị.
2. Dán mô tả tổng quát vào ô đầu (tiếng Việt OK, tự dịch nội bộ).
3. Gõ **mỗi mốc sự kiện trên 1 dòng** vào ô "Danh sách khoảnh khắc", **đúng thứ tự thời gian** — số
   dòng ở đây quyết định N (số cột frame_id) khi Add to Queue. Lưu ý: N được đọc lại từ ô này **tại
   đúng lúc bấm Add to Queue**, không phải từ lúc bấm Run — nếu sửa số dòng ở ô này SAU khi Run mà
   không Run lại, bảng frame_ids cũ sẽ lệch N mới và bị chặn Add (báo thiếu/thừa mốc). Sửa ô này thì
   luôn Run lại trước khi Add to Queue.
4. Bấm **🎬 Run TRAKE Pipeline** — chờ lâu hơn Q&A (2 giai đoạn: chọn video → căn từng mốc tuần
   tự, chạy N lần gọi LLM).
5. Rà soát bảng — cột **frame_ids** dạng `40530 | 40727 | 40895`, đối chiếu đúng thứ tự đã nhập.
6. Sửa tay trực tiếp trong ô frame_ids nếu 1 mốc bị lệch — giữ đúng định dạng `số | số | số`, đủ
   N mốc, toàn số nguyên. Nếu thiếu/sai số lượng hoặc có ký tự không phải số, hệ thống **chặn Add**
   và báo lỗi rõ (không cho lọt vào queue thiếu mốc).
7. Gõ Query ID (`query-3-trake`), bấm **➕ Add to Queue**.

## Phase 2 — Trước mỗi lần Export/Nộp (tối đa 3 lần!)

- [ ] Sang tab **📦 Export**. Bấm 🔄 Refresh Queue để xem lại toàn bộ (chỉ để xem — Export vẫn lấy
      đúng dữ liệu dù không refresh).
- [ ] Đếm số dòng trong bảng queue khớp đúng **tổng số file** BTC cấp (KIS + Q&A + TRAKE cộng lại)
      — thiếu 1 query nghĩa là query đó ăn 0 điểm.
- [ ] Bấm **📦 Export ZIP** — hệ thống tự chạy validate nội bộ, đọc kỹ status hiện ra (✅/⚠️).
- [ ] Nếu có ⚠️: quay lại đúng tab, sửa, Add to Queue lại (cùng Query ID tự ghi đè), Export lại.
- [ ] Đối chiếu tay thêm với checklist chính thức BTC (§4.6 trong tài liệu BTC) — validator nội bộ
      **không** kiểm tra được "tên file khớp đúng truy vấn gốc" hay "file không có header row" một
      cách tuyệt đối, phải tự soát bằng mắt.
- [ ] Copy đường dẫn ZIP ở ô "📁 Đường dẫn file ZIP".
- [ ] Đăng nhập hệ thống chấm bằng tài khoản BTC cấp, upload đúng file ZIP vừa export.
- [ ] Ghi lại thời điểm nộp + số lần đã dùng (còn tối đa 3 lần — đừng nộp lần đầu vội khi chưa rà
      xong hết query, nhưng cũng đừng để dồn tới sát 22:30 mới nộp lần đầu).

## Phase 3 — Sau khi nộp

- Xem Public Leaderboard nhưng nhớ: chỉ tính trên 50% đáp án, có nhiễu — đừng vội sửa lại chỉ vì
  điểm Public tạm thời thấp/cao.
- Nếu còn thời gian + còn lượt nộp: ưu tiên rà lại các query có độ tự tin thấp (Q&A: cột "Độ tin
  cậy" thấp; KIS/TRAKE: gallery không rõ ràng), sửa, Add đè lên, Export + nộp lại.
- **Lần nộp cuối cùng trước 22:30 mới là điểm thật** — canh giờ, đừng để sát giờ đóng mới bấm
  Export/Upload (mạng chậm, hệ thống đông người nộp cùng lúc cuối giờ).

## Xử lý sự cố nhanh

| Tình huống | Xử lý |
|---|---|
| App lag/treo lúc chạy Q&A/TRAKE | Bình thường nếu provider LLM ưu tiên (Gemini) bị rate-limit — hệ thống tự chuyển Groq → NVIDIA, chỉ cần đợi thêm vài giây, không cần thao tác gì. |
| Sửa ô `frame_id` thành trống/không hợp lệ rồi bấm Add | App báo ⚠️ lỗi thân thiện, không crash — sửa lại ô rồi bấm Add lại. |
| Lỡ đóng nhầm tab trình duyệt | Server Gradio vẫn chạy ở `localhost:7860` — mở lại tab mới cùng địa chỉ, **queue vẫn còn** (State nằm ở server, không phải trình duyệt). |
| Bắt buộc phải tắt/restart `app.py` giữa giờ | **Queue sẽ mất sạch** (chỉ sống trong RAM) — Export ZIP **ngay trước khi restart**, dù chưa add đủ hết, để không mất phần đã làm. |
| Không chắc Query ID đúng chưa | Mở lại đúng file `.txt` BTC cấp, xem tên file (bỏ phần mở rộng), copy chính xác — đừng gõ tay. |
| TRAKE báo lỗi khi Add | Đếm lại đúng số dòng trong ô "Danh sách khoảnh khắc" (N) so với số token trong ô frame_ids (`a \| b \| c`) — phải khớp tuyệt đối và toàn số nguyên. |

## Tham chiếu nhanh vị trí nút/ô trên UI (`scripts/app.py`)

| Tab | Ô nhập chính | Nút chạy | Nút thêm vào queue |
|---|---|---|---|
| 🔍 KIS | Mô tả cảnh cần tìm | 🔍 Search | ➕ Add to Submission Queue |
| ❓ Q&A | Mô tả cảnh + Câu hỏi cụ thể | 🤖 Run Q&A Pipeline | ➕ Add to Queue |
| 🎬 TRAKE | Mô tả tổng quát + Danh sách khoảnh khắc | 🎬 Run TRAKE Pipeline | ➕ Add to Queue |
| 📦 Export | — | 🔄 Refresh Queue | 📦 Export ZIP / 🗑️ Clear Queue |
