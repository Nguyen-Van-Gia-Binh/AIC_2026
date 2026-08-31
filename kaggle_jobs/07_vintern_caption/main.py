"""
Kaggle GPU job — sinh caption tiếng Việt ngắn gọn cho keyframe AIC2026 bằng Vintern-1B-v3.5
(5CD-AI/Vintern-1B-v3_5, dựa trên InternVL2.5-1B, fine-tune riêng cho tiếng Việt). Đây là PHASE 2
trong chiến lược tách OCR/caption:
  Phase 1 (kaggle_jobs/06_rapidocr_ocr/): OCR toàn bộ 177.321 keyframe bằng RapidOCR — job riêng.
  Phase 2 (job này): caption tiếng Việt, CHỈ trên tập frame đã lọc (KHÔNG cần toàn bộ 177K — xem
    scripts/offline/analysis/analyze_frame_similarity.py). Manifest lọc THẬT (build_ocr_frame_manifest.py)
    CHƯA viết — job này tạm dùng FRAME_STRIDE làm placeholder, SẼ SỬA để đọc manifest sau khi có số
    giây/frame thật từ SMOKE_TEST (số đó quyết định τ/MAX_GAP_SEC dùng ở bước lọc).
  Merge: scripts/index_ocr_es.py ghép ocr_text (Phase 1, dày) + caption (Phase 2, thưa) theo "n"
    trước khi đẩy vào Elasticsearch — CHƯA sửa.

LÝ DO đổi từ SmolVLM-Instruct sang Vintern-1B-v3.5: SmolVLM-Instruct CHỈ hỗ trợ chính thức 6 ngôn
ngữ (Anh/Pháp/Tây Ban Nha/Đức/Ý/Bồ Đào Nha) — KHÔNG có tiếng Việt (xác nhận qua model card
2026-08-23), ép sinh tiếng Việt rủi ro ra chữ hỏng/lẫn tiếng Anh. Vintern-1B-v3.5 (0.9B tham số,
dựa trên InternVL2.5-1B) được fine-tune riêng cho tiếng Việt, có benchmark VQA/caption tiếng Việt
thật (vi-MTVQA, DocVQA) — xem https://huggingface.co/5CD-AI/Vintern-1B-v3_5.

Input dataset: kiet1106/aic26-frames — cùng dataset và cách dò path như các job trước.

Output (trong /kaggle/working/, tải về bằng `kaggle kernels output`):
  caption_vintern1b/{video_id}.jsonl -> 1 dòng JSON/frame: {"n": int, "caption": str} (n khớp cột
                                         "n" trong map-keyframes, KHÔNG phải frame_id — xem CLAUDE.md)
  caption_vintern1b.zip              -> nén toàn bộ .jsonl ở trên

API model — lấy NGUYÊN VĂN từ model card chính thức (WebFetch 2026-08-23, KHÔNG đoán):
  AutoModel.from_pretrained(..., torch_dtype=torch.bfloat16, trust_remote_code=True,
                             use_flash_attn=False).eval().cuda()
  AutoTokenizer.from_pretrained(..., trust_remote_code=True, use_fast=False)
  pixel_values = load_image(jpg, max_num=6)  -> dynamic_preprocess() chia ảnh thành tối đa 6 tile
                                                 448x448 (hàm copy nguyên văn từ model card)
  response, history = model.chat(tokenizer, pixel_values, question, generation_config,
                                  history=None, return_history=True)
LƯU Ý: generation_config ở đây KHÁC ví dụ gốc trên model card (ví dụ gốc dùng num_beams=3,
repetition_penalty=2.5, max_new_tokens=1024 — tối ưu cho trích xuất văn bản dài dạng markdown).
Job này cần caption 1 câu NGẮN nên đổi sang max_new_tokens=30, num_beams=1 (greedy, nhanh hơn beam
search ~3x), bỏ repetition_penalty — ĐÂY LÀ THAY ĐỔI CHỦ ĐỘNG cho use-case khác, chưa verify chất
lượng thật, cần xem output SMOKE_TEST có hợp lý không, chỉnh lại nếu caption sinh ra kém.

CẢNH BÁO: GPU T4 (Turing, sm_75) KHÔNG có tensor core hỗ trợ bfloat16 gốc (chỉ từ Ampere/sm_80 trở
lên) — bfloat16 vẫn chạy đúng số học (không tràn số như float16 với model có tower nhạy cảm, xem
kaggle_jobs/03_jina/main.py lịch sử NaN) nhưng có thể chậm hơn tối ưu trên T4. Giữ nguyên bfloat16
theo đúng khuyến nghị model card thay vì tự đổi sang float16 (rủi ro NaN đã có tiền lệ).

Resume: giống job 05/06 — JSONL + flush() ngay mỗi dòng, cộng restore_resume_cache() qua nhiều lần
push (xem kaggle_jobs/01_vit_l14/main.py).
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


# PIN cùng transformers==4.57.3 như job 01-05 (bản 4.x ổn định cuối, xem kaggle_jobs/README.md "Cập
# nhật 6"). timm/einops/sentencepiece/accelerate: dependency thường gặp của model kiến trúc
# InternVL/EVA tương tự job 03 (jina) — thêm phòng hờ, không hại gì nếu model không cần tới.
# KHÔNG reinstall torch/torchvision — dùng bản có sẵn trên image Kaggle để tránh lệch ABI.
_pip_install("transformers==4.57.3", "timm", "einops", "sentencepiece", "accelerate")

import torch
import torchvision.transforms as T
from PIL import Image
from torchvision.transforms.functional import InterpolationMode
from transformers import AutoModel, AutoTokenizer

MODEL_ID = "5CD-AI/Vintern-1B-v3_5"
TAG = "caption_vintern1b"

# ── CHẾ ĐỘ SMOKE-TEST: đổi SMOKE_TEST = True rồi push để đo giây/frame THẬT trước khi chạy full.
SMOKE_TEST = True
SMOKE_TEST_NUM_VIDEOS = 1
SMOKE_TEST_NUM_IMAGES = 5

# Placeholder tạm — SẼ THAY bằng manifest lọc theo similarity (xem docstring đầu file) sau khi có
# số giây/frame thật từ SMOKE_TEST. 1 = xử lý mọi frame (chỉ hợp lý cho SMOKE_TEST, KHÔNG dùng cho
# full corpus).
FRAME_STRIDE = 1
MAX_NEW_TOKENS = 30     # theo đúng yêu cầu: caption ngắn gọn
DYNAMIC_TILE_MAX_NUM = 6  # số tile 448x448 tối đa/ảnh (đúng ví dụ model card) — giảm xuống nếu
                           # SMOKE_TEST cho thấy quá chậm, đổi ít chất lượng lấy tốc độ

FRAMES_DATASET_REF = "kiet1106/aic26-frames"
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
_RUN_TAG = f"smoketest_{TAG}" if SMOKE_TEST else TAG
OUTPUT_DIR = Path(f"/kaggle/working/{_RUN_TAG}")
ZIP_PATH = Path(f"/kaggle/working/{_RUN_TAG}.zip")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

QUESTION = ("<image>\nMô tả ngắn gọn trong 1 câu tiếng Việt nội dung khung hình này "
            "(người, vật, hành động, bối cảnh).")

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

_MODEL = None
_TOKENIZER = None
_debug_dumped = False


# ── Tiền xử lý ảnh — copy NGUYÊN VĂN từ model card 5CD-AI/Vintern-1B-v3_5 (WebFetch 2026-08-23,
# đây là code chuẩn của kiến trúc InternVL, KHÔNG viết lại theo cách khác để tránh lệch input so
# với lúc model được huấn luyện/đánh giá) ──
def build_transform(input_size):
    transform = T.Compose([
        T.Lambda(lambda img: img.convert('RGB') if img.mode != 'RGB' else img),
        T.Resize((input_size, input_size), interpolation=InterpolationMode.BICUBIC),
        T.ToTensor(),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    ])
    return transform


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
# ── hết phần copy từ model card ──


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
    restored = 0
    for ds_dir in list_input_dataset_dirs():
        if ds_dir.name == FRAMES_DATASET_SLUG:
            continue
        for jsonl in ds_dir.rglob("*.jsonl"):
            dst = OUTPUT_DIR / jsonl.name
            if not dst.exists():
                shutil.copy2(jsonl, dst)
                restored += 1
    return restored


def list_videos(root: Path):
    if not root.exists():
        root = resolve_keyframes_root()
    if not root.exists():
        contents = [str(x) for x in list(INPUT_BASE.rglob("*"))[:30]] if INPUT_BASE.exists() else []
        raise FileNotFoundError(f"Không thấy ảnh trong {INPUT_BASE}. Các file tìm thấy: {contents}")

    found_map = {}
    for jpg in root.rglob("*.jpg"):
        vid_id = jpg.parent.name
        found_map.setdefault(vid_id, []).append(jpg)

    videos = []
    for vid_id in sorted(found_map.keys()):
        jpgs = sorted(found_map[vid_id], key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
        videos.append((vid_id, jpgs))

    if not videos:
        contents = [str(x) for x in list(INPUT_BASE.rglob("*"))[:30]] if INPUT_BASE.exists() else []
        raise FileNotFoundError(f"Không tìm thấy file .jpg nào trong {root}. Nội dung: {contents}")

    return videos


def load_model():
    global _MODEL, _TOKENIZER
    print(f"[{TAG}] tải model {MODEL_ID} (device={DEVICE}) ...")
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
    print(f"[{TAG}] Ready.")
    _MODEL, _TOKENIZER = model, tokenizer
    return model, tokenizer


@torch.no_grad()
def caption_frame(model, tokenizer, jpg_path: Path) -> str:
    """1 lần gọi model.chat() cho 1 ảnh -> caption tiếng Việt. Dump raw response 1 lần đầu ra log
    để kiểm tra nhanh chất lượng thật (không phải vì API không chắc — API đã lấy nguyên văn model
    card — mà để phát hiện sớm nếu generation_config đã đổi (bỏ num_beams=3/repetition_penalty) làm
    caption kém, cần chỉnh lại QUA SMOKE_TEST trước khi chạy full)."""
    global _debug_dumped
    pixel_values = load_image(str(jpg_path), max_num=DYNAMIC_TILE_MAX_NUM).to(torch.bfloat16)
    if DEVICE == "cuda":
        pixel_values = pixel_values.cuda()

    generation_config = dict(max_new_tokens=MAX_NEW_TOKENS, do_sample=False, num_beams=1)
    response, _ = model.chat(
        tokenizer, pixel_values, QUESTION, generation_config, history=None, return_history=True
    )

    if not _debug_dumped:
        _debug_dumped = True
        print(f"[{TAG}] DEBUG response mẫu: {response!r}")

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
            if FRAME_STRIDE > 1 and (n % FRAME_STRIDE != 0):
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
    if SMOKE_TEST:
        print(f"[{TAG}] === SMOKE_TEST=True — chỉ chạy {SMOKE_TEST_NUM_VIDEOS} video x "
              f"{SMOKE_TEST_NUM_IMAGES} ảnh để ĐO GIÂY/FRAME THẬT. Output ghi vào {OUTPUT_DIR}/ ===")
    print(f"[{TAG}] device={DEVICE}, FRAME_STRIDE={FRAME_STRIDE} (placeholder), "
          f"MAX_NEW_TOKENS={MAX_NEW_TOKENS}, DYNAMIC_TILE_MAX_NUM={DYNAMIC_TILE_MAX_NUM}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restored = restore_resume_cache()
    if restored:
        print(f"[{TAG}] resume: đã khôi phục {restored} file .jsonl từ dataset input trước đó")

    model, tokenizer = load_model()
    input_root = resolve_keyframes_root()
    print(f"[{TAG}] keyframes root: {input_root}")
    videos = list_videos(input_root)
    print(f"[{TAG}] tổng số video tìm thấy: {len(videos)}")
    if SMOKE_TEST:
        videos = [(vid, jpgs[:SMOKE_TEST_NUM_IMAGES]) for vid, jpgs in videos[:SMOKE_TEST_NUM_VIDEOS]]
        print(f"[{TAG}] SMOKE_TEST: rút xuống {len(videos)} video, "
              f"{[len(j) for _, j in videos]} ảnh/video")

    total_done = 0
    total_error = 0
    t0 = time.time()
    for i, (video_id, jpgs) in enumerate(videos, start=1):
        v_t0 = time.time()
        n_done, n_error = process_video(model, tokenizer, video_id, jpgs)
        v_elapsed = time.time() - v_t0
        total_done += n_done
        total_error += n_error
        sec_per_frame = (v_elapsed / n_done) if n_done else float("nan")
        print(f"[{TAG}] video {i}/{len(videos)} ({video_id}): {n_done} frame mới, {n_error} lỗi, "
              f"{v_elapsed:.1f}s ({sec_per_frame:.2f}s/frame)")

    elapsed = time.time() - t0
    print(f"[{TAG}] nén kết quả vào {ZIP_PATH} ...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUTPUT_DIR.glob("*.jsonl")):
            zf.write(f, arcname=f"{_RUN_TAG}/{f.name}")

    size_mb = ZIP_PATH.stat().st_size / 1e6
    print(f"[{TAG}] XONG. {total_done} frame mới xử lý, {total_error} lỗi, {elapsed:.0f}s tổng. "
          f"Zip: {ZIP_PATH} ({size_mb:.1f} MB)")
    if total_done:
        spf = elapsed / total_done
        print(f"[{TAG}] >>> Giây/frame TRUNG BÌNH thật: {spf:.2f}s/frame — dùng số này để chạy lại "
              f"scripts/offline/analysis/analyze_frame_similarity.py (đổi SEC_PER_FRAME) và chọn "
              f"(τ, MAX_GAP_SEC) cho scripts/build_ocr_frame_manifest.py (chưa viết).")


if __name__ == "__main__":
    main()
