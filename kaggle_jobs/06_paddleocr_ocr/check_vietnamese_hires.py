"""
BẢN THỬ NGHIỆM ĐỘ PHÂN GIẢI — nhân bản từ check_vietnamese.py (xem file gốc để đối chiếu), CHỈ khác
đúng 1 chỗ: load_engine() thêm text_det_limit_side_len=1280, text_det_limit_type="max".

LÝ DO: keyframe gốc AIC2026 là 1280x720 (đã xác nhận: data/extracted/keyframes/L21/L21_V001/001.jpg).
PaddleOCR mặc định giới hạn cạnh dài nhất ảnh đưa vào detector là 960px (limit_type="max" — xác nhận
qua thảo luận chính thức PaddleOCR, WebSearch 2026-08-26) -> ảnh 1280x720 đang bị TỰ ĐỘNG THU NHỎ
xuống ~960x540 trước khi OCR, mất ~25% chi tiết. Nghi đây là nguyên nhân chính khiến chữ nhỏ (phụ đề
chạy, tin tức, đề toán) mất dấu nhiều trong kết quả check_vietnamese.py gốc (chạy 2026-08-26, ví dụ
"hình ch nht" thay vì "hình chữ nhật"). Đặt giới hạn = 1280 (đúng bằng cạnh dài ảnh gốc) để KHÔNG bị
thu nhỏ nữa — không phóng to (limit_type="max" chỉ co lại khi vượt ngưỡng, không phóng to ảnh nhỏ
hơn ngưỡng), chỉ đơn giản là ngừng làm mất chi tiết đã có sẵn. Chạy đúng 25 video/75 frame giống hệt
lần test gốc (cùng seed lấy mẫu tất định NUM_VIDEOS/FRAMES_PER_VIDEO) để so sánh công bằng 1-1.

Kaggle GPU job — KIỂM TRA RIÊNG chất lượng dấu tiếng Việt của PaddleOCR (lang="vi") trên keyframe
AIC2026 thật. File ĐỘC LẬP với main.py (không sharding, không đo giây/frame) — mục đích DUY NHẤT là
in OCR text ra thẳng log Kaggle để đọc bằng mắt, không cần tải file .jsonl về máy (tránh phụ thuộc
`kaggle kernels output`, từng bị rate-limit 429 khi gọi liên tục).

Dùng lại NGUYÊN VẸN cơ chế cài đặt cô lập đã xác nhận CHẠY ĐƯỢC THẬT (SỬA LẦN 5 trong
kaggle_jobs/06_paddleocr_ocr/main.py — torch CPU-only cài trực tiếp vào /kaggle/working/paddle_pkgs,
--timeout/--retries cho wheel paddlepaddle-gpu ~1.9GB) — xem docstring main.py để biết lịch sử 5 lần
sửa nếu cần đối chiếu.

Chọn mẫu: lấy rải rác NUM_VIDEOS video trên toàn bộ 873 video (bước nhảy đều theo danh sách đã sort,
KHÔNG lấy 2-3 video liền kề như SMOKE_TEST của main.py) để tăng khả năng gặp nhiều loại chữ khác nhau
(tin tức, lịch, biển hiệu, phụ đề...) thay vì lặp lại cùng 1 nguồn — mỗi video lấy FRAMES_PER_VIDEO
ảnh rải đều (không chỉ lấy ảnh đầu, tránh toàn frame intro giống nhau).

Cách chạy: Kaggle KHÔNG có nút tạo riêng "New Script" — luôn tạo Notebook trước, rồi phải ĐỔI kiểu
editor bên trong: mở kernel mới (Notebook mặc định) -> menu File (góc trên trái) -> Editor Type ->
chọn "Script" (giao diện đổi từ nhiều cell sang 1 vùng code .py duy nhất) -> xoá code mặc định, dán
TOÀN BỘ nội dung file này vào. Settings ⚙️ → Accelerator: T4 (KHÔNG chọn P100 — xem lý do lỗi P100 ở
mục "Sự cố đã gặp" của kaggle_jobs/README.md), bật Internet, thêm dataset kiet1106/aic26-frames, Run.
NHẦM LẪN ĐÃ GẶP THẬT (2026-08-26): chạy nhầm ở chế độ Notebook 2 lần liên tiếp (kể cả sau khi thêm
guard __file__ dưới đây) vì tưởng có nút tạo Script riêng — không có, phải đổi Editor Type như trên.

VÌ SAO PHẢI LÀ "SCRIPT", KHÔNG PHẢI "NOTEBOOK": script tự gọi lại chính nó qua
`subprocess.run([sys.executable, __file__], ...)` để đổi PYTHONPATH sang thư mục cài cô lập (xem
_bootstrap_isolated_install_and_reexec()) — cần biến `__file__` trỏ tới 1 file .py THẬT trên đĩa.
Kernel kiểu "Script" của Kaggle lưu đúng thành file .py nên có `__file__`; kernel kiểu "Notebook"
chạy từng cell qua papermill/ipykernel, KHÔNG có `__file__` -> `NameError: name '__file__' is not
defined` ngay khi gọi hàm trên (đã xác nhận thật khi chạy nhầm Notebook 2026-08-26).
"""

import os
import sys
import subprocess
from pathlib import Path

if "__file__" not in globals():
    raise RuntimeError(
        "Script này BẮT BUỘC chạy dưới dạng Kaggle 'Script' kernel (Create -> New Script), "
        "KHÔNG chạy được trong 'Notebook' (.ipynb) vì biến __file__ không tồn tại trong cell "
        "notebook (cần để tự gọi lại chính mình qua subprocess). Tạo lại kernel mới, chọn đúng "
        "loại Script rồi dán code này vào."
    )

TAG = "check_vi_hires"
PKG_DIR = Path("/kaggle/working/paddle_pkgs_checkvi_hires")  # thư mục riêng, không đụng bản check_vietnamese.py/main.py
_ISOLATED_FLAG = "_PADDLE_PKGS_ISOLATED"

NUM_VIDEOS = 25          # số video rải đều trên toàn bộ 873 video
FRAMES_PER_VIDEO = 3     # số ảnh rải đều trong mỗi video đó (đầu/giữa/cuối, không chỉ lấy ảnh đầu)


def _bootstrap_isolated_install_and_reexec() -> None:
    """Giống hệt _bootstrap_isolated_install_and_reexec() trong main.py — xem giải thích đầy đủ ở đó."""
    print(f"[{TAG}] Cài torch (CPU-only, riêng) + paddleocr + paddlepaddle-gpu vào {PKG_DIR} ...")
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
        "torch", "paddleocr==3.7.0", "paddlepaddle-gpu==3.3.0",
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
    """Rải đều NUM_VIDEOS video trên toàn bộ danh sách (đã sort L21->L30), mỗi video lấy
    FRAMES_PER_VIDEO ảnh rải đều đầu/giữa/cuối — tối đa hoá đa dạng nội dung chữ."""
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


def load_engine():
    from paddleocr import PaddleOCR
    # text_det_limit_side_len=1280 (limit_type="max"): ảnh gốc 1280x720, mặc định paddleocr giới hạn
    # cạnh dài nhất = 960 -> đang bị thu nhỏ mất chi tiết trước khi OCR. Đặt = đúng cạnh dài ảnh gốc
    # để KHÔNG thu nhỏ nữa (limit_type="max" chỉ co lại khi vượt ngưỡng, không tự phóng to) — xem
    # giải thích đầy đủ ở docstring đầu file.
    kwargs = dict(lang="vi", text_det_limit_side_len=1280, text_det_limit_type="max")
    print(f"[{TAG}] tải model PaddleOCR (lang=vi, text_det_limit_side_len=1280/max, "
          f"thử device='gpu:0' trước) ...")
    try:
        engine = PaddleOCR(device="gpu:0", **kwargs)
        print(f"[{TAG}] Ready (device='gpu:0').")
    except Exception as e:
        print(f"[{TAG}] CẢNH BÁO: device='gpu:0' lỗi ({type(e).__name__}: {e}) — fallback mặc định.")
        engine = PaddleOCR(**kwargs)
        print(f"[{TAG}] Ready (fallback).")
    return engine


def ocr_frame(engine, jpg_path: Path) -> str:
    result = engine.predict(str(jpg_path))
    texts = []
    for res in result:
        rec_texts = res.get("rec_texts") if hasattr(res, "get") else getattr(res, "rec_texts", None)
        if rec_texts:
            texts.extend(rec_texts)
    return " ".join(str(t) for t in texts).strip()


def main():
    input_root = resolve_keyframes_root()
    print(f"[{TAG}] keyframes root: {input_root}")
    videos = list_all_videos(input_root)
    print(f"[{TAG}] tổng số video tìm thấy: {len(videos)}")

    sample = pick_sample(videos, NUM_VIDEOS, FRAMES_PER_VIDEO)
    print(f"[{TAG}] Lấy mẫu {len(sample)} frame rải đều trên {NUM_VIDEOS} video "
          f"({FRAMES_PER_VIDEO} ảnh/video) để kiểm tra dấu tiếng Việt.\n")

    engine = load_engine()

    n_empty = 0
    print(f"[{TAG}] ====================== KẾT QUẢ OCR (đọc trực tiếp bên dưới) ======================")
    for vid_id, jpg_path in sample:
        n = jpg_path.stem
        try:
            text = ocr_frame(engine, jpg_path)
        except Exception as e:
            print(f"[{TAG}] {vid_id}/{n}: LỖI ({type(e).__name__}: {e})")
            continue
        if not text:
            n_empty += 1
            text = "(không có chữ / không nhận dạng được)"
        print(f"[{TAG}] {vid_id}/{n}: {text}")

    print(f"[{TAG}] ====================================================================================")
    print(f"[{TAG}] XONG. {len(sample)} frame, {n_empty} frame không ra chữ (bình thường nếu ảnh không "
          f"có text). Đọc trực tiếp các dòng phía trên để đánh giá dấu tiếng Việt — không cần tải file.")


if __name__ == "__main__":
    main()
