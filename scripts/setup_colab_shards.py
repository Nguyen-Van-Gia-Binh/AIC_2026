"""
scripts/setup_colab_shards.py — Sinh 3 notebook Colab (colab_jobs/06_paddleocr_vietocr_shard{0,1,2}/
notebook.ipynb) cho PHASE 1 OCR full corpus bằng pipeline HYBRID: PaddleOCR (chỉ detection) + VietOCR
(recognition riêng tiếng Việt) — xác nhận THẮNG RÕ RỆT về chất lượng dấu so với recognizer mặc định
của PaddleOCR qua kaggle_jobs/06_paddleocr_ocr/check_vietnamese_vietocr.py (chạy thật trên Kaggle,
2026-08-26): "hình ch nht" -> "hình chữ nhật", "Tác gi: Tuyt Minh" -> "Tác giả: Tuyết Minh"...

VÌ SAO COLAB (không phải kaggle_jobs/06_paddleocr_ocr_shard*/ đã có sẵn): dự định chạy 3 tài khoản
Google song song, không dùng Kaggle CLI. Kiến trúc Colab KHÁC Kaggle ở vài điểm quan trọng — xem
từng cell trong notebook để biết chi tiết + lý do, tóm tắt:
  - Không cần trick subprocess re-exec + PYTHONPATH như kaggle_jobs (đó là để né lỗi Notebook không
    có `__file__` khi paste vào Kaggle Script kernel) — Colab LUÔN chạy theo cell trong 1 process,
    chỉ cần `sys.path.insert()` thẳng, không cần relaunch subprocess.
  - torch/torchvision KHÔNG bị ép CPU-only như trên Kaggle (ở đó phải né lỗi NCCL vì torch cu128 có
    sẵn trên Kaggle bị hỏng khi paddlepaddle-gpu cài đè lên) — trên Colab, CHỈ cách ly paddleocr +
    paddlepaddle-gpu vào thư mục riêng, giữ nguyên torch/torchvision gốc của Colab cho VietOCR chạy
    THẬT bằng GPU (khác bản test check_vietnamese_vietocr.py trên Kaggle phải chạy VietOCR CPU).
    **CHƯA XÁC NHẬN THẬT trên Colab** — có cell diagnostic riêng kiểm tra torch còn nguyên vẹn sau
    khi cài, đọc kỹ output trước khi chạy full.
  - Ổ đĩa Colab là TẠM THỜI (mất hết khi runtime bị ngắt) — output PHẢI ghi vào Google Drive đã
    mount, không ghi vào /content/ thường (dataset ảnh gốc thì để /content/ vẫn ổn vì tải lại được,
    không cần giữ).
  - Cải thiện thêm so với check_vietnamese_vietocr.py: sắp xếp box theo thứ tự đọc tự nhiên
    (trên->dưới, trái->phải) trước khi nối chuỗi — bản test trước bị xáo trộn thứ tự vì dt_polys trả
    về không theo vị trí. Lọc bớt box điểm tin cậy thấp (dt_scores < 0.5, CHƯA kiểm chứng ngưỡng này
    tối ưu, chỉ là giá trị khởi điểm hợp lý) để giảm chữ rác.

Chia shard: round-robin videos[SHARD_IDX::3] trên danh sách 873 video ĐÃ SORT — GIỐNG HỆT cách chia
kaggle_jobs/06_paddleocr_ocr_shard{0,1,2}/ (291 video/shard, tránh lệch tải vì batch L26 chiếm tới
498/873 video) — nhưng đây là NGUỒN DỮ LIỆU KHÁC (Colab tự tải, không phải Kaggle input mount), nên
không dùng chung code, chỉ dùng chung THUẬT TOÁN chia.

Sau khi sinh notebook: tự upload lên Google Drive của mỗi tài khoản (hoặc mở trực tiếp trong Colab
qua File > Upload notebook), làm theo hướng dẫn ở cell Markdown đầu tiên trong mỗi notebook.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLAB_JOBS_DIR = ROOT / "colab_jobs"

TOTAL_SHARDS = 3

# ────────────────────────────────────────────────────────────────────────────────────────────────
# Nội dung từng cell — __SHARD_IDX__ được thay bằng số thật lúc sinh file.
# ────────────────────────────────────────────────────────────────────────────────────────────────

CELL_INTRO_MD = """\
# AIC2026 — OCR Phase 1 (PaddleOCR detect + VietOCR recognize) — Shard __SHARD_IDX__ / 3

**Chạy theo đúng thứ tự cell từ trên xuống.** Chuẩn bị trước khi chạy:

1. **Runtime > Change runtime type > T4 GPU** (bắt buộc, chưa test CPU-only cho pipeline này).
2. Vào https://www.kaggle.com/settings, mục **API TOKEN** — copy chuỗi token (dạng `KGAT_...`, Kaggle
   hiện cấp thẳng token này, không còn file `kaggle.json` như trước). Dán vào 1 file text, đặt tên
   `aic2026_kaggle_token.txt`, **upload 1 lần duy nhất** lên Google Drive tài khoản này tại đúng
   đường dẫn: `MyDrive/aic2026_kaggle_token.txt` — dùng lại cho mọi lần chạy sau, không cần lặp lại.
   **Không dán token thẳng vào code/notebook** (tránh lộ nếu share notebook cho người khác).
3. Chạy cell **SMOKE_TEST** trước (mặc định đã bật `SMOKE_TEST = True` ở cell cấu hình) để xác nhận
   môi trường ổn (đặc biệt: torch còn nguyên vẹn sau khi cài paddleocr, VietOCR chạy được GPU thật —
   đọc kỹ output 2 cell "CÀI ĐẶT" và "KIỂM TRA SAU CÀI ĐẶT"). Chỉ đổi `SMOKE_TEST = False` sau khi
   smoke-test chạy sạch, không lỗi.
4. Nếu Colab bị ngắt kết nối giữa chừng: mở lại notebook, **Runtime > Run all** — dataset tự tải lại
   (idempotent, bỏ qua nếu đã có), output đã ghi vào Drive tự resume theo `"n"` đã xong, không mất
   tiến độ (trừ đúng frame đang xử lý dở lúc bị ngắt).
"""

CELL_DIAGNOSTIC_1 = """\
# CELL 1 — Kiểm tra môi trường Colab GỐC (trước khi cài gì) — biết baseline torch/CUDA thật của máy
# ảo này, không đoán.
import subprocess
print(subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout)
try:
    import torch
    print("torch (gốc Colab):", torch.__version__, "| cuda build:", torch.version.cuda,
          "| cuda available:", torch.cuda.is_available())
except Exception as e:
    print("torch chưa có sẵn hoặc lỗi:", type(e).__name__, e)
"""

CELL_MOUNT_DRIVE = """\
# CELL 2 — Mount Google Drive (bắt buộc — output phải ghi vào đây, ổ /content/ của Colab mất hết
# khi runtime bị ngắt).
from google.colab import drive
drive.mount("/content/drive")
"""

CELL_DOWNLOAD_DATASET = """\
# CELL 3 — Lấy Kaggle API token từ Drive + tải dataset keyframes (~30GB, vài phút). Idempotent: bỏ
# qua nếu phiên này đã tải rồi (Colab bị ngắt kết nối thì ổ /content/ mất, sẽ tự tải lại khi chạy lại).
# LƯU Ý: Kaggle hiện cấp thẳng 1 API TOKEN dạng "KGAT_..." (Settings > API TOKEN), KHÔNG còn file
# kaggle.json (username+key) như trước — dùng cơ chế access_token của Kaggle CLI (đã xác nhận chạy
# được thật, cùng cách dùng ở máy local trong phiên làm việc này).
import os
import shutil
import subprocess
from pathlib import Path

TOKEN_DRIVE_PATH = "/content/drive/MyDrive/aic2026_kaggle_token.txt"
KAGGLE_DIR = Path(os.path.expanduser("~/.kaggle"))
KAGGLE_DIR.mkdir(parents=True, exist_ok=True)
if not Path(TOKEN_DRIVE_PATH).exists():
    raise FileNotFoundError(
        f"Chưa thấy {TOKEN_DRIVE_PATH} — xem hướng dẫn ở cell Markdown đầu notebook: copy API TOKEN "
        f"từ kaggle.com/settings (dạng KGAT_...), lưu vào file text rồi upload lên đúng đường dẫn "
        f"này trong Drive."
    )
token = Path(TOKEN_DRIVE_PATH).read_text(encoding="utf-8").strip()
access_token_path = KAGGLE_DIR / "access_token"
access_token_path.write_text(token, encoding="utf-8")
os.chmod(access_token_path, 0o600)

subprocess.run(["pip", "install", "-q", "kaggle"], check=True)

DATASET_REF = "kiet1106/aic26-frames"
LOCAL_DATA_DIR = Path("/content/aic26_data")
if not any(LOCAL_DATA_DIR.rglob("keyframes")):
    print("Chưa có dữ liệu trong phiên này — tải + giải nén dataset (~30GB)...")
    LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["kaggle", "datasets", "download", "-d", DATASET_REF, "-p", str(LOCAL_DATA_DIR), "--unzip"],
        check=True,
    )
else:
    print("Dữ liệu đã có sẵn trong phiên này, bỏ qua bước tải.")
"""

CELL_INSTALL_ISOLATED = """\
# CELL 4 — CÀI ĐẶT: chỉ cài paddleocr + paddlepaddle-gpu vào thư mục CÔ LẬP (--target), KHÔNG cài
# torch/torchvision — giữ nguyên bản torch/torchvision GỐC của Colab (đã khớp đúng CUDA runtime máy
# ảo) để VietOCR dùng thẳng, chạy được GPU thật. Khác cách làm trên Kaggle (main.py SỬA LẦN 5) — ở
# đó phải ép torch CPU-only vì torch cu128 có sẵn trên Kaggle BỊ HỎNG khi paddlepaddle-gpu cài đè;
# ĐÃ XÁC NHẬN THẬT trên Colab (shard 0, 2026-08-26): torch/CUDA còn nguyên vẹn sau cài, VietOCR chạy
# GPU thật — GIỮ NGUYÊN đúng lệnh dưới đây, KHÔNG đổi version/index-url dù gặp lỗi khác (vd bị ngắt
# giữa chừng/KeyboardInterrupt — chỉ cần chạy lại y nguyên, không phải lỗi cần "sửa" gói/version).
# Cảnh báo: 1 lần chạy thật đã bị Colab AI tự gợi ý "sửa" nhầm dòng paddlepaddle-gpu (bỏ ghim version,
# đổi sang index cu121 trong khi torch thật là cu128) sau khi thấy KeyboardInterrupt — ĐỪNG áp dụng
# gợi ý auto-fix loại này cho cell này, chỉ cần chạy lại nguyên bản.
import sys
import subprocess
from pathlib import Path

PKG_DIR = Path("/content/paddle_pkgs_isolated")
PKG_DIR.mkdir(parents=True, exist_ok=True)

subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "--target", str(PKG_DIR),
    "--ignore-installed",
    "--timeout", "120", "--retries", "5",
    "--extra-index-url", "https://www.paddlepaddle.org.cn/packages/stable/cu126/",
    "paddleocr==3.7.0", "paddlepaddle-gpu==3.3.0",
], check=True)

if str(PKG_DIR) not in sys.path:
    sys.path.insert(0, str(PKG_DIR))
print("Đã cài paddleocr+paddlepaddle-gpu (cô lập) + thêm vào sys.path.")

# vietocr ghim cứng pillow==10.2.0 (không có wheel dựng sẵn cho Python 3.13 của Colab -> lỗi build
# từ source) — cài --no-deps để giữ nguyên Pillow hiện đại đã có sẵn (đã xác nhận vietocr chạy tốt
# với bản Pillow này ở shard 0, không cần đúng bản pin 10.2.0).
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "vietocr"], check=True)
print("Đã cài vietocr (--no-deps, dùng chung torch/torchvision/Pillow GỐC của Colab).")
"""

CELL_POST_INSTALL_CHECK = """\
# CELL 5 — KIỂM TRA SAU CÀI ĐẶT: xác nhận torch/CUDA còn hoạt động đúng SAU khi cài paddleocr —
# ĐỌC KỸ output cell này trước khi chạy tiếp. Nếu thấy cảnh báo, dừng lại, báo lại kết quả thay vì
# tự chạy full — nghĩa là chiến lược cách ly cần đổi (giống 5 lần sửa đã gặp trên Kaggle).
import torch

print("SAU KHI CÀI — torch:", torch.__version__, "| cuda available:", torch.cuda.is_available())
if not torch.cuda.is_available():
    print("CẢNH BÁO: torch KHÔNG còn thấy CUDA sau khi cài paddleocr/paddlepaddle-gpu/vietocr — "
          "có thể môi trường đã bị phá giống lỗi từng gặp trên Kaggle. VietOCR sẽ chạy CPU (chậm "
          "hơn nhiều cho full run). Thử Runtime > Restart session rồi chạy lại từ đầu, hoặc báo lại "
          "kết quả để đổi chiến lược cài đặt.")
else:
    try:
        x = torch.randn(4, 4, device="cuda")
        print("Test tensor CUDA thật OK, sample:", (x @ x).sum().item())
    except Exception as e:
        print("CẢNH BÁO: is_available()=True nhưng test tensor CUDA lỗi:", type(e).__name__, e)
"""

CELL_PIPELINE_CORE = """\
# CELL 6 — Định nghĩa pipeline: detection (PaddleOCR) + crop + sắp xếp thứ tự đọc + recognition
# (VietOCR). Sắp xếp box theo vị trí (trên->dưới, trái->phải) là ĐIỂM MỚI so với bản test
# check_vietnamese_vietocr.py trên Kaggle (bản đó bị xáo trộn thứ tự vì dùng thẳng thứ tự dt_polys
# trả về, không sort theo vị trí thật trên ảnh).
import json
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def get_rotate_crop_image(img: np.ndarray, points: np.ndarray) -> np.ndarray:
    \"\"\"Thuật toán crop chuẩn của PaddleOCR — perspective-warp theo đúng 4 góc box, xoay 90° nếu
    box cao hơn rộng nhiều (chữ dọc).\"\"\"
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
    \"\"\"Heuristic gom box thành 'hàng' theo tâm y (dung sai = 60% chiều cao box trung bình), sort
    trong từng hàng theo x — cho thứ tự đọc tự nhiên trên->dưới, trái->phải. Không hoàn hảo với bố
    cục phức tạp (nhiều cột) nhưng đủ tốt cho phụ đề/tin tức/credit dạng hàng ngang là chủ yếu.\"\"\"
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
    print("Tải TextDetection (PP-OCRv6_medium_det mặc định), thử GPU...")
    try:
        det = TextDetection(device="gpu:0")
        print("Detector ready (gpu:0).")
    except Exception as e:
        print(f"CẢNH BÁO device='gpu:0' lỗi ({type(e).__name__}: {e}) — fallback mặc định.")
        det = TextDetection()
        print("Detector ready (fallback).")
    return det


def load_recognizer():
    from vietocr.tool.predictor import Predictor
    from vietocr.tool.config import Cfg
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    print(f"Tải VietOCR (vgg_transformer, device={device})...")
    config = Cfg.load_config_from_name("vgg_transformer")
    config["device"] = device
    predictor = Predictor(config)
    print(f"Recognizer ready (device={device}).")
    return predictor


def ocr_frame(detector, recognizer, jpg_path: Path, score_thresh: float = 0.5) -> str:
    result = detector.predict(str(jpg_path))
    if not result:
        return ""
    r0 = result[0]
    dt_polys = r0.get("dt_polys") if hasattr(r0, "get") else getattr(r0, "dt_polys", None)
    dt_scores = r0.get("dt_scores") if hasattr(r0, "get") else getattr(r0, "dt_scores", None)
    if dt_polys is None or len(dt_polys) == 0:
        return ""

    # lọc box điểm tin cậy thấp — CHƯA kiểm chứng ngưỡng 0.5 tối ưu, chỉ là giá trị khởi điểm hợp lý
    # (bản test trước lẫn vài box rác kiểu "Manamesum nonsomentate" nghi từ box điểm thấp).
    if dt_scores is not None and len(dt_scores) == len(dt_polys):
        keep = [i for i, s in enumerate(dt_scores) if s >= score_thresh]
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
            print(f"LỖI recognize 1 box của {jpg_path.name}: {type(e).__name__}: {e}")
            continue
        if text:
            texts.append(str(text).strip())
    return " ".join(texts).strip()


def resolve_keyframes_root() -> Path:
    found = next(LOCAL_DATA_DIR.rglob("keyframes"), None)
    if found is None:
        raise FileNotFoundError(
            f"Không tìm thấy thư mục 'keyframes' dưới {LOCAL_DATA_DIR} — kiểm tra lại CELL 3."
        )
    return found


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


def process_video(detector, recognizer, video_id: str, jpgs, output_dir: Path):
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

    n_done, n_error = 0, 0
    with open(out_path, "a", encoding="utf-8") as f:
        for p in jpgs:
            n = int(p.stem)
            if n in done_n:
                continue
            try:
                text = ocr_frame(detector, recognizer, p)
            except Exception as e:
                print(f"LỖI frame {video_id}/{n}: {e}")
                n_error += 1
                continue
            f.write(json.dumps({"n": n, "ocr_text": text}, ensure_ascii=False) + "\\n")
            f.flush()
            n_done += 1
    return n_done, n_error


print("Đã định nghĩa xong pipeline.")
"""

CELL_CONFIG = """\
# CELL 7 — CẤU HÌNH SHARD (cell DUY NHẤT khác nhau giữa 3 notebook của 3 tài khoản).
SHARD_IDX = __SHARD_IDX__
TOTAL_SHARDS = 3

# Đổi False SAU KHI smoke-test chạy sạch (cell 5 không cảnh báo, cell chạy bên dưới không lỗi).
SMOKE_TEST = True
SMOKE_TEST_NUM_VIDEOS = 2
SMOKE_TEST_NUM_IMAGES = 10

OUTPUT_DIR = Path(
    f"/content/drive/MyDrive/aic2026_ocr_output/ocr_text_paddleocr_vietocr_shard{SHARD_IDX}"
)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
print(f"Shard {SHARD_IDX}/{TOTAL_SHARDS} — output ghi vào: {OUTPUT_DIR}")
"""

CELL_RUN = """\
# CELL 8 — CHẠY. Round-robin videos[SHARD_IDX::TOTAL_SHARDS] trên danh sách 873 video đã sort —
# GIỐNG THUẬT TOÁN chia của kaggle_jobs/06_paddleocr_ocr_shard{0,1,2}/ (291 video/shard đều nhau).
input_root = resolve_keyframes_root()
all_videos = list_all_videos(input_root)
print(f"Tổng video tìm thấy: {len(all_videos)}")

videos = all_videos[SHARD_IDX::TOTAL_SHARDS]
print(f"Video thuộc shard {SHARD_IDX}: {len(videos)}")

if SMOKE_TEST:
    videos = [(vid, jpgs[:SMOKE_TEST_NUM_IMAGES]) for vid, jpgs in videos[:SMOKE_TEST_NUM_VIDEOS]]
    print(f"SMOKE_TEST: rút xuống {len(videos)} video x {SMOKE_TEST_NUM_IMAGES} ảnh")

detector = load_detector()
recognizer = load_recognizer()

total_done, total_error = 0, 0
t0 = time.time()
for i, (video_id, jpgs) in enumerate(videos, start=1):
    v_t0 = time.time()
    n_done, n_error = process_video(detector, recognizer, video_id, jpgs, OUTPUT_DIR)
    v_elapsed = time.time() - v_t0
    total_done += n_done
    total_error += n_error
    spf = (v_elapsed / n_done) if n_done else float("nan")
    print(f"[{i}/{len(videos)}] {video_id}: {n_done} frame mới, {n_error} lỗi, "
          f"{v_elapsed:.1f}s ({spf:.3f}s/frame)")

elapsed = time.time() - t0
print(f"XONG. {total_done} frame mới, {total_error} lỗi, {elapsed:.0f}s tổng.")
if total_done:
    spf = elapsed / total_done
    total_frames_shard = sum(len(j) for _, j in all_videos[SHARD_IDX::TOTAL_SHARDS])
    print(f">>> {spf:.3f}s/frame trung bình — ước cả shard ({total_frames_shard:,} frame): "
          f"{spf * total_frames_shard / 3600:.2f} giờ GPU (SMOKE_TEST chưa đại diện đủ nếu đang "
          f"bật — chỉ tham khảo nhanh)")
"""


def _code_cell(source: str) -> dict:
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source}


def _md_cell(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def build_notebook(shard_idx: int) -> dict:
    cells = [
        _md_cell(CELL_INTRO_MD.replace("__SHARD_IDX__", str(shard_idx))),
        _code_cell(CELL_DIAGNOSTIC_1),
        _code_cell(CELL_MOUNT_DRIVE),
        _code_cell(CELL_DOWNLOAD_DATASET),
        _code_cell(CELL_INSTALL_ISOLATED),
        _code_cell(CELL_POST_INSTALL_CHECK),
        _code_cell(CELL_PIPELINE_CORE),
        _code_cell(CELL_CONFIG.replace("__SHARD_IDX__", str(shard_idx))),
        _code_cell(CELL_RUN),
    ]
    return {
        "cells": cells,
        "metadata": {
            "accelerator": "GPU",
            "colab": {"name": f"aic2026_ocr_paddleocr_vietocr_shard{shard_idx}", "provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main():
    for shard_idx in range(TOTAL_SHARDS):
        shard_dir = COLAB_JOBS_DIR / f"06_paddleocr_vietocr_shard{shard_idx}"
        shard_dir.mkdir(parents=True, exist_ok=True)
        nb = build_notebook(shard_idx)
        out_path = shard_dir / "notebook.ipynb"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(nb, f, ensure_ascii=False, indent=1)
        print(f"Đã sinh: {out_path}")


if __name__ == "__main__":
    main()
