---
name: kaggle-jobs
description: >-
  Quy trình quản lý 4 Kaggle GPU encoding job (ViT-L/14, SigLIP, Jina CLIP v2,
  DFN-5B): push/check/download, sự cố đã gặp & cách sửa, smoke-test, lưu ý
  khi chạy thật. Dùng khi debug Kaggle job, push job mới, hoặc tải kết quả
  embedding SOTA.
---

# Kaggle GPU Encoding Jobs

4 job độc lập, mỗi job encode 177K keyframe (873 video) bằng 1 model embedding khác nhau trên GPU
Kaggle miễn phí. Đây là **thăm dò/ensemble** — không thay đổi baseline `clip-ViT-B-32`.

| Job | Model | Thư viện | Pin version |
|-----|-------|----------|-------------|
| `01_vit_l14/` | OpenAI CLIP ViT-L/14 | `transformers==4.57.3` | ✅ |
| `02_siglip/` | Google SigLIP SO400M-384 | `transformers==4.57.3` | ✅ |
| `03_jina/` | Jina CLIP v2 | `transformers==4.57.3` | ✅ |
| `04_dfn/` | OpenCLIP DFN-5B ViT-H/14 | `open_clip_torch==2.32.0` | ✅ |

## Quy trình CLI

**Giới hạn**: Kaggle miễn phí cho tối đa **2 GPU session song song**.

### 1. Push job (đợt 1: job 01 & 02)
```powershell
.\.venv\Scripts\kaggle.exe kernels push -p kaggle_jobs/01_vit_l14
.\.venv\Scripts\kaggle.exe kernels push -p kaggle_jobs/02_siglip
```
Khi xong, push đợt 2:
```powershell
.\.venv\Scripts\kaggle.exe kernels push -p kaggle_jobs/03_jina
.\.venv\Scripts\kaggle.exe kernels push -p kaggle_jobs/04_dfn
```

### 2. Theo dõi
```powershell
.\.venv\Scripts\kaggle.exe kernels status vngiabnhnguyn/aic2026-encode-01-vit-l14
.\.venv\Scripts\kaggle.exe kernels status vngiabnhnguyn/aic2026-encode-02-siglip-so400m
.\.venv\Scripts\kaggle.exe kernels status vngiabnhnguyn/aic2026-encode-03-jina-clip-v2
.\.venv\Scripts\kaggle.exe kernels status vngiabnhnguyn/aic2026-encode-04-dfn5b-vit-h14
```

### 3. Tải kết quả
```powershell
.\.venv\Scripts\kaggle.exe kernels output vngiabnhnguyn/aic2026-encode-01-vit-l14      -p data/extracted/features_vitl14
.\.venv\Scripts\kaggle.exe kernels output vngiabnhnguyn/aic2026-encode-02-siglip-so400m -p data/extracted/features_siglip
.\.venv\Scripts\kaggle.exe kernels output vngiabnhnguyn/aic2026-encode-03-jina-clip-v2  -p data/extracted/features_jina
.\.venv\Scripts\kaggle.exe kernels output vngiabnhnguyn/aic2026-encode-04-dfn5b-vit-h14 -p data/extracted/features_dfn
```

## Smoke-test

Mỗi `main.py` có hằng số `SMOKE_TEST` ở đầu file:
- `SMOKE_TEST = True` → chạy 2 video × 4 ảnh (~1-2 phút GPU), output prefix `features_smoketest_*`
- `SMOKE_TEST = False` (default) → chạy full 873 video

**Luôn smoke-test trước khi chạy full** để phát hiện lỗi logic nhanh, tiết kiệm quota.

## Sự cố đã gặp & bài học

| # | Lỗi | Nguyên nhân | Giải pháp |
|---|------|-------------|-----------|
| 1 | Path mount sai | Kaggle thêm `datasets/<owner>/` vào path | `resolve_keyframes_root()` tự dò |
| 2 | GPU P100 crash | PyTorch cu128 cần sm_70+, P100 là sm_60 | Ép `NvidiaTeslaT4` trong metadata |
| 3 | Jina `torch_dtype` TypeError | Code tuỳ biến cần string, không phải object | Truyền `"float16"` thay vì `torch.float16` |
| 4 | Slug kernel lệch | `id` local ≠ slug trên Kaggle | Đồng bộ lại `kernel-metadata.json` |
| 5-7 | `transformers` 5.x breaking changes | `pip install -U` kéo major version mới | **Pin `transformers==4.57.3`** |

**Bài học lớn nhất**: Luôn pin version thư viện ML — không bao giờ dùng `-U` không pin trên
Kaggle/cloud, major version mới có thể đổi API bất kỳ lúc nào.

## Lưu ý

- Dataset `kiet1106/aic26-frames` không do mình sở hữu — nếu bị đổi tên/xoá thì cần đổi
  `FRAMES_DATASET_REF` + `dataset_sources`
- Job 03/04 tải weight vài GB lần đầu — vài phút đầu log đứng yên là bình thường
- Claude/Antigravity **không tự push job GPU thật** — chỉ sửa file cục bộ, người dùng tự push
