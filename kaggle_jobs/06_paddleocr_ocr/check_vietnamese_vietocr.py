"""
BẢN THỬ NGHIỆM HYBRID — PaddleOCR (chỉ Detection) + VietOCR (Recognition), THAY vì dùng recognizer
mặc định (PP-OCRv6_medium_rec) của PaddleOCR như check_vietnamese.py/check_vietnamese_hires.py.

LÝ DO: 2 lần test trước (check_vietnamese.py gốc, check_vietnamese_hires.py tăng độ phân giải —
KHÔNG có tác dụng, xác nhận bằng diff 75/75 dòng giống hệt nhau) đều cho thấy PaddleOCR ĐỊNH VỊ
đúng vùng có chữ (detection ổn — vẫn ra được text dài, đúng cấu trúc câu), nhưng NHẬN DẠNG KÝ TỰ
(recognition) làm rớt dấu tiếng Việt rất nhiều ở chữ nhỏ/dày đặc. VietOCR (pbcquoc/vietocr,
https://github.com/pbcquoc/vietocr) là model recognition huấn luyện CHUYÊN cho tiếng Việt (không
phải multilingual chung như PP-OCRv6_medium_rec) — thử thay đúng bước recognition, giữ nguyên bước
detection (PaddleOCR TextDetection, model_name mặc định = PP-OCRv6_medium_det, ĐÚNG model mà pipeline
đầy đủ PaddleOCR(lang="vi") đang dùng nội bộ — xác nhận qua log thật lúc load_engine() ở main.py:
"Creating model: ('PP-OCRv6_medium_det', ...)").

QUY TRÌNH: TextDetection.predict() -> dt_polys (4 điểm góc/box) -> cắt ảnh theo từng box bằng
get_rotate_crop_image() (thuật toán chuẩn của PaddleOCR — perspective-warp theo đúng 4 góc, xoay 90°
nếu box cao hơn rộng nhiều, để chữ luôn đọc được theo chiều ngang trước khi đưa vào recognizer) ->
từng crop đưa qua VietOCR Predictor.predict() -> nối lại thành 1 chuỗi/frame, giống định dạng
check_vietnamese.py để so sánh công bằng.

Chạy đúng 25 video/75 frame giống 2 lần test trước (cùng NUM_VIDEOS/FRAMES_PER_VIDEO) để so sánh
1-1 cả 3 cách: (1) PaddleOCR full mặc định, (2) PaddleOCR full + tăng độ phân giải, (3) file này.

Cách chạy: giống hệt 2 file check_vietnamese*.py trước — Kaggle KHÔNG có nút tạo riêng "New Script",
phải mở kernel (mặc định Notebook) -> menu File -> Editor Type -> Script -> dán code này vào.
Settings ⚙️ → Accelerator: T4 (không P100), bật Internet, thêm dataset kiet1106/aic26-frames, Run.
"""

import os
import sys
import subprocess
from pathlib import Path

if "__file__" not in globals():
    raise RuntimeError(
        "Script này BẮT BUỘC chạy dưới dạng Kaggle 'Script' kernel — mở kernel (mặc định Notebook) "
        "-> menu File -> Editor Type -> chọn Script -> dán code này vào. KHÔNG chạy được trong "
        "Notebook (.ipynb) vì biến __file__ không tồn tại trong cell notebook."
    )

TAG = "check_vi_vietocr"
PKG_DIR = Path("/kaggle/working/paddle_pkgs_checkvi_vietocr")  # thư mục riêng, không đụng 2 bản check_vietnamese*.py khác
_ISOLATED_FLAG = "_PADDLE_PKGS_ISOLATED"

NUM_VIDEOS = 25          # số video rải đều trên toàn bộ 873 video — GIỐNG check_vietnamese.py để so sánh công bằng
FRAMES_PER_VIDEO = 3     # số ảnh rải đều trong mỗi video đó (đầu/giữa/cuối)


def _bootstrap_isolated_install_and_reexec() -> None:
    """Giống hệt cơ chế cách ly torch CPU-only trong main.py/check_vietnamese.py — xem giải thích
    đầy đủ ở main.py (SỬA LẦN 5). Thêm 'vietocr' vào danh sách gói cài — package thuần Python +
    torch (dùng chung bản torch CPU-only đã cài cô lập ở trên, vietocr tự chọn cuda qua config khi
    infer, không xung đột gì với torch CPU-only ở bước cài vì infer-time mới thật sự cần cuda).
    LƯU Ý: predictor.py của vietocr tự `import torch` rồi kiểm tra `torch.cuda.is_available()` để
    chọn device — torch CPU-only cài ở đây vẫn báo cuda.is_available()=False dù máy có GPU T4 thật,
    vì bản CPU-only KHÔNG có binding CUDA. Xem ghi chú ở load_recognizer() bên dưới về cách xử lý.

    SỬA (lần chạy thật đầu tiên CRASH): vietocr backbone VGG cần `torchvision` (`from torchvision
    import models`) — KHÔNG liệt kê trực tiếp torchvision trong lệnh pip trước đó, nó chỉ là
    dependency GIÁN TIẾP của vietocr, nên (đúng bug đã ghi trong main.py SỬA LẦN 5:
    `--ignore-installed --target` không đảm bảo cài lại dependency bắc cầu) rơi về torchvision GỐC
    trên site-packages Kaggle (đã hỏng cùng gốc NCCL/nvidia-cu12 với torch gốc) ->
    `AttributeError: partially initialized module 'torchvision' has no attribute 'extension'`.
    Thêm `torchvision` TRỰC TIẾP, cùng --index-url CPU-only với torch (pip tự chọn version khớp cặp
    torch/torchvision trong cùng 1 lệnh resolve)."""
    print(f"[{TAG}] Cài torch+torchvision (CPU-only, riêng) + paddleocr + paddlepaddle-gpu + "
          f"vietocr vào {PKG_DIR} ...")
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
        "torch", "torchvision", "paddleocr==3.7.0", "paddlepaddle-gpu==3.3.0", "vietocr",
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

import cv2  # noqa: E402  (paddleocr/paddlepaddle-gpu đã kéo theo opencv-python, dùng chung)
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

FRAMES_DATASET_REF = "kiet1106/aic26-frames"
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")


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


def list_all_videos(root: Path):
    found_map = {}
    for jpg in root.rglob("*.jpg"):
        vid_id = jpg.parent.name
        found_map.setdefault(vid_id, []).append(jpg)
    videos = []
    for vid_id in sorted(found_map.keys()):
        jpgs = sorted(found_map[vid_id], key=lambda p: int(p.stem) if p.stem.isdigit() else p.stem)
        videos.append((vid_id, jpgs))
    return videos


def pick_sample(videos, num_videos: int, frames_per_video: int):
    """Giống hệt check_vietnamese.py — cùng công thức lấy mẫu để so sánh công bằng."""
    if not videos:
        return []
    stride = max(1, len(videos) // num_videos)
    sampled_videos = videos[::stride][:num_videos]

    sample = []
    for vid_id, jpgs in sampled_videos:
        if not jpgs:
            continue
        if len(jpgs) <= frames_per_video:
            picked = jpgs
        else:
            idxs = [round(i * (len(jpgs) - 1) / (frames_per_video - 1)) for i in range(frames_per_video)]
            picked = [jpgs[i] for i in sorted(set(idxs))]
        for p in picked:
            sample.append((vid_id, p))
    return sample


def load_detector():
    """TextDetection module-level API — model_name mặc định (None) = PP-OCRv6_medium_det, đúng model
    detector mà pipeline PaddleOCR(lang="vi") đầy đủ dùng nội bộ (xác nhận qua log thật của main.py)."""
    from paddleocr import TextDetection
    print(f"[{TAG}] tải TextDetection (model mặc định PP-OCRv6_medium_det), thử device='gpu:0' ...")
    try:
        det = TextDetection(device="gpu:0")
        print(f"[{TAG}] Detector ready (device='gpu:0').")
    except Exception as e:
        print(f"[{TAG}] CẢNH BÁO: device='gpu:0' lỗi ({type(e).__name__}: {e}) — fallback mặc định.")
        det = TextDetection()
        print(f"[{TAG}] Detector ready (fallback).")
    return det


def load_recognizer():
    """VietOCR Predictor — config vgg_transformer (đã có sẵn URL weight pretrained, tự tải lần đầu).
    GHI CHÚ QUAN TRỌNG: torch cài cô lập ở bước bootstrap là bản CPU-only (chủ đích, để tránh lệch
    version nvidia-*-cu12 với torch cu128 có sẵn trên Kaggle — xem main.py "SỬA LẦN 5") — nghĩa là
    dù máy có GPU T4 thật, `torch.cuda.is_available()` vẫn trả False với bản torch này, nên KHÔNG
    thể set config['device']='cuda:0' cho vietocr (sẽ lỗi vì không có CUDA binding). Đặt CPU cho
    riêng bước recognition của vietocr — chấp nhận chậm hơn vì đây chỉ là bài test chất lượng trên
    75 frame, không phải chạy full 177K frame (nếu sau này quyết định dùng hybrid này cho full run,
    cần đổi chiến lược cài torch để có CUDA thật cho vietocr, không nằm trong phạm vi test này)."""
    from vietocr.tool.predictor import Predictor
    from vietocr.tool.config import Cfg

    print(f"[{TAG}] tải VietOCR (config vgg_transformer, device=cpu — xem ghi chú trong code) ...")
    config = Cfg.load_config_from_name("vgg_transformer")
    config["device"] = "cpu"
    predictor = Predictor(config)
    print(f"[{TAG}] Recognizer ready.")
    return predictor


def get_rotate_crop_image(img: np.ndarray, points: np.ndarray) -> np.ndarray:
    """Thuật toán crop chuẩn của PaddleOCR (get_rotate_crop_image) — perspective-warp ảnh theo đúng
    4 góc box phát hiện được (không chỉ cắt bounding-box thẳng, xử lý được cả chữ hơi nghiêng), xoay
    90° nếu box cao hơn rộng nhiều (chữ dọc) để recognizer luôn nhận ảnh chữ nằm ngang."""
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
    dst_img = cv2.warpPerspective(
        img, M, (img_crop_width, img_crop_height),
        borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
    dst_h, dst_w = dst_img.shape[0:2]
    if dst_h * 1.0 / dst_w >= 1.5:
        dst_img = np.rot90(dst_img)
    return dst_img


def ocr_frame(detector, recognizer, jpg_path: Path) -> str:
    """Detection (PaddleOCR) -> crop từng box -> Recognition (VietOCR) -> nối lại 1 chuỗi."""
    result = detector.predict(str(jpg_path))
    if not result:
        return ""
    dt_polys = result[0].get("dt_polys") if hasattr(result[0], "get") else getattr(result[0], "dt_polys", None)
    if dt_polys is None or len(dt_polys) == 0:
        return ""

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


def main():
    input_root = resolve_keyframes_root()
    print(f"[{TAG}] keyframes root: {input_root}")
    videos = list_all_videos(input_root)
    print(f"[{TAG}] tổng số video tìm thấy: {len(videos)}")

    sample = pick_sample(videos, NUM_VIDEOS, FRAMES_PER_VIDEO)
    print(f"[{TAG}] Lấy mẫu {len(sample)} frame rải đều trên {NUM_VIDEOS} video "
          f"({FRAMES_PER_VIDEO} ảnh/video) để kiểm tra dấu tiếng Việt.\n")

    detector = load_detector()
    recognizer = load_recognizer()

    n_empty = 0
    print(f"[{TAG}] ====================== KẾT QUẢ OCR (đọc trực tiếp bên dưới) ======================")
    for vid_id, jpg_path in sample:
        n = jpg_path.stem
        try:
            text = ocr_frame(detector, recognizer, jpg_path)
        except Exception as e:
            print(f"[{TAG}] {vid_id}/{n}: LỖI ({type(e).__name__}: {e})")
            continue
        if not text:
            n_empty += 1
            text = "(không có chữ / không nhận dạng được)"
        print(f"[{TAG}] {vid_id}/{n}: {text}")

    print(f"[{TAG}] ====================================================================================")
    print(f"[{TAG}] XONG. {len(sample)} frame, {n_empty} frame không ra chữ. Đọc trực tiếp các dòng "
          f"phía trên để đánh giá dấu tiếng Việt — không cần tải file.")


if __name__ == "__main__":
    main()
