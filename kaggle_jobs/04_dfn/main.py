"""
Kaggle GPU job — encode toàn bộ keyframe AIC2026 bằng OpenCLIP DFN-5B ViT-H/14 (Apple DFN5B-CLIP,
qua thư viện open_clip). Xem kaggle_jobs/README.md để biết bức tranh chung 4 job encode SOTA.

Input dataset (dataset_sources trong kernel-metadata.json): kiet1106/aic26-frames
  -> nội dung là keyframes/{batch}/{video_id}/{n:03d}.jpg.
  LƯU Ý (phát hiện 2026-08-19 qua kaggle_jobs/_diag/): Kaggle mount dataset KHÔNG cố định 1 quy
  ước — có lúc là /kaggle/input/<slug>/..., có lúc là /kaggle/input/datasets/<owner>/<slug>/...
  Vì vậy KHÔNG hard-code INPUT_ROOT — resolve_keyframes_root() bên dưới tự dò cả 2 quy ước.

Output (trong /kaggle/working/, tải về bằng `kaggle kernels output`):
  features_dfn/{video_id}.npy  -> (num_keyframes, D) float16, đã L2-normalize, thứ tự n tăng dần
  manifest_dfn.csv             -> video_id, n, jpg (đường dẫn tương đối)
  features_dfn.zip             -> nén toàn bộ 2 thứ trên

Lưu ý riêng cho DFN-5B ViT-H/14: đây là checkpoint LỚN nhất trong 4 model (~632M tham số phần
vision, weight file vài GB) — open_clip sẽ tự tải từ HuggingFace Hub (apple/DFN5B-CLIP-ViT-H-14)
lúc chạy, cần enable_internet=true (đã bật trong kernel-metadata.json) và tốn vài phút đầu để tải
weight trước khi bắt đầu encode.

Resume: xem giải thích chi tiết trong kaggle_jobs/01_vit_l14/main.py — cơ chế giống hệt, chỉ đổi
prefix "vitl14" -> "dfn".
"""

import sys
import time
import shutil
import subprocess
import zipfile
from pathlib import Path


def _pip_install(*pkgs):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", *pkgs], check=True)


_pip_install("open_clip_torch", "pillow")

import torch
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
from PIL import Image
import open_clip

MODEL_NAME = "ViT-H-14-quickgelu"
PRETRAINED = "dfn5b"
TAG = "dfn"

FRAMES_DATASET_REF = "kiet1106/aic26-frames"  # "owner/slug" trong dataset_sources — đổi nếu dùng dataset khác
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
OUTPUT_DIR = Path(f"/kaggle/working/features_{TAG}")
MANIFEST_PATH = Path(f"/kaggle/working/manifest_{TAG}.csv")
ZIP_PATH = Path(f"/kaggle/working/features_{TAG}.zip")

BATCH_SIZE = 32  # ViT-H/14 to, hạ batch để an toàn VRAM trên GPU Kaggle (~16GB)
NUM_WORKERS = 4
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


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
    def __init__(self, jpg_paths, preprocess):
        self.jpg_paths = jpg_paths
        self.preprocess = preprocess

    def __len__(self):
        return len(self.jpg_paths)

    def __getitem__(self, idx):
        p = self.jpg_paths[idx]
        img = Image.open(p).convert("RGB")
        return self.preprocess(img), int(p.stem)


def list_videos(root: Path):
    videos = []
    if not root.exists():
        raise FileNotFoundError(f"Không thấy {root}")
    for batch_dir in sorted(root.iterdir()):
        if not batch_dir.is_dir():
            continue
        for video_dir in sorted(batch_dir.iterdir()):
            if not video_dir.is_dir():
                continue
            jpgs = sorted(video_dir.glob("*.jpg"), key=lambda p: int(p.stem))
            if jpgs:
                videos.append((video_dir.name, jpgs))
    return videos


def load_model():
    print(f"[encode_{TAG}] tải model {MODEL_NAME} (pretrained={PRETRAINED}) ...")
    model, _, preprocess = open_clip.create_model_and_transforms(MODEL_NAME, pretrained=PRETRAINED)
    model.eval().to(DEVICE)
    return model, preprocess


@torch.no_grad()
def encode_video(model, preprocess, jpg_paths):
    ds = KeyframeDataset(jpg_paths, preprocess)
    loader = DataLoader(ds, batch_size=BATCH_SIZE, num_workers=NUM_WORKERS, shuffle=False)

    feats_by_n = {}
    for batch_imgs, batch_n in loader:
        batch_imgs = batch_imgs.to(DEVICE, non_blocking=True)
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=(DEVICE == "cuda")):
            out = model.encode_image(batch_imgs)
        out = out.float()
        out = out / out.norm(dim=-1, keepdim=True).clamp_min(1e-12)
        out = out.cpu().numpy()
        for vec, n in zip(out, batch_n.numpy().tolist()):
            feats_by_n[n] = vec

    ordered = [feats_by_n[int(p.stem)] for p in jpg_paths]
    return np.stack(ordered, axis=0)


def main():
    print(f"[encode_{TAG}] device={DEVICE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restored = restore_resume_cache()
    if restored:
        print(f"[encode_{TAG}] resume: đã khôi phục {restored} file .npy từ dataset input trước đó")

    model, preprocess = load_model()
    input_root = resolve_keyframes_root()
    print(f"[encode_{TAG}] keyframes root: {input_root}")
    videos = list_videos(input_root)
    print(f"[encode_{TAG}] tổng số video tìm thấy: {len(videos)}")

    manifest_rows = []
    done_now = 0
    skipped = 0
    t0 = time.time()
    for i, (video_id, jpgs) in enumerate(videos, start=1):
        out_path = OUTPUT_DIR / f"{video_id}.npy"
        if out_path.exists():
            skipped += 1
            continue

        feats = encode_video(model, preprocess, jpgs)
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
            zf.write(f, arcname=f"features_{TAG}/{f.name}")
        if MANIFEST_PATH.exists():
            zf.write(MANIFEST_PATH, arcname=MANIFEST_PATH.name)

    size_mb = ZIP_PATH.stat().st_size / 1e6
    print(f"[encode_{TAG}] XONG. {done_now} video mới encode, {skipped} video đã có sẵn (resume). "
          f"Zip: {ZIP_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
