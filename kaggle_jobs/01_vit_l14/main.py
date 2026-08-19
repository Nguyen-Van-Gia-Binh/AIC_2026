"""
Kaggle GPU job — encode toàn bộ keyframe AIC2026 bằng OpenAI CLIP ViT-L/14 (qua HuggingFace
transformers). Đây là 1 trong 4 job encode SOTA (xem kaggle_jobs/README.md) — job này không
đụng vào baseline clip-ViT-B-32 hiện có trong scripts/index.py, chỉ tạo thêm 1 bộ embedding
song song để sau này ensemble/so sánh.

Input dataset (dataset_sources trong kernel-metadata.json): kiet1106/aic26-frames
  -> nội dung là keyframes/{batch}/{video_id}/{n:03d}.jpg (batch ví dụ "L21", video_id ví dụ
  "L21_V001", n khớp đúng cột "n" trong data/extracted/map-keyframes/{video_id}.csv của repo
  chính — KHÔNG phải frame_id, việc quy đổi frame_id = frame_idx + 1 vẫn chỉ làm ở
  scripts/agent/tools/retrieve.py như CLAUDE.md quy định).
  LƯU Ý (phát hiện 2026-08-19 qua kaggle_jobs/_diag/): Kaggle mount dataset KHÔNG cố định 1 quy
  ước — có lúc là /kaggle/input/<slug>/..., có lúc là /kaggle/input/datasets/<owner>/<slug>/...
  (đã đổi ít nhất 1 lần, khiến bản đầu của job này hard-code sai path và crash ngay ở
  list_videos()). Vì vậy KHÔNG hard-code INPUT_ROOT — resolve_keyframes_root() bên dưới tự dò cả
  2 quy ước, fallback rglob nếu cả 2 đều sai.

Output (trong /kaggle/working/, tải về bằng `kaggle kernels output`):
  features_vitl14/{video_id}.npy  -> (num_keyframes, D) float16, đã L2-normalize, thứ tự n tăng dần
                                      (khớp đúng convention của data/extracted/clip-features-32
                                      trong scripts/index.py -> có thể ghép trực tiếp sau này)
  manifest_vitl14.csv             -> video_id, n, jpg (đường dẫn tương đối) để đối chiếu thứ tự
  features_vitl14.zip             -> nén toàn bộ 2 thứ trên, tải về 1 file duy nhất

Resume: nếu output/{video_id}.npy đã tồn tại thì bỏ qua video đó. Để resume qua NHIỀU lần
`kaggle kernels push` riêng biệt (mỗi lần push là container sạch, /kaggle/working KHÔNG giữ lại):
  1. Tải features_vitl14.zip của lần chạy trước về máy (`kaggle kernels output ...`)
  2. Upload lại làm 1 Kaggle dataset mới (`kaggle datasets create -p <thư mục giải nén>`)
  3. Thêm dataset đó vào "dataset_sources" trong kernel-metadata.json rồi push lại
  Script này tự quét MỌI dataset input khác ngoài aic26-frames để tìm .npy có sẵn và copy vào
  output trước khi chạy — không cần sửa code, chỉ cần sửa kernel-metadata.json.
"""

import os
import sys
import time
import shutil
import subprocess
import zipfile
from pathlib import Path

# ── cài thêm dependency (image Kaggle có sẵn torch/transformers nhưng có thể là bản cũ) ──
def _pip_install(*pkgs):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *pkgs], check=True)


# PIN CỨNG transformers==4.57.3 (phát hành 2025-11-25, bản 4.x ổn định cuối cùng — xác nhận thật
# qua PyPI 2026-08-20, KHÔNG đoán). Trước đây cài "-U" (luôn kéo bản mới nhất) đã dính liên tiếp 2
# lỗi vì transformers lên major version 5.x (đổi hành vi get_image_features(), bỏ hàm nội bộ
# clip_loss — xem kaggle_jobs/README.md mục "Cập nhật 2/3"). Pin về 4.x để môi trường ổn định
# giữa các lần push, không còn bất ngờ giữa chừng. Vẫn giữ _get_image_embeds() phòng hờ bên dưới
# (không hại gì nếu 4.57.3 đã trả đúng tensor như kỳ vọng).
_pip_install("transformers==4.57.3", "pillow", "accelerate")

import torch
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import numpy as np
import pandas as pd
from PIL import Image
from transformers import CLIPModel

MODEL_ID = "openai/clip-vit-large-patch14"
TAG = "vitl14"

# ── CHẾ ĐỘ SMOKE-TEST: đổi SMOKE_TEST = True rồi push để chạy thử nhanh (vài phút GPU, không tốn
# nhiều quota) trước khi chạy full 873 video — chỉ encode SMOKE_TEST_NUM_VIDEOS video đầu tìm
# thấy, mỗi video chỉ lấy SMOKE_TEST_NUM_IMAGES ảnh đầu. Ghi ra file RIÊNG (tiền tố "smoketest_")
# để không đụng tới output thật và không làm hỏng cơ chế resume của lần chạy full sau này (nếu
# ghi chung, lần full sau sẽ tưởng 2 video đó đã xong dù chỉ mới encode vài ảnh). Nhớ đổi lại
# False + push lại trước khi chạy thật.
SMOKE_TEST = False  # đã smoke-test PASS 2026-08-20 (xem README "Cập nhật 7") — sẵn sàng chạy thật
SMOKE_TEST_NUM_VIDEOS = 2
SMOKE_TEST_NUM_IMAGES = 4

FRAMES_DATASET_REF = "kiet1106/aic26-frames"  # "owner/slug" trong dataset_sources — đổi nếu dùng dataset khác
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
_RUN_TAG = f"smoketest_{TAG}" if SMOKE_TEST else TAG
OUTPUT_DIR = Path(f"/kaggle/working/features_{_RUN_TAG}")
MANIFEST_PATH = Path(f"/kaggle/working/manifest_{_RUN_TAG}.csv")
ZIP_PATH = Path(f"/kaggle/working/features_{_RUN_TAG}.zip")

BATCH_SIZE = 64
NUM_WORKERS = 4
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# tiền xử lý ảnh chuẩn của OpenAI CLIP (giống hệt CLIPImageProcessor mặc định của model này,
# viết lại bằng torchvision để chạy song song trong DataLoader worker cho nhanh)
PREPROCESS = transforms.Compose([
    transforms.Resize(224, interpolation=transforms.InterpolationMode.BICUBIC),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.48145466, 0.4578275, 0.40821073],
        std=[0.26862954, 0.26130258, 0.27577711],
    ),
])


def resolve_keyframes_root() -> Path:
    """Tìm thư mục keyframes/ thật trong /kaggle/input — KHÔNG hard-code 1 path cố định vì Kaggle
    đã đổi quy ước mount ít nhất 1 lần (từ /kaggle/input/<slug>/... sang
    /kaggle/input/datasets/<owner>/<slug>/... — phát hiện bằng kaggle_jobs/_diag/main.py sau khi
    job này ban đầu chạy ra FileNotFoundError vì hard-code path cũ, xem kaggle_jobs/README.md).
    Thử các path quen thuộc trước, nếu không thấy thì rglob toàn /kaggle/input."""
    candidates = [
        INPUT_BASE / FRAMES_DATASET_SLUG / "keyframes",                              # quy ước cũ
        INPUT_BASE / "datasets" / _FRAMES_OWNER / FRAMES_DATASET_SLUG / "keyframes",  # quy ước mới (xác nhận 2026-08)
    ]
    for c in candidates:
        if c.exists():
            return c
    found = next(INPUT_BASE.rglob("keyframes"), None) if INPUT_BASE.exists() else None
    if found is not None:
        return found
    raise FileNotFoundError(
        f"Không tìm thấy thư mục 'keyframes' dưới {INPUT_BASE}. Đã thử: "
        f"{[str(c) for c in candidates]}. Kiểm tra dataset_sources trong kernel-metadata.json, "
        f"hoặc chạy kaggle_jobs/_diag/main.py để xem cấu trúc /kaggle/input thật trên phiên hiện tại."
    )


def list_input_dataset_dirs():
    """Liệt kê các thư mục dataset con thực sự dưới /kaggle/input, hỗ trợ cả quy ước mount cũ
    ('/kaggle/input/<slug>') lẫn mới ('/kaggle/input/datasets/<owner>/<slug>')."""
    if not INPUT_BASE.exists():
        return []
    dirs = []
    datasets_wrapper = INPUT_BASE / "datasets"
    if datasets_wrapper.is_dir():
        for owner_dir in datasets_wrapper.iterdir():
            if owner_dir.is_dir():
                dirs.extend(d for d in owner_dir.iterdir() if d.is_dir())
    for d in INPUT_BASE.iterdir():
        if d.is_dir() and d.name != "datasets":
            dirs.append(d)
    return dirs


def restore_resume_cache() -> int:
    """Quét mọi dataset input khác ngoài frames dataset, copy .npy có sẵn vào OUTPUT_DIR
    trước khi chạy, để resume được qua nhiều lần `kaggle kernels push` riêng biệt."""
    restored = 0
    for ds_dir in list_input_dataset_dirs():
        if ds_dir.name == FRAMES_DATASET_SLUG:
            continue
        for npy in ds_dir.rglob("*.npy"):
            dst = OUTPUT_DIR / npy.name
            if not dst.exists():
                shutil.copy2(npy, dst)
                restored += 1
    return restored


class KeyframeDataset(Dataset):
    """1 item = 1 ảnh jpg, trả về (tensor đã preprocess, n) để giữ đúng thứ tự khi ghép lại."""

    def __init__(self, jpg_paths):
        self.jpg_paths = jpg_paths

    def __len__(self):
        return len(self.jpg_paths)

    def __getitem__(self, idx):
        p = self.jpg_paths[idx]
        img = Image.open(p).convert("RGB")
        return PREPROCESS(img), int(p.stem)


def list_videos(root: Path):
    """Quét toàn bộ batch/video bằng rglob, gom theo video_id (tên thư mục chứa ảnh)."""
    if not root.exists():
        root = resolve_keyframes_root()
    if not root.exists():
        contents = [str(x) for x in list(INPUT_BASE.rglob("*"))[:30]] if INPUT_BASE.exists() else []
        raise FileNotFoundError(
            f"Không thấy ảnh trong {INPUT_BASE}. Các file tìm thấy: {contents}"
        )

    found_map = {}
    for jpg in root.rglob("*.jpg"):
        vid_id = jpg.parent.name
        if vid_id not in found_map:
            found_map[vid_id] = []
        found_map[vid_id].append(jpg)

    videos = []
    for vid_id in sorted(found_map.keys()):
        jpgs = sorted(found_map[vid_id], key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
        videos.append((vid_id, jpgs))

    if not videos:
        contents = [str(x) for x in list(INPUT_BASE.rglob("*"))[:30]] if INPUT_BASE.exists() else []
        raise FileNotFoundError(f"Không tìm thấy file .jpg nào trong {root}. Nội dung: {contents}")

    return videos


def load_model():
    print(f"[encode_{TAG}] tải model {MODEL_ID} ...")
    model = CLIPModel.from_pretrained(MODEL_ID)
    model.eval().to(DEVICE)
    return model


_debug_dumped = False  # in cấu trúc ModelOutput thật đúng 1 lần, tránh spam log 873 video


def _get_image_embeds(model, pixel_values):
    """Gọi get_image_features() nhưng phòng trường hợp bản `transformers` nào đó (do
    _pip_install(..., "-U") kéo bản mới nhất, không pin version) đổi hành vi trả về
    ModelOutput thô thay vì tensor cuối như trước — phát hiện thật 2026-08-19 (job 01 & 02
    cùng lỗi `AttributeError: 'BaseModelOutputWithPooling' object has no attribute 'float'`).

    LỊCH SỬ SỬA SAI 2 LẦN (2026-08-19, 2026-08-20) — cả 2 lần đều ĐOÁN nhầm field nào đã qua
    visual_projection: lần 1 áp projection() vô điều kiện -> double-projection khi field lấy
    được đã là 768 chiều. Lần 2 tưởng `pooler_output` luôn là 1024 chiều THÔ nên vẫn áp
    projection() -> vẫn double-projection (RuntimeError 64x768/1024x768 y hệt) vì bản
    `transformers` chạy thật hoá ra trả `pooler_output` ĐÃ là 768 chiều, không phải giả định.
    -> ĐỔI CHIẾN LƯỢC: không đoán field nào ứng với giai đoạn nào nữa — chỉ dựa vào SHAPE THẬT
    lúc runtime: nếu chiều cuối đã khớp projection_dim (768) thì dùng thẳng, chỉ áp projection
    khi chiều cuối CHƯA khớp. Đồng thời in cấu trúc ModelOutput thật 1 lần đầu để có dữ liệu
    thật cho lần sau, không phải đoán nữa nếu vẫn còn sai."""
    global _debug_dumped
    try:
        out = model.get_image_features(pixel_values=pixel_values, return_dict=False)
    except TypeError:
        out = model.get_image_features(pixel_values=pixel_values)
    if isinstance(out, torch.Tensor):
        return out

    if not _debug_dumped:
        _debug_dumped = True
        try:
            info = {k: (tuple(v.shape) if hasattr(v, "shape") else type(v).__name__)
                     for k, v in out.items()}
        except Exception:
            info = repr(out)[:300]
        print(f"[encode_{TAG}] DEBUG get_image_features() trả về {type(out).__name__}: {info}")

    candidate = getattr(out, "image_embeds", None)
    if candidate is None:
        candidate = getattr(out, "pooler_output", None)
    if candidate is None:
        candidate = out[1] if len(out) > 1 else out[0]

    expected_dim = getattr(model.config, "projection_dim", None)
    projection = getattr(model, "visual_projection", None)
    if projection is not None and expected_dim is not None and candidate.shape[-1] != expected_dim:
        candidate = projection(candidate)  # chỉ chiếu khi chiều THỰC SỰ chưa khớp — không đoán nữa
    return candidate


@torch.no_grad()
def encode_video(model, jpg_paths):
    """Encode toàn bộ ảnh của 1 video theo batch, trả về (num_keyframes, D) float32 đã L2-normalize,
    ĐÚNG thứ tự n tăng dần như jpg_paths đầu vào."""
    ds = KeyframeDataset(jpg_paths)
    loader = DataLoader(ds, batch_size=BATCH_SIZE, num_workers=NUM_WORKERS, shuffle=False)

    feats_by_n = {}
    for batch_imgs, batch_n in loader:
        batch_imgs = batch_imgs.to(DEVICE, non_blocking=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=(DEVICE == "cuda")):
            out = _get_image_embeds(model, batch_imgs)
        expected_dim = getattr(model.config, "projection_dim", None)
        if out.dim() != 2 or (expected_dim is not None and out.shape[-1] != expected_dim):
            raise RuntimeError(f"[encode_{TAG}] embedding bất thường sau get_image_features(): "
                                f"shape={tuple(out.shape)} (cần (batch, {expected_dim})) — kiểm tra "
                                f"lại _get_image_embeds(), có thể API transformers đổi khác nữa.")
        out = out.float()
        out = out / out.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        out = out.cpu().numpy()
        for vec, n in zip(out, batch_n.numpy().tolist()):
            feats_by_n[n] = vec

    ordered = [feats_by_n[int(p.stem)] for p in jpg_paths]
    return np.stack(ordered, axis=0)


def main():
    if SMOKE_TEST:
        print(f"[encode_{TAG}] === SMOKE_TEST=True — chỉ chạy {SMOKE_TEST_NUM_VIDEOS} video x "
              f"{SMOKE_TEST_NUM_IMAGES} ảnh để kiểm tra logic, KHÔNG PHẢI encode thật. "
              f"Output ghi vào features_{_RUN_TAG}/ (tách riêng, không đụng output thật) ===")
    print(f"[encode_{TAG}] device={DEVICE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restored = restore_resume_cache()
    if restored:
        print(f"[encode_{TAG}] resume: đã khôi phục {restored} file .npy từ dataset input trước đó")

    model = load_model()
    input_root = resolve_keyframes_root()
    print(f"[encode_{TAG}] keyframes root: {input_root}")
    videos = list_videos(input_root)
    print(f"[encode_{TAG}] tổng số video tìm thấy: {len(videos)}")
    if SMOKE_TEST:
        videos = [(vid, jpgs[:SMOKE_TEST_NUM_IMAGES]) for vid, jpgs in videos[:SMOKE_TEST_NUM_VIDEOS]]
        print(f"[encode_{TAG}] SMOKE_TEST: rút xuống {len(videos)} video, "
              f"{[len(j) for _, j in videos]} ảnh/video")

    manifest_rows = []
    done_now = 0
    skipped = 0
    t0 = time.time()
    for i, (video_id, jpgs) in enumerate(videos, start=1):
        out_path = OUTPUT_DIR / f"{video_id}.npy"
        if out_path.exists():
            skipped += 1
            continue

        feats = encode_video(model, jpgs)
        np.save(out_path, feats.astype(np.float16))
        for p in jpgs:
            manifest_rows.append({
                "video_id": video_id,
                "n": int(p.stem),
                "jpg": str(p.relative_to(input_root)),
            })
        done_now += 1

        if i % 20 == 0 or i == len(videos):
            elapsed = time.time() - t0
            print(f"[encode_{TAG}] {i}/{len(videos)} video đã xử lý "
                  f"(mới encode: {done_now}, đã có sẵn/skip: {skipped}), {elapsed:.0f}s trôi qua")

    if manifest_rows:
        pd.DataFrame(manifest_rows).to_csv(
            MANIFEST_PATH, mode="a", header=not MANIFEST_PATH.exists(), index=False
        )

    print(f"[encode_{TAG}] nén kết quả vào {ZIP_PATH} ...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUTPUT_DIR.glob("*.npy")):
            zf.write(f, arcname=f"features_{_RUN_TAG}/{f.name}")
        if MANIFEST_PATH.exists():
            zf.write(MANIFEST_PATH, arcname=MANIFEST_PATH.name)

    size_mb = ZIP_PATH.stat().st_size / 1e6
    print(f"[encode_{TAG}] XONG. {done_now} video mới encode, {skipped} video đã có sẵn (resume). "
          f"Zip: {ZIP_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
