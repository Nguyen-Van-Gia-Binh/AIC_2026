"""
Kaggle GPU job — encode toàn bộ keyframe AIC2026 bằng Google SigLIP 2 SO400M-384 (qua
HuggingFace transformers). Đây là bản tương đương của `kaggle_jobs/02_siglip/main.py`, nhưng
đổi sang model SigLIP 2 để thử backbone mạnh hơn cho ranker/encoder.

Input dataset (dataset_sources trong kernel-metadata.json): kiet1106/aic26-frames
  -> nội dung là keyframes/{batch}/{video_id}/{n:03d}.jpg.

Output (trong /kaggle/working/, tải về bằng `kaggle kernels output`):
  features_siglip2/{video_id}.npy  -> (num_keyframes, D) float16, đã L2-normalize, thứ tự n tăng dần
  manifest_siglip2.csv             -> video_id, n, jpg (đường dẫn tương đối)
  features_siglip2.zip             -> nén toàn bộ 2 thứ trên

Cơ chế resume / smoke-test / path mount tự dò giống hệt job 02 SigLIP 1, chỉ đổi model name
và tag prefix.
"""

import sys
import time
import shutil
import subprocess
import zipfile
from pathlib import Path


def _pip_install(*pkgs):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *pkgs], check=True)


# Pin cứng giống phiên SigLIP 1 trước đó: major version 4.x ổn định, không dùng `-U` để tránh
# breakage do transformers đổi API giữa các push Kaggle.
_pip_install("transformers==4.57.3", "pillow", "accelerate")

import torch
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
from PIL import Image
from transformers import AutoProcessor, SiglipVisionModel

MODEL_ID = "google/siglip2-so400m-patch14-384"
TAG = "siglip2"
IMG_SIZE = 384

SMOKE_TEST = False
SMOKE_TEST_NUM_VIDEOS = 2
SMOKE_TEST_NUM_IMAGES = 4

FRAMES_DATASET_REF = "kiet1106/aic26-frames"
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
_RUN_TAG = f"smoketest_{TAG}" if SMOKE_TEST else TAG
OUTPUT_DIR = Path(f"/kaggle/working/features_{_RUN_TAG}")
MANIFEST_PATH = Path(f"/kaggle/working/manifest_{_RUN_TAG}.csv")
ZIP_PATH = Path(f"/kaggle/working/features_{_RUN_TAG}.zip")

BATCH_SIZE = 8
NUM_WORKERS = 4
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def resolve_keyframes_root() -> Path:
    """Tự dò dataset mount đúng cả path cũ/lẫn mới trên Kaggle."""
    candidates = [
        INPUT_BASE / FRAMES_DATASET_SLUG / "keyframes",
        INPUT_BASE / "datasets" / _FRAMES_OWNER / FRAMES_DATASET_SLUG / "keyframes",
    ]
    for c in candidates:
        if c.exists():
            return c
    found = next(INPUT_BASE.rglob("keyframes"), None) if INPUT_BASE.exists() else None
    if found is not None:
        return found
    raise FileNotFoundError(
        f"Không tìm thấy thư mục 'keyframes' dưới {INPUT_BASE}. Đã thử: "
        f"{[str(c) for c in candidates]}. Kiểm tra dataset_sources trong kernel-metadata.json."
    )


def list_input_dataset_dirs():
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
    """Khôi phục .npy đã có sẵn từ các dataset input khác về OUTPUT_DIR để resume."""
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
    def __init__(self, jpg_paths):
        self.jpg_paths = jpg_paths

    def __len__(self):
        return len(self.jpg_paths)

    def __getitem__(self, idx):
        p = self.jpg_paths[idx]
        img = Image.open(p).convert("RGB")
        return img, int(p.stem)


def collate_keyframes(batch):
    images, frame_numbers = zip(*batch)
    return list(images), torch.tensor(frame_numbers, dtype=torch.long)


def list_videos(root: Path):
    if not root.exists():
        root = resolve_keyframes_root()
    if not root.exists():
        contents = [str(x) for x in list(INPUT_BASE.rglob("*"))[:30]] if INPUT_BASE.exists() else []
        raise FileNotFoundError(f"Không thấy ảnh trong {INPUT_BASE}. Các file tìm thấy: {contents}")

    print(f"[encode_{TAG}] bắt đầu quét ảnh JPG dưới {root} ...", flush=True)
    found_map = {}
    image_count = 0
    last_log_count = 0
    for jpg in root.rglob("*.jpg"):
        vid_id = jpg.parent.name
        if vid_id not in found_map:
            found_map[vid_id] = []
        found_map[vid_id].append(jpg)
        image_count += 1
        if image_count - last_log_count >= 25000:
            print(
                f"[encode_{TAG}] đã quét {image_count:,} ảnh, "
                f"{len(found_map):,} video ...",
                flush=True,
            )
            last_log_count = image_count

    videos = []
    for vid_id in sorted(found_map.keys()):
        jpgs = sorted(found_map[vid_id], key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
        videos.append((vid_id, jpgs))

    if not videos:
        contents = [str(x) for x in list(INPUT_BASE.rglob("*"))[:30]] if INPUT_BASE.exists() else []
        raise FileNotFoundError(f"Không tìm thấy file .jpg nào trong {root}. Nội dung: {contents}")

    print(
        f"[encode_{TAG}] quét xong: {image_count:,} ảnh trong "
        f"{len(videos):,} video",
        flush=True,
    )
    return videos


def load_model():
    print(f"[encode_{TAG}] tải model {MODEL_ID} ...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    # Checkpoint SigLIP 2 vẫn dùng kiến trúc vision SigLIP trong Transformers 4.x.
    model = SiglipVisionModel.from_pretrained(MODEL_ID)
    model.eval().to(DEVICE)
    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    print(
        f"[encode_{TAG}] model đã sẵn sàng: {parameter_count / 1e6:.1f}M tham số, "
        f"device={DEVICE}",
        flush=True,
    )
    return model, processor


def _get_image_embeds(model, processor, images):
    inputs = processor(
        images=images,
        return_tensors="pt",
        size={"height": IMG_SIZE, "width": IMG_SIZE},
    )
    pixel_values = inputs["pixel_values"].to(DEVICE)
    outputs = model(pixel_values=pixel_values)
    pooled = outputs.pooler_output
    if pooled is None:
        pooled = outputs.last_hidden_state.mean(dim=1)
    return pooled


@torch.no_grad()
def encode_video(model, processor, jpg_paths):
    ds = KeyframeDataset(jpg_paths)
    loader = DataLoader(
        ds,
        batch_size=BATCH_SIZE,
        num_workers=NUM_WORKERS,
        shuffle=False,
        collate_fn=collate_keyframes,
        pin_memory=(DEVICE == "cuda"),
    )

    feats_by_n = {}
    for batch_imgs, batch_n in loader:
        with torch.autocast(device_type="cuda", dtype=torch.float16, enabled=(DEVICE == "cuda")):
            out = _get_image_embeds(model, processor, list(batch_imgs))
        if out.dim() != 2:
            raise RuntimeError(
                f"[encode_{TAG}] embedding bất thường sau Siglip2VisionModel: "
                f"shape={tuple(out.shape)} (cần (batch, D))"
            )
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
              f"Output ghi vào features_{_RUN_TAG}/ ===")
    print(f"[encode_{TAG}] device={DEVICE}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restored = restore_resume_cache()
    print(f"[encode_{TAG}] resume cache: khôi phục {restored} file .npy", flush=True)

    model, processor = load_model()
    input_root = resolve_keyframes_root()
    print(f"[encode_{TAG}] keyframes root: {input_root}")
    videos = list_videos(input_root)
    total_images = sum(len(jpgs) for _, jpgs in videos)
    print(
        f"[encode_{TAG}] dữ liệu đầu vào: {len(videos):,} video, "
        f"{total_images:,} ảnh",
        flush=True,
    )
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

        if i == 1 or i % 10 == 0:
            print(
                f"[encode_{TAG}] bắt đầu video {i}/{len(videos)}: "
                f"{video_id} ({len(jpgs)} ảnh)",
                flush=True,
            )
        feats = encode_video(model, processor, jpgs)
        np.save(out_path, feats.astype(np.float16))
        for p in jpgs:
            manifest_rows.append({
                "video_id": video_id,
                "n": int(p.stem),
                "jpg": str(p.relative_to(input_root)),
            })
        done_now += 1

        if i % 10 == 0 or i == len(videos):
            elapsed = time.time() - t0
            processed_images = sum(len(video_jpgs) for _, video_jpgs in videos[:i] if video_jpgs)
            print(f"[encode_{TAG}] {i}/{len(videos)} video đã xử lý "
                  f"(mới encode: {done_now}, đã có sẵn/skip: {skipped}), "
                  f"{processed_images:,}/{total_images:,} ảnh, {elapsed:.0f}s trôi qua",
                  flush=True)

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
