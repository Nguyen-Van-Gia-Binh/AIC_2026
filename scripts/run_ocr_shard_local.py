"""
scripts/run_ocr_shard_local.py — BIỆN PHÁP BACKUP: chạy tiếp (hoặc chạy mới) 1 shard OCR NGAY TRÊN
MÁY LOCAL (GPU riêng), dùng khi 1 trong 3 tài khoản Colab (colab_jobs/06_paddleocr_vietocr_shard{N}/)
không chạy xong kịp trong giới hạn phiên/quota GPU miễn phí.

Pipeline: PaddleOCR (chỉ Detection, model PP-OCRv6_medium_det) + VietOCR (Recognition riêng tiếng
Việt) — ĐÃ XÁC NHẬN THẮNG RÕ RỆT về chất lượng dấu tiếng Việt so với recognizer mặc định của
PaddleOCR (xem kaggle_jobs/06_paddleocr_ocr/check_vietnamese_vietocr.py, chạy thật 2026-08-26) và
ĐÃ XÁC NHẬN chạy GPU thật trên Colab (colab_jobs/06_paddleocr_vietocr_shard0/, smoke-test PASS,
0.457s/frame). File này port lại đúng logic đó cho máy local — code CỐ TÌNH giống
scripts/run_caption_shard_local.py (bootstrap, resume, CLI args) để nhất quán quy ước cả repo.

AN TOÀN KHI DÙNG LÀM BACKUP GIỮA NHIỀU NƠI: chia shard TẤT ĐỊNH (round-robin videos[SHARD_IDX::3]
trên đúng 1 danh sách 873 video đã sort — GIỐNG HỆT thuật toán colab_jobs dùng), và resume theo "n"
đã có trong file .jsonl đích — nghĩa là chạy shard N ở BẤT KỲ đâu (Colab, local) đều tính ra đúng
cùng 1 tập video, và tự động bỏ qua đúng phần frame đã xong ở nơi khác (miễn đưa đúng phần output dở
dang từ Google Drive về đặt vào OUTPUT_DIR trước khi chạy — xem hướng dẫn "CÁCH DÙNG BACKUP" dưới).

Input:  data/extracted/keyframes/{batch}/{video_id}/{n:03d}.jpg (đã giải nén sẵn cục bộ)
Output: data/extracted/ocr_shard{N}/{video_id}.jsonl — 1 dòng/frame: {"n": int, "ocr_text": str}
        Đặt ĐÚNG tên thư mục scripts/merge_ocr.py đã quét sẵn — chạy xong chỉ cần gọi thẳng
        `scripts/merge_ocr.py`, không cần bước gộp riêng.

Yêu cầu cài đặt (KHÔNG có trong requirements.txt gốc — nặng, chỉ cần khi thật sự dùng backup này):
  .venv\\Scripts\\python.exe -m pip install paddleocr==3.7.0 paddlepaddle-gpu==3.3.0 --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cu126/
  .venv\\Scripts\\python.exe -m pip install --no-deps vietocr
  (--no-deps bắt buộc — vietocr ghim cứng pillow==10.2.0, không có wheel cho Python bản mới, lỗi
  build từ source; --no-deps giữ nguyên Pillow/torch/torchvision đã có sẵn trong venv, đã xác nhận
  đủ dùng — xem ghi chú y hệt trong colab_jobs/06_paddleocr_vietocr_shard0/notebook.ipynb Cell 4)
  KHÔNG cần cách ly --target như trên Kaggle/Colab — venv local của repo này CHƯA có torch/paddle
  xung đột từ trước (khác Kaggle site-packages gốc đã bị hỏng sẵn), cài thẳng bình thường được. Nếu
  sau này venv dính xung đột NCCL/torch tương tự Kaggle, xem cách xử lý ở kaggle_jobs/06_paddleocr_ocr/
  main.py (SỬA LẦN 5) để áp dụng lại kiểu cách ly --target.

CÁCH DÙNG BACKUP (khi 1 shard Colab bị kẹt vì hết giờ):
  1. Trên Colab, tải thư mục output dở dang từ Drive
     (MyDrive/aic2026_ocr_output/ocr_text_paddleocr_vietocr_shard{N}/) về máy.
  2. Đặt các file .jsonl đó vào data/extracted/ocr_shard{N}/ (TRÙNG tên với --shard N bên dưới).
  3. Chạy lệnh dưới — script tự đọc file đã có, bỏ qua "n" đã xong, xử lý tiếp phần còn thiếu.
  4. Xong thì output đã nằm sẵn ở data/extracted/ocr_shard{N}/ — đúng nơi scripts/merge_ocr.py cần,
     không cần thao tác gì thêm để gộp.

Usage:
  .venv\\Scripts\\python.exe scripts\\run_ocr_shard_local.py --shard 0               # chạy full shard 0
  .venv\\Scripts\\python.exe scripts\\run_ocr_shard_local.py --shard 0 --smoke-test   # 2 video x 10 ảnh để đo giây/frame thật trước
"""

import sys
import json
import time
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# UTF-8 cho console Windows — log có dấu tiếng Việt (giống run_caption_shard_local.py).
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

TAG = "ocr_local"
TOTAL_SHARDS = 3
SCORE_THRESH = 0.5  # lọc box điểm tin cậy thấp — CHƯA kiểm chứng ngưỡng tối ưu, giá trị khởi điểm hợp lý (xem colab_jobs)

ROOT = Path(__file__).resolve().parent.parent
KEYFRAMES_ROOT = ROOT / "data" / "extracted" / "keyframes"

_DEVICE = None  # set trong main() sau khi torch import được (torch chỉ cần cho VietOCR, không cho paddleocr)


def get_rotate_crop_image(img: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Thuật toán crop chuẩn của PaddleOCR — perspective-warp theo đúng 4 góc box, xoay 90° nếu
    box cao hơn rộng nhiều (chữ dọc). Giống hệt colab_jobs/06_paddleocr_vietocr_shard*/notebook.ipynb."""
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


def sort_boxes_reading_order(dt_polys):
    """Heuristic gom box thành 'hàng' theo tâm y, sort trong hàng theo x — thứ tự đọc tự nhiên.
    Giống hệt colab_jobs — xem giải thích đầy đủ ở đó."""
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
    print(f"[{TAG}] tải TextDetection (PP-OCRv6_medium_det mặc định), thử GPU...")
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
    global _DEVICE
    _DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"[{TAG}] tải VietOCR (vgg_transformer, device={_DEVICE})...")
    config = Cfg.load_config_from_name("vgg_transformer")
    config["device"] = _DEVICE
    predictor = Predictor(config)
    print(f"[{TAG}] Recognizer ready (device={_DEVICE}).")
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

    dt_polys = sort_boxes_reading_order(dt_polys)

    img_bgr = cv2.imread(str(jpg_path))
    if img_bgr is None:
        return ""

    texts = []
    for box in dt_polys:
        box_arr = np.array(box, dtype=np.float32)
        crop_bgr = get_rotate_crop_image(img_bgr, box_arr)
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


def list_videos_for_shard(shard_idx: int):
    """round-robin videos[shard_idx::3] trên danh sách 873 video ĐÃ SORT — GIỐNG HỆT thuật toán
    colab_jobs/06_paddleocr_vietocr_shard*/ và kaggle_jobs/06_paddleocr_ocr_shard*/. Chỉ quét trực
    tiếp keyframes local (không cần manifest — OCR chạy trên TOÀN BỘ frame của video được giao)."""
    found_map: dict[str, list[Path]] = {}
    for jpg in KEYFRAMES_ROOT.rglob("*.jpg"):
        vid_id = jpg.parent.name
        found_map.setdefault(vid_id, []).append(jpg)

    all_videos = []
    for vid_id in sorted(found_map.keys()):
        jpgs = sorted(found_map[vid_id], key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
        all_videos.append((vid_id, jpgs))

    if not all_videos:
        raise FileNotFoundError(f"Không tìm thấy video nào dưới {KEYFRAMES_ROOT}.")

    return all_videos[shard_idx::TOTAL_SHARDS]


def process_video(detector, recognizer, video_id: str, jpgs, output_dir: Path) -> tuple[int, int]:
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shard", type=int, required=True, choices=[0, 1, 2],
                         help="Chỉ số shard (0/1/2) — GIỐNG HỆT SHARD_IDX của colab_jobs/kaggle_jobs")
    parser.add_argument("--smoke-test", action="store_true",
                         help="Chỉ chạy 2 video x 10 ảnh đầu để đo giây/frame thật trước khi chạy full")
    parser.add_argument("--smoke-test-videos", type=int, default=2)
    parser.add_argument("--smoke-test-images", type=int, default=10)
    args = parser.parse_args()

    output_dir = ROOT / "data" / "extracted" / (
        f"smoketest_ocr_shard{args.shard}" if args.smoke_test else f"ocr_shard{args.shard}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{TAG}] ======================================================")
    print(f"[{TAG}] SHARD {args.shard} — chạy LOCAL (backup)")
    print(f"[{TAG}] Output: {output_dir}")
    print(f"[{TAG}] ======================================================")

    detector = load_detector()
    recognizer = load_recognizer()

    videos = list_videos_for_shard(args.shard)
    print(f"[{TAG}] Số video thuộc shard {args.shard} tìm thấy trên máy: {len(videos)}")

    if args.smoke_test:
        videos = [(vid, jpgs[:args.smoke_test_images]) for vid, jpgs in videos[:args.smoke_test_videos]]
        print(f"[{TAG}] SMOKE_TEST: rút xuống {len(videos)} video x {args.smoke_test_images} ảnh.")

    total_frames_target = sum(len(jpgs) for _, jpgs in videos)
    print(f"[{TAG}] Tổng số frame cần xử lý: {total_frames_target:,} frame")

    total_done = 0
    total_error = 0
    t0 = time.time()

    for i, (video_id, jpgs) in enumerate(videos, start=1):
        v_t0 = time.time()
        n_done, n_error = process_video(detector, recognizer, video_id, jpgs, output_dir)
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
