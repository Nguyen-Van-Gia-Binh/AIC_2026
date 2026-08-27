"""
scripts/run_caption_shard_local.py — Chạy 1 shard caption Vintern-1B-v3.5 NGAY TRÊN MÁY LOCAL (GPU
riêng), thay vì đẩy lên Kaggle qua kaggle_jobs/07_vintern_caption_shard{N}/.

Lý do có file này: logic xử lý (dynamic_preprocess/load_image/caption_frame/...) giống HỆT
kaggle_jobs/07_vintern_caption_shard{N}/main.py (sinh ra từ scripts/setup_kaggle_shards.py), nhưng
kaggle_jobs/ hard-code /kaggle/input + /kaggle/working (chỉ chạy được trên Kaggle) và tự pip-install
trong script (hợp lý cho kernel dùng 1 lần, không hợp lý cho venv cố định của máy local) — xem
"DO NOT" trong CLAUDE.md, không đụng gì tới kaggle_jobs/ hiện có, tạo file riêng cho đường chạy local.

Input:  data/extracted/keyframes/{batch}/{video_id}/{n:03d}.jpg (đã giải nén sẵn cục bộ)
        data/manifests/manifest_shard_{N}.json  ({video_id: [n, n, ...]}, sinh bởi
        scripts/build_caption_manifest.py + scripts/setup_kaggle_shards.py)
Output: data/extracted/caption_shard{N}/{video_id}.jsonl — 1 dòng/frame: {"n": int, "caption": str}
        Đặt ĐÚNG tên thư mục scripts/merge_captions.py đã quét sẵn (SHARD_SEARCH_PATHS) — chạy xong
        chỉ cần gọi thẳng `scripts/merge_captions.py`, không cần bước gộp riêng.

Yêu cầu cài đặt (KHÔNG có trong requirements.txt gốc — venv gốc dùng torch CPU cho app chính, xem
CLAUDE.md Tech Stack): torch bản CUDA (vd cu128, xác nhận hỗ trợ Blackwell/sm_120 từ PyTorch stable
>=2.7.0), torchvision, transformers==4.57.3 (pin khớp bản dùng trên Kaggle), timm, einops,
sentencepiece, accelerate. Cài 1 lần:
  .venv\\Scripts\\python.exe -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
  .venv\\Scripts\\python.exe -m pip install transformers==4.57.3 timm einops sentencepiece accelerate

Usage:
  .venv\\Scripts\\python.exe scripts\\run_caption_shard_local.py --shard 1                # chạy full shard 1
  .venv\\Scripts\\python.exe scripts\\run_caption_shard_local.py --shard 1 --smoke-test    # 2 video x 5 ảnh để đo giây/frame thật trước
"""

import sys
import json
import time
import argparse
from pathlib import Path

import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer

# UTF-8 cho console Windows (giống merge_captions.py) — log có dấu tiếng Việt.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

TAG = "caption_local"
MODEL_ID = "5CD-AI/Vintern-1B-v3_5"
MAX_NEW_TOKENS = 30
DYNAMIC_TILE_MAX_NUM = 6
QUESTION = ("<image>\nMô tả ngắn gọn trong 1 câu tiếng Việt nội dung khung hình này (người, vật, "
            "hành động, bối cảnh).")

ROOT = Path(__file__).resolve().parent.parent
KEYFRAMES_ROOT = ROOT / "data" / "extracted" / "keyframes"
MANIFEST_DIR = ROOT / "data" / "manifests"

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_manifest(shard_idx: int) -> dict[str, set[int]]:
    path = MANIFEST_DIR / f"manifest_shard_{shard_idx}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {path} — chạy scripts/build_caption_manifest.py + "
            f"scripts/setup_kaggle_shards.py trước."
        )
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return {k: set(v) for k, v in raw.items()}


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


def list_videos_for_shard(manifest: dict[str, set[int]]):
    """Dò keyframe local theo đúng manifest của shard — không rglob toàn bộ 177K ảnh, chỉ cần
    tìm đúng các video_id có trong manifest (khớp cấu trúc data/extracted/keyframes/{batch}/{video_id}/)."""
    videos = []
    for vid_id in sorted(manifest.keys()):
        batch = vid_id.split("_")[0]  # "L21_V001" -> "L21"
        vid_dir = KEYFRAMES_ROOT / batch / vid_id
        if not vid_dir.is_dir():
            print(f"[{TAG}] CẢNH BÁO: không thấy thư mục {vid_dir}, bỏ qua video này.")
            continue
        selected_set = manifest[vid_id]
        jpgs = []
        for p in vid_dir.glob("*.jpg"):
            try:
                n_val = int(p.stem)
            except ValueError:
                continue
            if n_val in selected_set:
                jpgs.append(p)
        jpgs.sort(key=lambda p: int(p.stem))
        if jpgs:
            videos.append((vid_id, jpgs))
    return videos


def load_model():
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


def process_video(model, tokenizer, video_id: str, jpgs, output_dir: Path) -> tuple[int, int]:
    out_path = output_dir / f"{video_id}.jsonl"

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
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            n_done += 1

    return n_done, n_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=int, required=True, choices=[0, 1, 2],
                         help="Chỉ số shard (0/1/2), khớp data/manifests/manifest_shard_{N}.json")
    parser.add_argument("--smoke-test", action="store_true",
                         help="Chỉ chạy 2 video x 5 ảnh đầu để đo giây/frame thật trước khi chạy full")
    parser.add_argument("--smoke-test-videos", type=int, default=2)
    parser.add_argument("--smoke-test-images", type=int, default=5)
    args = parser.parse_args()

    output_dir = ROOT / "data" / "extracted" / (
        f"smoketest_caption_shard{args.shard}" if args.smoke_test else f"caption_shard{args.shard}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{TAG}] ======================================================")
    print(f"[{TAG}] SHARD {args.shard} — chạy LOCAL, device={DEVICE}"
          + (f" ({torch.cuda.get_device_name(0)})" if DEVICE == "cuda" else " (CPU — sẽ RẤT chậm)"))
    print(f"[{TAG}] Output: {output_dir}")
    print(f"[{TAG}] ======================================================")

    manifest = load_manifest(args.shard)
    model, tokenizer = load_model()
    videos = list_videos_for_shard(manifest)
    print(f"[{TAG}] Số video thuộc shard {args.shard} tìm thấy trên máy: {len(videos)}/{len(manifest)}")

    if args.smoke_test:
        videos = [(vid, jpgs[:args.smoke_test_images]) for vid, jpgs in videos[:args.smoke_test_videos]]
        print(f"[{TAG}] SMOKE_TEST: rút xuống {len(videos)} video x {args.smoke_test_images} ảnh.")

    total_frames_target = sum(len(jpgs) for _, jpgs in videos)
    print(f"[{TAG}] Tổng số frame cần xử lý: {total_frames_target:,} frames")

    total_done = 0
    total_error = 0
    t0 = time.time()

    for i, (video_id, jpgs) in enumerate(videos, start=1):
        v_t0 = time.time()
        n_done, n_error = process_video(model, tokenizer, video_id, jpgs, output_dir)
        v_elapsed = time.time() - v_t0
        total_done += n_done
        total_error += n_error
        spf = (v_elapsed / n_done) if n_done else 0.0
        print(f"[{TAG}] [{i}/{len(videos)}] {video_id}: {n_done}/{len(jpgs)} frame mới "
              f"(lỗi {n_error}), {v_elapsed:.1f}s ({spf:.2f}s/frame)")

    elapsed = time.time() - t0
    print(f"[{TAG}] XONG. {total_done:,} frame mới, {total_error} lỗi, {elapsed/3600:.2f} giờ.")
    if total_done:
        spf = elapsed / total_done
        remaining = total_frames_target - total_done
        print(f"[{TAG}] >>> {spf:.2f}s/frame trung bình — ước tính phần còn lại của shard "
              f"({remaining:,} frame nếu chạy full): {spf * remaining / 3600:.2f} giờ GPU.")


if __name__ == "__main__":
    main()
