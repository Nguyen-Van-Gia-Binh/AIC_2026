"""
Kaggle GPU job — encode toàn bộ keyframe AIC2026 bằng Jina CLIP v2 (jinaai/jina-clip-v2, qua
HuggingFace transformers với trust_remote_code=True). Xem kaggle_jobs/README.md để biết bức tranh
chung 4 job encode SOTA.

Input dataset (dataset_sources trong kernel-metadata.json): kiet1106/aic26-frames
  -> nội dung là keyframes/{batch}/{video_id}/{n:03d}.jpg.
  LƯU Ý (phát hiện 2026-08-19 qua kaggle_jobs/_diag/): Kaggle mount dataset KHÔNG cố định 1 quy
  ước — có lúc là /kaggle/input/<slug>/..., có lúc là /kaggle/input/datasets/<owner>/<slug>/...
  Vì vậy KHÔNG hard-code INPUT_ROOT — resolve_keyframes_root() bên dưới tự dò cả 2 quy ước.

Output (trong /kaggle/working/, tải về bằng `kaggle kernels output`):
  features_jina/{video_id}.npy  -> (num_keyframes, D) float16, đã L2-normalize, thứ tự n tăng dần
  manifest_jina.csv             -> video_id, n, jpg (đường dẫn tương đối)
  features_jina.zip             -> nén toàn bộ 2 thứ trên

Lưu ý riêng cho Jina CLIP v2:
  - Model dùng code tuỳ biến trên HuggingFace (trust_remote_code=True) nên có sẵn hàm tiện lợi
    model.encode_image(...) tự lo preprocessing + batching bên trong -> KHÔNG cần tự viết
    DataLoader/transform như 2 job kia.
  - Model mặc định có thể bật flash-attention, nhưng GPU Kaggle phổ biến (T4) là kiến trúc Turing,
    KHÔNG hỗ trợ flash-attn -> đã tắt cứng use_flash_attn=False khi load. Nếu Kaggle assign cho bạn
    GPU đời mới hơn (A100/L4) có thể bật lại để nhanh hơn, nhưng để mặc định tắt cho chắc ăn.
  - API encode_image() có thể đổi signature giữa các version model card — nếu script lỗi ở bước
    này, kiểm tra lại model card https://huggingface.co/jinaai/jina-clip-v2 trước khi sửa.
  - (phát hiện 2026-08-19 qua Log3.txt) configuration_clip.py tuỳ biến của model này đòi
    torch_dtype là STRING ("float16"), không phải object torch.float16 — đã sửa trong
    load_model(). Đây là quirk riêng của model này, không áp dụng cho 3 job kia.

Resume: xem giải thích chi tiết trong kaggle_jobs/01_vit_l14/main.py — cơ chế giống hệt, chỉ đổi
prefix "vitl14" -> "jina".
"""

import sys
import time
import shutil
import subprocess
import zipfile
from pathlib import Path


def _pip_install(*pkgs):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", *pkgs], check=True)


# jina-clip-v2 cần transformers mới + einops/timm cho phần vision tower tuỳ biến
_pip_install("transformers", "pillow", "einops", "timm", "accelerate")

import torch
import numpy as np
import pandas as pd
from transformers import AutoModel

MODEL_ID = "jinaai/jina-clip-v2"
TAG = "jina"

FRAMES_DATASET_REF = "kiet1106/aic26-frames"  # "owner/slug" trong dataset_sources — đổi nếu dùng dataset khác
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
OUTPUT_DIR = Path(f"/kaggle/working/features_{TAG}")
MANIFEST_PATH = Path(f"/kaggle/working/manifest_{TAG}.csv")
ZIP_PATH = Path(f"/kaggle/working/features_{TAG}.zip")

BATCH_SIZE = 32  # model ~865M tham số, hạ batch để an toàn VRAM trên GPU Kaggle (~16GB)
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
    print(f"[encode_{TAG}] tải model {MODEL_ID} ...")
    # LƯU Ý (phát hiện 2026-08-19 qua Log3.txt): configuration_clip.py tuỳ biến của model này làm
    # `hasattr(torch, torch_dtype)` -> torch_dtype PHẢI là string ("float16"/"float32"), truyền
    # thẳng object torch.float16 sẽ crash với TypeError: attribute name must be string.
    dtype_str = "float16" if DEVICE == "cuda" else "float32"
    try:
        model = AutoModel.from_pretrained(
            MODEL_ID, trust_remote_code=True, torch_dtype=dtype_str, use_flash_attn=False
        )
    except TypeError:
        # bản model card cũ hơn không nhận kwarg use_flash_attn -> load lại không kèm nó
        model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True, torch_dtype=dtype_str)
    model.eval().to(DEVICE)
    return model


@torch.no_grad()
def encode_video(model, jpg_paths):
    """encode_image() của jina-clip-v2 tự lo preprocessing + batching nội bộ, giữ đúng thứ tự
    input -> output (danh sách jpg_paths đã sort theo n tăng dần từ trước)."""
    paths_str = [str(p) for p in jpg_paths]
    out = model.encode_image(paths_str, batch_size=BATCH_SIZE)
    out = np.asarray(out, dtype=np.float32)
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out = out / norms
    return out


def main():
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
            zf.write(f, arcname=f"features_{TAG}/{f.name}")
        if MANIFEST_PATH.exists():
            zf.write(MANIFEST_PATH, arcname=MANIFEST_PATH.name)

    size_mb = ZIP_PATH.stat().st_size / 1e6
    print(f"[encode_{TAG}] XONG. {done_now} video mới encode, {skipped} video đã có sẵn (resume). "
          f"Zip: {ZIP_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
