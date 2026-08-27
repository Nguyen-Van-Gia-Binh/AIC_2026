"""
scripts/setup_kaggle_shards.py — Thiết lập 3 thư mục Kaggle Jobs (Shard 0, 1, 2) cho Vintern-1B Captioning.

Mỗi thư mục gồm:
  - main.py (tối ưu hóa theo manifest, GPU T4, bfloat16, batch resume, progress logging)
  - manifest_shard.json (chứa 291 video và danh sách frame cụ thể của Shard đó)
  - kernel-metadata.json (metadata để đẩy trực tiếp qua Kaggle CLI)
"""

from pathlib import Path
import shutil
import json

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_DIR = ROOT / "data" / "manifests"
KAGGLE_JOBS_DIR = ROOT / "kaggle_jobs"


MAIN_PY_TEMPLATE = '''"""
Kaggle GPU Job — Vintern-1B-v3.5 Captioning (SHARD __SHARD_IDX__ / __TOTAL_SHARDS__).

Chạy trên GPU Nvidia Tesla T4 (Kaggle).
Tập dữ liệu: __NUM_VIDEOS__ video (~__NUM_FRAMES__ keyframe được chọn theo Semantic Manifest Filtering).
Output: /kaggle/working/caption_vintern1b_shard__SHARD_IDX__.zip
"""

import os
import sys
import json
import time
import shutil
import subprocess
import zipfile
from pathlib import Path

def _pip_install(*pkgs):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *pkgs], check=True)

# Cài đặt dependency tương thích
_pip_install("transformers==4.57.3", "timm", "einops", "sentencepiece", "accelerate")

import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer

SHARD_IDX = __SHARD_IDX__
TOTAL_SHARDS = __TOTAL_SHARDS__
TAG = f"caption_vintern1b_shard{SHARD_IDX}"
MODEL_ID = "5CD-AI/Vintern-1B-v3_5"

# Chế độ Smoke-Test (chuyển False khi chạy thật trên Kaggle)
SMOKE_TEST = False
SMOKE_TEST_NUM_VIDEOS = 2
SMOKE_TEST_NUM_IMAGES = 5

MAX_NEW_TOKENS = 30
DYNAMIC_TILE_MAX_NUM = 6

FRAMES_DATASET_REF = "kiet1106/aic26-frames"
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
_RUN_TAG = f"smoketest_{TAG}" if SMOKE_TEST else TAG
OUTPUT_DIR = Path(f"/kaggle/working/{_RUN_TAG}")
ZIP_PATH = Path(f"/kaggle/working/{_RUN_TAG}.zip")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
QUESTION = "<image>\\nMô tả ngắn gọn trong 1 câu tiếng Việt nội dung khung hình này (người, vật, hành động, bối cảnh)."

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

_MODEL = None
_TOKENIZER = None
_MANIFEST = None


def load_manifest() -> dict[str, set[int]]:
    global _MANIFEST
    if _MANIFEST is not None:
        return _MANIFEST

    candidates = [
        Path(__file__).parent / "manifest_shard.json",
        Path("/kaggle/working/manifest_shard.json"),
    ]
    for c in candidates:
        if c.exists():
            with open(c, "r", encoding="utf-8") as f:
                raw = json.load(f)
            _MANIFEST = {k: set(v) for k, v in raw.items()}
            print(f"[{TAG}] Đã nạp manifest_shard.json: {len(_MANIFEST)} video được chỉ định.")
            return _MANIFEST

    found = next(Path(".").rglob("manifest_shard.json"), None)
    if found and found.exists():
        with open(found, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _MANIFEST = {k: set(v) for k, v in raw.items()}
        print(f"[{TAG}] Đã nạp manifest từ {found}: {len(_MANIFEST)} video.")
        return _MANIFEST

    raise FileNotFoundError("Không tìm thấy manifest_shard.json trong bundle code!")


def build_transform(input_size):
    return T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])


def find_closest_aspect_ratio(aspect_ratio, target_ratios, width, height, image_size):
    best_ratio_diff = float('inf')
    best_ratio = (1, 1)
    area = width * height
    for ratio in target_ratios:
        target_aspect_ratio = ratio[0] / ratio[1]
        ratio_diff = abs(aspect_ratio - target_aspect_ratio)
        if ratio_diff < best_ratio_diff:
            best_ratio_diff = ratio_diff
            best_ratio = ratio
        elif ratio_diff == best_ratio_diff:
            if area > 0.5 * image_size * image_size * ratio[0] * ratio[1]:
                best_ratio = ratio
    return best_ratio


def dynamic_preprocess(image, min_num=1, max_num=12, image_size=448, use_thumbnail=False):
    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    target_ratios = set(
        (i, j) for n in range(min_num, max_num + 1) for i in range(1, n + 1)
        for j in range(1, n + 1) if i * j <= max_num and i * j >= min_num)
    target_ratios = sorted(target_ratios, key=lambda x: x[0] * x[1])

    target_aspect_ratio = find_closest_aspect_ratio(
        aspect_ratio, target_ratios, orig_width, orig_height, image_size)

    target_width = image_size * target_aspect_ratio[0]
    target_height = image_size * target_aspect_ratio[1]
    blocks = target_aspect_ratio[0] * target_aspect_ratio[1]

    resized_img = image.resize((target_width, target_height))
    processed_images = []
    for i in range(blocks):
        box = (
            (i % (target_width // image_size)) * image_size,
            (i // (target_width // image_size)) * image_size,
            ((i % (target_width // image_size)) + 1) * image_size,
            ((i // (target_width // image_size)) + 1) * image_size
        )
        split_img = resized_img.crop(box)
        processed_images.append(split_img)

    if use_thumbnail and len(processed_images) != 1:
        thumbnail_img = image.resize((image_size, image_size))
        processed_images.append(thumbnail_img)
    return processed_images


def load_image(image_file, input_size=448, max_num=12):
    image = Image.open(image_file).convert('RGB')
    transform = build_transform(input_size=input_size)
    images = dynamic_preprocess(image, image_size=input_size, use_thumbnail=True, max_num=max_num)
    pixel_values = [transform(img) for img in images]
    pixel_values = torch.stack(pixel_values)
    return pixel_values


def resolve_keyframes_root() -> Path:
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
    raise FileNotFoundError(f"Không tìm thấy thư mục 'keyframes' dưới {INPUT_BASE}.")


def restore_resume_cache() -> int:
    restored = 0
    if not INPUT_BASE.exists():
        return 0
    for d in INPUT_BASE.rglob("*.jsonl"):
        dst = OUTPUT_DIR / d.name
        if not dst.exists():
            shutil.copy2(d, dst)
            restored += 1
    return restored


def list_videos_for_shard(root: Path, manifest: dict[str, set[int]]):
    found_map = {}
    for jpg in root.rglob("*.jpg"):
        vid_id = jpg.parent.name
        if vid_id in manifest:
            found_map.setdefault(vid_id, []).append(jpg)

    videos = []
    for vid_id in sorted(found_map.keys()):
        selected_set = manifest[vid_id]
        jpgs = []
        for p in found_map[vid_id]:
            try:
                n_val = int(p.stem)
                if n_val in selected_set:
                    jpgs.append(p)
            except ValueError:
                continue
        jpgs.sort(key=lambda p: int(p.stem))
        if jpgs:
            videos.append((vid_id, jpgs))

    return videos


def load_model():
    global _MODEL, _TOKENIZER
    print(f"[{TAG}] Tải model {MODEL_ID} (device={DEVICE}) ...")
    model = AutoModel.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        low_cpu_mem_usage=True,
        trust_remote_code=True,
        use_flash_attn=False,
    ).eval()
    if DEVICE == "cuda":
        model = model.cuda()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True, use_fast=False)
    print(f"[{TAG}] Model đã sẵn sàng.")
    _MODEL, _TOKENIZER = model, tokenizer
    return model, tokenizer


@torch.no_grad()
def caption_frame(model, tokenizer, jpg_path: Path) -> str:
    pixel_values = load_image(str(jpg_path), max_num=DYNAMIC_TILE_MAX_NUM).to(torch.bfloat16)
    if DEVICE == "cuda":
        pixel_values = pixel_values.cuda()

    generation_config = dict(max_new_tokens=MAX_NEW_TOKENS, do_sample=False, num_beams=1)
    response, _ = model.chat(
        tokenizer, pixel_values, QUESTION, generation_config, history=None, return_history=True
    )
    return response.strip()


def process_video(model, tokenizer, video_id: str, jpgs) -> tuple[int, int]:
    out_path = OUTPUT_DIR / f"{video_id}.jsonl"

    done_n = set()
    if out_path.exists():
        with open(out_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    done_n.add(json.loads(line)["n"])
                except (json.JSONDecodeError, KeyError):
                    continue

    n_done = 0
    n_error = 0
    with open(out_path, "a", encoding="utf-8") as f:
        for p in jpgs:
            n = int(p.stem)
            if n in done_n:
                continue
            try:
                caption = caption_frame(model, tokenizer, p)
            except Exception as e:
                print(f"[{TAG}] LỖI frame {video_id}/{n}: {e}")
                n_error += 1
                continue
            rec = {"n": n, "caption": caption}
            f.write(json.dumps(rec, ensure_ascii=False) + "\\n")
            f.flush()
            n_done += 1

    return n_done, n_error


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()

    print(f"[{TAG}] ======================================================")
    print(f"[{TAG}] KHỞI CHẠY SHARD {SHARD_IDX} / {TOTAL_SHARDS}")
    print(f"[{TAG}] Device: {DEVICE}, Max Tokens: {MAX_NEW_TOKENS}, Dynamic Tiles: {DYNAMIC_TILE_MAX_NUM}")
    print(f"[{TAG}] ======================================================")

    restored = restore_resume_cache()
    if restored:
        print(f"[{TAG}] Resume: Đã khôi phục {restored} file .jsonl từ cache trước.")

    model, tokenizer = load_model()
    input_root = resolve_keyframes_root()
    print(f"[{TAG}] Keyframes root: {input_root}")

    videos = list_videos_for_shard(input_root, manifest)
    print(f"[{TAG}] Số video thuộc Shard {SHARD_IDX}: {len(videos)}")

    if SMOKE_TEST:
        videos = [(vid, jpgs[:SMOKE_TEST_NUM_IMAGES]) for vid, jpgs in videos[:SMOKE_TEST_NUM_VIDEOS]]
        print(f"[{TAG}] SMOKE_TEST: Rút xuống {len(videos)} video x {SMOKE_TEST_NUM_IMAGES} ảnh.")

    total_frames_target = sum(len(jpgs) for _, jpgs in videos)
    print(f"[{TAG}] Tổng số frame cần xử lý: {total_frames_target:,} frames")

    total_done = 0
    total_error = 0
    t0 = time.time()

    for i, (video_id, jpgs) in enumerate(videos, start=1):
        v_t0 = time.time()
        n_done, n_error = process_video(model, tokenizer, video_id, jpgs)
        v_elapsed = time.time() - v_t0
        total_done += n_done
        total_error += n_error
        spf = (v_elapsed / n_done) if n_done else 0.0
        print(f"[{TAG}] [{i}/{len(videos)}] {video_id}: {n_done}/{len(jpgs)} frame mới "
              f"(lỗi {n_error}), {v_elapsed:.1f}s ({spf:.2f}s/frame)")

    elapsed = time.time() - t0
    print(f"[{TAG}] Đang nén kết quả vào {ZIP_PATH} ...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUTPUT_DIR.glob("*.jsonl")):
            zf.write(f, arcname=f"{TAG}/{f.name}")

    size_mb = ZIP_PATH.stat().st_size / 1e6
    print(f"[{TAG}] HOÀN THÀNH SHARD {SHARD_IDX}!")
    print(f"[{TAG}] Tổng frame đã sinh: {total_done:,} | Lỗi: {total_error} | Thời gian: {elapsed/3600:.2f} giờ")
    print(f"[{TAG}] File nén: {ZIP_PATH} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
'''


def main():
    if not MANIFEST_DIR.exists():
        raise FileNotFoundError(f"Không tìm thấy thư mục {MANIFEST_DIR}. Hãy chạy scripts/build_caption_manifest.py trước!")

    for shard_idx in range(3):
        shard_dir = KAGGLE_JOBS_DIR / f"07_vintern_caption_shard{shard_idx}"
        shard_dir.mkdir(parents=True, exist_ok=True)

        manifest_src = MANIFEST_DIR / f"manifest_shard_{shard_idx}.json"
        manifest_dst = shard_dir / "manifest_shard.json"
        shutil.copy2(manifest_src, manifest_dst)

        with open(manifest_src, "r", encoding="utf-8") as f:
            shard_manifest = json.load(f)

        num_videos = len(shard_manifest)
        num_frames = sum(len(v) for v in shard_manifest.values())

        # Thay thế placeholder đơn giản
        content = (
            MAIN_PY_TEMPLATE
            .replace("__SHARD_IDX__", str(shard_idx))
            .replace("__TOTAL_SHARDS__", "3")
            .replace("__NUM_VIDEOS__", str(num_videos))
            .replace("__NUM_FRAMES__", f"{num_frames:,}")
        )
        with open(shard_dir / "main.py", "w", encoding="utf-8") as f:
            f.write(content)

        # Ghi kernel-metadata.json
        metadata = {
            "id": f"thanhnghiphan/aic2026-caption-07-vintern1b-shard{shard_idx}",
            "title": f"AIC2026 Caption 07 Vintern1B Shard {shard_idx}",
            "code_file": "main.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "machine_shape": "NvidiaTeslaT4",
            "enable_tpu": False,
            "enable_internet": True,
            "dataset_sources": [
                "kiet1106/aic26-frames"
            ],
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": []
        }
        with open(shard_dir / "kernel-metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

        print(f"✅ Đã tạo Shard {shard_idx}: {shard_dir} ({num_videos} video, {num_frames:,} frames)")


if __name__ == "__main__":
    main()
