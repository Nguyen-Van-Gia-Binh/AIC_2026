---
# ============================================================
# METADATA — Đọc phần này trước, quyết định có cần đọc sâu không
# ============================================================

title: "AIC2026 — Hỏi đáp trước Vòng Sơ tuyển: Quy trình thi, Nộp bài & Chấm điểm"
file: "AIC2026_SoTuyen_QuyTrinh_NopBai_ChamDiem.md"
created: "2026-08-19"
session: "pre-qualifying-round QnA"
tags:
  - AIC2026
  - vòng-sơ-tuyển
  - nộp-bài
  - chấm-điểm
  - KIS
  - QnA
  - TRAKE
  - Codabench
  - FiftyOne
  - timeline
  - human-in-the-loop

# --- Tóm tắt 1 dòng (cho agent scan nhanh) ---
summary: >
  Ghi chép buổi hỏi-đáp trước vòng sơ tuyển AIC 2026: định dạng file nộp bài
  (zip → CSV, KIS/Q&A/TRAKE), cách tính frame & timestamp, phạm vi câu hỏi,
  công cụ được phép dùng (FiftyOne baseline, vector DB, API trả phí), quy tắc
  chấm điểm & hậu kiểm, cấu trúc 3 đợt sơ tuyển, so sánh sơ tuyển vs chung kết,
  timeline và danh sách các điều dễ nhầm lẫn.

# --- Mức độ ưu tiên đọc ---
read_priority: high          # high | medium | low
read_depth_needed: deep      # shallow | deep
# deep vì chứa nhiều quy tắc kỹ thuật cụ thể ảnh hưởng trực tiếp đến điểm số

# --- Khi nào cần đọc sâu ---
read_deep_when:
  - "Chuẩn bị nộp bài lần đầu (định dạng file zip/CSV, tên file, encoding)"
  - "Tính frame/timestamp từ video (presentation time × FPS, frame bắt đầu từ 1)"
  - "Hiểu cách tính điểm R@k cho KIS, Q&A, TRAKE"
  - "Xử lý Q&A có thông tin âm thanh hoặc kiến thức ngoài video"
  - "Quyết định có cần xây UI hay chỉ cần API"
  - "Tìm hiểu baseline FiftyOne và các vector DB tích hợp"
  - "Kiểm tra lại các điều dễ nhầm (Section 14)"

# --- Khi nào KHÔNG cần đọc sâu ---
skip_when:
  - "Chỉ cần hiểu bài toán video retrieval là gì → đọc NoiDungBuoi4.md"
  - "Đang tìm kiến trúc hệ thống / pipeline kỹ thuật → file này không chứa"
  - "Cần thông tin về dữ liệu B1/B2 chi tiết → xem tài liệu chính thức BTC"

# --- Nội dung đặc biệt hữu ích ---
key_sections:
  - "Section 2: Định dạng nộp bài (KIS/Q&A/TRAKE → zip → CSV)"
  - "Section 3: Cách tính frame chính xác (presentation time × FPS)"
  - "Section 8: Chấm điểm & hậu kiểm (khi nào sai lệch vẫn được tính đúng)"
  - "Section 14: Danh sách điều dễ nhầm lẫn — ĐỌC TRƯỚC KHI NỘP BÀI"

# --- Quan hệ với file khác ---
related_files:
  - "docs/Training/NoiDungBuoi4.md"        # Buổi 1: bối cảnh bài toán, CLIP, AI Agent
  - "docs/Training/NoiDungBuoi2.md"        # (nếu có)
  - "README.md"

# --- Người viết / nguồn ---
source: "Transcript buổi hỏi-đáp trước vòng sơ tuyển AIC HCMC 2026 — đã làm sạch & nhóm theo chủ đề"
language: vi
---

# Ghi chú buổi tập huấn AIC HCMC 2026 — Vòng sơ tuyển

> Tài liệu này tổng hợp và làm sạch nội dung từ transcript buổi tập huấn/hỏi-đáp trước vòng sơ tuyển AIC HCMC 2026. Đã loại bỏ timestamp, từ đệm, nói lắp, và đoạn nhạc nền đầu video; nội dung được **nhóm lại theo chủ đề** thay vì theo trình tự thời gian gốc để dễ tra cứu. Tài liệu này **bổ sung/làm rõ** cho tài liệu chính thức "Thông tin vòng Sơ tuyển AIC2026", không thay thế nó.

---

## 1. Dữ liệu & hệ thống thi

- Cuộc thi sử dụng hệ thống **Codabench** để nộp bài, giúp tránh việc bị bên thứ ba làm chậm/ảnh hưởng trong lúc chấm.
- Tài khoản thi thử sẽ được gửi **trễ nhất vào thứ Ba** (kỳ vọng gửi sớm hơn, có thể ngay ngày hôm sau buổi tập huấn).
- **Vòng sơ tuyển đợt 1** (thi tối thứ Sáu tuần sau buổi tập huấn) sẽ chỉ dùng **dữ liệu Batch 1 (B1)** — bộ dữ liệu đã cung cấp sẵn cho thí sinh làm quen. Batch 2 (B2) chưa kịp chốt danh sách nên chưa dùng cho đợt 1.
- **B2** (dự kiến dùng cho đợt 2, đợt 3 và vòng chung kết) sẽ tập trung chủ yếu vào **dữ liệu giao thông và thể thao**, đồng thời BTC sẽ giới hạn phạm vi nội dung câu hỏi để thí sinh dễ tập trung ôn luyện hơn so với B1 (B1 có chủ đề rất đa dạng: nấu ăn, học/luyện thi, v.v. nên phạm vi câu hỏi khá rộng).

## 2. Nộp bài — định dạng & quy trình

- Với mỗi truy vấn, thí sinh nộp một **danh sách câu trả lời** (tối đa 100 dòng, giống khái niệm "run list" trong các hệ thống truy vấn thông tin), xếp theo thứ tự ưu tiên — Final Score được tính dựa trên vị trí xếp hạng của câu trả lời đúng đầu tiên (xem công thức R@k trong tài liệu chính).
- Định dạng mỗi dòng theo loại truy vấn:
  - **KIS**: `video_id, frame_id`
  - **Q&A**: `video_id, frame_id, answer`
  - **TRAKE**: `video_id, frame_id_1, frame_id_2, ..., frame_id_n`
- File cuối cùng nộp lên là **1 file zip**, bên trong chứa **1 folder tên "submission"**, trong đó là các **file CSV** — mỗi file CSV tương ứng với một file truy vấn (tên file CSV cần khớp với tên file truy vấn được cung cấp, có tiền tố theo đợt thi và loại truy vấn, ví dụ dạng `query_<đợt>_<loại>.csv`). Cấu trúc/tên file chính xác sẽ được BTC thông báo chính thức kèm theo khi mở hệ thống nộp bài (trễ nhất thứ Ba).
- **Tên video khi nộp không cần đuôi `.mp4`** — chỉ cần ghi tên file, ví dụ `video_abc` (không phải `video_abc.mp4`).
- BTC sẽ cung cấp **submission validator / input validator** để thí sinh tự kiểm tra file nộp đúng định dạng trước khi nộp thật.
- Lỗi thường gặp mọi năm: **encoding không phải UTF-8** (thường do lưu bằng Excel rồi export ra CSV) — BTC có script xử lý các trường hợp phổ biến này nên không cần quá lo lắng.
- Nếu thí sinh **sai cú pháp nhỏ** (dù lỗi đã được cảnh báo từ lúc thi thử) nhưng thực chất đã **tìm đúng đáp án**, BTC vẫn hỗ trợ chấm/sửa lại thủ công, không bị mất điểm oan vì lỗi kỹ thuật nhỏ.

## 3. Frame, timestamp & cách xác định đáp án

- **Frame đầu tiên được tính là frame 1** (không phải frame 0).
- Khoảng đáp án đúng `[s, e]` được cho theo **cả frame và giây** — nhưng nộp theo **frame sẽ chính xác hơn** vì quy đổi sang giây có thể lệch một chút do làm tròn.
- Cách tính frame hiện tại: `frame = presentation time × FPS` (dùng **presentation time**, tức mốc thời gian mà frame đó thực sự hiển thị — khác với thứ tự frame thô mà decoder trả về).
- FPS của video xem trong thông tin encoding (ví dụ dùng phần mềm **MPC-HC**: bấm `Ctrl+G` hoặc vào `Navigator → Go to` để xem frame hiện tại và FPS).
- Nếu tính ra frame = 0 hoặc không khớp, có thể **cộng thêm 1** hoặc dùng **keyframe map** đính kèm dữ liệu — năm trước BTC xử lý bằng cách sửa lại script chấm. **Sai lệch khoảng 1 frame vẫn được tính đúng.**
- **Keyframe BTC cung cấp chỉ mang tính chất gợi ý/giải pháp mẫu**, không bắt buộc phải dùng đúng các keyframe đó. Thí sinh hoàn toàn có thể tự trích xuất thêm frame để tăng độ phủ nếu cảm thấy keyframe có sẵn chưa đủ (đánh đổi là tốn thêm thời gian tính toán).
- **Vòng sơ tuyển:** chỉ được nộp đáp án bằng **frame**, KHÔNG được nộp bằng millisecond.
- **Vòng chung kết:** cho phép nộp bằng **frame hoặc millisecond**, tùy hệ thống chấm của thí sinh.

## 4. Độ dài & đặc điểm của các đoạn mô tả

- **KIS & Q&A:** đoạn mô tả tương ứng với một khoảng video thường dao động từ khoảng **4–10 giây (ngắn nhất)** đến khoảng **5 phút (dài nhất)**, tương đương từ vài trăm đến vài nghìn frame. Nếu cần đặt một ngưỡng an toàn (upper bound) cho hệ thống tìm kiếm, có thể dùng mốc **5 phút**.
- Có trường hợp mô tả gồm **2 đoạn tách rời** trong cùng một bản tin (ví dụ đầu và cuối bản tin), đoạn giữa không liên quan đến mô tả — khoảng cách giữa 2 đoạn mô tả này thường **3–5 phút**. Nộp frame nằm trong khoảng đáp án đã định vẫn được tính đúng dù đoạn giữa không khớp mô tả.
- **TRAKE:** khoảng đúng cho mỗi khoảnh khắc ngữ nghĩa **thường dưới 10 frame** — đây là **giá trị điển hình** tham khảo từ dữ liệu năm trước, **không phải cam kết trần tuyệt đối**. Một khoảnh khắc (ví dụ chân vận động viên rời mặt đất) thực tế có thể chỉ kéo dài khoảng 3 frame.

## 5. Phạm vi nội dung câu hỏi

- Vì dữ liệu là video nên câu hỏi có thể khai thác **mọi loại thông tin** trong đó: nhận dạng chữ (OCR/text trong khung hình), đồ vật, sự kiện hoặc chuỗi sự kiện liên tiếp, tracking (đối tượng di chuyển theo hướng nào trong đoạn video), âm thanh, v.v. Với chủ đề giao thông, tập câu hỏi liên quan sẽ khá rộng.
- Mô tả truy vấn có thể yêu cầu **kiến thức/tra cứu bên ngoài**. Ví dụ: video chỉ nói "Tổng thống Mỹ" nhưng mô tả truy vấn ghi rõ "Donald Trump"; hoặc câu hỏi kiểu "quốc gia có GDP cao nhất năm được nhắc đến trong video là gì?". Trong các trường hợp này, thí sinh **được phép tra cứu ngoài (Google search...)** để lấy thông tin bổ trợ — điều kiện là vẫn phải **xác định đúng đoạn video** làm minh chứng cho câu trả lời, chứ không được chỉ dựa vào search engine để suy ra đáp án mà không chỉ ra đúng vị trí trong kho video.
- Truy vấn dạng **Q&A** (lưu ý: gọi là "Q&A", không phải "VQA") — câu trả lời **có thể phụ thuộc vào audio**, không nhất thiết chỉ dựa trên hình ảnh (visual).

## 6. Công cụ & kỹ thuật được phép dùng

- **Không giới hạn kỹ thuật**: được dùng OCR, object detection, hoặc bất kỳ phương pháp nào để khai thác thông tin từ dữ liệu.
- **Được phép dùng công cụ/API trả phí** trong pipeline. BTC không đồng bộ hay kiểm soát cấu hình máy của từng đội nên không giới hạn việc này.
- **Được tự do sử dụng giải pháp có sẵn** từ các đội/nhóm khác hoặc từ các paper công khai (ghép nối các thành phần lại và chạy trên dữ liệu cuộc thi là hợp lệ). Tuy nhiên, nếu mục tiêu là **nộp kết quả để viết bài báo khoa học** (đưa vào kỷ yếu hội nghị), thí sinh **cần thể hiện được đóng góp/tính mới** của hệ thống, không chỉ đơn thuần ghép các giải pháp sẵn có.

### Baseline mẫu do BTC cung cấp
- Baseline xây dựng dựa trên công cụ mã nguồn mở **FiftyOne ("51")** — công cụ giúp explore/quản lý dataset, có giao diện app trực quan để xem annotation và thực hiện tìm kiếm/lọc dữ liệu.
- **FiftyOne Brain**: cung cấp các phép tính như similarity, kiểm tra dữ liệu unique, biểu diễn không gian embedding để xem các ảnh lân cận nhau, v.v.
- FiftyOne có thể **tích hợp với vector database** (Qdrant, Pinecone, Milvus, LanceDB...) — nhiều đội dùng thử để so tốc độ, cũng có đội chỉ dùng thư viện tính nearest-neighbor (ví dụ FAISS của Facebook) mà không cần vector database riêng.
- BTC **không nhận tài trợ** từ FiftyOne — chỉ giới thiệu vì thấy công cụ phù hợp, thí sinh hoàn toàn không bắt buộc phải dùng.
- Baseline sẽ được gửi dưới dạng **Jupyter notebook** kèm **video hướng dẫn chạy cụ thể**, đăng trên Google Drive chung, có email thông báo khi cập nhật (dự kiến gửi trong ngày diễn ra buổi tập huấn).
- Lưu ý kỹ thuật: FiftyOne hiện **chưa hỗ trợ Python 3.14**, nên dùng **Python 3.10–3.12** để chạy ổn định. Phần tích hợp vector database yêu cầu cài thêm **Docker**.

### Hệ thống tham khảo khác
- Có thể tham khảo các hệ thống mã nguồn mở/paper từ hai cuộc thi truy vấn video tương tự:
  - **VBS (Video Browser Showdown)** — cùng hình thức thi, chỉ khác dữ liệu và đặc trưng câu hỏi; nhiều đội có công bố (open-source) hệ thống của họ.
  - **LSC (Lifelog Search Challenge)** — có nhiều metadata hơn so với dữ liệu của AIC (dữ liệu AIC chủ yếu chỉ có video).

## 7. Human-in-the-loop (con người can thiệp vào kết quả)

- Cuộc thi **cho phép** kết quả nộp có sự can thiệp thủ công của con người — **không bắt buộc giải pháp tự động hoàn toàn**.
- File truy vấn (input) do BTC cung cấp **không nhất thiết phải đưa thẳng vào hệ thống để tự động ra đáp án**. Thí sinh có thể:
  - Tự paraphrase/viết lại câu truy vấn theo cách phù hợp với hệ thống của mình (hiểu hệ thống của mình dùng từ ngữ nào sẽ ra đáp án đúng hơn), hoặc
  - Tự xem lại video để xác nhận/chỉnh sửa/sắp xếp lại đáp án trước khi nộp.
- Mục tiêu hướng đến của hệ thống là **hỗ trợ người dùng tốt nhất có thể** (tương tác người–máy), không phải một pipeline tự động hoàn toàn không cần con người.
- Chiến thuật nhiều thành viên trong đội cùng thử nghiệm, tìm nhiều câu truy vấn mẫu để tăng kỹ năng search cũng là chiến thuật hợp lệ. Tuy nhiên nếu hướng đến việc nộp bài viết báo khoa học, việc đánh giá sẽ **ưu tiên tính mới** của hệ thống hơn là kỹ năng thao tác thủ công.

## 8. Chấm điểm & hậu kiểm

- Công thức R-Score / Final Score theo từng loại truy vấn (KIS, Q&A, TRAKE) áp dụng đúng như trong tài liệu chính thức.
- **Q&A**: việc so khớp ngữ nghĩa giữa đáp án nộp và đáp án đúng do một **mô hình LLM** đảm nhận ở bước đầu, sau đó **BTC đọc lại/lọc lại thủ công** danh sách đáp án. Vì đáp án Q&A thường là tên riêng hoặc thông tin số lượng nên mô hình chấm khá chính xác, ít gặp trường hợp gây khó cho mô hình.
- **Hậu kiểm bằng mắt**: sau khi thí sinh nộp bài, BTC sẽ trích xuất đúng frame đã nộp và xem lại có khớp với mô tả hay không, có nằm trong đoạn video đáp án hay không.
  - Nếu frame nộp bị mờ do đang chuyển cảnh, hoặc đoạn nộp dài hơn đáp án gốc nhưng nội dung vẫn đúng, sau khi hậu kiểm thường **vẫn được tính đúng** — không cần quá lo lắng về sai lệch nhỏ.
  - Trường hợp hy hữu (khoảng **30 câu thì có ~1 câu**) đáp án gốc hóa ra **không "unique"** (có nhiều đoạn/video khác cũng hợp lý) — các trường hợp này thí sinh vẫn được tính điểm đúng.
  - Trường hợp mô tả bị lỗi nhẹ do khác biệt giữa người ra đề và người review (ví dụ mô tả màu sắc không khớp, hoặc số lượng đối tượng đếm được có tranh cãi — như có tính thủ môn là "cầu thủ" hay không) — **cả hai đáp án hợp lý đều được chấp nhận là đúng**. Theo kinh nghiệm các năm, mỗi vòng thường chỉ có khoảng 1–2 câu gặp tình huống này.
- Kết quả vòng sơ tuyển **chỉ nhằm đánh giá thí sinh có đủ điều kiện vào vòng chung kết**, không phản ánh hoàn toàn thứ hạng cuối cùng. Nhiều đội có thứ hạng sơ tuyển thấp vẫn có thể đạt kết quả cao ở chung kết, vì vòng chung kết có **áp lực thời gian mỗi câu truy vấn cao hơn** vòng sơ tuyển.

## 9. Cấu trúc thi & xét vào vòng chung kết

- Sơ tuyển gồm **3 đợt**, mỗi đợt đều thi cả **3 loại truy vấn** (KIS, Q&A, TRAKE) — **không loại trực tiếp qua từng đợt**, mà **tính tổng điểm cả 3 đợt** để xét vào vòng chung kết. Nếu đợt 1 làm không tốt, vẫn có thể gỡ lại bằng kết quả đợt 2, đợt 3 (các đợt sau có nhiều câu hỏi hơn).
- **Đợt 1** mang tính chất làm quen: số câu hỏi ít hơn, tỉ trọng nghiêng nhiều về **KIS**. Ví dụ tham khảo: khoảng 20 câu, trong đó ~15 câu KIS, 4 câu Q&A, 1 câu TRAKE (số liệu ước tính, BTC có thể điều chỉnh theo thời lượng thực tế).
- Các đợt sau (2, 3): số lượng câu hỏi tăng dần, tỉ trọng Q&A và TRAKE cũng tăng lên so với đợt 1.
- Số câu mỗi đợt của năm trước (tham khảo): **25, 30, 35** (đợt 1/2/3).
- Danh sách đội chính thức vào vòng chung kết phụ thuộc vào **không gian địa điểm tổ chức** (năm ngoái tổ chức tại ĐH Sư phạm Kỹ thuật, tổng cộng khoảng **60 đội** cho cả hai bảng A+B; năm nay địa điểm dự kiến thay đổi, sẽ thông báo sau).
- Tiêu chí xét vào vòng trong: (1) xếp hạng cao trên bảng tổng; (2) có thể bị loại nếu vi phạm quy chế; (3) có thể được mời xét theo tiêu chí phụ khác.
- Theo trí nhớ của BTC, năm ngoái **top 30** gần như chắc chắn vào được vòng trong ở bảng A.

## 10. So sánh Sơ tuyển vs Chung kết

| Tiêu chí | Vòng sơ tuyển | Vòng chung kết |
|---|---|---|
| Ngôn ngữ truy vấn | Tiếng Việt | Song ngữ Anh + Việt |
| Định dạng nộp vị trí | Chỉ **frame** | **Frame** hoặc **millisecond** |
| Dữ liệu | B1 (đợt 1); B1+B2 (đợt 2, 3) | Bộ dữ liệu chung kết riêng |
| Áp lực thời gian/câu | Thấp hơn | Cao hơn |
| Cho phép human-in-the-loop | Có | Có (thường áp lực thời gian khiến can thiệp thủ công khó hơn) |

## 11. Về giao diện (UI/UX)

- **Không bắt buộc** phải thiết kế giao diện đồ họa riêng. Một giao diện dòng lệnh (CLI) hoặc gọi thẳng API cũng được xem là một hình thức UI/UX hợp lệ.
- Thí sinh hoàn toàn có thể dự thi chỉ bằng cách **viết một API để nộp bài**, không cần bất kỳ giao diện người dùng nào khác.
- Việc đánh giá UI/UX (qua hình thức để các đội đổi hệ thống thử của nhau) **không nằm trong tiêu chí xét giải chính thức** — năm trước có đề xuất nhưng không đủ thời gian tổ chức trong khuôn khổ cuộc thi.

## 12. Ground truth (đáp án gốc) cho mục đích viết báo khoa học

- Sau vòng sơ tuyển, BTC có thể cung cấp **ground truth/đáp án gốc** cho các nhóm có nhu cầu viết bài báo khoa học — nhưng chỉ cấp **thông qua giảng viên hướng dẫn** của nhóm, không cấp trực tiếp cho thí sinh.
- Quy trình: giảng viên hướng dẫn liên hệ **hội đồng chuyên môn** của BTC (qua email hoặc thông qua BTC), trình bày thông tin nhóm/đội, cam kết chỉ sử dụng ground truth cho mục đích viết paper, **ký giấy cam kết** trước khi được cấp dữ liệu.
- Đáp án gốc có thể **không trùng khớp hoàn toàn với keyframe** BTC cung cấp sẵn — vì keyframe chỉ là giải pháp mẫu, còn đáp án thực tế có thể nằm giữa hai keyframe liên tiếp (ví dụ bài toán đếm số lượng, một keyframe đơn lẻ không đủ thể hiện hết đối tượng cần đếm nếu camera đang quét ngang; phải xem cả đoạn video mới chính xác nhất).

## 13. Timeline dự kiến

- Tài khoản thi thử + hệ thống nộp bài chính thức: gửi **trễ nhất thứ Ba** (kỳ vọng sớm hơn).
- Baseline (FiftyOne notebook) + video hướng dẫn: đăng trên Google Drive **trong ngày diễn ra buổi tập huấn**, có email thông báo khi cập nhật.
- **Vòng thi đợt 1**: tối **thứ Sáu** (tuần sau buổi tập huấn).

## 14. Tổng hợp nhanh — Những điều dễ nhầm lẫn

- ❌ Frame bắt đầu từ 0 → ✅ Frame bắt đầu từ **1**.
- ❌ Tên video phải có đuôi `.mp4` → ✅ **Không cần** đuôi file.
- ❌ Sơ tuyển cho nộp bằng millisecond → ✅ Sơ tuyển **chỉ nộp bằng frame**; millisecond chỉ áp dụng ở **chung kết**.
- ❌ TRAKE bắt buộc khoảng đúng dưới 10 frame → ✅ Đó chỉ là **giá trị điển hình tham khảo**, không phải cam kết cứng.
- ❌ Sai 1 frame là bị tính sai → ✅ Sai lệch khoảng 1 frame **vẫn được tính đúng**.
- ❌ Không được tra cứu thông tin ngoài dữ liệu video → ✅ **Được phép** tra cứu ngoài, miễn là chỉ ra đúng đoạn video minh chứng.
- ❌ Phải có giải pháp tự động 100% mới hợp lệ → ✅ **Cho phép human-in-the-loop**, chỉ cần không phải thao tác thủ công thay thế hoàn toàn cho hệ thống.
- ❌ Không được dùng tool trả phí / giải pháp có sẵn của người khác → ✅ **Được phép**, chỉ cần lưu ý nếu viết paper thì cần thể hiện tính mới.
