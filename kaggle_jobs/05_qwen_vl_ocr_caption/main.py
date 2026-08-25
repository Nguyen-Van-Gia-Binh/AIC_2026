"""
Kaggle GPU job — OCR (trích văn bản) + captioning (mô tả cảnh) toàn bộ keyframe AIC2026 bằng
Qwen2.5-VL-3B-Instruct (qua HuggingFace transformers). Job này KHÔNG đụng baseline clip-ViT-B-32 ở
scripts/index.py — chỉ sinh thêm dữ liệu text (OCR + caption) để sau này index vào Elasticsearch
qua scripts/agent/tools/es_index.py (chạy ở máy local, không cần GPU cho bước index đó).

Input dataset (dataset_sources trong kernel-metadata.json): kiet1106/aic26-frames — cùng dataset và
cùng cách dò path (resolve_keyframes_root()) như 4 job encode ở kaggle_jobs/01-04 (xem docstring
01_vit_l14/main.py để biết lịch sử phát hiện path mount đổi quy ước).

Output (trong /kaggle/working/, tải về bằng `kaggle kernels output`):
  ocr_caption_qwen25vl/{video_id}.jsonl -> 1 dòng JSON/frame: {"n": int, "ocr_text": str,
                                            "caption": str} (n khớp cột "n" trong map-keyframes,
                                            KHÔNG phải frame_id — quy đổi frame_id = frame_idx + 1
                                            CHỈ làm ở scripts/agent/tools/retrieve.py, không lặp lại
                                            ở đây, xem CLAUDE.md)
  ocr_caption_qwen25vl.zip               -> nén toàn bộ .jsonl ở trên, tải về 1 file duy nhất

CẢNH BÁO QUY MÔ THỜI GIAN (ĐỌC TRƯỚC KHI CHẠY THẬT): sinh text bằng generate() của 1 model 3B là
1 phép decode tuần tự (sequential decode) — CHẬM HƠN NHIỀU so với 1 lần forward pass của CLIP encode
(4 job kia mỗi ảnh chỉ mất vài chục ms). Job này CHƯA được đo thời gian thật trên GPU T4 — số giây
thật/frame chỉ biết được sau khi chạy SMOKE_TEST. Với 177.321 keyframe, nếu thời gian thật/frame ở
mức vài giây thì tổng thời gian có thể vượt xa giới hạn 1 phiên Kaggle (~9-12h) — gần chắc chắn cần
chia làm nhiều lần push (xem cơ chế resume bên dưới) hoặc tăng FRAME_STRIDE để bỏ bớt frame.
BẮT BUỘC: chạy SMOKE_TEST = True trước, đọc log để biết giây/frame thật, rồi mới quyết định
FRAME_STRIDE + có cần chia nhỏ theo batch (L21-L30) qua nhiều lần push hay không.

Resume (2 lớp, vì decode chậm hơn hẳn CLIP encode — mất giữa 1 video cũng đáng tiếc, không chỉ mất
giữa các video):
  1. Trong 1 video: mỗi frame ghi thành 1 dòng JSONL + flush() ngay — nếu kernel bị Kaggle cắt giữa
     chừng, các dòng đã ghi + flush vẫn còn nguyên trong file .jsonl.
  2. Giữa nhiều lần push riêng biệt (/kaggle/working KHÔNG giữ lại qua các lần push): restore_
     resume_cache() quét MỌI dataset input khác ngoài aic26-frames để tìm .jsonl có sẵn và copy vào
     OUTPUT_DIR trước khi chạy — quy trình giống hệt 4 job kia (tải zip lần trước -> `kaggle datasets
     create` -> thêm vào dataset_sources -> push lại), xem kaggle_jobs/01_vit_l14/main.py.
  Khi resume 1 video dở dang, các dòng n đã có trong .jsonl được đọc lại vào done_n và bỏ qua — chỉ
  gọi model cho frame còn thiếu.
"""

import os
import sys
import json
import time
import shutil
import subprocess
import zipfile
from pathlib import Path

# ── cài thêm dependency (image Kaggle có sẵn torch/transformers nhưng có thể là bản cũ) ──
def _pip_install(*pkgs):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *pkgs], check=True)


# PIN CỨNG cùng version transformers==4.57.3 như 4 job kia (xem kaggle_jobs/README.md "Cập nhật 6"
# — bản 4.x ổn định cuối cùng, transformers 5.x đổi hành vi 1 số API). Qwen2.5-VL đã được hỗ trợ từ
# transformers >=4.49 nên 4.57.3 có đủ Qwen2_5_VLForConditionalGeneration.
_pip_install("transformers==4.57.3", "accelerate", "qwen-vl-utils==0.0.14", "pillow")

import torch
from PIL import Image
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration

MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"
TAG = "ocr_caption_qwen25vl"

# ── CHẾ ĐỘ SMOKE-TEST: đổi SMOKE_TEST = True rồi push để đo giây/frame THẬT trên GPU T4 trước khi
# chạy full 873 video — chỉ xử lý SMOKE_TEST_NUM_VIDEOS video đầu tìm thấy, mỗi video
# SMOKE_TEST_NUM_IMAGES ảnh đầu. Ghi ra thư mục RIÊNG (tiền tố "smoketest_") để không đụng output
# thật/không hỏng cơ chế resume của lần chạy full sau. Nhớ đổi lại False trước khi chạy thật.
SMOKE_TEST = True  # BẮT BUỘC chạy thật ít nhất 1 lần trước khi đổi False — xem cảnh báo ở docstring
SMOKE_TEST_NUM_VIDEOS = 1
SMOKE_TEST_NUM_IMAGES = 5

# Bỏ bớt frame để giảm thời gian (1 = xử lý MỌI frame, 5 = 1/5 số frame...). Quyết định giá trị này
# SAU KHI đã biết giây/frame thật từ SMOKE_TEST — để 1 tạm thời cho tới lúc đó.
FRAME_STRIDE = 1
MAX_NEW_TOKENS = 256

FRAMES_DATASET_REF = "kiet1106/aic26-frames"  # "owner/slug" trong dataset_sources
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
_RUN_TAG = f"smoketest_{TAG}" if SMOKE_TEST else TAG
OUTPUT_DIR = Path(f"/kaggle/working/{_RUN_TAG}")
ZIP_PATH = Path(f"/kaggle/working/{_RUN_TAG}.zip")

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Cùng prompt với scripts/agent/tools/vlm_ocr_caption.py (repo chính) — giữ format JSON đầu ra khớp
# nhau giữa 2 nơi để khi index vào Elasticasearch không cần parse 2 kiểu khác nhau.
PROMPT = (
    "Look at this video keyframe carefully. Reply with ONLY a single JSON object, no other text, "
    "with exactly two keys:\n"
    '  "ocr_text": all readable text visible in the image (signs, subtitles, captions, UI text, '
    'labels...), transcribed as-is. Use an empty string "" if there is no readable text.\n'
    '  "caption": one concise English sentence describing what is happening in the scene (people, '
    "objects, action, setting).\n"
    'Example: {"ocr_text": "EXIT", "caption": "A man walks through a doorway marked EXIT."}'
)


def resolve_keyframes_root() -> Path:
    """Giống hệt 01_vit_l14/main.py:resolve_keyframes_root() — Kaggle đã đổi quy ước mount ít nhất
    1 lần, không hard-code 1 path cố định."""
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
    """Giống hệt 01_vit_l14/main.py — hỗ trợ cả 2 quy ước mount cũ/mới."""
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
    """Quét mọi dataset input khác ngoài frames dataset, copy .jsonl có sẵn vào OUTPUT_DIR trước
    khi chạy, để resume được qua nhiều lần `kaggle kernels push` riêng biệt (xem docstring đầu file)."""
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
    """Giống hệt 01_vit_l14/main.py:list_videos() — quét toàn bộ batch/video bằng rglob."""
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
    print(f"[{TAG}] tải model {MODEL_ID} (device={DEVICE}) ...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = Qwen2_5_VLForConditionalGeneration.from_pretrained(MODEL_ID, torch_dtype="auto", device_map="auto")
    model.eval()
    print(f"[{TAG}] Ready.")
    return model, processor


def _parse_model_output(text: str) -> dict:
    """Trích khối {...} đầu tiên trong output — model đôi khi bọc thêm text/markdown quanh JSON.
    Fail loud (raise) nếu không tìm thấy JSON hợp lệ, để main() log lỗi và bỏ qua đúng frame đó
    thay vì ghi dữ liệu rác vào .jsonl."""
    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"Không tìm thấy JSON trong output model: {text!r}")
    data = json.loads(match.group(0))
    return {
        "ocr_text": str(data.get("ocr_text", "")).strip(),
        "caption": str(data.get("caption", "")).strip(),
    }


@torch.no_grad()
def describe_frame(model, processor, jpg_path: Path) -> dict:
    """1 lần gọi generate() cho 1 ảnh -> {"ocr_text": str, "caption": str}. KHÔNG batch nhiều ảnh
    cùng lúc (khác 4 job encode kia dùng DataLoader batch) — decode tuần tự của model sinh text khó
    batch an toàn cùng độ phức tạp trong lần viết đầu này; batch hoá là hướng tối ưu để dành sau nếu
    SMOKE_TEST cho thấy quá chậm."""
    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "image": str(jpg_path)},
            {"type": "text", "text": PROMPT},
        ],
    }]
    chat_text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

    from qwen_vl_utils import process_vision_info
    image_inputs, video_inputs = process_vision_info(messages)

    inputs = processor(
        text=[chat_text], images=image_inputs, videos=video_inputs,
        padding=True, return_tensors="pt",
    ).to(model.device)

    generated_ids = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )[0]
    return _parse_model_output(output_text)


def process_video(model, processor, video_id: str, jpgs) -> tuple[int, int]:
    """Xử lý 1 video, ghi/append vào {video_id}.jsonl. Trả về (số frame mới xử lý, số lỗi)."""
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
                    # dòng bị cắt giữa chừng do phiên trước bị Kaggle ngắt đột ngột — bỏ qua, frame
                    # đó sẽ không nằm trong done_n nên được xử lý lại (ghi thêm dòng mới, không sửa
                    # dòng hỏng cũ — dòng hỏng vô hại vì lúc đọc .jsonl ở scripts/index_ocr_es.py
                    # cũng sẽ bỏ qua dòng JSON không parse được theo cùng logic).
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
                result = describe_frame(model, processor, p)
            except Exception as e:
                print(f"[{TAG}] LỖI frame {video_id}/{n}: {e}")
                n_error += 1
                continue
            rec = {"n": n, "ocr_text": result["ocr_text"], "caption": result["caption"]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            n_done += 1

    return n_done, n_error


def main():
    if SMOKE_TEST:
        print(f"[{TAG}] === SMOKE_TEST=True — chỉ chạy {SMOKE_TEST_NUM_VIDEOS} video x "
              f"{SMOKE_TEST_NUM_IMAGES} ảnh để ĐO GIÂY/FRAME THẬT, KHÔNG PHẢI chạy thật. "
              f"Output ghi vào {OUTPUT_DIR}/ (tách riêng, không đụng output thật) ===")
    print(f"[{TAG}] device={DEVICE}, FRAME_STRIDE={FRAME_STRIDE}, MAX_NEW_TOKENS={MAX_NEW_TOKENS}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restored = restore_resume_cache()
    if restored:
        print(f"[{TAG}] resume: đã khôi phục {restored} file .jsonl từ dataset input trước đó")

    model, processor = load_model()
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
        n_done, n_error = process_video(model, processor, video_id, jpgs)
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
    if SMOKE_TEST and total_done:
        print(f"[{TAG}] >>> Giây/frame TRUNG BÌNH thật (dùng để ước lượng full 177.321 keyframe, "
              f"quyết định FRAME_STRIDE + có cần chia nhỏ theo nhiều lần push hay không): "
              f"{elapsed / total_done:.2f}s/frame")


if __name__ == "__main__":
    main()
