---
# ============================================================
# METADATA — Đọc phần này trước, quyết định có cần đọc sâu không
# ============================================================

title: "AIC2026 — Buổi 1: Bối cảnh và Bài toán Video Retrieval"
file: "NoiDungBuoi4.md"
created: "2026-08-19"
session: 1
tags:
  - AIC2026
  - video-retrieval
  - KIS
  - AVS
  - VQA
  - CLIP
  - AI-Agent
  - LVLM
  - lifelog
  - surveillance

# --- Tóm tắt 1 dòng (cho agent scan nhanh) ---
summary: >
  Ghi chép buổi tập huấn đầu tiên AIC 2026: bối cảnh bài toán video retrieval,
  4 dạng task (KIS, AVS, VQA, Conversational KIS), công nghệ CLIP/LVLM/AI Agent,
  kiến trúc hệ thống indexing + query, dữ liệu BTC cung cấp, chiến thuật thi đấu.

# --- Mức độ ưu tiên đọc ---
read_priority: high          # high | medium | low
read_depth_needed: shallow   # shallow | deep
# shallow = chỉ cần đọc summary + section headers là đủ định hướng
# deep    = cần đọc toàn bộ để implement hoặc ra quyết định kỹ thuật

# --- Khi nào cần đọc sâu ---
read_deep_when:
  - "Thiết kế pipeline indexing hoặc query/retrieval"
  - "Hiểu rõ từng dạng bài toán KIS / AVS / VQA để implement"
  - "Tìm chiến lược truy vấn và best practice thi đấu"
  - "Nắm rõ cấu trúc dữ liệu BTC cung cấp (keyframe, metadata, CLIP feature)"

# --- Khi nào KHÔNG cần đọc sâu ---
skip_when:
  - "Chỉ cần biết project AIC2026 là gì → xem summary"
  - "Đang tìm code/implementation cụ thể → file này không chứa code"
  - "Cần thông tin về buổi tập huấn khác → xem file Buoi khác"

# --- Quan hệ với file khác ---
related_files:
  - "docs/Training/NoiDungBuoi2.md"   # (nếu có) kỹ thuật submit, công cụ BTC
  - "docs/Training/NoiDungBuoi3.md"   # (nếu có)
  - "README.md"

# --- Người viết / nguồn ---
source: "Livestream tập huấn AIC 2026 — Thầy Nguyễn Hải Đăng, phòng lab CAB"
language: vi
---

# Tập huấn AI Challenge (AIC) 2026 — Buổi 1: Bối cảnh và Bài toán

## 1. Giới thiệu đội ngũ tập huấn

- Trình bày: **Thầy Nguyễn Hải Đăng** — Phòng thí nghiệm Công nghệ phần mềm CAB, Trường Đại học Khoa học Tự nhiên.
- Cùng đội ngũ tập huấn viên: thầy Lễ, thầy Thức, thầy Triết (cùng phòng thí nghiệm CAB).
- Tinh thần cuộc thi: đến để **học hỏi và trải nghiệm** là chính, giải thưởng chỉ là phần phụ.

## 2. Nội dung buổi hôm nay

1. Bối cảnh và bài toán — vì sao cuộc thi liên quan đến xử lý dữ liệu surveillance/lifelog.
2. Công nghệ cốt lõi hiện nay (CLIP, LVLM…).
3. Quy trình hệ thống: pipeline trích xuất đặc trưng, tương tác người dùng.
4. Chiến thuật truy vấn cho từng dạng bài toán.
5. Dữ liệu & tài nguyên do ban tổ chức (BTC) cung cấp: keyframe, metadata, đặc trưng.
6. Một số kinh nghiệm cho các đội.

## 3. Bối cảnh: vì sao cần hệ thống truy xuất video

Lượng dữ liệu hình ảnh/video ngày nay là khổng lồ: video trên YouTube, livestream, short-video (TikTok, Facebook — hàng trăm triệu video/ngày), dữ liệu cá nhân lưu trên điện thoại… Từ đó nảy sinh nhu cầu có hệ thống **phân tích và truy xuất video** thay vì con người phải xem thủ công.

Hai nhóm dữ liệu video chính được đề cập:

- **Surveillance (giám sát công cộng/cá nhân):** camera an ninh, camera giao thông (phạt nguội), camera nhà dân. Đặc điểm: góc quay cố định, bối cảnh không đổi, đối tượng lặp đi lặp lại. Hệ thống AI cần tự động phát hiện đối tượng, chuyển động, sự kiện đáng chú ý thay vì con người ngồi xem 24/24.
- **Lifelog / góc nhìn thứ nhất (egocentric):** dữ liệu từ kính thông minh, action cam, camera đeo ngực, camera gắn nón bảo hiểm, dashcam ô tô. Mục tiêu là ghi lại và sau này truy xuất lại "nhật ký cuộc sống".

Mục tiêu chung: xây dựng hệ thống cho phép **tìm kiếm bằng mô tả ngôn ngữ tự nhiên** (thay vì thao tác bằng tay/câu lệnh), tiến tới một trợ lý ảo đủ thông minh để hội thoại và tìm kiếm giúp người dùng.

## 4. Các dạng bài toán trong cuộc thi

### 4.1 Item Search / KIS (Known-Item Search)

Tìm **một khoảnh khắc/video duy nhất** dựa trên mô tả hoặc hình ảnh gợi ý. Có hai dạng:

- **Video KIS:** BTC trình chiếu một đoạn video, đội phải xác định chính xác đây là video nào trong kho dữ liệu. Nộp càng sớm và đúng thì điểm càng cao.
- **Textual KIS:** BTC cung cấp mô tả dạng văn bản về nội dung video, đội tìm lại đúng video/khoảnh khắc đó.

Yêu cầu độ chính xác tuyệt đối: kết quả top 1 phải đúng; nộp sai phải nộp lại và bị trừ điểm.

**Ví dụ:** "Tìm phân cảnh tôi vô tình đánh rơi chiếc chìa khóa có móc khóa hình gấu bông màu hồng khi đang đi bộ qua một quầy bán hoa quả." Hoặc: "Tìm khoảnh khắc bạn đang ăn kem bên bờ biển" — chỉ tính là đúng khi **cả hai yếu tố** (kem + biển) cùng xuất hiện trong một khoảnh khắc, chứ không phải chỉ một trong hai.

### 4.2 Video Search / AVS (Ad-hoc Video Search)

Khác với KIS, dạng này yêu cầu tìm **tất cả các phân đoạn** thỏa mãn mô tả (tìm kiếm diện rộng), phục vụ thống kê/phân tích hành vi. Hệ thống trả về danh sách các phân đoạn xếp hạng theo độ tương đồng ngữ nghĩa từ cao xuống thấp. Điểm số dựa trên số lượng đoạn nộp lên trùng với danh sách đáp án của BTC (danh sách này không được công bố trước).

**Ví dụ:** "Tìm tất cả phân cảnh người lớn hướng dẫn trẻ em trồng cây hoặc tưới hoa trong vườn" — AI cần hiểu mối quan hệ/ngữ cảnh giữa hành động và đối tượng, không chỉ nhận diện vật thể rời rạc.

**Ví dụ khác:** "Tìm khoảnh khắc anh ấy ăn đồ ăn nhanh một mình trong nhà hàng, khi đang ở xa nhà (khoai tây chiên, hamburger, đồ uống). Những khoảnh khắc ăn hamburger tự nướng ở nhà thì không tính." Cái khó ở đây là AI phải phân biệt được "ăn ở nhà hàng" và "ăn ở nhà" — nhiều khi cần dựa thêm vào **metadata** (vd vị trí địa lý) chứ không chỉ xử lý hình ảnh thuần túy.

### 4.3 Video Question Answering (VQA / Video QA)

Xuất hiện lần đầu trong cuộc thi năm ngoái (lưu ý: khác với "VQA = Visual Question Answering" trong xử lý ảnh nói chung). BTC chiếu một video (có thể tương đối dài) và đặt câu hỏi bằng ngôn ngữ tự nhiên; đội phải nộp lên **câu trả lời**, không phải video.

Thử thách: AI phải suy luận theo thời gian — đếm, xác định trình tự hành động, theo dõi diễn biến để trả lời chính xác, súc tích.

**Ví dụ:** Video 2 phút quay tiệc sinh nhật. Câu hỏi: "Cậu bé mặc áo hình siêu nhân màu đỏ đã thổi tổng cộng bao nhiêu cây nến? Sau đó ai là người tặng quà?"

Có một dạng đặc biệt từng xuất hiện: video quay cảnh một người giải đề (ví dụ đề thi đại học) — câu hỏi là đáp án của bài toán trong video. AI đọc đề và tự giải sẽ nhanh hơn nhiều so với đội tự xem lại và giải tay; đây là điểm cạnh tranh về tốc độ xử lý.

### 4.4 Conversational KIS (xu hướng mới, có thể chưa xuất hiện trong cuộc thi năm nay)

Đây là điểm nhấn công nghệ multimedia năm 2026: thay vì người dùng nhập một câu truy vấn duy nhất rồi chờ kết quả, **trợ lý ảo chủ động hội thoại** để làm rõ ý định khi mô tả còn mơ hồ (ví dụ hỏi lại: "cuộc gặp diễn ra trong nhà hay ngoài trời?", "người đó là nam hay nữ?"), qua đó thu hẹp dần phạm vi tìm kiếm.

Xu hướng giao diện: tối giản hóa, không còn nhiều nút bấm/thanh lọc phức tạp, chỉ còn **một khung chat** với trợ lý ảo; hệ thống bên dưới tự động chọn (hoặc kết hợp — "fusion") chức năng cần dùng, không cần người dùng thao tác thủ công trên nhiều bộ lọc.

## 5. Đặc điểm dữ liệu multimedia

- Nhiều dạng dữ liệu kết hợp: hình ảnh (frame), âm thanh, văn bản (metadata, subtitle rút trích từ âm thanh).
- Khối lượng cực lớn, ban đầu phi cấu trúc → cần tổ chức lại thành dữ liệu có cấu trúc (rút đặc trưng, lưu vector) để tìm kiếm hiệu quả hơn.
- Có thể nhiễu: góc quay rung lắc, âm thanh ồn, ánh sáng thay đổi liên tục, subtitle không chính xác.
- Dữ liệu lifelog thường **giàu ngữ nghĩa cá nhân** — cần dựa vào ngữ cảnh xung quanh (đoạn trước/sau, subtitle) để suy luận. Ví dụ: đoán một người là nhân viên lễ tân khách sạn dựa trên bối cảnh (đang giới thiệu khách sạn, sắp nhận phòng) dù hình ảnh đơn lẻ không nói rõ điều đó.
- Ứng dụng nghiên cứu liên quan: truy xuất thông tin quy mô lớn, tương tác người–máy (HCI), đạo đức & quyền riêng tư dữ liệu, nhân học/dân tộc học (hiểu văn hóa, món ăn đặc trưng của từng dân tộc…).

## 6. Các phương pháp/công nghệ chính

### 6.1 Bag-of-Visual-Words (BoVW) — phương pháp truyền thống

Rút đặc trưng ảnh dựa trên đường viền, góc cạnh (không dựa vào vùng đều màu, vì mắt người cũng không tập trung vào đó). Quy trình gồm hai giai đoạn:

- **Indexing:** rút đặc trưng (ví dụ SIFT) cho toàn bộ dữ liệu → phân cụm (k-means) → lượng tử hóa → tính TF-IDF → lưu vào database có chỉ mục, tạo thành "visual vocabulary".
- **Query:** rút đặc trưng cho ảnh/câu truy vấn theo đúng quy trình tương tự → tính độ tương đồng cosine với các vector trong kho dữ liệu → xếp hạng (ranking) → có thể thêm query expansion / spatial verification để kiểm chứng lại.

Hạn chế: độ chính xác không cao, dễ nhầm giữa các ảnh có đường viền/kết cấu tương tự nhưng nội dung khác nhau.

### 6.2 Object Detection / Deep Learning

Dùng các mô hình như Faster R-CNN, YOLO để rút trích và phân loại đối tượng (loại, màu sắc…). Có thể kết hợp thêm self-attention, image feature encoder.

### 6.3 Text-to-Image Retrieval

Mỗi ảnh/video trong kho dữ liệu được gán sẵn một hoặc nhiều câu mô tả (caption) khi index. Khi truy vấn, hệ thống so sánh trực tiếp trên văn bản (text) thay vì so sánh đặc trưng ảnh — nhanh hơn nhiều. Yêu cầu bước Image-to-Text (captioning) phải chính xác; nên lưu nhiều caption khả dĩ cho cùng một ảnh để tránh bỏ sót hoặc caption sai lệch ngữ nghĩa.

### 6.4 Xu hướng kỹ thuật qua từng năm (trong các cuộc thi trước)

- **2022:** object, places, keyword/caption.
- **2023:** personalized concept, xử lý màu sắc, sequence view (lướt nhanh qua thumbnail như thanh tua trên YouTube).
- **2024:** natural description (mô tả tự nhiên hơn).
- **2025:** AI Agent.
- **2026:** chưa rõ xu hướng mới — các đội được khuyến khích tự brainstorm và chuẩn bị trước.

### 6.5 CLIP & LVLM (Large Vision-Language Model)

- **CLIP** (Contrastive Language–Image Pretraining): mô hình nền tảng/baseline phổ biến, ánh xạ ảnh và câu văn vào cùng một không gian vector sao cho câu mô tả nằm gần ảnh tương ứng. Có khả năng **zero-shot** — nhận diện được khái niệm chưa từng thấy trong lúc huấn luyện, rất quan trọng cho các truy vấn phức tạp, mới lạ.
- **LVLM** (trước đây gọi là VLM): mô hình ngôn ngữ–hình ảnh lớn, có thể giao tiếp bằng ngôn ngữ tự nhiên (giống ChatGPT/Gemini) nhưng đồng thời hiểu được hình ảnh/video.
- **Generative query expansion:** dùng LLM để mở rộng câu truy vấn ban đầu thành nhiều mô tả chi tiết hơn, giúp tăng độ chính xác tìm kiếm.
- **Smart interaction:** trợ lý ảo tự đặt câu hỏi ngược lại ("critical question") để thu hẹp lựa chọn, thay vì để người dùng tự lướt xem hàng loạt video ứng viên.

## 7. AI Agent

Định nghĩa gồm ba thành phần chính:

1. **Perception** (cảm nhận): thu thập, xử lý dữ liệu đầu vào (hình ảnh, âm thanh, văn bản, cảm biến) một cách tự động.
2. **Reasoning** (lý luận): phân tích, lập kế hoạch, ra quyết định dựa trên thông tin thu thập được.
3. **Action** (hành động): thực hiện hành vi để tương tác và thay đổi môi trường.

Ví dụ thực tế: xe tự hành, chatbot thông minh, hệ thống đề xuất nội dung (recommendation system — nền tảng bên dưới các mạng xã hội, quyết định nội dung hiển thị dựa trên sở thích người dùng).

Kỳ vọng của BTC cho cuộc thi: hệ thống của đội tự đặt câu hỏi làm rõ khi cần, tự tổng hợp và thậm chí **tự động nộp bài** thay người dùng — giảm tối đa thao tác thủ công. Năm 2025 các đội chưa đạt tới mức độ này; BTC hy vọng năm nay có cải thiện.

## 8. Ba thách thức kỹ thuật cốt lõi ("the big challenges")

1. **Semantic gap (khoảng cách ngữ nghĩa):** khoảng cách giữa ngôn ngữ tự nhiên trừu tượng của con người (ví dụ "không khí ấm cúng", "khoảnh khắc hoài niệm") và dữ liệu điểm ảnh thô. Cần dựa vào các foundation model mạnh, sau đó fine-tuning thêm cho bài toán cụ thể.
2. **Sự thưa thớt dữ liệu / quy mô lớn:** một khoảnh khắc cần tìm (dạng KIS) thường chỉ dài khoảng 2–3 giây trong một kho dữ liệu khổng lồ. Nếu đưa toàn bộ dữ liệu qua mô hình AI lớn ngay từ đầu, hệ thống dễ quá tải → cần một **bộ lọc thô** nhanh trước (ví dụ lọc bằng so sánh text/caption ngắn để thu hẹp còn vài chục ứng viên) trước khi xử lý sâu hơn.
3. **Ràng buộc logic về thời gian (temporal constraint):** phân biệt thứ tự trước–sau của hành động, ví dụ "người đàn ông cởi mũ trước khi bước vào phòng" khác với "bước vào phòng rồi mới cởi mũ". Đây là thách thức khó nhất — các hệ thống AI hiện tại chủ yếu hiểu tốt nội dung của từng khung hình riêng lẻ nhưng còn hạn chế trong liên kết trình tự thời gian giữa các hành động.

## 9. Kiến trúc hệ thống tổng quan

- **Tầng giao diện (UI):**
  - Cách làm cũ: nhiều chức năng hiển thị trực tiếp (query metadata, query by text description, filter theo thời gian/địa điểm, bản đồ…) — người dùng tự chọn từng chức năng một, thao tác chậm.
  - Xu hướng mới: chỉ còn **một khung chat** với AI Agent. Người dùng nhập câu truy vấn tự nhiên; agent tự động biết nên gọi chức năng nào, thậm chí kết hợp nhiều chức năng cùng lúc ("fusion") — nhanh và hiệu quả hơn so với việc con người phải thao tác tuần tự từng bộ lọc.
- **Tầng hệ thống (System Integration Platform):** đóng vai trò backend, kết nối cơ sở dữ liệu, xử lý truy vấn và trả kết quả lên UI.
- **Tiền xử lý dữ liệu:** filtering, normalization/grouping, xử lý riêng theo đặc trưng của từng loại dữ liệu — ví dụ dữ liệu lifelog cần thêm các bước như place recognition, action detection, entity detection.

### Quy trình xây dựng hệ thống — 2 giai đoạn

1. **Indexing (lập chỉ mục):** trích xuất keyframe → rút đặc trưng → lưu vào vector database. Có thể giữ nguyên cách làm của các năm trước hoặc cải tiến thêm ở bước rút đặc trưng.
2. **Query/Retrieval (truy vấn):** từ câu hỏi/mô tả của người dùng → mở rộng truy vấn, re-ranking, hiển thị kết quả. BTC khuyến khích các đội **tích hợp LLM Reasoner** vào bước này (tự động mở rộng truy vấn, tự hỏi lại người dùng khi cần, tự tính toán độ tương đồng, tự hiển thị kết quả) — đây là phần trọng tâm mà BTC mong các đội cải tiến năm nay, vì công nghệ LLM đã phát triển đáng kể so với năm ngoái.

## 10. Case study — một số câu truy vấn thực tế trong cuộc thi

- *"I was looking at le soldier in mall next to some clothes"* → cần hiểu đúng là "lead soldier" (mô hình lính chì đồ chơi), không phải người lính thật. Nếu AI hiểu nhầm nghĩa đen sẽ tìm sai kết quả.
- Câu có yếu tố lifelog + địa điểm: *"I was taking a photo of a man sitting at a table. I took a flight to this city three days ago... in Greece"* → AI cần suy ra vị trí địa lý (Hy Lạp) từ ngữ cảnh câu văn, sau đó có thể lọc theo tên quốc gia — thay vì phải thao tác bấm bản đồ thủ công như cách làm trước đây.
- Câu cần phân biệt bằng màu sắc quần áo (một người mặc áo tím, một người mặc áo trắng) → bắt buộc hệ thống phải có khả năng xử lý hình ảnh thực sự, không chỉ dựa vào văn bản/metadata.

## 11. Best practice / chiến lược cho các đội

- Thu hẹp phạm vi tìm kiếm dần dần: lọc theo từ khóa → thời gian → địa điểm → đối tượng → cảnh vật…
- Thử nhiều cách diễn đạt khác nhau cho cùng một mô tả (tương tự prompt engineering) — mô tả càng chi tiết, kết quả trả về càng chính xác.
- Có thể để AI xác nhận lại cách hiểu trước khi bắt đầu tìm kiếm sâu, tránh mất thời gian khi hiểu sai ý ngay từ đầu.
- Tận dụng nhiều mô hình AI song song (chia việc) để tăng tốc độ và độ phủ khi mở rộng truy vấn.

## 12. Dữ liệu & tài nguyên do BTC cung cấp

- **Video gốc:** có thể lấy từ nhiều nguồn trên YouTube (kênh thời sự, thể thao, v.v.), tùy BTC chuẩn bị.
- **Keyframe:** là một khung hình (frame) hiển thị **đầy đủ** nội dung ảnh — khác với các frame chuyển cảnh/mờ giữa hai cảnh, vốn không được tính là keyframe. BTC cung cấp thông tin dưới dạng **thời điểm** (timestamp, không phải khoảng thời gian), kèm theo thông số FPS (frame per second) mà video được trích xuất, để xác định chính xác keyframe tương ứng.
  - Với dạng bài toán yêu cầu một đáp án duy nhất: nếu đáp án đúng của BTC là một **đoạn liên tiếp nhiều keyframe** thỏa mãn, đội có thể nộp bất kỳ keyframe nào nằm trong đoạn đó và vẫn được tính điểm đầy đủ; nộp lệch ra ngoài đoạn hợp lệ thì mất điểm.
- **Object:** đối tượng được rút trích sẵn bằng mô hình Faster R-CNN Inception ResNet, huấn luyện trên tập dữ liệu Open Images V4. Nếu thấy chưa chính xác, đội có thể tự trích lại bằng mô hình khác tốt hơn, hoặc tự làm thêm segmentation.
- **CLIP feature:** đặc trưng được rút sẵn bằng mô hình CLIP.
- **Metadata:** lấy từ thông tin video trên YouTube — gồm channel ID, channel URL, mô tả (description), từ khóa (keyword), độ dài video, ngày giờ đăng, thumbnail, tiêu đề (title)…
- **Khối lượng dữ liệu:** các năm trước khoảng vài trăm giờ video; năm nay chưa xác nhận cụ thể, có thể nhiều hơn (chưa rõ có đạt tới hàng nghìn giờ hay không).
- Độ khó thường tăng dần mỗi năm để tạo động lực cải tiến cho các đội cũ; đội mới tham gia năm nay nên tập trung làm quen là chính.

## 13. Đánh giá kết quả & lợi ích khác

- Kết quả thi được chấm dựa trên **độ chính xác của frame/kết quả nộp**, không phải độ đẹp của giao diện (UI). Tuy nhiên, UI đẹp và dễ thao tác sẽ giúp đội thao tác nhanh hơn, gián tiếp cải thiện kết quả.
- Sau mỗi mùa thi, BTC thường giới thiệu cơ hội nộp bài báo khoa học vào một hội nghị liên quan. Các đội có thể viết bài mô tả tính năng UI, thuật toán hoặc cải tiến kỹ thuật của mình — dù kết quả thi ra sao — để có thêm một kết quả công bố khoa học, củng cố hồ sơ cá nhân.

## 14. Một số lưu ý / hỏi đáp trong buổi tập huấn

- Buổi tập huấn được livestream trên YouTube (không ghi lại qua Zoom); các bạn có thể xem lại trên đó.
- Slide bài giảng sẽ được BTC gửi lại cho các đội sau buổi học.
- Phần kỹ thuật cụ thể về cách lưu trữ và nộp bài (submit keyframe…) sẽ được hướng dẫn chi tiết ở buổi tập huấn tiếp theo, cùng với hướng dẫn sử dụng công cụ do BTC cung cấp (CLIP hoặc công cụ mới hơn).
- Mọi thắc mắc thêm nên gửi qua link hỏi–đáp chính thức của ban tổ chức, để đảm bảo công bằng — BTC sẽ không trả lời riêng cho từng đội mà công bố chung cho tất cả.
