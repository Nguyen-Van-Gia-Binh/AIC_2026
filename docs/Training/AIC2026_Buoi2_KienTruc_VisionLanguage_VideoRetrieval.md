---
# ============================================================
# METADATA — Đọc phần này trước, quyết định có cần đọc sâu không
# ============================================================

title: "AIC2026 — Buổi 2: Kiến trúc Vision-Language Models trong Hệ thống Tìm kiếm Video"
file: "AIC2026_Buoi2_KienTruc_VisionLanguage_VideoRetrieval.md"
created: "2026-08-19"
session: 2
presenter: "ThS. Nguyễn Quang Thức"
tags:
  - AIC2026
  - vision-language
  - CLIP
  - early-fusion
  - late-fusion
  - GLIP
  - UNINEXT
  - ImageBind
  - ControlNet
  - video-retrieval
  - prompt-engineering
  - vitrivr
  - VISIONE
  - TRAKE
  - indexing
  - retrieval

# --- Tóm tắt 1 dòng (cho agent scan nhanh) ---
summary: >
  Tài liệu kỹ thuật Buổi 2 AIC 2026: kiến trúc hệ thống tìm kiếm video (indexing + retrieval),
  phân tích Early-fusion (GLIP, UNINEXT — chính xác, chậm) vs Late-fusion (CLIP — nhanh, kém kiểm soát),
  các bước trung gian sau fusion (mean pooling → LSTM → Transformer), cơ chế hiển thị kết quả
  (SOM, VISIONE), xử lý phản hồi người dùng (exploration vs exploitation), mở rộng đa phương thức
  (ImageBind, ControlNet, sketch retrieval), prompt engineering và liên hệ với pipeline dự thi.

# --- Mức độ ưu tiên đọc ---
read_priority: high          # high | medium | low
read_depth_needed: deep      # shallow | deep
# deep vì chứa kiến thức kỹ thuật nền tảng để thiết kế pipeline và lựa chọn mô hình

# --- Khi nào cần đọc sâu ---
read_deep_when:
  - "Lựa chọn kiến trúc mô hình (early-fusion vs late-fusion vs hybrid)"
  - "Thiết kế pipeline: khi nào dùng CLIP, khi nào dùng GLIP/Grounding DINO"
  - "Hiểu tại sao baseline CLIP chạy nhanh nhưng khó kiểm soát kết quả"
  - "Thiết kế tầng rerank sau khi CLIP lọc sơ bộ"
  - "Giải bài toán TRAKE (frame linking / temporal alignment)"
  - "Cải thiện truy vấn bằng prompt engineering (Section 8)"
  - "Xây dựng UI hỗ trợ exploration/exploitation và gợi ý concept (Section 3–4)"
  - "Tham khảo hệ thống vitrivr và VISIONE làm tài liệu mẫu"

# --- Khi nào KHÔNG cần đọc sâu ---
skip_when:
  - "Chỉ cần biết quy trình nộp bài, định dạng CSV → xem AIC2026_SoTuyen_QuyTrinh_NopBai_ChamDiem.md"
  - "Cần hiểu bài toán KIS/AVS/VQA ở mức khái niệm → xem NoiDungBuoi4.md"
  - "Không liên quan đến thiết kế mô hình hay pipeline kỹ thuật"

# --- Nội dung đặc biệt hữu ích ---
key_sections:
  - "Section 6: Early-fusion vs Late-fusion — bảng so sánh và khi nào dùng cái nào"
  - "Section 6.3: Các cách tiếp cận trung gian (mean pooling → LSTM → Transformer)"
  - "Section 8: Prompt Engineering — cải tiến ngay trên baseline không cần train lại"
  - "Section 9: Bảng tổng hợp thuật ngữ / mô hình — tra cứu nhanh"
  - "Section 10: Liên hệ với hệ thống dự thi — kết nối lý thuyết vào thực tế"

# --- Quan hệ với file khác ---
related_files:
  - "docs/Training/NoiDungBuoi4.md"                           # Buổi 1: bối cảnh bài toán, CLIP overview
  - "docs/Training/AIC2026_SoTuyen_QuyTrinh_NopBai_ChamDiem.md"  # Quy trình thi & nộp bài

# --- Người viết / nguồn ---
source: "Slide tập huấn Buổi 2 — ThS. Nguyễn Quang Thức, AIC HCMC 2026. Đã diễn giải thêm và sắp xếp lại theo mạch logic."
language: vi
---

# Tài liệu tổng hợp — Tập huấn AIC HCMC 2026, Buổi 2
### Chủ đề: Kiến trúc mô hình Thị giác – Ngôn ngữ trong hệ thống tìm kiếm video
**Trình bày:** ThS. Nguyễn Quang Thức — Hội thi Thử thách Trí tuệ Nhân tạo TP.HCM 2026 (AIC HCMC 2026)

> *Tài liệu này tổng hợp lại nội dung slide của buổi tập huấn thứ 2, diễn giải thêm cho rõ nghĩa (đặc biệt là các thuật ngữ/mô hình được nêu trong slide nhưng không giải thích chi tiết trên slide), và sắp xếp lại theo mạch logic để vừa tiện cho người đọc, vừa dùng làm ngữ cảnh (context) cho AI khi hỗ trợ xây dựng hệ thống dự thi. Phần diễn giải thêm được đánh dấu rõ để phân biệt với nội dung gốc trên slide.*

---

## 0. Bố cục buổi trình bày (theo slide "Tổng quan")

1. Hệ thống tìm kiếm video cần những gì?
2. Một số vấn đề cơ bản
3. Sơ lược về mô hình Thị giác – Ngôn ngữ (Vision-Language models)

---

## 1. Kiến trúc tổng quan của một hệ thống tìm kiếm video

### 1.1. Hai giai đoạn: Indexing và Retrieval

```
[Indexing stage]                          [Retrieval stage]
Image data → AI models → Databases ⇄ User interface ⇄ User
```

Câu hỏi mở đầu buổi: **"Hệ thống tìm kiếm video chỉ cần mô hình rút trích đặc trưng mạnh là đủ?"** — Đây là câu hỏi phản biện xuyên suốt bài trình bày: chỉ có một mô hình rút trích đặc trưng (feature extractor) tốt là chưa đủ để có một hệ thống tìm kiếm hiệu quả.

### 1.2. Khung tham chiếu: "Bridging the gap between what machines know vs. what we think they know" (Stanford)

Khoảng cách (gap) giữa "những gì máy biết" và "những gì con người nghĩ là máy biết" đến từ ba nguồn:

1. **Assumptions** — công cụ được xây dựng dựa trên giả định sai?
2. **Expectations** — mô hình không làm đúng như ta nghĩ nó làm?
3. **Beyond us** — con người vốn dĩ không hiểu hết được mô hình?

Ba hướng nghiên cứu tương ứng để thu hẹp khoảng cách này:
- Nghiên cứu cách con người sử dụng công cụ (điều gì có thể sai) — việc này quan trọng ngang với việc tạo ra công cụ.
- Khoảng cách kỳ vọng sẽ khác nhau tùy vào mục tiêu cuối (end-task); nên chọn phương án đơn giản nhất đạt được mục tiêu trực tiếp.
- Nghiên cứu mô hình như một "loài mới" — quan sát và thực nghiệm có kiểm soát.

Câu trích dẫn đi kèm: *"Good artists steal. Good researchers doubt."*

### 1.3. Mục tiêu cốt lõi

> **"Mục tiêu của hệ thống tìm kiếm là tìm được video chúng ta mong muốn."**

Câu hỏi tiếp theo: **"Sẽ làm gì nếu mô hình truy vấn không đủ tốt?"**
→ Câu trả lời của buổi trình bày: cần thêm hai thành phần bổ trợ ngoài mô hình truy vấn — **Cơ chế hiển thị** và **Phản hồi người dùng**.

### 1.4. Vòng lặp ba thành phần của hệ thống

```
Các mô hình truy vấn → Cơ chế hiển thị → Phản hồi người dùng
        ↑_________________________________________|
                         ↓
                   Video Browser
```

Ba thành phần này tạo thành một **vòng lặp tương tác** (không phải một chiều): kết quả truy vấn được hiển thị, người dùng phản hồi, phản hồi đó quay lại điều chỉnh mô hình truy vấn cho vòng lặp kế tiếp. Sản phẩm cuối cùng của toàn bộ vòng lặp là **Video Browser** — giao diện người dùng thao tác trực tiếp.

---

## 2. Các vấn đề trong xây dựng mô hình truy vấn

**Câu hỏi khung:** *"Các mô hình trong bài toán truy vấn video cần giải quyết yếu tố nào?"*

### 2.1. Truy vấn hiệu quả trên lượng dữ liệu lớn

- Ví dụ cụ thể được nêu: **bộ dữ liệu V3C1 có tới 1000 giờ nội dung video** — minh họa cho quy mô dữ liệu thực tế mà hệ thống phải xử lý.
- Đánh đổi giữa ba yếu tố (mô hình tam giác Better – Faster – Cheaper):
  - **Tốc độ chạy thuật toán** (Faster)
  - **Sức mạnh thuật toán** (Better)
  - **Chi phí hệ thống** (Cheaper)
- Về nguyên tắc, không thể tối ưu cả ba cùng lúc — đây là chủ đề cũng đã được nhắc ở buổi 1 (modeling video dài phải đánh đổi giữa sức mạnh, tốc độ, chi phí).

### 2.2. Truy vấn không có liên kết 1–1 với video

- Vấn đề: thông tin do người dùng cung cấp có thể **khớp với nhiều đoạn video khác nhau**, chứ không chỉ một.
- Ba hướng xử lý được đề xuất:
  1. **Tăng thêm lượng truy vấn** để thu hẹp phạm vi tìm kiếm (search nhiều lần, mỗi lần thêm ràng buộc).
  2. **Thay đổi phương thức truy vấn** để tạo liên kết chặt chẽ hơn — ví dụ: truy vấn bằng ảnh được sinh ra từ sketch (phác thảo) thay vì mô tả chữ thuần túy.
  3. **Cơ chế kết hợp nhiều kiểu truy vấn** cùng lúc (ví dụ: text + sketch + màu sắc + pose).
- **Ví dụ hệ thống minh họa: [vitrivr](https://vitrivr.org/)** — một hệ thống truy vấn video mã nguồn mở, cho phép:
  - Truy vấn bằng sketch màu sắc/bố cục (color sketch) để tìm video có layout tương tự.
  - Truy vấn bằng sketch tư thế người (pose/skeleton sketch) để tìm hành động tương tự.

  *(Ghi chú: vitrivr là một trong các hệ thống tham chiếu phổ biến trong cộng đồng thi Video Retrieval — như VBS, LSC — có thể dùng làm nguồn tham khảo kiến trúc UI/truy vấn đa phương thức cho hệ thống dự thi.)*

### 2.3. Liên kết thông tin giữa các khung hình (frame linking)

- Vấn đề: các mô hình rút trích đặc trưng trên **ảnh đơn** (single-image models) không tự động nắm bắt được **chuỗi thời gian** giữa các khung hình.
- Ví dụ minh họa trong slide: một chuỗi khung hình được phân cụm phân cấp (hierarchical clustering) với các nhãn — *canyon (0.99), canyon (0.92), stream (0.81), bridge (0.94), creek (0.77)...* — nhằm khớp với câu truy vấn có tính tuần tự:
  > *"A slow pan up from a canyon, static shots of a bridge and redrock mountain."*
- Ý nghĩa: khi câu mô tả có cấu trúc chuỗi sự kiện/hành động theo thời gian (tương tự bài toán **TRAKE** trong đề thi AIC2026), hệ thống cần cơ chế liên kết các frame lại thành một trình tự có nghĩa, chứ không chỉ xử lý từng frame độc lập.

---

## 3. Các vấn đề trong cách hiển thị kết quả truy vấn

**Câu hỏi khung:** *"Vì sao việc hiển thị đóng vai trò quan trọng?"*

### 3.1. Số lượng kết quả trả về quá nhiều

Hai nguồn gây nhiễu loạn kết quả:
- **Các frame gần giống nhau trong cùng một video** (trùng lặp nội dung).
- **Số lượng video có liên quan** đến truy vấn (nhiều video cùng thỏa mãn một phần mô tả).

Câu hỏi cốt lõi: **"Chúng ta sẽ hiển thị gì khi người dùng không biết bắt đầu từ đâu?"**

- Ví dụ minh họa: **Self-Organizing Map (SOM)** — một kỹ thuật giảm chiều/phân cụm trực quan:
  - **Unbiased SOM**: sắp xếp không gian feature đều nhau, không thiên lệch.
  - **Relevance-weighted SOM**: không gian được "biến dạng" theo độ liên quan (relevance) với truy vấn — giúp người dùng thấy ngay vùng nào đáng chú ý hơn.

### 3.2. Ví dụ tìm kiếm ảnh tương tự (reverse image search)

- Minh họa bằng ví dụ tìm giày: từ một **ảnh truy vấn**, hệ thống trả về danh sách **ảnh liên quan** — minh họa nguyên lý tìm kiếm dựa trên độ tương đồng thị giác (visual similarity search), một kỹ thuật nền tảng cho việc "tìm ảnh giống ảnh" trong hệ thống video retrieval.

### 3.3. Ví dụ hệ thống hiển thị theo cụm: VISIONE'23

- **VISIONE** là hệ thống tham dự các cuộc thi Video Retrieval quốc tế (VBS – Video Browser Showdown), nổi bật với cách hiển thị kết quả theo **nhóm/cụm video** (mỗi hàng trong lưới kết quả là các frame thuộc cùng một video), giúp người dùng nhanh chóng loại trừ cả một nhóm kết quả không phù hợp thay vì duyệt từng frame riêng lẻ.

---

## 4. Các vấn đề trong xử lý phản hồi của người dùng

**Câu hỏi khung:** *"Phản hồi của người dùng nên được xử lý ra sao?"*

### 4.1. Cân bằng giữa Khám phá (Exploration) và Khai phá (Exploitation)

| | **Khám phá (Exploration)** | **Khai phá (Exploitation)** |
|---|---|---|
| Mục đích | Mở rộng phạm vi tìm kiếm | Tách bạch giữa các video có độ giống nhau cao |
| Cách làm | Hiển thị thông tin **ít liên quan** hơn | Hiển thị thông tin có **mức độ liên quan cao** |
| Khi nào dùng | Khi mô tả người dùng chưa đủ chặt chẽ, hoặc mô hình rút trích đặc trưng chưa đủ chính xác | Khi đã khoanh vùng đúng nhưng vùng đó còn nhiều lựa chọn gần giống nhau |

*(Đây chính là bài toán kinh điển **exploration–exploitation trade-off** quen thuộc trong reinforcement learning / bandit problems, được áp dụng vào ngữ cảnh tìm kiếm tương tác.)*

### 4.2. Gợi ý concept (concept suggestion) từ truy vấn người dùng

Hệ thống có thể chủ động gợi ý các khái niệm (concept) liên quan để hỗ trợ:
- **Concept phục vụ khám phá**: những gì mô hình *nghĩ* người dùng đang muốn tìm (mở rộng theo hướng model dự đoán).
- **Concept phục vụ khai phá**: những gì giúp mô hình *giảm sự không chắc chắn* trong kết quả trả về (thu hẹp, làm rõ).

**Ví dụ minh họa (tìm giày "nmd"):**
- Nhóm concept khám phá: `primeknit`, `adidas`, `sneakers`, `yeezy`, `japanese`, `boost`, `nike` — mở rộng theo thương hiệu/kiểu dáng/chất liệu liên quan.
- Nhóm concept khai phá: `grey`, `purple`, `cream`, `beige` — thu hẹp theo thuộc tính cụ thể (màu sắc) để phân biệt các kết quả gần giống nhau.

---

## 5. Sơ lược về mô hình Thị giác – Ngôn ngữ (Vision-Language Models)

### 5.1. Điểm khởi đầu tự nhiên nhất

> *"Hãy bắt đầu bằng cách tự nhiên nhất — Mô tả những gì chúng ta thấy."*

Ý tưởng: trước khi nghĩ tới các kỹ thuật phức tạp, cách con người tự nhiên nhất để truy vấn hình ảnh/video vẫn là **mô tả bằng ngôn ngữ tự nhiên** — đây là lý do các mô hình Thị giác–Ngôn ngữ (Vision-Language, VL) đóng vai trò trung tâm trong bài toán video retrieval.

### 5.2. Lược sử phát triển mô hình xử lý ngôn ngữ tự nhiên

Dòng thời gian (theo slide, nguồn scribbledata.io):

| Năm | Mốc |
|---|---|
| 1967 | ELIZA — chatbot rule-based đầu tiên |
| 1997 | LSTM — kiến trúc mạng hồi quy xử lý chuỗi dài |
| 2010 | Stanford CoreNLP |
| 2011 | Google Brain |
| 2017 | Kiến trúc Transformer (Google, *"Attention Is All You Need"*) |
| 2020 | OpenAI GPT-3 |

Slide cũng trích biểu đồ **"Language Model Sizes to Mar/2023"** (nguồn: LifeArchitect.ai) minh họa quy mô tham số của các mô hình ngôn ngữ lớn tính đến thời điểm đó (GPT-3, PaLM, LLaMA, GPT-4, BLOOM, Chinchilla, v.v.) — cho thấy tốc độ tăng trưởng nhanh chóng về quy mô mô hình trong giai đoạn 2020–2023.

### 5.3. Sự ra đời của các mô hình Thị giác – Ngôn ngữ lớn

Ba điều kiện hội tụ dẫn đến sự bùng nổ của VL models:
1. **Nguồn dữ liệu khổng lồ** về cặp (ảnh, câu mô tả) **không cần gán nhãn thủ công** (thu thập tự động từ web).
2. **Kiến trúc mô hình mới** có khả năng tận dụng dữ liệu lớn — điển hình là **Transformer**.
3. **Tài nguyên tính toán và hệ thống lớn** đủ để huấn luyện các mô hình này.

---

## 6. Fusion: Early-fusion vs. Late-fusion

Đây là phần trọng tâm kỹ thuật của buổi trình bày — trả lời câu hỏi: **"Tốc độ chạy hay sức mạnh thuật toán?"**

### 6.1. Kiến trúc Early-fusion

```
[Text tokens] [Image tokens] → Model (xử lý chung, có tương tác qua lại) → Output
```

- **Đặc điểm**: thông tin ảnh và ngôn ngữ được đưa vào cùng một mô hình, có **tương tác qua lại** (cross-attention) trong quá trình rút trích đặc trưng — chứ không xử lý độc lập.
- **Mô hình tiêu biểu**: **GLIP** (Grounded Language-Image Pre-training), **UNINEXT** (Universal Instance Perception).
- **Ưu điểm**: tăng tính lý giải (interpretability) cho các bài toán cần liên kết chính xác giữa ngôn ngữ và vùng ảnh/video cụ thể — gọi là **visual grounding**.
- **Nhược điểm**: phải **chạy lại toàn bộ mô hình cho mỗi truy vấn khác nhau** — rất tốn chi phí khi số lượng ứng viên (candidate) lớn.
- **Khi nào nên dùng**: phù hợp khi **số lượng dữ liệu cần xử lý thấp** — tức là ở **các bước cuối cùng** của quá trình truy vấn (sau khi đã lọc từ hàng nghìn xuống còn một danh sách nhỏ ứng viên).

**Các khái niệm/mô hình minh họa liên quan đến early-fusion trong slide:**

- **Scene Graph Grounding**: biểu diễn câu mô tả (ví dụ: *"A standing woman wearing dark sunglasses"*) thành một đồ thị gồm **objects** (woman, sunglasses), **attributes** (standing, dark), **relationships** (wearing) — rồi đối chiếu (grounding) đồ thị này với vùng ảnh cụ thể kèm điểm số (energy score).
- **GLIPv2**: một mô hình hợp nhất (unified) cả nhóm bài toán **Localization** (Object Detection, Instance Segmentation) lẫn nhóm **Understanding** (VL Grounding, Visual Question Answering, Image Caption) — dùng chung Image Encoder + Text Encoder + Deep Fusion Block, cho đầu ra thống nhất.
- **Referring Expression Comprehension**: các ví dụ như *"person holding tray"*, *"girl in red coat"*, *"darkest colored horse"*, *"the slice of cake on the left"* — minh họa khả năng định vị chính xác một đối tượng cụ thể trong ảnh dựa trên mô tả phân biệt (kiểu bài toán này gần với **Textual KIS** trong đề thi AIC2026, nơi mô tả cần đủ chi tiết để phân biệt với các đối tượng/video tương tự khác).
- **Composed Image Retrieval** (ảnh tham chiếu + caption tương đối → ảnh đích): ví dụ trong slide — ảnh một người lái mô-tô + caption *"is on a track and has the front wheel in the air"* → trả về các ảnh khớp với sự thay đổi mô tả đó. Đây là dạng truy vấn kết hợp ảnh gốc + chỉnh sửa bằng ngôn ngữ, một hướng mở rộng khả dụng cho các vòng phản hồi/tinh chỉnh (refinement) trong hệ thống.

### 6.2. Kiến trúc Late-fusion

```
[Text] → Text Encoder → Vector T
[Image] → Image Encoder → Vector I
Similarity = T · I  (dot product / cosine similarity)
```

- **Đặc điểm**: mỗi loại dữ liệu (ảnh, văn bản) được **rút trích đặc trưng độc lập**, chỉ kết hợp (so khớp) ở bước cuối cùng.
- **Mô hình tiêu biểu**: **CLIP** (Contrastive Language–Image Pretraining), **OWL-ViT** (Open-World Localization với Vision Transformer).
- **Ưu điểm**: **tiết kiệm thời gian truy vấn** vì đặc trưng của ảnh/video đã được rút trích và lưu sẵn (index trước) — đúng nguyên lý indexing/retrieval đã nêu ở mục 1.1.
- **Nhược điểm**: **rất khó kiểm soát kết quả trả về**, vì chất lượng hoàn toàn phụ thuộc vào sức mạnh của mô hình rút trích đặc trưng (feature extractor).
- **Khi nào nên dùng**: khi cần **truy vấn trên dữ liệu lớn** — vì mức độ phức tạp ở bước so khớp cuối cùng có thể điều chỉnh linh hoạt tùy theo độ lớn dữ liệu.

> **Ghi chú liên hệ:** hệ thống baseline hiện tại (CLIP ViT-B/32) chính là một kiến trúc **late-fusion điển hình** — đây là lý do nó chạy nhanh trên toàn bộ tập keyframe, nhưng cũng lý giải vì sao chất lượng truy vấn phụ thuộc gần như hoàn toàn vào khả năng của backbone CLIP.

### 6.3. Các cách tiếp cận trung gian sau fusion (nằm giữa Early và Late)

Late-fusion **không nhất thiết chỉ dừng ở phép so khớp (similarity) đơn giản** — có thể thêm các bước xử lý phức tạp hơn sau khi đã có embedding, xếp theo độ phức tạp tăng dần (đồng thời thời gian chạy cũng tăng):

| Kiểu | Cách kết hợp | Đặc điểm |
|---|---|---|
| **Parameter-free** | Mean Pooling các frame embedding | Nhanh nhất, không cần huấn luyện thêm |
| **Sequential** | Transformer Encoder / LSTM trên chuỗi frame | Cân bằng giữa tốc độ và độ chính xác |
| **Tight** | Transformer Encoder + lớp Linear | Chính xác cao nhất, chậm nhất — gần với early-fusion |

→ Nguyên tắc chung: **càng xử lý phức tạp sau bước fusion, độ chính xác càng cao nhưng thời gian chạy càng lâu** — đây là dải lựa chọn nằm **giữa** hai thái cực early-fusion và late-fusion, phù hợp để áp dụng theo tầng (rút gọn ứng viên dần dần) như đã thảo luận ở buổi 1.

---

## 7. Các hướng mở rộng đa phương thức (multi-modal) liên quan

### 7.1. Truy vấn xuyên phương thức (Cross-modal retrieval)

Minh họa kiểu **ImageBind** (Meta AI): gắn kết nhiều phương thức (audio, image & video, depth, text) vào **cùng một không gian embedding**, cho phép:
- Tìm hình ảnh/video từ một đoạn âm thanh (ví dụ: tiếng còi tàu → ảnh đoàn tàu).
- **Embedding-space arithmetic**: cộng vector của một ảnh với vector của một âm thanh để truy vấn ra ảnh mới phù hợp cả hai (ví dụ: ảnh chim bồ câu + âm thanh động cơ xe máy → ảnh người đi xe máy giữa đàn chim).
- **Audio-to-image generation**: sinh ảnh trực tiếp từ âm thanh (ví dụ: tiếng chim cánh cụt kêu → ảnh đàn chim cánh cụt).

### 7.2. Retrieval-augmented Multimodal Generator

Kiến trúc kiểu **RA-CM3**: mô hình Transformer sinh nội dung (main document) đồng thời tham chiếu đến các tài liệu được truy xuất trước đó (retrieved docs) — mỗi ảnh được mã hóa thành chuỗi token (ví dụ dùng **VQGAN**, 1024 token/ảnh) để đưa vào cùng luồng xử lý với văn bản.

### 7.3. Truy vấn bằng sketch qua ControlNet

Quy trình minh họa trong slide:
```
Sketch image + Image caption → ControlNet → Ảnh được sinh ra (giống ảnh thật)
→ Image encoder → query vector → Database → Top-k ảnh gần nhất
```
**Ý nghĩa**: thay vì so khớp trực tiếp sketch thô với ảnh thật (vốn rất khác biệt về modality — như đã bàn ở buổi 1), hệ thống dùng **ControlNet** để "dịch" sketch + caption thành một ảnh photorealistic trung gian, sau đó dùng ảnh trung gian này để truy vấn như một ảnh bình thường — cách này giúp thu hẹp khoảng cách giữa modality của input và modality của dữ liệu trong database.

---

## 8. Prompt Engineering và Ensembling

Trích dẫn từ bài báo gốc của CLIP (Radford et al.):

> *"Zero-shot performance can be significantly improved by customizing the prompt text to each task."*

**Ý nghĩa thực tiễn**: với các mô hình late-fusion kiểu CLIP, việc **tinh chỉnh cách diễn đạt câu truy vấn** (prompt) theo từng loại nhiệm vụ cụ thể — thay vì dùng nguyên văn mô tả gốc của đề thi — có thể cải thiện đáng kể chất lượng truy vấn mà không cần huấn luyện lại mô hình. Đây là một hướng cải tiến chi phí thấp, phù hợp để thử nghiệm sớm trên baseline hiện tại.

---

## 9. Bảng tổng hợp thuật ngữ / mô hình được nhắc đến

| Thuật ngữ | Giải thích ngắn gọn |
|---|---|
| **Early-fusion** | Kết hợp thông tin đa phương thức ngay từ đầu, có tương tác qua lại trong lúc rút trích đặc trưng. Chính xác hơn, chậm hơn. |
| **Late-fusion** | Rút trích đặc trưng từng phương thức độc lập, chỉ kết hợp ở bước so khớp cuối. Nhanh hơn, kém kiểm soát hơn. |
| **GLIP / GLIPv2** | Mô hình grounding ngôn ngữ–ảnh dạng early-fusion, hợp nhất nhiều tác vụ localization + understanding. |
| **UNINEXT** | Mô hình nhận thức đối tượng đa nhiệm (universal instance perception), dạng early-fusion. |
| **CLIP** | Mô hình đối lập (contrastive) ảnh–văn bản dạng late-fusion — nền tảng của baseline hiện tại. |
| **OWL-ViT** | Mô hình phát hiện đối tượng mở-từ-vựng (open-vocabulary detection) dựa trên ViT, dạng late-fusion. |
| **Scene Graph Grounding** | Biểu diễn mô tả thành đồ thị object–attribute–relationship để đối chiếu với vùng ảnh. |
| **Composed Image Retrieval** | Truy vấn bằng ảnh tham chiếu + mô tả chỉnh sửa tương đối, trả về ảnh đích đã "áp dụng" chỉnh sửa đó. |
| **Self-Organizing Map (SOM)** | Kỹ thuật giảm chiều/trực quan hóa không gian đặc trưng để hỗ trợ hiển thị kết quả. |
| **vitrivr** | Hệ thống truy vấn video mã nguồn mở, hỗ trợ nhiều kiểu truy vấn (text, sketch màu, sketch pose). |
| **VISIONE** | Hệ thống truy vấn video từng tham dự VBS, nổi bật với cách hiển thị kết quả theo cụm video. |
| **ImageBind** | Mô hình gắn kết nhiều phương thức (audio, ảnh, video, depth, text) vào cùng một không gian embedding. |
| **ControlNet** | Framework điều kiện hóa mô hình sinh ảnh (diffusion) bằng input phụ như sketch, dùng để "dịch" sketch thành ảnh thật trước khi truy vấn. |
| **RA-CM3** | Kiến trúc sinh nội dung đa phương thức có tham chiếu tài liệu truy xuất (retrieval-augmented generation) cho cả ảnh và văn bản. |

---

## 10. Liên hệ với hệ thống dự thi hiện tại

*(Phần tổng hợp thêm, không có trong slide gốc — nhằm kết nối nội dung buổi học với pipeline đang xây dựng.)*

- **Baseline CLIP ViT-B/32** hiện tại là kiến trúc **late-fusion thuần túy** — phù hợp cho bước lọc sơ bộ trên toàn bộ tập keyframe (theo đúng khuyến nghị ở mục 6.2), nhưng sẽ có giới hạn về độ chính xác so với các mô hình mạnh hơn (SigLIP2, BEiT-3, EVA-CLIP, PE-Core đã được xác định trước đó để nâng cấp backbone).
- Việc dùng **object detection JSON** có sẵn (Faster R-CNN/OpenImages) và tích hợp thêm **Grounding DINO** có thể xem như một bước tiến gần hơn tới hướng **early-fusion / scene-graph grounding** ở mục 6.1 — dùng cho **bước rerank cuối cùng** trên tập ứng viên đã được thu hẹp từ CLIP, thay vì chạy trên toàn bộ dữ liệu.
- Bài toán **TRAKE** (căn chỉnh chuỗi sự kiện theo thời gian) liên hệ trực tiếp với vấn đề "liên kết thông tin giữa các khung hình" ở mục 2.3 — các thuật toán temporal alignment như DANTE/MADTempo chính là công cụ giải quyết vấn đề mô hình ảnh-đơn không nắm được trình tự thời gian.
- Cơ chế **hiển thị + phản hồi người dùng** (mục 3–4) là phần dễ bị đánh giá thấp nhưng theo buổi trình bày lại đóng vai trò ngang hàng với mô hình truy vấn — đáng cân nhắc đầu tư UI hỗ trợ khám phá/khai phá (ví dụ: gợi ý concept, hiển thị theo cụm video kiểu VISIONE) song song với việc nâng cấp backbone.
- **Prompt engineering** (mục 8) là hướng cải tiến chi phí thấp, có thể thử nghiệm ngay trên baseline hiện tại trước khi đầu tư vào các nâng cấp phức tạp hơn.
