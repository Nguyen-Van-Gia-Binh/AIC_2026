# TÀI LIỆU BÁO CÁO & KỊCH BẢN THUYẾT TRÌNH NHÓM

## HỆ THỐNG XỬ LÝ 3 BÀI TOÁN KIS - Q&A - TRAKE (AIC 2026)

> **File Slide tương tác HTML:** [presentation_aic2026.html](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/docs/presentation_aic2026.html)
> **Sơ đồ kiến trúc độc lập:** [diagram_system_architecture.html](file:///c:/Users/admin/Documents/A_FPT/Tempory_Project/AIC2026/docs/diagrams/diagram_system_architecture.html)

---

## 1. TỔNG QUAN KIẾN TRÚC & TRIẾT LÝ THIẾT KẾ

### 1.1. Bối Cảnh & Đề Bài AIC 2026

- **Mục tiêu:** Hệ thống tìm kiếm video-frame bằng ngôn ngữ tự nhiên trên tập dữ liệu gồm hơn **177.000 keyframe** được trích xuất từ hàng trăm video độ phân giải cao.
- **3 dạng bài toán:**
  1. **KIS (Known-Item Search):** Cho câu mô tả bối cảnh/sự kiện &rarr; Trả về danh sách `(video_id, frame_id)` xếp hạng theo độ chính xác.
  2. **Q&A (Video Question Answering):** Cho câu mô tả cảnh + câu hỏi cụ thể &rarr; Trả về `(video_id, frame_id, answer)`.
  3. **TRAKE (Trajectory / Event Sequence Alignment):** Cho mô tả cảnh chung + $N$ mốc sự kiện liên tiếp &rarr; Trả về `(video_id, frame_id_1, ..., frame_id_N)` thỏa mãn tính thời gian tăng ngặt.
- **Thang điểm BTC:** R-Score / R@k trung bình tại rank 1, 5, 20, 50, 100 ($Final = \frac{1}{5} \sum R@k$).

### 1.2. Quyết Định Thiết Kế Cốt Lõi (Architecture Decisions)

1. **Không dùng chung 1 AI Agent ("One-Size-Fits-All"):**
   - KIS là bài toán thuần retrieval &rarr; **Workflow tuyến tính, 0 LLM**, tối ưu tốc độ (< 0.3s/lần chạy).
   - Q&A cần suy luận và chống ảo giác &rarr; **Orchestrator-Workers với Reflection Loop** (tối đa 2 vòng).
   - TRAKE cần xác định chuỗi thời gian &rarr; **Pipeline cố định 3 giai đoạn** kết hợp **Quy hoạch động (DP)**.
2. **Nguyên tắc "Single Source of Truth":**
   - Toàn bộ lời gọi LLM tập trung duy nhất tại `scripts/agent/config.py:call_llm()` bọc LiteLLM với chuỗi dự phòng: Gemini 3.5 Flash &rarr; Groq (Llama 3.3 70B) &rarr; OpenRouter.
   - Toàn bộ file nộp bài (CSV/ZIP) được sinh độc quyền tại `scripts/submit/build_submission.py` và kiểm tra bởi `validate_submission.py`.
3. **File-Based & In-Memory State:** Không dùng cơ sở dữ liệu (ORM/DB) cồng kềnh; ma trận embedding và metadata được nạp trực tiếp vào RAM, đảm bảo không gặp lỗi kết nối hay deadlock trong phòng thi.
4. **Human-in-the-Loop:** Thí sinh có giao diện React 19 để tua video từng frame, chỉnh sửa `frame_id`, sửa `answer` và sắp xếp danh sách nộp trực quan trước khi chốt.

---

## 2. CHI TIẾT KỸ THUẬT TỪNG BÀI TOÁN

### 2.1. Pipeline 1: KIS (Known-Item Search)

```
User Query ──► Hybrid Retrieval (Dense SigLIP + Sparse BM25 via RRF) ──► Pool 500
                    │
                    ▼
           Risk-Aware Re-ranking (Margin = Score#1 - Score#2)
           ├── Margin ≥ 0.012 ──► BET MODE (Đào sâu video #1, chiếm ≤ 50% dòng)
           └── Margin < 0.012 ──► SPREAD MODE (Trải đều rủi ro, max 3 frame/video)
                    │
                    ▼
           Temporal NMS (Δt ≥ 3s) + OCR Rerank Bonus ──► Top 100 Rows
```

- **Bước 1: Hybrid Retrieval (Dense + Sparse):**

  - **Dense Retrieval:** Vector hóa query bằng mô hình `google/siglip-so400m-patch14-384`, nhân ma trận cosine similarity với 177K keyframe.
  - **Sparse Retrieval (BM25):** Tìm kiếm trên 171.800 tài liệu offline trích xuất từ Objects JSON (Faster R-CNN) và Vintern-1B Captions.
  - **Dung hợp RRF (Reciprocal Rank Fusion):**
    $$
    RRF\_Score(d) = \frac{0.75}{60 + Rank_{dense}(d)} + \frac{0.25}{60 + Rank_{sparse}(d)}
    $$
  - Trích xuất **Pool = 500 ứng viên thô** (đảm bảo không bỏ sót Ground Truth).
- **Bước 2: Xếp hạng rủi ro (Risk-Aware Re-ranking - `rerank.py`):**

  - Tính khoảng cách điểm giữa Video số 1 và Video số 2:
    $$
    \Delta_{margin} = BestScore(V_1) - BestScore(V_2)
    $$
  - **Chế độ Đặt Cược (Bet Mode) khi $\Delta_{margin} \ge 0.012$:** Video số 1 vượt trội rõ rệt &rarr; Hệ thống đào sâu thêm trong video này (`fast_retrieve_for_video`) và cấp tối đa **50% số dòng nộp (50 dòng)** cho video này để tối ưu $R@1$ và $R@5$.
  - **Chế độ Trải Rủi Ro (Spread Mode) khi $\Delta_{margin} < 0.012$:** Các video sàn sàn điểm nhau &rarr; Giới hạn mỗi video tối đa **3 frame** (`SPREAD_MAX_PER_VIDEO=3`) nhằm tăng cơ hội trúng $R@50$ và $R@100$.
- **Bước 3: Hậu xử lý (Temporal NMS & OCR Bonus):**

  - **Temporal NMS:** Lọc bỏ các keyframe liền kề trong cùng 1 video nếu khoảng cách thời gian $\Delta t < 3.0\text{s}$, tránh lãng phí dòng nộp bài cho cùng một góc máy.
  - **OCR Rerank Bonus:** Tự động nhận diện nếu query chứa số áo, biển số, năm hoặc tỷ số để cộng điểm bonus nếu OCR/caption khớp chính xác.

---

### 2.2. Pipeline 2: Q&A (Video Question Answering)

```
Query (VN/EN) ──► Rewrite Query (VN→EN + tách Question) ──► SigLIP2 + BM25 Retrieval ──► Top 100 Hits
                                                                   │
                                                                   ▼
                                                   Cluster by Video (Gom cụm video)
                                                                   │
    ┌──────────────────────────────────────────────────────────────┴──────────────────────────────────┐
    ▼                                                                                                 ▼
[Cụm Video #1]                                                                                [Cụm Video #2 & #3]
    │                                                                                                 │
    ▼                                                                                                 ▼
2-Tier Evidence Answering:                                                                    2-Tier Evidence Answering
- Tier 1: Objects JSON (Faster R-CNN, free)                                                   - Trích xuất đáp án riêng
- Tier 2: Vision LLM + Evidence Bundle (Captions, ASR, OCR)                                   - Độc lập cho từng video
- Gate: OCR Direct Overwrite (khi đọc số hiển thị)                                                    │
    │                                                                                                 │
    └──────────────────────────────────────────────┬──────────────────────────────────────────────────┘
                                                   ▼
                                        Confidence Evaluation
                                        ├── Confidence < 0.5 & Loop < 2 ──► REFLECTION (Feedback + Rewrite Vòng 2)
                                        └── Confidence ≥ 0.5 ───────────► Canonical Extractor ──► Top 100 Rows
```

- **Thách thức cốt tử:** *"Sai đáp án = 0 điểm toàn bộ dòng nộp bài dù đúng video và frame"*.
- **Đột phá 1 - Trích xuất đáp án theo Cụm Video (`answer_by_video_cluster`):**

  - **Vấn đề của hệ thống cũ:** Lấy 1 đáp án của video top-1 gán cho toàn bộ 100 dòng. Nếu video top-1 sai, 100 dòng đều bị 0 điểm.
  - **Giải pháp:** Gom 100 hits thành các cụm video. **Top 3 cụm video được chạy trích xuất đáp án độc lập**. Nếu video top-1 sai nhưng video đúng nằm ở hạng 7, dòng của video hạng 7 vẫn mang đáp án đúng của chính nó &rarr; Bảo toàn $R@20 / R@50 / R@100$.
- **Đột phá 2 - Trích xuất 2 tầng chống ảo giác (`answer_from_hits`):**

  - **Tầng 1 (Offline Objects JSON + ASR):** Miễn phí, chạy ngay trên danh sách vật thể detect được. Bỏ qua nếu câu hỏi cần đọc chữ/số hoặc đếm.
  - **Tầng 2 (Vision VLM + Evidence Bundle):** Gửi top keyframe ảnh kèm bó bằng chứng gồm OCR (PaddleOCR/VietOCR), Vintern-1B Caption và PhoWhisper ASR Transcript.
  - **OCR Direct Overwrite:** Khi câu hỏi hỏi về số hiển thị (biển số, giá tiền, số áo...) và OCR đọc được duy nhất 1 chuỗi số &rarr; **Ghi đè trực tiếp kết quả của VLM**, triệt tiêu nguy cơ VLM đoán mò con số.
  - **Canonical Extractor:** Cắt bỏ văn phong giao tiếp dài dòng ("The answer in this frame is..."), rút gọn thành 1-3 từ khóa ngắn gọn, đúng tiếng Việt/Anh để so khớp tuyệt đối với Ground Truth của BTC.
- **Đột phá 3 - Vòng lặp Reflection (Tự sửa sai):**

  - Đánh giá độ tin cậy ($Confidence$). Nếu $Confidence < 0.5$ và $Loop < 2$, Agent tự động tổng hợp các vật thể đã tìm thấy để tạo Feedback, viết lại truy vấn tiếng Anh (`query_en_v2`) và truy xuất lại vòng 2.

---

### 2.3. Pipeline 3: TRAKE (Tracking / Trajectory Keyframe Alignment)

```
Global Query + N Event Descriptions
         │
         ▼
[GIAI ĐOẠN 1: Multi-Event Coverage Pooling]
  • Encode Global Query + N Event Queries
  • Video_Score(V) = Sim_global(V) + ∑ max_{f in V} Sim(e_i, f)
  • Sắp xếp theo (Số mốc có mặt trong pool, Tổng điểm) ──► Chọn Top 20 Candidate Videos
         │
         ▼
[GIAI ĐOẠN 2: Strict Monotonic Dynamic Programming (DP)]
  • Với mỗi video: Tìm chuỗi (f_1, f_2, ..., f_N) sao cho:
      f_1 < f_2 < ... < f_N  (TĂNG NGHIÊM NGẶT - Strict Monotonic)
      ∑ Score(e_i, f_i) ──► MAX
  • Video không tồn tại chuỗi tăng hợp lệ ──► LOẠI HOÀN TOÀN
         │
         ▼
[GIAI ĐOẠN 3: Gated Multi-Modal Verification]
  • Cổng 1 (Rule-based, 100% video): So khớp từ khóa Objects JSON vs mô tả event
      Score = Trake_Score + 0.03 * Rule_Score
  • Cổng 2 (LLM Cross-check, có điều kiện):
      NẾU Margin(#1, #2) ≤ 0.02 ──► Gọi LLM đánh giá Plausibility (Top 3 videos)
      Score = Score + 0.05 * LLM_Score
         │
         ▼
Top Ranked Candidates (video_id, frame_id_1, ..., frame_id_N)
```

- **Mục tiêu:** Định vị chuỗi $N$ hành động tuần tự theo thời gian (ví dụ: vận động viên chạy đà &rarr; giậm nhảy &rarr; qua xà &rarr; tiếp đất).
- **Giai đoạn 1 - Multi-Event Coverage Pooling:**

  - Không chỉ dùng 1 câu tổng quát để tìm video. Hệ thống tính điểm bao phủ của video $V$ qua công thức:
    $$
    \text{Score}(V) = \text{Sim}_{\text{global}}(V) + \sum_{i=1}^N \max_{f \in V} \text{Sim}(e_i, f)
    $$
  - Ưu tiên video có mặt đủ $N$ mốc sự kiện &rarr; Loại bỏ ngay các video chỉ trùng bối cảnh chung nhưng không có hành động. Chọn ra **Top 20 candidate videos**.
- **Giai đoạn 2 - Strict Monotonic Dynamic Programming:**

  - **Vì sao Greedy thất bại:** Thuật toán tham lam (Greedy) chọn frame điểm cao nhất cho mốc 1. Nếu frame đó nằm ở cuối video, nó sẽ chặn đứng không cho các mốc sau tìm được frame hợp lệ.
  - **Giải pháp DP:**
    $$
    dp[i][j] = \max_{k \text{ s.t. } frame\_idx(k) < frame\_idx(j)} \left( dp[i-1][k] + \text{Score}(hit_{i,j}) \right)
    $$
  - Điều kiện $f_1 < f_2 < \dots < f_N$ (Tăng nghiêm ngặt) đảm bảo các mốc không bị trùng keyframe. Video nào không có chuỗi hợp lệ bị loại bỏ ngay lập tức.
- **Giai đoạn 3 - Cổng Xác Thực 2 Tầng (Gated Verification):**

  - **Cổng 1 (Rule-based):** Đo tỷ lệ từ khóa của từng event xuất hiện trong Objects JSON của frame tương ứng. Chạy nhanh, miễn phí cho 100% video ứng viên.
  - **Cổng 2 (LLM Cross-check):** Chỉ kích hoạt khi chênh lệch điểm số $\text{Margin}(\#1, \#2) \le 0.02$ (tối đa 3 video). Khi video số 1 đã thắng cách biệt, bỏ qua gọi LLM để **tiết kiệm 85% chi phí API và rút ngắn thời gian phản hồi**.

---

## 3. KỊCH BẢN THUYẾT TRÌNH TỪNG SLIDE (SPEAKER SCRIPT)

### Slide 1: Kiến Trúc Tổng Thể 3 Pipeline Độc Lập

> *"Kính thưa thầy cô và các bạn, hệ thống AIC 2026 của nhóm được thiết kế để giải quyết 3 bài toán truy xuất video đa phương thức. Thay vì áp dụng một AI Agent cồng kềnh cho mọi bài toán, nhóm đã phân hóa kiến trúc thành 3 pipeline chuyên biệt: KIS là luồng tuyến tính không tốn token LLM; Q&A sử dụng mô hình Orchestrator với cơ chế trích xuất theo cụm video và phản tư tối đa 2 vòng; còn TRAKE sử dụng Quy hoạch động để căn chỉnh chuỗi thời gian tăng ngặt. Toàn bộ hệ thống giao tiếp qua REST API FastAPI và giao diện React SPA hiện đại."*

### Slide 2: Pipeline KIS - Truy Xuất Tuyến Tính & Xếp Hạng Rủi Ro

> *"Trong bài toán KIS, mục tiêu là tìm kiếm một khoảnh khắc cụ thể. Đầu tiên, query được đưa vào bộ Hybrid Retrieval kết hợp Dense SigLIP và Sparse BM25 qua thuật toán RRF để lấy ra 500 ứng viên tiềm năng. Điểm bứt phá của nhóm nằm ở bộ Risk-Aware Re-ranking: Hệ thống đo khoảng cách Margin giữa video top 1 và top 2. Nếu video top 1 vượt trội rõ rệt, hệ thống kích hoạt chế độ 'Đặt cược' để đào sâu thêm các frame trong video đó, chiếm tối đa 50% dòng nộp bài nhằm tối đa hóa R@1 và R@5. Ngược lại, nếu điểm số sàn sàn nhau, hệ thống chuyển sang chế độ 'Trải rủi ro', giới hạn tối đa 3 frame mỗi video để bảo vệ R@50 và R@100. Cuối cùng, Temporal NMS loại bỏ các frame trùng lặp thời gian dưới 3 giây."*

### Slide 3: Pipeline Q&A - Trả Lời Theo Cụm Video & Chống Ảo Giác

> *"Đối với bài toán Q&A, luật thi quy định rằng chỉ cần sai câu trả lời thì toàn bộ dòng nộp bài sẽ bị 0 điểm. Nhóm đã giải quyết triệt để vấn đề này bằng 3 cơ chế: Thứ nhất, 'Answer by Video Cluster' — trích xuất câu trả lời riêng cho top 3 cụm video, giúp bảo toàn điểm số cho các video đúng ở thứ hạng sau nếu video top 1 bị trật. Thứ hai, hệ thống xác thực 2 tầng: Ưu tiên tra cứu Objects JSON miễn phí trước, sau đó mới gọi Vision VLM kèm Evidence Bundle; đặc biệt khi hỏi về số hiển thị, OCR sẽ ghi đè trực tiếp để chống ảo giác. Thứ ba, nếu độ tự tin dưới 0.5, Agent sẽ tự động phản tư và tìm kiếm lại ở vòng 2."*

### Slide 4: Pipeline TRAKE - Căn Chỉnh Chuỗi Sự Kiện Bằng Quy Hoạch Động

> *"TRAKE là bài toán đòi hỏi tìm chuỗi N hành động tuần tự theo thời gian. Quy trình của nhóm gồm 3 giai đoạn chặt chẽ: Giai đoạn 1 là Coverage Pooling — chấm điểm bao phủ của video trên cả N mốc sự kiện để lọc ra 20 video tốt nhất. Giai đoạn 2 là bước đột phá thuật toán: Sử dụng Strict Monotonic Dynamic Programming để tìm chuỗi frame f1 < f2 < ... < fN có tổng điểm similarity lớn nhất, loại bỏ hoàn toàn nhược điểm của thuật toán Tham lam. Giai đoạn 3 là Cổng xác thực 2 tầng: Cổng Rule chạy miễn phí cho mọi video, còn cổng LLM chỉ mở khi chênh lệch điểm top 1 và top 2 dưới 0.02, giúp tiết kiệm 85% chi phí API."*

### Slide 5: So Sánh Hệ Thống & Điểm Bứt Phá Kỹ Thuật

> *"Slide này tổng hợp toàn bộ bức tranh kỹ thuật. Chúng ta có thể thấy sự tối ưu hóa tài nguyên rất rõ ràng: KIS chạy 0 token LLM với độ trễ dưới 0.3 giây; Q&A được trang bị SigLIP2 và trích xuất theo cụm video; TRAKE ứng dụng Quy hoạch động giải quyết triệt để chuỗi thời gian. Mọi module đều được bảo vệ bởi Regression Guard tự động cảnh báo nếu Final Score bị tụt hơn 0.01."*

### Slide 6: Giao Diện Human-in-the-Loop & Kết Luận

> *"Cuối cùng, hệ thống đặt thí sinh làm trung tâm điều khiển với giao diện React SPA tốc độ cao. Thí sinh có thể tua video frame-by-frame bằng công cụ VideoVerifier, chỉnh sửa kết quả trực tiếp và xuất file nộp bài chuẩn quy cách BTC chỉ trong 1 cú click. Hệ thống đã sẵn sàng cho các vòng thi đấu chính thức. Xin chân thành cảm ơn thầy cô và các bạn đã lắng nghe!"*

---

## 4. DỰ PHÒNG CÂU HỎI VẤN ĐÁP (Q&A DEFENSE PREPARATION)

**Q1: Tại sao KIS không dùng LLM để rewrite query tiếng Việt sang tiếng Anh tự động trong pipeline?**

* **Trả lời:** Đây là quyết định kiến trúc đã chốt. Để KIS đạt tốc độ tối đa (< 0.3s) và không phụ thuộc vào quota mạng lúc thi, pipeline KIS là hoàn toàn tuyến tính (0 LLM). Việc dịch tiếng Việt được đặt ở tầng UI bằng nút bấm chủ động (checkbox Auto-translate), cho phép thí sinh xem và duyệt câu tiếng Anh trước khi gửi truy vấn.

**Q2: Thuật toán DP trong TRAKE hơn gì so với thuật toán Tham lam (Greedy)?**

* **Trả lời:** Thuật toán Tham lam sẽ chọn frame có điểm cao nhất cho mốc đầu tiên. Nếu mốc 1 có điểm cao nhất ở frame thứ 900 (cuối video), nó sẽ chặn hoàn toàn các mốc 2, 3, 4 vì không còn frame nào phía sau thỏa mãn điều kiện tăng dần thời gian. DP duyệt qua toàn bộ không gian trạng thái $dp[i][j]$ để tìm chuỗi có **tổng điểm toàn cục lớn nhất**, đảm bảo không bị nghẽn cục bộ.

**Q3: Cơ chế "Answer by Video Cluster" trong Q&A giải quyết bài toán gì?**

* **Trả lời:** Theo luật BTC, nếu dòng nộp bài có `frame_id` đúng nhưng `answer` sai thì điểm dòng đó bằng 0. Nếu 100 dòng nộp bài đều dùng chung đáp án của video top-1, khi video top-1 bị nhận diện sai (ví dụ áo trắng thay vì áo xanh), toàn bộ 100 dòng sẽ mất sạch điểm ($R@20, R@50, R@100 = 0$). Bằng cách gom cụm và sinh đáp án riêng cho top 3 video, nếu video đúng nằm ở hạng 5 hay 10, dòng đó vẫn giữ nguyên câu trả lời đúng của chính nó.

**Q4: Hệ thống làm thế nào để không bị cạn Quota API như bài học ở Lần 1?**

* **Trả lời:** Nhóm áp dụng 4 lớp bảo vệ:
  1. KIS: 0 token LLM.
  2. Q&A: Ưu tiên tầng 1 Objects JSON (miễn phí), chỉ mở VLM tầng 2 khi cần, giới hạn tối đa 2 vòng reflection.
  3. TRAKE: Cổng LLM chỉ mở khi Margin $\le 0.02$, tối đa 3 video.
  4. Quản lý provider tập trung: Chuỗi fallback tự động Gemini Flash &rarr; Groq &rarr; OpenRouter tại `config.py`.
