# scripts/preprocess/

Các script **tiền xử lý ngoại tuyến** (offline preprocessing) — chạy **trước** pipeline truy vấn realtime.
Chia thành 3 nhóm con độc lập theo loại dữ liệu xử lý.

---

## Cấu trúc

\scripts/preprocess/
├── captions/          # Sinh & gộp caption Vintern-1B cho keyframe
├── ocr/               # Chạy & gộp OCR (PaddleOCR + VietOCR) cho keyframe
└── shards/            # Quản lý hạ tầng shard (Kaggle / Colab)
\
---

## 📹 captions/ — Caption Vintern-1B

Sinh mô tả ngắn (1 câu tiếng Việt) cho từng keyframe đã lọc, dùng model **Vintern-1B-v3.5**.

| File | Mục đích |
|------|----------|
| \uild_caption_manifest.py\ | Lọc keyframe theo Semantic Similarity (τ=0.72, gap≤25s) + phân 3 shard bằng Greedy Bin-Packing |
| un_caption_shard_local.py\ | Chạy Vintern-1B trên **GPU local** thay cho Kaggle (hỗ trợ resume) |
| \merge_captions.py\ | Gộp output 3 shard Kaggle → \data/extracted/caption_vintern1b/\ + sanity check |

**Thứ tự chạy:**
\\powershell
# 1. Sinh manifest phân shard (cần data/features_siglip2 + data/map-keyframes)
.venv\Scripts\python.exe scripts\preprocess\captions\build_caption_manifest.py

# 2a. Đẩy lên Kaggle (xem shards/)
# 2b. Hoặc chạy local (cần torch CUDA + transformers==4.57.3)
.venv\Scripts\python.exe scripts\preprocess\captions\run_caption_shard_local.py --shard 0

# 3. Sau khi tải output về, gộp lại
.venv\Scripts\python.exe scripts\preprocess\captions\merge_captions.py
\
---

## 🔤 ocr/ — OCR PaddleOCR + VietOCR

Trích xuất văn bản từ **toàn bộ** keyframe (không lọc như caption), dùng pipeline hybrid
**PaddleOCR** (detection) + **VietOCR** (recognition tiếng Việt).

| File | Mục đích |
|------|----------|
| un_ocr_shard_local.py\ | Backup: chạy OCR trên **GPU local** khi Colab hết giờ (resume-safe) |
| \merge_ocr.py\ | Gộp output 3 shard Colab → \data/extracted/ocr_text_paddleocr/\ + sanity check |
| \index_ocr_es.py\ | Đẩy OCR + caption vào **Elasticsearch** (3 chế độ: live / from-jsonl / split) |

**Thứ tự chạy:**
\\powershell
# 1. Chạy OCR trên Colab (xem shards/setup_colab_shards.py) — hoặc backup local:
.venv\Scripts\python.exe scripts\preprocess\ocr\run_ocr_shard_local.py --shard 0

# 2. Gộp kết quả 3 shard về
.venv\Scripts\python.exe scripts\preprocess\ocr\merge_ocr.py

# 3. Index vào Elasticsearch (chế độ 3 — đường dùng thật hiện tại)
.venv\Scripts\python.exe scripts\preprocess\ocr\index_ocr_es.py     --ocr-jsonl-dir data\extracted\ocr_text_paddleocr     --caption-jsonl-dir data\extracted\caption_vintern1b
\
---

## ⚙️ shards/ — Quản lý hạ tầng shard

Sinh notebook / script cho Kaggle & Colab, push/pull job, kiểm tra trạng thái.

| File | Mục đích |
|------|----------|
| \setup_kaggle_shards.py\ | Sinh 3 thư mục \kaggle_jobs/07_vintern_caption_shard{N}/\ (caption) |
| \setup_colab_shards.py\ | Sinh 3 notebook \colab_jobs/06_paddleocr_vietocr_shard{N}/\ (OCR) |
| \undle_shards_self_contained.py\ | Nhúng manifest vào \main.py\ (tránh lỗi 409 Kaggle API) |
| \push_all_shards.py\ | Push 3 shard caption lên Kaggle qua CLI |
| \check_shards_status.py\ | Kiểm tra trạng thái các Kaggle kernel job |
| \download_all_shards.py\ | Tải output 3 shard caption từ Kaggle về |
| \generate_sotuyen1_csv.py\ | Sinh CSV từ bộ đề thi SOTUYEN1 (dữ liệu test) |

**Thứ tự chạy (Kaggle caption):**
\\powershell
.venv\Scripts\python.exe scripts\preprocess\shards\setup_kaggle_shards.py
.venv\Scripts\python.exe scripts\preprocess\shards\bundle_shards_self_contained.py
.venv\Scripts\python.exe scripts\preprocess\shards\push_all_shards.py
.venv\Scripts\python.exe scripts\preprocess\shards\check_shards_status.py
.venv\Scripts\python.exe scripts\preprocess\shards\download_all_shards.py
\
---

## Ghi chú

- Tất cả script đều dùng \ROOT = Path(__file__).resolve().parent.parent.parent.parent  để trỏ về thư mục gốc repo — **không cần \cd\** trước khi chạy.
- Output dữ liệu nằm dưới \data/\ (git-ignored) — xem [\GEMINI.md\](../../GEMINI.md) để biết quy ước.
- Dependency nặng (torch CUDA, paddleocr, vietocr) **không có trong equirements.txt\**;
  xem docstring từng file để cài thêm khi cần.
