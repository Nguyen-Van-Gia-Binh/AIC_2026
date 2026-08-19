# kaggle_jobs/ — 4 job encode keyframe SOTA trên Kaggle GPU

4 job độc lập, mỗi job encode toàn bộ 177.321 keyframe (873 video) bằng 1 model embedding khác
nhau, chạy trên GPU miễn phí của Kaggle qua `kaggle kernels push` (không cần bấm tay trên web).
Đây là các job **thăm dò/ensemble bên ngoài pipeline chính** — không thay đổi baseline
`clip-ViT-B-32` mà `scripts/index.py` đang dùng.

| Thư mục         | Model                          | Thư viện                    | Output prefix     |
|-----------------|---------------------------------|------------------------------|--------------------|
| `01_vit_l14/`   | OpenAI CLIP ViT-L/14            | `transformers`               | `features_vitl14`  |
| `02_siglip/`    | Google SigLIP SO400M-384        | `transformers`                | `features_siglip`  |
| `03_jina/`      | Jina CLIP v2                    | `transformers` (remote code) | `features_jina`     |
| `04_dfn/`       | OpenCLIP DFN-5B ViT-H/14        | `open_clip_torch`            | `features_dfn`      |

Mỗi job đọc keyframe từ dataset Kaggle `kiet1106/aic26-frames` (cấu trúc
`keyframes/{batch}/{video_id}/{n:03d}.jpg`, khớp đúng quy ước `video_id`/`n` của repo chính — xem
`data/extracted/map-keyframes/{video_id}.csv`), rồi ghi ra `/kaggle/working/`:

- `features_<tag>/{video_id}.npy` — `(num_keyframes, D)` float16, đã L2-normalize, thứ tự `n` tăng
  dần (khớp convention `data/extracted/clip-features-32/` của `scripts/index.py`).
- `manifest_<tag>.csv` — cột `video_id, n, jpg` để đối chiếu thứ tự khi merge về sau.
- `features_<tag>.zip` — nén toàn bộ output, tự tạo cuối mỗi lần chạy.

Chi tiết cơ chế resume, batching, GPU-optim: xem docstring đầu mỗi `main.py` (đầy đủ nhất ở
`01_vit_l14/main.py`, 3 file kia chỉ ghi phần khác biệt).

## Quy trình CLI (Windows PowerShell & Bash)

Chạy từ thư mục gốc repo. Lệnh CLI nằm trong virtualenv: `.\.venv\Scripts\kaggle.exe` (Windows) hoặc `kaggle` (Linux/Mac).

> [!NOTE]
> **Giới hạn Kaggle**: Tài khoản miễn phí cho phép chạy tối đa **2 GPU session song song** cùng lúc (`Maximum batch GPU session count of 2`). 
> Vì vậy, ta chạy Job 01 & Job 02 trước. Khi Job 01/02 hoàn tất, ta đẩy tiếp Job 03 & Job 04 (hoặc gửi code cho đồng đội chạy song song).

### 1. Đẩy các job lên Kaggle (Đợt 1: Job 01 & 02)

```powershell
.\.venv\Scripts\kaggle.exe kernels push -p kaggle_jobs/01_vit_l14
.\.venv\Scripts\kaggle.exe kernels push -p kaggle_jobs/02_siglip
```

*(Khi Job 01 hoặc 02 hoàn thành, đẩy tiếp Đợt 2:)*
```powershell
.\.venv\Scripts\kaggle.exe kernels push -p kaggle_jobs/03_jina
.\.venv\Scripts\kaggle.exe kernels push -p kaggle_jobs/04_dfn
```

### 2. Theo dõi tiến độ

Link theo dõi trực tiếp trên web:
- **Job 01 (ViT-L/14)**: https://www.kaggle.com/code/vngiabnhnguyn/aic2026-encode-01-vit-l14
- **Job 02 (SigLIP)**: https://www.kaggle.com/code/vngiabnhnguyn/aic2026-encode-02-siglip-so400m
- **Job 03 (Jina CLIP v2)**: https://www.kaggle.com/code/vngiabnhnguyn/aic2026-encode-03-jina-clip-v2
- **Job 04 (DFN-5B)**: https://www.kaggle.com/code/vngiabnhnguyn/aic2026-encode-04-dfn5b-vit-h14

Hoặc kiểm tra qua Terminal:

```powershell
.\.venv\Scripts\kaggle.exe kernels status vngiabnhnguyn/aic2026-encode-01-vit-l14
.\.venv\Scripts\kaggle.exe kernels status vngiabnhnguyn/aic2026-encode-02-siglip-so400m
.\.venv\Scripts\kaggle.exe kernels status vngiabnhnguyn/aic2026-encode-03-jina-clip-v2
.\.venv\Scripts\kaggle.exe kernels status vngiabnhnguyn/aic2026-encode-04-dfn5b-vit-h14
```

### 3. Tải kết quả (zip) về máy khi hoàn thành

```powershell
.\.venv\Scripts\kaggle.exe kernels output vngiabnhnguyn/aic2026-encode-01-vit-l14      -p data/extracted/features_vitl14
.\.venv\Scripts\kaggle.exe kernels output vngiabnhnguyn/aic2026-encode-02-siglip-so400m -p data/extracted/features_siglip
.\.venv\Scripts\kaggle.exe kernels output vngiabnhnguyn/aic2026-encode-03-jina-clip-v2  -p data/extracted/features_jina
.\.venv\Scripts\kaggle.exe kernels output vngiabnhnguyn/aic2026-encode-04-dfn5b-vit-h14 -p data/extracted/features_dfn
```

Lệnh này tải toàn bộ file trong `/kaggle/working/` của mỗi kernel (gồm `features_<tag>.zip` + log) về máy local.

## Lưu ý trước khi chạy thật

- Dataset `kiet1106/aic26-frames` không phải do bạn sở hữu — nếu bị đổi tên/xoá quyền truy cập,
  cả 4 job sẽ lỗi ngay ở bước `list_videos()`. Đổi `FRAMES_DATASET_REF` + `dataset_sources`
  trong từng file nếu bạn chuyển sang dataset keyframes khác (ví dụ ghép từ
  `akiyanguyen/aic2026-keyframes-l2X` hoặc `vnhtbo/aic2026-infoshootpp-keyframes-*`).
- Job 3 (Jina CLIP v2) và job 4 (DFN-5B) tải weight model vài GB lúc chạy lần đầu (`enable_internet`
  phải bật, đã bật sẵn) — vài phút đầu log sẽ đứng ở bước tải weight, không phải bị treo.
- Resume qua nhiều lần push riêng biệt cần thao tác tay (tải zip → `kaggle datasets create` →
  thêm vào `dataset_sources` → push lại) — xem chi tiết trong docstring `main.py`. Nếu 1 job chạy
  xong trong 1 phiên (nhiều khả năng, vì mỗi model ước tính dưới vài giờ trên GPU Kaggle với
  177K ảnh) thì không cần bước này.

## Sự cố đã gặp & đã sửa (2026-08-19)

Lần chạy đầu tiên: job 01/02/04 lỗi ngay ở `list_videos()`, job 03 lỗi ở `load_model()`. Log gốc
(`Log1.txt`–`Log4.txt`) giữ lại trong thư mục này để đối chiếu. Đã xác nhận bằng
[`kaggle_jobs/_diag/`](_diag/) (kernel chẩn đoán nhỏ, không tốn GPU quota đáng kể) rồi sửa:

1. **Path mount sai** — cả 4 job hard-code `/kaggle/input/aic26-frames/keyframes/...`, nhưng Kaggle
   thực tế mount ở `/kaggle/input/datasets/kiet1106/aic26-frames/keyframes/...` (thêm tiền tố
   `datasets/<owner>/`). Không rõ đây là quy ước mới cố định hay ngẫu nhiên theo phiên, nên đã sửa
   `main.py` để **tự dò** (`resolve_keyframes_root()`): thử path cũ → thử path mới → fallback rglob
   toàn `/kaggle/input`. Nếu Kaggle đổi quy ước lần nữa, chạy lại `kaggle_jobs/_diag/` để xem cấu
   trúc thật thay vì đoán.
2. **GPU P100 không chạy được** — Kaggle mặc định (không set `machine_shape`) đã gán **Tesla P100**
   cho cả 4 job, nhưng bản PyTorch cài sẵn trên image hiện tại (2.10.0+cu128) chỉ hỗ trợ compute
   capability sm_70 trở lên — P100 là sm_60 (Pascal) nên **mọi phép tính CUDA đều lỗi**
   (`CUDA error: no kernel image is available for execution on the device`), đã xác nhận thật bằng
   phép nhân ma trận trong `_diag/`. Đã thêm `"machine_shape": "NvidiaTeslaT4"` vào cả 4
   `kernel-metadata.json` để ép chọn GPU T4 (sm_75, tương thích) thay vì để Kaggle tự chọn — đã test
   lại và chạy được (xem `_diag/`). Giá trị hợp lệ khác: `NvidiaTeslaP100`, `Tpu1VmV38`.
3. **Jina CLIP v2 (job 03) — `TypeError: attribute name must be string, not 'torch.dtype'`** —
   `configuration_clip.py` tuỳ biến (`trust_remote_code=True`) của model này làm
   `hasattr(torch, torch_dtype)`, nghĩa là `torch_dtype` phải truyền vào dạng **string** (`"float16"`)
   chứ không phải object `torch.float16` như 3 job kia dùng được bình thường qua `transformers`
   chuẩn. Đã sửa trong `load_model()` của `03_jina/main.py`.
4. **Slug kernel trên Kaggle lệch với `id` cục bộ** — 4 kernel đã push đổi sang slug có gạch nối
   (`aic2026-encode-01-vit-l14`, `...-02-siglip-so400m`, `...-03-jina-clip-v2`,
   `...-04-dfn5b-vit-h14`) — đã đồng bộ lại field `id` trong 4 `kernel-metadata.json` cho khớp, để
   lần push tiếp theo cập nhật ĐÚNG kernel đã chạy (không tạo kernel trùng ở slug cũ).

Sau khi sửa cả 4 điểm trên, push lại cả 4 job theo lệnh ở mục 1 phía trên.
