# AIC2026 — Hệ thống tìm kiếm Video-Frame bằng ngôn ngữ tự nhiên

> Dự án tham dự **Hội thi Thử thách Trí tuệ Nhân tạo TP.HCM 2026 (AIC 2026)** — vòng Sơ tuyển & Chung kết.
> Cho câu mô tả sự kiện tự nhiên, hệ thống truy vấn và trả về danh sách xếp hạng `video_id` + `frame_id` (KIS), kèm `answer` (Q&A) hoặc chuỗi mốc sự kiện tuần tự `frame_id` (TRAKE).

---

## 📑 Mục lục

- [1. Tổng quan &amp; Tính năng nổi bật](#1-tổng-quan--tính-năng-nổi-bật)
- [2. Kiến trúc hệ thống](#2-kiến-trúc-hệ-thống)
- [3. Tech Stack](#3-tech-stack)
- [4. Cấu trúc thư mục](#4-cấu-trúc-thư-mục)
- [5. Cài đặt &amp; Khởi chạy](#5-cài-đặt--khởi-chạy)
- [6. Hướng dẫn sử dụng](#6-hướng-dẫn-sử-dụng)
- [7. Pipeline chi tiết](#7-pipeline-chi-tiết)
- [8. Kết quả đánh giá &amp; Benchmark](#8-kết-quả-đánh-giá--benchmark)
- [9. Kaggle Jobs — Encode SOTA](#9-kaggle-jobs--encode-sota)
- [10. Quy ước code &amp; Lưới an toàn](#10-quy-ước-code--lưới-an-toàn)
- [11. Thông tin Đội thi](#11-thông-tin-đội-thi)

---

## 1. Tổng quan & Tính năng nổi bật

Hệ thống xử lý tối ưu cho **3 dạng bài thi chính thức** của AIC 2026:

| Dạng bài                            | Mô tả bài toán                                     | Kiến trúc Pipeline                                                                                  | Backbone mặc định           |
| :------------------------------------ | :----------------------------------------------------- | :---------------------------------------------------------------------------------------------------- | :----------------------------- |
| **KIS** *(Known-Item Search)* | Tìm 1 frame cụ thể từ mô tả sự kiện            | Tuyến tính, Hybrid Dense + BM25, Risk-Aware Rerank & Temporal NMS (không LLM)                      | `Google SigLIP SO400M-384`   |
| **Q&A** *(Question & Answer)* | Tìm frame mục tiêu + trả lời câu hỏi nội dung  | Orchestrator-workers, 2-tier Anti-hallucination (Objects JSON + Vision LLM)                           | `Google SigLIP 2 SO400M-384` |
| **TRAKE** *(Tracking Events)* | Tìm chuỗi$N$ frame theo đúng thứ tự thời gian | 2 giai đoạn: Top-K video retrieval$\rightarrow$ Monotonic DP event alignment + Selective LLM gate | `Google SigLIP SO400M-384`   |

### 🌟 Điểm nổi bật công nghệ:

- 🚀 **Dual-Singleton SOTA Backbone**: Sử dụng đồng thời `SigLIP` (cho KIS/TRAKE) và `SigLIP 2` (cho Q&A) nạp sẵn trong RAM trên ma trận ~177K keyframe (873 video).
- ⚡ **Hybrid Retrieval (Dense + Sparse)**: Kết hợp vector cosine similarity và BM25 offline (Objects JSON + captions) qua thuật toán Reciprocal Rank Fusion (RRF).
- 🛡️ **Risk-Aware Reranking & Temporal NMS**: Khử cụm trùng lặp theo thời gian ($NMS_{\Delta t}$) và tự động chuyển chế độ trải rủi ro khi khoảng cách điểm (margin) quá hẹp.
- 👁️ **Video Verifier & Human-in-the-loop**: Giao diện React SPA hiện đại cho phép tua video trực tiếp theo frame với HTTP Range streaming, kéo thả card để xếp hạng, shortlist nhanh và export ZIP 1-click.
- 🛡️ **Anti-Hallucination 2 tầng**: Tự động đối soát câu trả lời Q&A với Faster R-CNN Object Detection offline trước khi chốt đáp án.
- 📦 **Submission Engine & Validator**: Tự động sinh file nộp theo định dạng chuẩn BTC kèm validator nội bộ kiểm tra nghiêm ngặt cấu trúc CSV/ZIP trước khi upload.

---

## 2. Kiến trúc hệ thống

```
                           NGƯỜI DÙNG (THÍ SINH)
                                     │
           Giao diện Web UI (Tìm kiếm, Kéo thả, Xem video, Sửa tay kết quả)
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │        FRONTEND (React 19 + TypeScript + Vite)          │
        │   - KIS / Q&A / TRAKE / Chat / Export Management        │
        │   - VideoVerifier: Streaming MP4 HTTP Range Scrubbing   │
        └────────────────────────────┬────────────────────────────┘
                                     │ REST API (Proxy /api)
                                     ▼
        ┌─────────────────────────────────────────────────────────┐
        │             BACKEND (FastAPI + Uvicorn)                 │
        │   - Router: /api/kis, /api/qa, /api/trake, /api/queue   │
        │   - Router: /api/videos (Range + meta), /api/images     │
        │   - In-Memory Session Queue State                       │
        └───────┬────────────────────┬────────────────────┬───────┘
                │                    │                    │
                ▼                    ▼                    ▼
        ┌───────────────┐    ┌───────────────┐    ┌───────────────┐
        │ pipeline_kis  │    │  pipeline_qa  │    │pipeline_trake │
        │ (Hybrid Dense │    │ (Orchestrator │    │ (2-Stage DP   │
        │ + BM25 + NMS) │    │  Reflection)  │    │  Alignment)   │
        └───────┬───────┘    └───────┬───────┘    └───────┬───────┘
                │                    │                    │
                └───────────┬────────┴───────────┬────────┘
                            │                    │
                            ▼                    ▼
     ┌──────────────────────────────┐    ┌──────────────────────────────┐
     │   RETRIEVAL & EMBEDDING      │    │     AGENT LLM & VISION       │
     │ - Singleton Index: SigLIP/2  │    │ - config.py: call_llm()      │
     │ - sparse_index.py (BM25)     │    │ - OpenRouter / Gemini Flash  │
     │ - rerank.py & temporal_nms   │    │ - Objects JSON Faster R-CNN  │
     └──────────────┬───────────────┘    └──────────────┬───────────────┘
                    │                                   │
                    └─────────────────┬─────────────────┘
                                      ▼
                        ┌───────────────────────────┐
                        │   SUBMISSION GENERATOR    │
                        │ - build_submission.py     │
                        │ - validate_submission.py  │
                        │ ➔ submissions/*.zip       │
                        └───────────────────────────┘
```

---

## 3. Tech Stack

| Thành phần                 | Công nghệ / Thư viện                                        | Vai trò                                                        |
| :--------------------------- | :-------------------------------------------------------------- | :-------------------------------------------------------------- |
| **Backend API**        | `Python 3.10+`, `FastAPI`, `Uvicorn`                      | REST API service, xử lý pipeline, streaming video             |
| **Frontend UI**        | `React 19`, `TypeScript`, `Vite`, `TailwindCSS`         | Single Page Application, Video Player, Shortlist Board          |
| **Dense Models**       | `Google SigLIP SO400M-384`, `Google SigLIP 2 SO400M-384`    | Image & Text Embedding SOTA (1152 chiều)                       |
| **Sparse Index**       | `BM25Okapi` (`sparse_index.py`)                             | Lexical search trên Object detection + ASR + Captions          |
| **Deep Learning**      | `PyTorch` (CPU build), `HuggingFace Transformers`           | Text tokenization, encoder inference                            |
| **Data Ops**           | `NumPy`, `Pandas`, `Pillow`, `OpenCV`                   | Ma trận vector, metadata index, xử lý frame ảnh             |
| **LLM Gateway**        | `LiteLLM` qua **OpenRouter** (`Gemini 2.5/3.7 Flash`) | Dịch VN$\rightarrow$ EN, Query Rewrite, VQA, DP Verification |
| **Anti-Hallucination** | `Faster R-CNN` (Objects JSON offline)                         | Căn cứ xác thực độc lập cho câu trả lời Q&A           |

> **Không sử dụng**: Database SQL/NoSQL hay Message Queue phức tạp. Toàn bộ state vector lưu trữ dưới dạng file tĩnh (`.npy`), session queue lưu trong RAM backend để đạt tốc độ tối đa.

---

## 4. Cấu trúc thư mục

```
AIC2026/
├── frontend/                       # Giao diện người dùng React 19 + Vite
│   ├── src/
│   │   ├── components/             # UI Components (VideoVerifier, KeyframeModal, ShortlistGrid, ...)
│   │   ├── pages/                  # 5 Màn hình: KIS, QA, TRAKE, Chat, Export/Queue
│   │   └── services/api.ts         # Client API gọi Backend FastAPI
│   ├── package.json
│   └── vite.config.ts              # Proxy /api ➔ http://127.0.0.1:8000
│
├── scripts/                        # Mã nguồn Python backend & pipelines
│   ├── api/                        # FastAPI Backend Application
│   │   ├── main.py                 # App entrypoint, middleware CORS, preloading
│   │   ├── state.py                # In-memory session queue manager
│   │   ├── schemas.py              # Pydantic request/response models
│   │   ├── _smoke_test.py          # Script kiểm thử tự động toàn diện API
│   │   └── routers/                # Endpoints (kis, qa, trake, queue, images, videos)
│   │
│   ├── agent/                      # Lõi pipeline và công cụ retrieval/LLM
│   │   ├── config.py               # Gateway LLM tập trung (call_llm, fallback chain)
│   │   ├── pipeline_kis.py         # Pipeline KIS (Dense + BM25 Hybrid + Rerank)
│   │   ├── pipeline_qa.py          # Pipeline Q&A (Reflection Orchestrator + Anti-hallucination)
│   │   ├── pipeline_trake.py       # Pipeline TRAKE (2 giai đoạn: Candidate ➔ DP Alignment)
│   │   └── tools/                  # Thư viện công cụ dùng chung
│   │       ├── index_store.py      # Sở hữu ma trận + meta + encoder; ĐIỂM DUY NHẤT quy đổi frame_id
│   │       ├── retrieve.py         # Truy vấn dense thuần (SigLIP / SigLIP 2)
│   │       ├── hybrid.py           # Dense + BM25 dung hợp bằng RRF, multi-model RRF
│   │       ├── frames.py           # Tra cứu keyframe cho tầng UI (không có score)
│   │       ├── sparse_index.py     # BM25 lexical index builder & searcher
│   │       ├── fusion.py           # Reciprocal Rank Fusion (RRF) — module thuần
│   │       ├── rerank.py           # Risk-Aware Ranking + giữ đuôi theo retrieval gốc
│   │       ├── temporal_nms.py     # Khử trùng lặp theo thời gian — module thuần
│   │       ├── query_expand.py     # Multi-Aspect Query Expansion — module thuần
│   │       ├── trake_align.py      # DP đơn điệu + rule plausibility — module thuần
│   │       ├── rewrite.py          # LLM Query Translation (VN➔EN) & Candidates
│   │       ├── translate_raw.py    # Dịch thô VN➔EN, không qua LLM (để đối chiếu)
│   │       ├── answer_qa.py        # Logic trả lời Q&A 3 tầng + cross-check
│   │       ├── qa_prompts.py       # 9 prompt template của nhánh Q&A
│   │       ├── qa_classify.py      # Nhận dạng loại câu hỏi (đếm / đọc chữ / số hiển thị)
│   │       ├── qa_normalize.py     # Canonicalize answer + cổng chống ảo giác
│   │       ├── objects_lookup.py   # Đọc Objects JSON (Faster R-CNN) — KHÔNG phải OCR
│   │       ├── ocr_read.py         # OCR thật, chạy on-demand tối đa 3 ảnh
│   │       └── asr_lookup.py       # Tra transcript quanh một mốc thời gian
│   │
│   ├── submit/                     # Đóng gói và xác thực bài nộp
│   │   ├── build_submission.py     # Sinh file CSV và file ZIP theo chuẩn BTC
│   │   └── validate_submission.py  # Bộ kiểm tra tính hợp lệ bài nộp
│   │
│   └── offline/                    # Chạy MỘT LẦN, ghi vào data/ — không nằm trên đường truy vấn
│       ├── captions/               # Sinh & gộp caption Vintern-1B
│       ├── ocr/                    # OCR hàng loạt + đẩy vào Elasticsearch
│       ├── shards/                 # Đóng gói / đẩy / tải shard cho Kaggle & Colab
│       └── analysis/               # Phân tích dữ liệu (vd. độ tương tự frame liền kề)
│
├── tests/                          # Bộ kiểm thử & Benchmark theo chuẩn BTC
│   ├── conftest.py                 # Đặt repo root lên sys.path — điểm duy nhất cho pytest
│   ├── unit/                       # pytest, tất định, KHÔNG cần data/ hay API key (~10s)
│   ├── e2e/                        # Chạy đường production (cần API key)
│   │   ├── score_pipelines.py      # Chấm Final Score BTC thật end-to-end
│   │   ├── golden_kis_snapshot.py  # Ảnh chụp TẤT ĐỊNH của cả đường KIS (không cần API key)
│   │   └── test_smoke_pipelines.py # Smoke test KIS, QA, TRAKE & Submission
│   │   ├── run_eval.py             # So sánh backbone trên bộ query
│   │   ├── multi_index.py          # Index loader hỗ trợ nhiều model đồng thời
│   │   ├── gt_loader.py            # Module nạp ground truth tập trung
│   │   └── eval_ground_truth_*.json # 3 bộ ground truth hand-label KIS/QA/TRAKE
│   └── data/                       # Dữ liệu query dùng chung (sample_queries, bộ đề BTC)
│
├── data/                           # [git-ignored] Dữ liệu BTC & Vector Features
│   ├── extracted/
│   │   ├── features_siglip/        # Ma trận SigLIP SO400M (KIS & TRAKE)
│   │   ├── features_siglip2/       # Ma trận SigLIP 2 SO400M (Q&A)
│   │   ├── keyframes/              # Toàn bộ ảnh keyframe (.jpg)
│   │   ├── map-keyframes/          # CSV mapping video_id, frame_idx, pts_time
│   │   └── objects/                # Objects JSON Faster R-CNN
│   └── bm25_cache.pkl              # Cache BM25 offline
│
├── kaggle_jobs/                    # Scripts encode GPU Kaggle cho các model SOTA
├── submissions/                    # Thư mục chứa bài nộp CSV/ZIP xuất ra
├── docs/                           # Tài liệu thiết kế, đề thi & _archive/ (mã nguồn cũ)
├── requirements.txt                # Danh sách thư viện Python
├── .env.example                    # File cấu hình mẫu
└── README.md
```

---

## 5. Cài đặt & Khởi chạy

### Yêu cầu môi trường:

- **Python**: `3.10` trở lên.
- **Node.js**: `18.0` trở lên (cho Frontend).
- **RAM**: Tối thiểu 8GB (khuyên dùng 16GB để nạp đồng thời index SigLIP & SigLIP 2).

### Bước 1: Cài đặt Backend Python

```powershell
# 1. Tạo và kích hoạt virtualenv
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Cài đặt các thư viện phụ thuộc
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Bước 2: Cài đặt Frontend React

```powershell
cd frontend
npm install
cd ..
```

### Bước 3: Cấu hình API Key

Tạo file `.env` từ `.env.example` và điền key:

```env
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=google/gemini-2.5-flash
```

### Bước 4: Xây dựng BM25 Index Cache (chỉ làm 1 lần)

```powershell
.venv\Scripts\python.exe scripts\agent\tools\sparse_index.py --build
```

### Bước 5: Khởi động hệ thống

Mở 2 cửa sổ terminal:

```powershell
# Terminal 1 — Khởi động Backend API:
.venv\Scripts\python.exe -m uvicorn scripts.api.main:app --reload --port 8000
# ➔ API Sẵn sàng tại: http://127.0.0.1:8000/api/health

# Terminal 2 — Khởi động Giao diện Web:
cd frontend
npm run dev
# ➔ Giao diện truy cập tại: http://localhost:5173
```

---

## 6. Hướng dẫn sử dụng

### 🖥️ Các Tab trên Giao diện Web:

1. **Tab KIS (Known-Item Search)**:

   - Nhập query (tiếng Việt hoặc tiếng Anh) $\rightarrow$ Nhấn **Search** (hoặc chọn gợi ý Rewrite).
   - Danh sách keyframe hiển thị trực quan kèm Video ID, Frame ID, thời gian và điểm số.
   - Bấm vào keyframe để mở **VideoVerifier** (xem video gốc, tua từng frame, kiểm tra độ chính xác).
   - Kéo thả sắp xếp thứ tự các kết quả ưng ý, loại bỏ kết quả sai.
   - Nhập `Query ID` (ví dụ: `query-01-kis`) và bấm **Add to Queue**.
2. **Tab Q&A (Question & Answer)**:

   - Nhập mô tả bối cảnh và câu hỏi chi tiết.
   - Bấm **Run Q&A Pipeline** $\rightarrow$ Hệ thống tự động truy vấn qua SigLIP 2, trích xuất objects, gọi Vision LLM và đối soát chống ảo giác.
   - Rà soát câu trả lời tại ô **Câu trả lời**, chỉnh sửa nếu cần rồi thêm vào hàng đợi.
3. **Tab TRAKE (Tracking Events)**:

   - Nhập danh sách các mốc sự kiện theo thứ tự thời gian.
   - Bấm **Run TRAKE** $\rightarrow$ Hệ thống tìm top video ứng viên và căn chỉnh chuỗi $N$ frame tăng dần.
   - Thêm kết quả chuỗi frame vào hàng đợi.
4. **Tab Export & Hàng đợi**:

   - Theo dõi trạng thái tất cả các query đã thêm trong phiên làm việc.
   - Bấm **Export ZIP** $\rightarrow$ Hệ thống tự động đóng gói bài nộp vào `submissions/` và chạy trình validate tức thì.

---

## 7. Pipeline chi tiết

### 🔍 1. KIS Pipeline

```
[Query Input] ──► [Rewrite VN➔EN] ──► [Dense SigLIP Cosine] ──┐
                                                               ├──► [RRF Fusion] ──► [Temporal NMS] ──► [Risk-Aware Rerank] ──► [Top-K Hits]
                                  ──► [Sparse BM25 Index]   ──┘
```

- **Temporal NMS**: Lọc bỏ các keyframe quá gần nhau trong cùng 1 video ($\Delta t < 5s$).
- **Risk-Aware Rerank**: Nếu khoảng cách điểm giữa Top-1 và Top-2 nhỏ hơn ngưỡng an toàn, tự động xen kẽ các video đa dạng vào Top đầu để tối ưu $R@k$.

### ❓ 2. Q&A Pipeline

```
[Query + Question] ──► [SigLIP 2 Dense Search] ──► [Top Video Clusters]
                                                           │
        ┌──────────────────────────────────────────────────┴──────────────────────────────────────────────────┐
        ▼                                                                                                     ▼
[Tầng 1: Objects JSON (Faster R-CNN)]                                                                [Tầng 2: Vision LLM]
Xác định vật thể, thuộc tính cơ bản                                                             Phân tích trực tiếp chi tiết ảnh
        │                                                                                                     │
        └─────────────────────────────────────────┬───────────────────────────────────────────────────────────┘
                                                  ▼
                                       [_crosscheck_answer()]
                                                  │
                                                  ├── Confidence >= 0.5 ──► [Chốt đáp án]
                                                  └── Confidence < 0.5  ──► [Reflection vòng 2 với feedback] (Tối đa 2 vòng)
```

### ⏱️ 3. TRAKE Pipeline

```
[Event 1..N] ──► [Giai đoạn 1: Global Query Retrieval] ──► [Top-20 Candidate Videos]
                                                                   │
                                                                   ▼
[Giai đoạn 2: Monotonic Alignment DP] ──► Khớp từng event vào frame_idx tăng dần trong từng video
                                                                   │
                                                                   ▼
[Selective LLM Validation Gate] ───────► Chỉ kích hoạt LLM xác thực khi margin điểm giữa Top-1 & Top-2 < 0.02
                                                                   │
                                                                   ▼
                                                       [Chuỗi Frame ID tối ưu]
```

---

## 8. Kết quả đánh giá & Benchmark

Đánh giá thực nghiệm trên bộ **Ground Truth 33 query chuẩn** (KIS=18, QA=5, TRAKE=10) theo công thức chấm điểm chính thức của BTC:

$$
\text{Final Score} = \frac{1}{5} \sum_{k \in \{1, 5, 20, 50, 100\}} R@k
$$

### 📊 So sánh Backbone Retrieval (Retrieval-Only Bake-Off):

| Backbone Model                              | Kích thước Feature |       R@1       |       R@5       |      R@20      |      R@50      |      R@100      | **Final Score** |   So với Baseline   |
| :------------------------------------------ | :-------------------: | :-------------: | :-------------: | :-------------: | :-------------: | :-------------: | :-------------------: | :-------------------: |
| `OpenAI CLIP ViT-B/32` *(Baseline cũ)* |          512          |      0.136      |      0.207      |      0.298      |      0.389      |      0.419      |    **0.290**    |       Baseline       |
| `OpenCLIP DFN-5B ViT-H/14`                |         1024         |      0.265      |      0.477      |      0.586      |      0.616      |      0.737      |    **0.536**    |      $+84.8\%$      |
| **`Google SigLIP SO400M-384`**      |    **1152**    | **0.295** | **0.457** | **0.624** | **0.654** | **0.715** |    **0.549**    | **$+89.3\%$** |
| **`Google SigLIP 2 SO400M-384`**    |    **1152**    | **0.227** | **0.475** | **0.604** | **0.694** | **0.755** |    **0.551**    | **$+90.0\%$** |

> **Kết luận**: `SigLIP` đạt điểm số KIS cao nhất (**0.744**), trong khi `SigLIP 2` vượt trội hoàn toàn ở bài toán Q&A (**0.440** so với 0.000 của baseline). Do đó, hệ thống chọn kiến trúc **Dual-Singleton**: SigLIP cho KIS/TRAKE và SigLIP 2 cho Q&A.

---

## 9. Kaggle Jobs — Encode SOTA

Các notebook trích xuất đặc trưng trên Kaggle GPU (T4 x2) nằm trong `kaggle_jobs/`:

- `01_vit_l14/`: Trích xuất đặc trưng `OpenAI CLIP ViT-L/14` (768 chiều).
- `02_siglip/`: Trích xuất đặc trưng `Google SigLIP SO400M-384` (1152 chiều) — *Production*.
- `03_jina/`: Job thử nghiệm `Jina CLIP v2`.
- `04_dfn/`: Trích xuất đặc trưng `OpenCLIP DFN-5B ViT-H/14` (1024 chiều).
- `05_qwen_vl_ocr_caption/`: Trích xuất đặc trưng `SigLIP 2 SO400M` & captioning Qwen-VL.

---

## 10. Quy ước code & Lưới an toàn

- **Ngôn ngữ**: Toàn bộ ghi chú code, docstrings và text trên giao diện sử dụng **tiếng Việt**.
- **Quy tắc định danh**: `video_id` luôn ở dạng `{batch}_{video_num}` (ví dụ: `L21_V001`, không chứa đuôi `.mp4`).
- **Quy ước frame**: `frame_id = frame_idx + 1` (chỉ chuyển đổi tại duy nhất `retrieve.py`).
- **Lưới an toàn nghiêm ngặt**:
  - ❌ Không gọi LLM trực tiếp bên ngoài `scripts/agent/config.py:call_llm()`.
  - ❌ Không ghi file CSV/ZIP bài nộp bên ngoài `scripts/submit/build_submission.py`.
  - ❌ Không chạy vòng lặp LLM vô hạn (bắt buộc trần `MAX_AGENT_LOOPS = 2`).
  - ❌ Không commit API key hoặc file `.env` lên Git.

---

## 🛠️ Lệnh Kiểm Thử Thường Dùng

```powershell
# 1. Smoke test toàn bộ API Backend (KIS ➔ QA ➔ TRAKE ➔ Queue ➔ Export ➔ Validate)
.venv\Scripts\python.exe scripts\api\_smoke_test.py

# 2. Smoke test các pipeline độc lập
.venv\Scripts\python.exe tests\e2e\test_smoke_pipelines.py

# 3. Đánh giá Final Score BTC thật end-to-end
.venv\Scripts\python.exe tests\e2e\score_pipelines.py --types kis

# 4. Chạy bake-off so sánh các backbone embedding
.venv\Scripts\python.exe tests\eval\run_eval.py

# 5. Kiểm tra tính hợp lệ của file bài nộp mới nhất
.venv\Scripts\python.exe scripts\submit\validate_submission.py
```

---

## 11. Thông tin Đội thi

- **Tên đội**: **Gain**
- **Mã đội thi**: `AIC2026-140`
- **Bảng đăng ký dự thi**: Bảng A (Thanh niên, sinh viên)
- **Đơn vị**: Trường Đại học FPT (FPT University)

### 👥 Thành viên nhóm:

| STT | Họ và Tên                     | Vai trò                     | Đơn vị      |
| :-: | :------------------------------- | :--------------------------- | :------------- |
|  1  | **Nguyễn Văn Gia Bình** | Đội trưởng (Team Leader) | FPT University |
|  2  | **Lê Phan Thanh Nghi**    | Thành viên (Member)        | FPT University |
|  3  | **Lê Tuấn Kiệt**        | Thành viên (Member)        | FPT University |
|  4  | **Hồ Nhật Tân**         | Thành viên (Member)        | FPT University |

---

## 📜 Giấy phép & Bản quyền

Dự án phục vụ mục đích tham gia cuộc thi **AIC 2026**. Mọi quyền được bảo lưu.
