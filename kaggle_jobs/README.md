# kaggle_jobs/ — 4 job encode keyframe SOTA trên Kaggle GPU

> **Quy ước khi Claude sửa code trong thư mục này**: Claude **không tự push job GPU thật** lên
> Kaggle (job 01/02/03/04) — chỉ sửa file cục bộ, compile-check, và nếu cần chẩn đoán thì dùng
> [`kaggle_jobs/_diag/`](_diag/) (không tốn GPU đáng kể). Sau khi sửa xong, Claude phải:
> 1. Báo rõ đã đổi gì + đã kiểm chứng tới đâu (chạy thật hay chỉ sửa theo lý thuyết).
> 2. Hỏi bạn muốn chạy bằng GPU nào trước khi bạn tự set `machine_shape` và tự push/chạy thật:
>    `"None"` (mặc định, Kaggle tự chọn — từng ra P100 và lỗi), `"NvidiaTeslaT4"` (khuyên dùng,
>    xem mục "Sự cố đã gặp"), `"NvidiaTeslaP100"`, hoặc `"Tpu1VmV38"` (TPU, cần đổi code khác).
> Bạn tự sửa `machine_shape` trong `kernel-metadata.json` tương ứng rồi tự chạy lệnh push ở mục
> "Quy trình CLI" bên dưới.

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

## Cập nhật 2 (2026-08-19, sau khi chạy lại đợt 1)

Log đợt 2 (`aic2026-encode-01-vit-l14.log`, `aic2026-encode-02-siglip-so400m.log`) xác nhận 3 lỗi
ở mục trên đã hết thật: path mount đúng, GPU chạy T4 (không còn cảnh báo P100), tìm đúng 873
video. Log gốc đợt 1 (`Log1–4.txt`) đã chuyển vào
[`_archive_logs_20260819_first_run/`](_archive_logs_20260819_first_run/) để khỏi lẫn.

5. **`AttributeError: 'BaseModelOutputWithPooling' object has no attribute 'float'`** (job 01 và
   02, lỗi giống hệt nhau) — cả 2 job cài `transformers` bằng `pip install -U` (không pin version),
   và bản mới nhất kéo về tại thời điểm chạy đã đổi hành vi `get_image_features()`: trả thẳng
   ModelOutput thô của vision encoder (`BaseModelOutputWithPooling`, CHƯA qua pooling+projection)
   thay vì tensor cuối như trước. Đã sửa bằng hàm `_get_image_embeds()` mới trong cả 2
   `main.py` — không đoán API mới của `transformers`, mà tự lấy lại đúng tensor qua
   `vision_model` + `visual_projection` (2 submodule public ổn định của `CLIPModel`; `SiglipModel`
   không có `visual_projection` riêng nên chỉ lấy `pooler_output`), có kiểm tra `shape` để
   fail loud nếu vẫn sai. **Chưa chạy lại thật để xác nhận hết lỗi** — đây là fix theo phân tích
   traceback + cấu trúc model, giống trường hợp job 03 (Jina) ở mục 3 phía trên.

Job 04 (DFN) — chưa có log đợt 2, vẫn ở trạng thái "đã sửa theo lý thuyết, chưa chạy lại để xác
nhận" tính đến thời điểm này.

## Cập nhật 3 (2026-08-19, job 03 chạy lại lần 2)

Log job 03 (`aic2026-encode-03-jina-clip-v2.log`) xác nhận lỗi `torch_dtype` ở mục 3 đã hết thật
(chỉ còn warning "deprecated", không còn crash). Lỗi mới xuất hiện ngay sau đó:

6. **`ImportError: cannot import name 'clip_loss' from 'transformers.models.clip.modeling_clip'`**
   — code tuỳ biến của jina-clip-v2 (`trust_remote_code=True`) làm
   `from transformers.models.clip.modeling_clip import (CLIPOutput, CLIPTextModelOutput,
   CLIPVisionModelOutput, clip_loss)`; bản `transformers` mới nhất (cùng nguyên nhân gốc với mục
   5 — cài bằng `-U` không pin version) đã bỏ hàm nội bộ `clip_loss` (3 tên kia vẫn còn, đã xác
   nhận qua WebFetch source thật của Jina trên HuggingFace). `clip_loss` chỉ dùng để tính loss lúc
   **huấn luyện** (`return_loss=True`), pipeline này chỉ gọi `encode_image()` nên không bao giờ
   chạy tới nhánh đó — đã sửa bằng `_patch_missing_clip_loss()` trong `03_jina/main.py`: tự "vá"
   lại đúng tên hàm (công thức gốc ổn định nhiều năm của CLIP) vào module trước khi Jina import,
   thay vì pin version `transformers` (rủi ro hơn vì 4 file custom khác của Jina —
   `transform.py`/`rope_embeddings.py`/`eva_model.py`/`hf_model.py` — cũng vừa được tải bản mới,
   có thể cần transformers mới). **Chưa chạy lại thật để xác nhận hết lỗi.**

## Cập nhật 4 (2026-08-20, job 01 chạy lại — lộ bug do chính fix trước gây ra)

Log job 01 (`aic2026-encode-01-vit-l14.log`) cho thấy tiến thêm 1 bước: path/GPU/873 video vẫn
đúng, và lỗi `BaseModelOutputWithPooling` (mục 5) **đã hết** — nhưng crash tiếp ngay sau đó bằng
1 lỗi **do chính `_get_image_embeds()` ở mục 5 gây ra** (không phải lỗi mới từ Kaggle/transformers):

```
RuntimeError: mat1 and mat2 shapes cannot be multiplied (64x768 and 1024x768)
```

7. **Double-projection trong `_get_image_embeds()`** — bản vá ở mục 5 lấy `pooled` ưu tiên từ
   `out.image_embeds` nếu có, NHƯNG dòng cuối vẫn áp `model.visual_projection(pooled)` **vô điều
   kiện** bất kể `pooled` lấy từ nhánh nào. Trường hợp thật: `out.image_embeds` tồn tại và ĐÃ qua
   projection (768 chiều) — bị chiếu thêm 1 lần qua `Linear(1024→768)` → sai shape ngay. Đã sửa
   trong `01_vit_l14/main.py`: chỉ áp `visual_projection` khi phải fallback về `pooler_output`
   THÔ (1024 chiều, trước projection); nếu đã có `image_embeds` thì trả thẳng, không chiếu lại.
   Đồng thời thêm kiểm tra `out.shape[-1] == model.config.projection_dim` (768) vào
   `encode_video()` để lần sau nếu còn sai chiều sẽ fail loud ngay, không âm thầm ra embedding sai
   không gian. Job 02 (SigLIP) KHÔNG dính bug này vì `_get_image_embeds()` của nó không áp thêm
   projection nào (SigLIP không có `visual_projection` riêng) — không cần sửa. **Chưa chạy lại
   thật để xác nhận hết lỗi.**

## Cập nhật 5 (2026-08-20, job 01 chạy lại lần 3 — mục 7 sửa vẫn sai, đổi chiến lược)

Log job 01 chạy lại **crash y hệt lỗi ở mục 7** (`RuntimeError: mat1 and mat2 shapes cannot be
multiplied (64x768 and 1024x768)`), cùng dòng code. Bản sửa ở mục 7 đoán sai giả định: tưởng
`pooler_output` luôn là 1024 chiều THÔ (trước projection) nên vẫn áp `visual_projection()` — bản
`transformers` chạy thật lại trả `pooler_output` **đã là 768 chiều** (không đúng giả định đó) nên
vẫn bị double-projection. Đây là lần đoán sai thứ 2 liên tiếp về cấu trúc `ModelOutput` — không
đoán field nào ứng với giai đoạn xử lý nào nữa.

**Đổi chiến lược trong `_get_image_embeds()`**: dựa hoàn toàn vào **shape thật lúc runtime**
thay vì giả định API — chỉ áp `visual_projection` khi `candidate.shape[-1] != model.config.projection_dim`
(768); nếu đã khớp thì dùng thẳng, không quan tâm field đó tên gì/lấy từ đâu. Đồng thời thêm dump
debug 1 lần đầu (`type(out).__name__` + shape từng field) ra log — nếu lần này vẫn còn sai kiểu
gì khác, log sẽ có dữ liệu thật để sửa đúng ngay lần đầu thay vì đoán tiếp. **Chưa chạy lại thật để
xác nhận.**

## Cập nhật 6 (2026-08-20, pin version + chế độ smoke-test cho cả 4 job)

Cả mục 5 và mục 6 ở trên đều bắt nguồn từ 1 nguyên nhân gốc: `_pip_install(..., "-U")` không pin
version, mỗi lần push kéo bản `transformers` MỚI NHẤT tại thời điểm đó — môi trường không ổn định
giữa các lần chạy. Đã xác nhận qua PyPI thật (không đoán): **`transformers` đã lên major version
5.x** (đây chính là nguồn gốc đổi hành vi `get_image_features()` + bỏ `clip_loss`); bản 4.x ổn
định cuối cùng là **`4.57.3`** (phát hành 2025-11-25). `open_clip_torch` (job 04) cũng vừa nhảy
2.x → 3.x; bản 2.x cuối là **`2.32.0`** (2025-04-05).

**Đã sửa cả 4 job:**
- Bỏ `-U`, pin cứng `transformers==4.57.3` (job 01/02/03) và `open_clip_torch==2.32.0` (job 04) —
  chặn đứng cả nhóm lỗi do thư viện đổi hành vi giữa các lần push. Vẫn giữ nguyên các bản vá phòng
  hờ đã viết trước đó (`_get_image_embeds()`, `_patch_missing_clip_loss()`) — không hại gì nếu
  4.57.3 đã đúng như kỳ vọng, chỉ là lớp an toàn thêm.
- Thêm **chế độ `SMOKE_TEST`**: đổi hằng số `SMOKE_TEST = True` ở đầu mỗi `main.py` rồi push để
  chạy thử nhanh (chỉ `SMOKE_TEST_NUM_VIDEOS=2` video đầu, mỗi video `SMOKE_TEST_NUM_IMAGES=4`
  ảnh đầu) thay vì đợi full 873 video — phát hiện lỗi logic (như bug double-projection ở mục 7)
  trong ~1-2 phút GPU thay vì ~10 phút. Ghi ra file RIÊNG (tiền tố `features_smoketest_<tag>`),
  KHÔNG đụng tới output thật/không làm hỏng cơ chế resume của lần chạy full sau. Nhớ đổi lại
  `SMOKE_TEST = False` trước khi chạy thật (mặc định đã là `False`).

Compile sạch cả 4 file. **Chưa chạy lại thật để xác nhận** — khuyên bạn bật `SMOKE_TEST = True`
chạy thử job 01 trước (đang có bug double-projection cần xác nhận hết chưa) trước khi chạy full.

## Cập nhật 7 (2026-08-20, smoke-test job 01 PASS — bug double-projection hết thật)

Chạy `SMOKE_TEST = True` cho job 01: **PASS** — 2 video x 4 ảnh encode xong, không crash, in
"XONG". Đáng chú ý: dòng debug dump trong `_get_image_embeds()` (in cấu trúc `ModelOutput` khi
`get_image_features()` không trả thẳng Tensor) **không xuất hiện** trong log — nghĩa là với
`transformers==4.57.3` (pin ở mục "Cập nhật 6"), `get_image_features()` đã trả thẳng
`torch.Tensor` như hành vi gốc, không còn rơi vào nhánh `ModelOutput` gây lỗi double-projection ở
mục 5/7 nữa. Xác nhận: **pin version đã sửa tận gốc chuỗi lỗi `BaseModelOutputWithPooling` +
double-projection**, các bản vá phòng hờ (`_get_image_embeds()` shape-based) giờ chỉ còn là lớp an
toàn dự phòng, không thực sự được dùng tới nữa với bản 4.57.3.

Đã tắt lại `SMOKE_TEST = False` trong `01_vit_l14/main.py` — sẵn sàng push chạy thật.
