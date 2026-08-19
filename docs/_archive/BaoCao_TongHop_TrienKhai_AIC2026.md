# BÁO CÁO TỔNG HỢP TOÀN BỘ HỆ THỐNG & TIẾN TRÌNH TRIỂN KHAI AIC 2026

> **Tài liệu tổng hợp toàn diện các thành phần đã xây dựng, cấu trúc mã nguồn, giải pháp kỹ thuật và hướng dẫn vận hành hệ thống AI Agent Video Retrieval phục vụ Cuộc thi Trí tuệ Nhân tạo TP.HCM (AIC HCMC 2026) — Vòng Sơ tuyển.**

---

## 1. TỔNG QUAN DỰ ÁN & MỤC TIÊU

### 1.1. Bối cảnh cuộc thi & Yêu cầu kỹ thuật

Vòng Sơ tuyển cuộc thi **AIC HCMC 2026** yêu cầu thí sinh giải quyết 3 dạng bài toán truy vấn video trên tập dữ liệu lớn (Batch 1 gồm 873 video, 177.321 keyframes):

| Dạng truy vấn       | Bản chất bài toán                                                                             | Định dạng đầu ra nộp bài                 |
| --------------------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------------- |
| **Textual KIS** | Định vị chính xác video và khung hình khớp với mô tả văn bản                         | `<video_id>, <frame_id>`                      |
| **Q&A**         | Định vị khoảnh khắc**và** trả lời chính xác câu hỏi ngữ cảnh                  | `<video_id>, <frame_id>, <answer>`            |
| **TRAKE**       | Tìm đúng video**và** căn chỉnh chuỗi $N$ khoảnh khắc ngữ nghĩa theo thời gian | `<video_id>, <frame_id_1>, ..., <frame_id_N>` |

### 1.2. Chiến lược thiết kế hệ thống

- **Chấm điểm theo vị trí xếp hạng ($R@k$ với $k \in \{1,5,20,50,100\}$):** Câu trả lời đúng càng xếp ở top đầu thì điểm số càng cao, do đó hệ thống chú trọng tối ưu hóa độ chính xác xếp hạng (Ranking/Reranking).
- **Quy định về dữ liệu & nộp bài:**
  - `frame_id` bắt đầu từ **1** (quy đổi `frame_id = frame_idx + 1`).
  - `video_id` không chứa đuôi mở rộng `.mp4`.
  - Tối đa 100 câu trả lời trên mỗi file CSV truy vấn.
  - Mã hóa bắt buộc: `UTF-8`.
- **Human-in-the-loop:** Luật thi sơ tuyển cho phép con người tham gia rà soát, tinh chỉnh đáp án. Hệ thống được xây dựng theo kiến trúc bán tự động linh hoạt kết hợp giao diện tương tác trực quan.

---

## 2. KIẾN TRÚC HỆ THỐNG TỔNG THỂ

```
                                      ┌──────────────────────────────────────────────┐
                                      │              NGƯỜI DÙNG / THÍ SINH           │
                                      └──────────────────────┬───────────────────────┘
                                                             │ (Tương tác / Rà soát)
                                                             ▼
                                      ┌──────────────────────────────────────────────┐
                                      │         GRADIO UI (scripts/app.py)           │
                                      │  [ Tab KIS ]  [ Tab Q&A ]  [ Tab TRAKE ]     │
                                      │         [ Tab 4: Export ZIP Nộp Bài ]        │
                                      └──────┬───────────────┬──────────────┬────────┘
                                             │               │              │
                    ┌────────────────────────┘               │              └────────────────────────┐
                    ▼                                        ▼                                       ▼
     ┌────────────────────────────┐       ┌────────────────────────────────────┐       ┌────────────────────────────┐
     │      PIPELINE KIS          │       │           PIPELINE Q&A             │       │      PIPELINE TRAKE        │
     │  (scripts/pipeline_kis.py) │       │     (scripts/pipeline_qa.py)       │       │ (scripts/pipeline_trake.py)│
     └──────────────┬─────────────┘       └──────────────────┬─────────────────┘       └─────────────┬──────────────┘
                    │                                        │                                       │
                    │ ┌──────────────────────────────────────┴─────────────────────────────────────┐ │
                    │ │                                                                           │ │
                    ▼ ▼                                                                           ▼ ▼
┌────────────────────────────────────────┐                   ┌───────────────────────────────────────────────┐
│     MODULE TRUY XUẤT (RETRIEVER)       │                   │          MODULE AGENT & MULTIMODAL            │
│      (scripts/agent/tools/retrieve.py) │                   │       (scripts/agent/config.py & tools/)      │
│  - Load 177K CLIP ViT-B/32 Embeddings  │                   │  - Query Rewrite: VN → EN Visual Prompts      │
│  - Cosine Similarity Matrix Search     │                   │  - Offline Objects Lookup (Faster R-CNN)      │
│  - Single-Video Temporal Search        │                   │  - VLM Vision & Answer Cross-checking         │
└───────────────────┬────────────────────┘                   └───────────────────────┬───────────────────────┘
                    │                                                                │
                    └────────────────────────────────┬───────────────────────────────┘
                                                     ▼
                                  ┌─────────────────────────────────────┐
                                  │      SUBMISSION ENGINE & VALIDATOR  │
                                  │     (scripts/submit/*.py)           │
                                  │  - Tạo CSV (KIS / QA / TRAKE)       │
                                  │  - Đóng gói ZIP chuẩn BTC           │
                                  │  - Tự động kiểm tra lỗi (Validator) │
                                  └─────────────────────────────────────┘
```

---

## 3. TIẾN TRÌNH & CHI TIẾT CÁC THÀNH PHẦN ĐÃ THỰC HIỆN

### 3.1. NGÀY 1 — NỀN TẢNG TÌM KIẾM CƠ SỞ & BỘ CÔNG CỤ NỘP BÀI (BASELINE)

* **Bộ máy tìm kiếm véc-tơ (`scripts/agent/tools/retrieve.py`):**

  - Triển khai Singleton Pattern để nạp toàn bộ 177.321 keyframes từ ma trận CLIP véc-tơ (`.npy`) và dữ liệu metadata một lần duy nhất vào bộ nhớ RAM.
  - Cung cấp hàm `fast_retrieve(query_text, top_k)` cho phép tìm kiếm toàn bộ kho video qua cosine similarity chỉ mất vài phần mười giây.
  - Cung cấp hàm `fast_retrieve_for_video(query_text, video_id, top_k)` hỗ trợ tìm kiếm cục bộ trong một video đơn lẻ (dùng cho TRAKE).
  - Chuẩn hóa trường `frame_id` tự động cộng `+1` theo đúng quy ước BTC và ánh xạ chỉ số `n` để tra cứu object.
* **Pipeline KIS chuẩn (`scripts/agent/pipeline_kis.py`):**

  - Workflow tuyến tính hiệu năng cao, không phụ thuộc API ngoài, xử lý tìm kiếm văn bản đơn giản.
* **Bộ sinh và kiểm tra tệp nộp bài (`scripts/submit/`):**

  - `build_submission.py`: Hỗ trợ xuất 3 định dạng CSV chuẩn (`build_kis_csv`, `build_qa_csv`, `build_trake_csv`), tự động cắt giới hạn 100 hàng, loại bỏ đuôi `.mp4`, và đóng gói `build_zip_submission`.
  - `validate_submission.py`: Bộ kiểm tra toàn diện, rà soát encoding `UTF-8`, định dạng số nguyên dương `frame_id ≥ 1`, số lượng dòng, cấu trúc cột trước khi nộp lên hệ thống chấm (Codabench).
* **Kiểm thử tích hợp Ngày 1 (`scripts/test_day1.py`):**

  - Đã chạy kiểm thử thành công: truy xuất véc-tơ, xuất 2 file CSV KIS, đóng gói file ZIP và vượt qua validator với kết quả **100% PASS**.

---

### 3.2. NGÀY 2 — KIẾN TRÚC AI AGENT ĐA PHƯƠNG THỨC (Q&A + TRAKE)

* **Cấu hình & Quản lý Mô hình Ngôn ngữ (`scripts/agent/config.py`):**

  - Tích hợp `litellm` và `python-dotenv` để gọi API Google Gemini (`gemini-3.5-flash`).
  - Xử lý đặc thù của Reasoning/Thinking model: Tự động điều chỉnh `MIN_OUTPUT_TOKENS = 2048` để tránh cạn kiệt token trong quá trình suy luận ngầm.
  - Cung cấp hàm đa năng `call_llm(prompt, image_paths, model)` hỗ trợ cả Text và Vision.
* **Tối ưu hóa & Dịch truy vấn (`scripts/agent/tools/rewrite.py`):**

  - Nhận truy vấn tiếng Việt hoặc tiếng Anh phức tạp, lược bỏ các từ ngữ dư thừa, chuyển đổi thành mô tả trực quan (visual-centric description: vật thể, màu sắc, khung cảnh) tối ưu cho không gian nhúng của CLIP ViT-B/32.
  - Hỗ trợ cơ chế phản hồi (feedback loop) để viết lại câu truy vấn nếu vòng tìm kiếm trước chưa đạt kết quả tốt.
* **Khai thác Dữ liệu Đối tượng Offline (`scripts/agent/tools/ocr_lookup.py`):**

  - Đọc trực tiếp các tệp JSON đối tượng (Faster R-CNN trên tập OpenImages V4 do BTC cung cấp) từ thư mục `data/extracted/objects-aic25-b1/objects/{video_id}/{n:03d}.json`.
  - Hoạt động hoàn toàn offline, tốc độ cực nhanh, không tốn chi phí gọi API.
* **Trích xuất Câu trả lời & Kiểm tra chéo (`scripts/agent/tools/answer_qa.py`):**

  - Cơ chế **2 tầng (Two-Tier)**:
    - *Tầng 1:* Đối chiếu trực tiếp với danh sách vật thể từ Objects JSON để trả lời ngay các câu hỏi về đếm hoặc nhận diện thực thể.
    - *Tầng 2:* Đọc ảnh keyframe thực tế và gọi Gemini Vision nếu câu hỏi đòi hỏi thông tin chi tiết.
  - **Cross-check chống ảo giác (Anti-hallucination):** Tự động đối chiếu câu trả lời do VLM sinh ra với danh mục vật thể thực tế trong frame trước khi chấp nhận, đảm bảo không bị mất điểm R-Score oan.
* **Orchestrator Q&A (`scripts/agent/pipeline_qa.py`):**

  - Điều phối quy trình tìm kiếm Q&A qua tối đa 2 vòng phản tư (Reflection Loop). Nếu độ tin cậy vòng 1 thấp, agent tự động điều chỉnh truy vấn dựa trên feedback và tìm kiếm lại.
* **Pipeline TRAKE căn chỉnh chuỗi sự kiện (`scripts/agent/pipeline_trake.py`):**

  - Quy trình 2 giai đoạn:
    - *Giai đoạn 1 (Retrieval):* Tìm kiếm tổng quát để xác định video ứng viên có điểm tích lũy cao nhất.
    - *Giai đoạn 2 (Alignment):* Căn chỉnh từng khoảnh khắc sự kiện với **World Model thời gian nhẹ** (`frame_idx_i > frame_idx_{i-1}`), đảm bảo chuỗi sự kiện xảy ra đúng tuần tự vật lý.
* **Kiểm thử tích hợp Ngày 2 (`scripts/test_day2_full.py`):**

  - Đã chạy kiểm thử toàn diện: Rewrite câu hỏi, chạy Q&A pipeline, chạy TRAKE pipeline trên video thể thao `L25_V049`, sinh đầy đủ CSV/ZIP và validate thành công.

---

### 3.3. NGÀY 3 — GIAO DIỆN NGƯỜI DÙNG HUMAN-IN-THE-LOOP HOÀN CHỈNH (`scripts/app.py`)

Xây dựng ứng dụng web tương tác bằng Gradio với 4 Tab chuyên biệt:

1. **Tab 1 — 🔍 KIS (Textual Keyframe Search):**

   - Hộp nhập truy vấn tiếng Việt/tiếng Anh, tích hợp nút bật/tắt **Auto-translate**.
   - Thanh trượt tùy chỉnh `Top-k` (5 đến 100).
   - Gallery hiển thị hình ảnh keyframe trực tiếp.
   - Bảng kết quả tương tác (`gr.Dataframe`): Cho phép người dùng trực tiếp xóa dòng không khớp hoặc hoán đổi thứ tự trước khi bấm **➕ Add to Submission Queue**.
2. **Tab 2 — ❓ Q&A (Question Answering):**

   - Ô nhập mô tả cảnh và câu hỏi chi tiết.
   - Hiển thị Gallery ảnh top kết quả, câu trả lời do AI đề xuất, độ tin cậy (Confidence).
   - Ô đáp án dạng tương tác: Cho phép người dùng chỉnh sửa câu trả lời theo ý muốn trước khi thêm vào hàng đợi.
3. **Tab 3 — 🎬 TRAKE (Event Sequence Alignment):**

   - Ô nhập mô tả tổng quát và danh sách $N$ khoảnh khắc (mỗi dòng 1 sự kiện).
   - Trình bày danh sách video kèm chuỗi `frame_ids` đã căn chỉnh thời gian.
   - Cho phép chỉnh sửa trực tiếp các chỉ số khung hình trên giao diện.
4. **Tab 4 — 📦 Export (Xuất file nộp bài):**

   - Bảng tổng kết hàng đợi nộp bài trong phiên làm việc.
   - Nút **📦 Export ZIP**: Tự động tạo toàn bộ file CSV tương ứng, đóng gói thành 1 tệp ZIP duy nhất đặt tại thư mục `submissions/` và hiển thị đường dẫn tệp để nộp lên Codabench.
   - Nút **🗑️ Clear Queue**: Xóa trắng hàng đợi để chuẩn bị cho đợt truy vấn mới.

---

## 4. CẤU TRÚC TỆP TIN DỰ ÁN

```
AIC2026/
├── docs/
│   ├── BaoCao_TongHop_TrienKhai_AIC2026.md   # [MỚI] Báo cáo tổng hợp toàn bộ hệ thống
│   ├── Thong tin vong So tuyen AIC2026.md   # Tài liệu luật thi chính thức
│   └── Training/                            # Tài liệu tập huấn chuyên sâu
│       ├── AIC2026_Buoi1_BaiToanVaHeThongVideoRetrieval.md
│       ├── AIC2026_Buoi2_KienTruc_VisionLanguage_VideoRetrieval.md
│       ├── AIC2026_SoTuyen_QuyTrinh_NopBai_ChamDiem.md
│       └── AIC2026_TongHop_LuatThi_va_KienTrucAgent.md
├── scripts/
│   ├── app.py                               # [MỚI] Ứng dụng Gradio Web UI (4 Tabs)
│   ├── index.py                             # Bộ nạp dữ liệu và lập chỉ mục véc-tơ gốc
│   ├── test_day1.py                         # [MỚI] Kịch bản kiểm thử Ngày 1
│   ├── test_day2_basic.py                   # [MỚI] Kịch bản kiểm thử cơ bản Ngày 2
│   ├── test_day2_full.py                    # [MỚI] Kịch bản kiểm thử toàn diện Ngày 2
│   ├── agent/
│   │   ├── __init__.py                      # [MỚI]
│   │   ├── config.py                        # [MỚI] Cấu hình LLM/VLM Gemini 3.5 Flash
│   │   ├── pipeline_kis.py                  # [MỚI] Pipeline tìm kiếm KIS
│   │   ├── pipeline_qa.py                   # [MỚI] Pipeline Q&A Orchestrator
│   │   ├── pipeline_trake.py                # [MỚI] Pipeline TRAKE Alignment
│   │   └── tools/
│   │       ├── __init__.py                  # [MỚI]
│   │       ├── retrieve.py                  # [MỚI] Bộ truy xuất véc-tơ vĩ mô & vi mô
│   │       ├── rewrite.py                   # [MỚI] Công cụ dịch & tối ưu truy vấn
│   │       ├── ocr_lookup.py                # [MỚI] Công cụ đọc Objects JSON offline
│   │       └── answer_qa.py                 # [MỚI] Công cụ trả lời & cross-check
│   └── submit/
│       ├── __init__.py                      # [MỚI]
│       ├── build_submission.py              # [MỚI] Công cụ tạo CSV & ZIP nộp bài
│       └── validate_submission.py           # [MỚI] Công cụ kiểm tra tính hợp lệ
├── queries/
│   └── sample_queries.json                  # [MỚI] Tập truy vấn mẫu kiểm thử
├── submissions/                             # [MỚI] Thư mục chứa kết quả CSV và ZIP
├── .env                                     # [MỚI] Tệp cấu hình API Key bí mật
├── .env.example                             # [MỚI] Tệp mẫu cấu hình API
├── .gitignore                               # [CẬP NHẬT] Bổ sung .env, submissions/*.zip
└── requirements.txt                         # [CẬP NHẬT] Đóng băng phiên bản thư viện
```

---

## 5. HƯỚNG DẪN CÀI ĐẶT & VẬN HÀNH

### 5.1. Môi trường & Thư viện

Dự án sử dụng Python Virtual Environment (`.venv`). Đảm bảo các gói phụ thuộc sau đã được cài đặt:

```powershell
.venv\Scripts\pip.exe install sentence-transformers gradio pandas torch pillow litellm python-dotenv
```

### 5.2. Cấu hình API Key

Tạo file `.env` tại thư mục gốc của dự án với nội dung:

```env
GEMINI_API_KEY=AIzaSy...your_gemini_api_key...
```

### 5.3. Khởi chạy Ứng dụng Giao diện Web (Khuyên dùng khi thi)

Chạy lệnh sau trên PowerShell:

```powershell
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe scripts\app.py
```

- Ứng dụng sẽ tự động tải véc-tơ index và mở trình duyệt tại: **`http://127.0.0.1:7860`**
- Thao tác: Chọn Tab tương ứng (`KIS` / `Q&A` / `TRAKE`) → Nhập thông tin → Bấm chạy → Rà soát kết quả trên bảng → Bấm **Add to Queue** → Chuyển sang Tab **Export** và bấm **Export ZIP**.

### 5.4. Chạy kiểm thử tự động (Command Line)

- **Kiểm thử Ngày 1 (KIS & Submission Engine):**
  ```powershell
  .venv\Scripts\python.exe scripts\test_day1.py
  ```
- **Kiểm thử Ngày 2 (Q&A, TRAKE & LLM Agent):**
  ```powershell
  .venv\Scripts\python.exe scripts\test_day2_full.py
  ```

---

## 6. KẾT LUẬN & ĐÁNH GIÁ

Hệ thống đã đạt được các tiêu chuẩn cốt lõi:

1. **Độ tin cậy kỹ thuật:** Toàn bộ file xuất ra đều được kiểm tra tự động, không có lỗi định dạng hay vi phạm quy chế thi.
2. **Khả năng mở rộng:** Kiến trúc phân lớp theo Tool-use / Orchestrator pattern giúp dễ dàng tích hợp thêm các mô hình Vision lớn hơn (SigLIP2, BEiT-3) hoặc bổ sung Batch 2 khi BTC công bố.
3. **Tính thực chiến cao:** Thời gian phản hồi nhanh, kết hợp linh hoạt giữa tự động hóa và sự can thiệp của con người, tối ưu hóa điểm $R@k$ cho vòng sơ tuyển.
