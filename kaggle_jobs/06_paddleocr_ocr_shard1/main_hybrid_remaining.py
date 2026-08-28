"""
Kaggle GPU job — OCR HYBRID (PaddleOCR Detection + VietOCR Recognition) cho PHẦN CÒN LẠI của SHARD 1/3
keyframe AIC2026. Sinh ra 2026-08-28 để chạy tiếp phần shard 1 chưa xong (232/291 video còn lại — 59
video đã có sẵn ở local từ trước, xem DONE_VIDEOS bên dưới, KHÔNG cần OCR lại).

Khác với kaggle_jobs/06_paddleocr_ocr_shard1/main.py (dùng PaddleOCR.predict() — recognizer đa ngôn
ngữ mặc định, dấu tiếng Việt kém): file này dùng pipeline HYBRID đã xác nhận đọc dấu tiếng Việt tốt hơn
hẳn (xem kaggle_jobs/06_paddleocr_ocr/check_vietnamese_vietocr.py, test thật 2026-08-26, và
colab_jobs/06_paddleocr_vietocr_shard1/notebook.ipynb đã chạy thật) — TextDetection (PaddleOCR,
device='gpu:0') tìm vị trí chữ, crop từng box, VietOCR (vgg_transformer) nhận diện riêng tiếng Việt.

LƯU Ý QUAN TRỌNG VỀ TỐC ĐỘ: torch cài cô lập ở đây là bản CPU-ONLY (bắt buộc — Kaggle base
site-packages có torch hỏng sẵn, gây lỗi NCCL nếu không cô lập, xem lịch sử sửa lỗi trong
kaggle_jobs/06_paddleocr_ocr/main.py). Hệ quả: `torch.cuda.is_available()` luôn trả False dù máy có
GPU T4 thật, nên bước NHẬN DIỆN (VietOCR) chạy CPU — chỉ bước PHÁT HIỆN (PaddleOCR TextDetection,
paddlepaddle-gpu là runtime RIÊNG, không phụ thuộc torch) chạy GPU thật. Vì vậy tốc độ CHẬM HƠN bản
Colab (đã đo full-GPU 0.457s/frame) — đây là đánh đổi đã biết, không phải lỗi.

CÁCH DÙNG (dán tay vào 1 Kaggle Notebook — không cần kernel-metadata.json/CLI push):
  1. Tạo Kaggle Notebook mới, bật GPU (Settings > Accelerator > GPU T4 x2 hoặc P100).
  2. Add Input Data > tìm dataset "kiet1106/aic26-frames" > Add.
  3. Dán TOÀN BỘ nội dung file này vào 1 code cell, chạy (Run All).
  4. Sau khi chạy xong: Output ở /kaggle/working/ocr_paddleocr_vietocr_shard1_remaining/ +
     ocr_paddleocr_vietocr_shard1_remaining.zip — tải zip về, giải nén đè vào
     data/extracted/ocr_shard1/ trên máy local (KHÔNG xoá 59 file cũ — file mới đặt tên khác video_id
     nên không đụng nhau), rồi chạy lại:
       .venv\\Scripts\\python.exe scripts\\preprocess\\ocr\\merge_ocr.py

Output: /kaggle/working/ocr_paddleocr_vietocr_shard1_remaining/{video_id}.jsonl
        1 dòng JSON/frame: {"n": int, "ocr_text": str} — ĐÚNG schema scripts/preprocess/ocr/merge_ocr.py cần.
Resume: JSONL append + flush() ngay mỗi dòng — nếu Kaggle bị ngắt giữa chừng, chạy lại kernel này
        (không cần sửa gì) sẽ tự bỏ qua "n" đã xong trong mỗi video, và bỏ qua HẲN video nào đã có đủ
        358 dòng trở lên (heuristic: coi như xong nếu file đã tồn tại — xem process_video()).
"""

import os
import sys
import json
import time
import shutil
import subprocess
import zipfile
from pathlib import Path

TAG = "ocr_paddleocr_vietocr_shard1_remaining"
SHARD_IDX = 1
TOTAL_SHARDS = 3
PKG_DIR = Path("/kaggle/working/paddle_pkgs")
_ISOLATED_FLAG = "_PADDLE_PKGS_ISOLATED"

# 59 video_id CỦA SHARD 1 đã OCR xong ở local trước đó (từ colab_jobs/06_paddleocr_vietocr_shard1/) —
# BỎ QUA các video này, chỉ chạy phần còn lại (232/291). Copy trực tiếp từ
# data/extracted/ocr_shard1/*.jsonl hiện có trên máy lúc sinh file này (2026-08-28).
DONE_VIDEOS = {
    "L21_V002", "L21_V006", "L21_V009", "L21_V012", "L21_V015", "L21_V018", "L21_V022", "L21_V025",
    "L21_V028", "L21_V031", "L22_V003", "L22_V006", "L22_V009", "L22_V012", "L22_V015", "L22_V018",
    "L22_V021", "L22_V024", "L22_V027", "L22_V030", "L23_V002", "L23_V005", "L23_V008", "L23_V011",
    "L23_V014", "L23_V017", "L23_V020", "L23_V023", "L24_V002", "L24_V005", "L24_V008", "L24_V011",
    "L24_V014", "L24_V017", "L24_V020", "L24_V023", "L24_V026", "L24_V029", "L24_V032", "L24_V036",
    "L24_V039", "L24_V042", "L24_V045", "L25_V003", "L25_V006", "L25_V009", "L25_V012", "L25_V015",
    "L25_V018", "L25_V021", "L25_V024", "L25_V027", "L25_V030", "L25_V033", "L25_V036", "L25_V039",
    "L25_V042", "L25_V045", "L25_V048",
}


def _bootstrap_isolated_install_and_reexec() -> None:
    print(f"[{TAG}] Cài torch (CPU-only, riêng) + paddleocr + paddlepaddle-gpu vào thư mục cô lập "
          f"{PKG_DIR} (--target --ignore-installed, không đụng site-packages gốc)...")
    PKG_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-q",
        "--target", str(PKG_DIR),
        "--ignore-installed",
        "--timeout", "120",
        "--retries", "5",
        "--index-url", "https://download.pytorch.org/whl/cpu",
        "--extra-index-url", "https://pypi.org/simple",
        "--extra-index-url", "https://www.paddlepaddle.org.cn/packages/stable/cu126/",
        "torch", "torchvision", "paddleocr==3.7.0", "paddlepaddle-gpu==3.3.0",
    ], check=True)
    print(f"[{TAG}] Cài xong paddleocr/torch. Cài riêng vietocr (--no-deps bắt buộc — ghim cứng "
          f"pillow==10.2.0 không có wheel cho Python bản mới) + gdown (dependency thật của vietocr, "
          f"bị --no-deps bỏ qua)...")
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-q",
        "--target", str(PKG_DIR), "--ignore-installed", "--no-deps",
        "vietocr",
    ], check=True)
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-q",
        "--target", str(PKG_DIR), "--ignore-installed",
        "gdown",
    ], check=True)
    print(f"[{TAG}] Cài xong. Gọi lại script với PYTHONPATH ưu tiên {PKG_DIR}...")

    env = dict(os.environ)
    env[_ISOLATED_FLAG] = "1"
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(PKG_DIR) + (os.pathsep + existing_pp if existing_pp else "")
    result = subprocess.run([sys.executable, __file__], env=env)
    sys.exit(result.returncode)


if os.environ.get(_ISOLATED_FLAG) != "1":
    _bootstrap_isolated_install_and_reexec()
    # không bao giờ chạy tới đây

# ── Từ đây trở xuống CHỈ chạy trong process con (PYTHONPATH đã ưu tiên PKG_DIR) ─────────────────

import cv2
import numpy as np
from PIL import Image

# Bật True để tự smoke-test riêng (2 video x 10 ảnh) trước khi chạy full — khuyên dùng cho lần chạy đầu.
SMOKE_TEST = False
SMOKE_TEST_NUM_VIDEOS = 2
SMOKE_TEST_NUM_IMAGES = 10
SCORE_THRESH = 0.5  # lọc box detection điểm tin cậy thấp — giống colab_jobs/run_ocr_shard_local.py

FRAMES_DATASET_REF = "kiet1106/aic26-frames"
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
_RUN_TAG = f"smoketest_{TAG}" if SMOKE_TEST else TAG
OUTPUT_DIR = Path(f"/kaggle/working/{_RUN_TAG}")
ZIP_PATH = Path(f"/kaggle/working/{_RUN_TAG}.zip")


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
        f"{[str(c) for c in candidates]}. Kiểm tra đã Add Input Data dataset {FRAMES_DATASET_REF} chưa."
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
    """Nếu bạn Add thêm 1 Input Data dataset khác chứa output .jsonl dở dang từ lần chạy trước (vd
    tự upload lại /kaggle/working cũ thành 1 Kaggle Dataset), script sẽ tự khôi phục để resume đúng
    "n" đã xong — KHÔNG bắt buộc, bỏ qua nếu không có dataset nào như vậy."""
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


def list_videos_for_shard(root: Path):
    """round-robin videos[SHARD_IDX::3] trên TOÀN BỘ 873 video đã sort (giống hệt colab_jobs/
    kaggle_jobs khác) rồi LOẠI BỎ các video đã có trong DONE_VIDEOS — chỉ trả về phần còn lại."""
    if not root.exists():
        root = resolve_keyframes_root()

    found_map = {}
    for jpg in root.rglob("*.jpg"):
        vid_id = jpg.parent.name
        found_map.setdefault(vid_id, []).append(jpg)

    all_videos = []
    for vid_id in sorted(found_map.keys()):
        jpgs = sorted(found_map[vid_id], key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
        all_videos.append((vid_id, jpgs))

    if not all_videos:
        contents = [str(x) for x in list(INPUT_BASE.rglob("*"))[:30]] if INPUT_BASE.exists() else []
        raise FileNotFoundError(f"Không tìm thấy file .jpg nào trong {root}. Nội dung: {contents}")

    shard_videos = all_videos[SHARD_IDX::TOTAL_SHARDS]
    remaining = [(vid, jpgs) for vid, jpgs in shard_videos if vid not in DONE_VIDEOS]
    print(f"[{TAG}] Shard {SHARD_IDX} đầy đủ: {len(shard_videos)} video — đã bỏ qua "
          f"{len(shard_videos) - len(remaining)} video trong DONE_VIDEOS — còn lại {len(remaining)} video.")
    return remaining


def _get_rotate_crop_image(img: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Thuật toán crop chuẩn PaddleOCR — giống hệt colab_jobs/06_paddleocr_vietocr_shard*/."""
    points = points.astype(np.float32)
    img_crop_width = int(max(
        np.linalg.norm(points[0] - points[1]), np.linalg.norm(points[2] - points[3])))
    img_crop_height = int(max(
        np.linalg.norm(points[0] - points[3]), np.linalg.norm(points[1] - points[2])))
    img_crop_width = max(img_crop_width, 1)
    img_crop_height = max(img_crop_height, 1)
    pts_std = np.float32([[0, 0], [img_crop_width, 0],
                           [img_crop_width, img_crop_height], [0, img_crop_height]])
    M = cv2.getPerspectiveTransform(points, pts_std)
    dst = cv2.warpPerspective(img, M, (img_crop_width, img_crop_height),
                               borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
    h, w = dst.shape[0:2]
    if h * 1.0 / w >= 1.5:
        dst = np.rot90(dst)
    return dst


def _sort_boxes_reading_order(dt_polys):
    """Gom box thành 'hàng' theo tâm y, sort trong hàng theo x — giống hệt colab_jobs."""
    if len(dt_polys) == 0:
        return dt_polys
    boxes = [np.array(b, dtype=np.float32) for b in dt_polys]
    centers = [(b[:, 0].mean(), b[:, 1].mean()) for b in boxes]
    heights = [max(np.linalg.norm(b[0] - b[3]), np.linalg.norm(b[1] - b[2])) for b in boxes]
    avg_h = float(np.mean(heights)) if heights else 20.0
    row_tol = max(avg_h * 0.6, 10.0)

    order = sorted(range(len(boxes)), key=lambda i: centers[i][1])
    rows = []
    for i in order:
        placed = False
        for row in rows:
            if abs(centers[i][1] - centers[row[0]][1]) <= row_tol:
                row.append(i)
                placed = True
                break
        if not placed:
            rows.append([i])
    final_order = []
    for row in rows:
        final_order.extend(sorted(row, key=lambda i: centers[i][0]))
    return [dt_polys[i] for i in final_order]


def load_detector():
    from paddleocr import TextDetection
    print(f"[{TAG}] tải TextDetection (PP-OCRv6_medium_det), thử device='gpu:0' ...")
    try:
        det = TextDetection(device="gpu:0")
        print(f"[{TAG}] Detector ready (gpu:0).")
    except Exception as e:
        print(f"[{TAG}] CẢNH BÁO: device='gpu:0' lỗi ({type(e).__name__}: {e}) — fallback mặc định.")
        det = TextDetection()
        print(f"[{TAG}] Detector ready (fallback).")
    return det


def load_recognizer():
    import torch
    from vietocr.tool.predictor import Predictor
    from vietocr.tool.config import Cfg
    # torch cài cô lập ở đây là bản CPU-only (bắt buộc, xem docstring đầu file) — cuda.is_available()
    # luôn False dù máy có GPU T4 thật. KHÔNG set 'cuda:0' — sẽ lỗi vì không có CUDA binding thật.
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[{TAG}] tải VietOCR (vgg_transformer, device={device}) ...")
    config = Cfg.load_config_from_name("vgg_transformer")
    config["device"] = device
    predictor = Predictor(config)
    print(f"[{TAG}] Recognizer ready (device={device}).")
    return predictor


def ocr_frame(detector, recognizer, jpg_path: Path) -> str:
    result = detector.predict(str(jpg_path))
    if not result:
        return ""
    r0 = result[0]
    dt_polys = r0.get("dt_polys") if hasattr(r0, "get") else getattr(r0, "dt_polys", None)
    dt_scores = r0.get("dt_scores") if hasattr(r0, "get") else getattr(r0, "dt_scores", None)
    if dt_polys is None or len(dt_polys) == 0:
        return ""

    if dt_scores is not None and len(dt_scores) == len(dt_polys):
        keep = [i for i, s in enumerate(dt_scores) if s >= SCORE_THRESH]
        dt_polys = [dt_polys[i] for i in keep]
    if len(dt_polys) == 0:
        return ""

    dt_polys = _sort_boxes_reading_order(dt_polys)

    img_bgr = cv2.imread(str(jpg_path))
    if img_bgr is None:
        return ""

    texts = []
    for box in dt_polys:
        box_arr = np.array(box, dtype=np.float32)
        crop_bgr = _get_rotate_crop_image(img_bgr, box_arr)
        crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
        crop_pil = Image.fromarray(crop_rgb)
        try:
            text = recognizer.predict(crop_pil)
        except Exception as e:
            print(f"[{TAG}] LỖI recognize 1 box của {jpg_path.name}: {type(e).__name__}: {e}")
            continue
        if text:
            texts.append(str(text).strip())
    return " ".join(texts).strip()


def process_video(detector, recognizer, video_id: str, jpgs) -> tuple[int, int]:
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
                text = ocr_frame(detector, recognizer, p)
            except Exception as e:
                print(f"[{TAG}] LỖI frame {video_id}/{n}: {e}")
                n_error += 1
                continue
            rec = {"n": n, "ocr_text": text}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            n_done += 1

    return n_done, n_error


def main():
    print(f"[{TAG}] ======================================================")
    print(f"[{TAG}] KHỞI CHẠY PHẦN CÒN LẠI CỦA SHARD {SHARD_IDX} / {TOTAL_SHARDS}")
    if SMOKE_TEST:
        print(f"[{TAG}] === SMOKE_TEST=True — chỉ chạy {SMOKE_TEST_NUM_VIDEOS} video x "
              f"{SMOKE_TEST_NUM_IMAGES} ảnh. Output ghi vào {OUTPUT_DIR}/ ===")
    print(f"[{TAG}] ======================================================")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restored = restore_resume_cache()
    if restored:
        print(f"[{TAG}] resume: đã khôi phục {restored} file .jsonl từ dataset input trước đó")

    detector = load_detector()
    recognizer = load_recognizer()
    input_root = resolve_keyframes_root()
    print(f"[{TAG}] keyframes root: {input_root}")
    videos = list_videos_for_shard(input_root)
    if SMOKE_TEST:
        videos = [(vid, jpgs[:SMOKE_TEST_NUM_IMAGES]) for vid, jpgs in videos[:SMOKE_TEST_NUM_VIDEOS]]
        print(f"[{TAG}] SMOKE_TEST: rút xuống {len(videos)} video, "
              f"{[len(j) for _, j in videos]} ảnh/video")

    total_frames_target = sum(len(jpgs) for _, jpgs in videos)
    print(f"[{TAG}] tổng số frame cần xử lý: {total_frames_target:,} frame")

    total_done = 0
    total_error = 0
    t0 = time.time()
    for i, (video_id, jpgs) in enumerate(videos, start=1):
        v_t0 = time.time()
        n_done, n_error = process_video(detector, recognizer, video_id, jpgs)
        v_elapsed = time.time() - v_t0
        total_done += n_done
        total_error += n_error
        sec_per_frame = (v_elapsed / n_done) if n_done else float("nan")
        print(f"[{TAG}] [{i}/{len(videos)}] {video_id}: {n_done} frame mới, {n_error} lỗi, "
              f"{v_elapsed:.1f}s ({sec_per_frame:.3f}s/frame)")

    elapsed = time.time() - t0
    print(f"[{TAG}] nén kết quả vào {ZIP_PATH} ...")
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(OUTPUT_DIR.glob("*.jsonl")):
            zf.write(f, arcname=f"{_RUN_TAG}/{f.name}")

    size_mb = ZIP_PATH.stat().st_size / 1e6
    print(f"[{TAG}] HOÀN THÀNH! {total_done} frame mới, {total_error} lỗi, {elapsed/3600:.2f} giờ. "
          f"Zip: {ZIP_PATH} ({size_mb:.1f} MB)")
    if total_done:
        spf = elapsed / total_done
        print(f"[{TAG}] >>> {spf:.3f}s/frame trung bình — ước cả phần còn lại "
              f"({total_frames_target:,} frame): {spf * total_frames_target / 3600:.2f} giờ.")


if __name__ == "__main__":
    main()
