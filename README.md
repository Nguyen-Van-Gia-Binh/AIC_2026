# AIC2026 — Hệ thống tìm kiếm Video-Frame bằng ngôn ngữ tự nhiên

> Dự án thi **Hội thi Thử thách Trí tuệ Nhân tạo TP.HCM 2026 (AIC 2026)** — vòng Sơ tuyển.
> Cho một câu mô tả sự kiện bằng ngôn ngữ tự nhiên, hệ thống trả về `video_id` + `frame_id`
> (KIS), kèm `answer` (Q&A) hoặc chuỗi `frame_id` (TRAKE).

---

## Mục lục

- [Tổng quan](#tổng-quan)
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Tech Stack](#tech-stack)
- [Cấu trúc thư mục](#cấu-trúc-thư-mục)
- [Cài đặt &amp; Khởi chạy](#cài-đặt--khởi-chạy)
- [Sử dụng](#sử-dụng)
- [Pipeline chi tiết](#pipeline-chi-tiết)
- [Kaggle Jobs — Encode SOTA](#kaggle-jobs--encode-sota)
- [Tài liệu liên quan](#tài-liệu-liên-quan)
- [Quy ước code](#quy-ước-code)

---

## Tổng quan

Hệ thống giải quyết **3 dạng bài** của cuộc thi AIC 2026:

| Dạng bài                        | Mô tả                                                           | Pipeline                                          |
| --------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------- |
| **KIS** (Known-Item Search) | Tìm 1 frame cụ thể từ mô tả text                            | Tuyến tính, không LLM                          |
| **Q&A** (Question & Answer) | Tìm frame + trả lời câu hỏi về nội dung                    | Orchestrator-workers, tối đa 2 vòng reflection |
| **TRAKE** (Tracking Events) | Tìm chuỗi N frame theo thứ tự thời gian cho N mốc sự kiện | Pipeline 2 giai đoạn cố định                 |

**Điểm nổi bật:**

- 🔍 **CLIP retrieval** trên ma trận ~177K keyframe (873 video) — cosine similarity realtime
- 🤖 **Agent đa phương thức** — LLM text/vision qua OpenRouter và LiteLLM
- 🛡️ **Anti-hallucination** bắt buộc cho Q&A — cross-check answer với Objects JSON (Faster R-CNN) offline
- 👤 **Human-in-the-loop** — Gradio UI cho phép rà soát, sửa tay kết quả trước khi nộp bài
- 📦 **Submission engine** — tự sinh CSV/ZIP theo format BTC, kèm validator nội bộ

Scoring: **R-Score / R@k** trung bình tại rank 1/5/20/50/100. Luật thi chi tiết trong
[`docs/Thong tin vong So tuyen AIC2026.md`](<docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>).

---

## Kiến trúc hệ thống

```
Người dùng (thí sinh)
        │  nhập query trên UI, rà soát/sửa kết quả (human-in-the-loop)
        ▼
scripts/app.py  (Gradio, 4 tab: KIS / Q&A / TRAKE / Export)
        │
   ┌────┴─────────────────┬──────────────────────┐
   ▼                      ▼                       ▼
pipeline_kis.py     pipeline_qa.py          pipeline_trake.py
(tuyến tính,         (orchestrator,          (2 giai đoạn cố định:
 không LLM)           tối đa 2 vòng           retrieve video → align
                       reflection)             N mốc theo thứ tự)
   │                      │                       │
   └──────────┬───────────┴───────────┬───────────┘
              ▼                       ▼
   agent/tools/retrieve.py    agent/tools/rewrite.py, answer_qa.py, ocr_lookup.py
   (CLIP cosine similarity     (agent/config.py: call_llm() → LiteLLM → PROVIDER_CHAIN)
    trên ma trận 177K keyframe)
              │
              ▼
        submit/build_submission.py → CSV (kis/qa/trake) → validate_submission.py → ZIP
```

**Quyết định kiến trúc chính:**

- Không dùng 1 agent chung cho cả 3 dạng bài — chọn kiến trúc phù hợp theo độ mở của task
- 1 nguồn cấu hình LLM duy nhất: `scripts/agent/config.py`
- File-based, không database — toàn bộ state là file (`.npy`, `.csv`, `.json`, `.zip`)
- `frame_id = frame_idx + 1` chỉ tính tại 1 điểm duy nhất (`retrieve.py`)

Chi tiết đầy đủ → [`ARCHITECTURE.md`](ARCHITECTURE.md)

---

## Tech Stack

| Thành phần     | Công nghệ                                                                                          |
| ---------------- | ---------------------------------------------------------------------------------------------------- |
| Ngôn ngữ       | Python (qua`.venv`, không có Node/JS)                                                            |
| Embedding        | `sentence-transformers` (`clip-ViT-B-32`) — image & text encoder chung 1 không gian            |
| Framework ML     | `torch` (CPU build)                                                                                |
| Dữ liệu        | `pandas`, `numpy` — metadata table & ma trận embedding                                         |
| UI               | `gradio` — 4 tab KIS/Q&A/TRAKE/Export                                                             |
| LLM              | `litellm` — route text/vision qua **OpenRouter** |
| Cấu hình       | `python-dotenv` — load API key từ `.env`                                                       |
| Object detection | Faster R-CNN — dữ liệu Objects JSON offline (không gọi API)                                     |

**Không sử dụng**: database, ORM, message queue. Mọi dữ liệu nằm trong file tĩnh dưới `data/`, `queries/`, `submissions/`.

---

## Cấu trúc thư mục

```
AIC2026/
├── scripts/                        # Toàn bộ mã nguồn chính
│   ├── app.py                      # Gradio UI — entry point chính (http://127.0.0.1:7860)
│   ├── index.py                    # Build ma trận CLIP (N, 512) + metadata từ data/extracted/
│   ├── agent/                      # Pipeline & agent LLM
│   │   ├── config.py               # Cấu hình LLM tập trung (call_llm(), PROVIDER_CHAIN)
│   │   ├── pipeline_kis.py         # Pipeline KIS — tuyến tính, không LLM
│   │   ├── pipeline_qa.py          # Pipeline Q&A — orchestrator, 2 vòng reflection
│   │   ├── pipeline_trake.py       # Pipeline TRAKE — 2 giai đoạn cố định
│   │   └── tools/                  # Công cụ dùng chung
│   │       ├── retrieve.py         # CLIP cosine similarity, singleton index
│   │       ├── rewrite.py          # Dịch VN→EN + tối ưu query cho CLIP
│   │       ├── answer_qa.py        # Trả lời 2 tầng (objects → vision) + cross-check
│   │       └── ocr_lookup.py       # Đọc Objects JSON offline (Faster R-CNN)
│   ├── submit/                     # Sinh & kiểm tra bài nộp
│   │   ├── build_submission.py     # Sinh CSV/ZIP theo format BTC
│   │   └── validate_submission.py  # Validator nội bộ (encoding, frame≥1, ≤100 dòng)
│   ├── eval/                       # Phase 6 — bộ eval offline, so baseline embedding bằng R@k
│   │   ├── multi_index.py          # Index + text encoder cho nhiều model (clip_vitb32/vitl14/siglip/dfn)
│   │   ├── run_eval.py             # So baseline theo eval_ground_truth.json, ghi eval_baseline_comparison.md
│   │   └── lookup_frame.py         # CLI tra frame_id theo (video_id, giây) khi gán ground truth
│   ├── test_day1.py                # Test tích hợp end-to-end KIS
│   ├── test_day2_basic.py          # Test cơ bản Q&A/TRAKE
│   └── test_day2_full.py           # Test đầy đủ Q&A/TRAKE
│
├── data/                           # [git-ignored] Dữ liệu ngoại tuyến từ BTC
│   └── extracted/
│       ├── clip-features-32/       # Embedding CLIP float16 (.npy) per video
│       ├── keyframes/              # Ảnh keyframe (.jpg)
│       ├── map-keyframes/          # CSV mapping video_id → frame metadata
│       ├── media-info/             # Thông tin video gốc
│       └── objects-aic25-b1/       # Objects JSON (Faster R-CNN)
│
├── kaggle_jobs/                    # 4 job encode keyframe SOTA trên Kaggle GPU
│   ├── 01_vit_l14/                 # OpenAI CLIP ViT-L/14
│   ├── 02_siglip/                  # Google SigLIP SO400M-384
│   ├── 03_jina/                    # Jina CLIP v2
│   └── 04_dfn/                     # OpenCLIP DFN-5B ViT-H/14
│
├── queries/                        # Query mẫu/test (JSON)
│   ├── sample_queries.json
│   ├── eval_ground_truth.json      # Bộ ground truth tự chấm Phase 6 (video_id/frame_id đúng)
│   └── EVAL_GUIDE.md               # Quy trình + schema gán ground truth cho eval_ground_truth.json
│
├── submissions/                    # Output CSV/ZIP (*.zip git-ignored)
│
├── docs/                           # Tài liệu cuộc thi & training
│   ├── Thong tin vong So tuyen AIC2026.md
│   ├── Training/                   # Tóm tắt các buổi training
│   └── paper/, slide/              # Paper & slide tham khảo
│
├── .env.example                    # Template API key (chỉ placeholder, không key thật)
├── .env                            # [git-ignored] API key thật
├── requirements.txt                # Dependencies đã pin version
├── ARCHITECTURE.md                 # Thiết kế hệ thống, quyết định đã chốt
├── PLAN.md                         # Tiến độ project theo Phase
└── CLAUDE.md                       # Quy ước code cho AI assistant
```

---

## Cài đặt & Khởi chạy

### Yêu cầu

- **Python** (khuyên dùng 3.10+)
- **Dữ liệu BTC** đã giải nén vào `data/extracted/` (xem cấu trúc ở trên)
- **API key** ít nhất 1 trong 3 provider LLM (cho Q&A và TRAKE)

### 1. Cài đặt dependencies

```powershell
# Tạo virtualenv (nếu chưa có)
python -m venv .venv

# Cài đặt
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

**`requirements.txt`** hiện tại:

```
gradio==6.24.0
gradio_client==2.6.0
hf-gradio==0.4.1
numpy==2.5.2
pandas==3.0.5
pillow==12.3.0
sentence-transformers==5.7.0
torch==2.13.0+cpu
litellm==1.97.0
python-dotenv==1.2.3

# scripts/eval/ (Phase 6 — so sánh baseline embedding, không phải app sản xuất KIS/QA/TRAKE):
transformers==5.15.0
open_clip_torch==2.32.0
sentencepiece==0.2.2
```

### 2. Cấu hình API key

```powershell
# Copy template
copy .env.example .env

# Điền key thật vào .env (OPENROUTER_API_KEY)
```

Hỗ trợ nhiều key xoay vòng để né rate-limit:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
OPENROUTER_MODEL=google/gemini-2.5-flash
```

### 3. Chạy ứng dụng

```powershell
# Khởi động Gradio UI (entry point chính)
.venv\Scripts\python.exe scripts\app.py
# Mở http://127.0.0.1:7860
```

### Lệnh hữu ích khác

```powershell
# Build index standalone (kiểm tra dữ liệu)
.venv\Scripts\python.exe scripts\index.py

# Chạy pipeline từ CLI (debug)
.venv\Scripts\python.exe scripts\agent\pipeline_kis.py "<query>"

# Validate file submission mới nhất
.venv\Scripts\python.exe scripts\submit\validate_submission.py
```

---

## Sử dụng

### Gradio UI — 4 Tab

| Tab              | Chức năng                                                                                                      |
| ---------------- | ---------------------------------------------------------------------------------------------------------------- |
| **KIS**    | Nhập mô tả text → tìm keyframe bằng CLIP → gallery preview → sửa tay → add to queue                    |
| **Q&A**    | Nhập câu hỏi → pipeline tự rewrite, retrieve, trả lời (2 tầng + cross-check) → sửa tay → add to queue |
| **TRAKE**  | Nhập N mốc sự kiện → tìm top video → align frame theo thứ tự thời gian → sửa tay → add to queue     |
| **Export** | Xem hàng đợi submission → export ZIP 1-click                                                                 |

**Quy trình thao tác ngày thi:**

1. Search (nhập query ở tab tương ứng)
2. Rà soát kết quả trên bảng
3. Sửa tay nếu cần (trực tiếp trên dataframe)
4. Bấm **Add to Queue**
5. Chuyển sang tab **Export** → **Export ZIP**
6. Nộp file ZIP lên hệ thống chấm

### CLI (dùng độc lập / debug)

```python
from agent.pipeline_kis import run_kis
from agent.pipeline_qa import run_qa
from agent.pipeline_trake import run_trake

# KIS
results = run_kis("a person riding a bicycle on a bridge", top_k=100)

# Q&A
result = run_qa("what color is the car?", top_k=100)
# → {"results": [...], "answer": "red", "best_hit": {...}, "n_loops": 1, "confidence": 0.8}

# TRAKE
result = run_trake("a man walks into a store", events=["enters door", "picks up item", "pays"], top_k_video=5)
# → {"results": [...], "best": {...}, "n_events": 3}
```

---

## Pipeline chi tiết

### KIS — Known-Item Search

```
Query text → fast_retrieve(query, top_k) → ranked hits → CSV
```

- Không gọi LLM, chỉ dùng CLIP cosine similarity
- Nhanh nhất trong 3 pipeline

### Q&A — Question & Answer

```
Query → rewrite_query(VN→EN) → fast_retrieve() → answer_from_hits()
                                                       │
                                           ┌───────────┴──────────┐
                                           ▼                      ▼
                                   Objects JSON             LLM Vision
                                   (Faster R-CNN)        (Gemini/Groq/NVIDIA)
                                           └───────────┬──────────┘
                                                       ▼
                                              _crosscheck_answer()
                                                       │
                                        confidence < 0.5? ──→ rewrite + feedback → vòng 2
                                                       │
                                                       ▼
                                                  Answer + CSV
```

- Tối đa **2 vòng** reflection (`MAX_AGENT_LOOPS=2`)
- Anti-hallucination bắt buộc: mọi answer phải qua cross-check với Objects JSON

### TRAKE — Tracking Events

```
Events list → Giai đoạn 1: rewrite + retrieve → chọn top-K video
                    │
                    ▼
              Giai đoạn 2: align N mốc tuần tự trong video
              (frame_idx phải tăng dần theo world-model)
                    │
                    ▼
              frame_id sequence → CSV
```

- Pipeline 2 giai đoạn cố định, không phải agent tự do
- Ràng buộc thứ tự thời gian: frame_idx phải tăng dần

---

## Kaggle Jobs — Encode SOTA

4 job thăm dò encode 177K keyframe bằng các model SOTA trên GPU Kaggle miễn phí (không thay đổi baseline `clip-ViT-B-32` đang dùng):

| Job             | Model                    | Thư viện                     | Trạng thái                                                                                                                                 |
| --------------- | ------------------------ | ------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- |
| `01_vit_l14/` | OpenAI CLIP ViT-L/14     | `transformers`               | Chạy xong, feature đã giải nén vào`data/extracted/` ✅                                                                               |
| `02_siglip/`  | Google SigLIP SO400M-384 | `transformers`               | Chạy xong, feature đã giải nén vào`data/extracted/` ✅                                                                               |
| `03_jina/`    | Jina CLIP v2             | `transformers` (remote code) | ❌ Output`features_jina/` hỏng 100% NaN (xác nhận 2026-08-20, xem `kaggle_jobs/README.md` mục "Cập nhật 8") — cần chạy lại job |
| `04_dfn/`     | OpenCLIP DFN-5B ViT-H/14 | `open_clip_torch`            | Chạy xong, feature đã giải nén vào`data/extracted/` ✅                                                                               |

Chi tiết quy trình CLI, sự cố đã gặp & cách sửa → [`kaggle_jobs/README.md`](kaggle_jobs/README.md)

---

## LLM Provider Chain

Chuỗi fallback tự động, chuyển provider khi gặp lỗi:

```
Gemini (gemini-3.5-flash)  ──lỗi──→  Groq (llama-3.3-70b / llama-3.2-11b-vision)  ──lỗi──→  NVIDIA NIM (llama-3.3-70b / llama-3.2-90b-vision)
       ↑                                                                                               │
       └── key rotation (nhiều key xoay vòng trong cùng 1 provider) ────────────────────────────────────┘
```

- Provider thiếu API key trong `.env` → tự bị bỏ qua (không crash)
- Key sai định dạng → tự bỏ qua, thử key tiếp theo
- Chỉ ném lỗi khi **tất cả** provider/key đều thất bại

Cấu hình tại [`scripts/agent/config.py`](scripts/agent/config.py).

---

## Tài liệu liên quan

| File                                                                                              | Nội dung                                                                          |
| ------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md)                                                             | Thiết kế hệ thống, trách nhiệm từng module, quyết định đã chốt        |
| [`PLAN.md`](PLAN.md)                                                                             | Tiến độ project theo Phase (1–5), blockers & risks                             |
| [`CLAUDE.md`](CLAUDE.md)                                                                         | Quy ước code, quick start, folder convention                                     |
| [`docs/Thong tin vong So tuyen AIC2026.md`](<docs/Thong%20tin%20vong%20So%20tuyen%20AIC2026.md>) | Luật thi vòng Sơ tuyển AIC 2026                                                |
| [`docs/Training/`](docs/Training/)                                                               | Tóm tắt các buổi training (kiến trúc, Vision-Language, quy trình nộp bài) |
| [`kaggle_jobs/README.md`](kaggle_jobs/README.md)                                                 | Hướng dẫn 4 job encode SOTA trên Kaggle GPU                                    |

---

## Quy ước code

- **Ngôn ngữ comment/UI**: tiếng Việt (toàn repo)
- **Đặt tên**: `snake_case` (Python convention) — `fast_retrieve`, `run_kis`, `build_kis_csv`
- **`video_id`**: format `{batch}_{video_num}`, ví dụ `L21_V001` — không kèm `.mp4`
- **`frame_id`**: = `frame_idx + 1`, chỉ chuyển đổi tại `retrieve.py`
- **Logging**: `print()` với prefix `[module_name]` — `[retrieve]`, `[qa]`, `[trake]`
- **Lỗi**: fail loud cho lỗi setup/dữ liệu; bắt + hiển thị `⚠️` trên UI cho lỗi runtime

### KHÔNG được làm

- ❌ Gọi `litellm` trực tiếp bên ngoài `agent/config.py:call_llm()`
- ❌ Ghi CSV/ZIP ngoài `submit/build_submission.py`
- ❌ Commit `.env` hoặc đặt key thật vào `.env.example`
- ❌ Để pipeline chạy vòng lặp LLM không giới hạn (phải có trần `MAX_AGENT_LOOPS`)
- ❌ Force-push hoặc rewrite git history trên `main`

---

## Trạng thái dự án

| Phase | Mô tả                                                                              | Trạng thái |
| ----- | ------------------------------------------------------------------------------------ | ------------ |
| 1     | Nền tảng Retrieval & Submission Engine                                             | ✅ Done      |
| 2     | Agent đa phương thức cho Q&A + TRAKE                                             | ✅ Done      |
| 3     | Gradio UI Human-in-the-loop                                                          | ✅ Done      |
| 4     | Hardening trước ngày thi (code review, fix bug, git)                              | ✅ Done      |
| 5     | Sẵn sàng thi (test thật trên Codabench, checklist ngày thi)                     | ⏳ Todo      |
| 6     | Nâng cấp retrieval baseline + bộ eval tự chấm (song song, không chặn Phase 5) | ⏳ Todo      |

Chi tiết từng Phase → [`PLAN.md`](PLAN.md)

---

## License

Dự án phục vụ mục đích thi AIC 2026. Không phân phối thương mại.
