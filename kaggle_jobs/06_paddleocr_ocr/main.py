"""
Kaggle GPU job — OCR (trích văn bản) TOÀN BỘ keyframe AIC2026 bằng PaddleOCR gốc (package
"paddleocr", framework PaddlePaddle, KHÔNG phải "rapidocr" — xem lý do đổi bên dưới). Đây là
PHASE 1 trong chiến lược tách OCR/caption:
  Phase 1 (job này): OCR toàn bộ 177.321 keyframe.
  Phase 2 (kaggle_jobs/07_vintern_caption/): caption tiếng Việt bằng Vintern-1B, CHỈ trên tập frame
    đã lọc (xem scripts/experiments/analyze_frame_similarity.py) — đã smoke-test: 2.64s/frame.
  Merge: scripts/index_ocr_es.py ghép ocr_text (Phase 1) + caption (Phase 2) theo "n" trước khi đẩy
    vào Elasticsearch — CHƯA sửa.

LÝ DO đổi từ rapidocr (kaggle_jobs/06_rapidocr_ocr/, đã xoá) sang paddleocr: rapidocr không có model
tiếng Việt riêng, LangRec.LATIN đọc được nhưng dấu thanh điệu tiếng Việt SAI/MẤT không nhất quán
(xác nhận thật qua SMOKE_TEST 2026-08-23, vd "TÌNH TRẠNG"→"TINH TRANG", "Ở"→"Ò", "Đ"→"D",
"QUỐC"→"QUÖC"). paddleocr có model "vi" chính thức (xác nhận qua doc PaddleOCR:
docs/version2.x/ppocr/blog/multi_languages.en.md, dòng "Vietnamese | vi |").

CÀI ĐẶT — SỬA 2026-08-24 LẦN 4 (3 lần trước đều lỗi thật khi chạy):
  Lần 1: cài paddlepaddle-gpu (cu126) THẲNG vào site-packages gốc của Kaggle — pip cảnh báo xung đột
    (torch 2.10.0+cu128 cần nvidia-*-cu12==12.8.x, bị ghi đè xuống 12.6.x) nhưng vẫn cài, rồi chính
    script `import torch` để check CUDA → crash `undefined symbol: ncclCommShrink`.
  Lần 2: bỏ `import torch` trong script — vẫn crash Y HỆT, vì `paddleocr` tự kéo theo `modelscope`
    (qua paddlex), và `modelscope/utils/torch_utils.py` tự `import torch` KHÔNG lazy — torch có sẵn
    trên máy đã bị hỏng từ bước cài paddlepaddle-gpu nên vẫn dính, dù code CỦA MÌNH không đụng torch.
  Lần 3: thử tạo virtualenv riêng (system_site_packages=False) — venv.create() tự crash ngay khi
    bootstrap pip: `ensurepip --upgrade` trả exit code 1 (nhiều khả năng image Kaggle không có sẵn
    wheel ensurepip bundled, không rõ lý do chính xác — lỗi xảy ra quá nhanh (~1.5s) để có traceback
    chi tiết từ chính ensurepip).
  Lần 4 (không cần venv/ensurepip): dùng `pip install --target <thư mục riêng>
  --ignore-installed` để cài paddleocr+paddlepaddle-gpu (và mọi dependency, gồm cả 1 bản torch mới
  do modelscope kéo theo) vào /kaggle/working/paddle_pkgs — TÁCH BIỆT hoàn toàn khỏi site-packages
  gốc (pip --target không đụng/ghi đè gì vào site-packages gốc, khác hẳn lần 1 cài thẳng). Gọi lại
  chính file này bằng CÙNG python gốc (không cần python riêng của venv) nhưng với biến môi trường
  PYTHONPATH chèn /kaggle/working/paddle_pkgs lên ĐẦU — Python ưu tiên PYTHONPATH trước site-packages
  gốc trong sys.path, nên `import torch`/`import paddleocr` sẽ tự động lấy bản mới cô lập, không
  chạm bản hỏng trong site-packages gốc.
  **CHẠY THẬT (2026-08-25) VẪN CRASH** — log xác nhận traceback dừng ở
  `/usr/local/lib/python3.12/dist-packages/torch/__init__.py` (site-packages GỐC, không phải
  `paddle_pkgs/torch/`), cùng lỗi `undefined symbol: ncclCommShrink` như lần 1. Đối chiếu traceback:
  `paddle_pkgs/modelscope/__init__.py` (module modelscope) ĐÃ cài đúng vào thư mục cô lập — cách ly
  hoạt động cho modelscope — nhưng `modelscope/utils/torch_utils.py` gọi `import torch` lại rơi về
  bản gốc, nghĩa là **torch không hề tồn tại trong paddle_pkgs/** dù có `--ignore-installed`. Nguyên
  nhân: `--ignore-installed` không đảm bảo pip cài lại mọi dependency BẮC CẦU (transitive, torch chỉ
  được modelscope kéo theo gián tiếp, không nằm trong danh sách gói truyền thẳng cho lệnh pip) vào
  đúng `--target` — đây là hành vi đã biết của pip, không nhất quán giữa các bản.
  SỬA LẦN 5 (lần này): liệt kê `torch` TRỰC TIẾP trong danh sách gói của lệnh pip install (không để
  modelscope kéo theo gián tiếp nữa) — ép nó thành dependency THẲNG nên `--target` chắc chắn cài vào
  `paddle_pkgs/`. Đồng thời chọn bản `torch` CPU-only (`--index-url
  https://download.pytorch.org/whl/cpu`, không kèm hậu tố phiên bản cụ thể) thay vì để pip tự chọn
  bản mặc định trên PyPI (bản Linux mặc định trên PyPI LÀ bản GPU, phụ thuộc đúng nhóm gói
  `nvidia-*-cu12` gây lỗi NCCL ban đầu) — vì torch ở đây CHỈ được `modelscope.utils.torch_utils`
  dùng để kiểm tra `is_dist()`/`is_master()` (không phải để chạy OCR — paddlepaddle-gpu mới là engine
  OCR thật, dùng runtime CUDA riêng của nó, không qua torch), nên bản CPU-only vẫn đủ để import
  thành công mà KHÔNG kéo theo bất kỳ gói `nvidia-*-cu12` nào — loại bỏ hẳn khả năng lệch version
  NCCL/CUDA thay vì phải đoán đúng version cần ghim. **Chưa chạy lại thật để xác nhận.**

Input dataset: kiet1106/aic26-frames — cùng dataset và cách dò path như các job trước.

Output (trong /kaggle/working/, tải về bằng `kaggle kernels output`):
  ocr_text_paddleocr/{video_id}.jsonl -> 1 dòng JSON/frame: {"n": int, "ocr_text": str} (n khớp cột
                                          "n" trong map-keyframes, KHÔNG phải frame_id — xem CLAUDE.md)
  ocr_text_paddleocr.zip              -> nén toàn bộ .jsonl ở trên

API paddleocr v3.7.0 — xác nhận qua doc chính thức (paddleocr.ai, WebFetch 2026-08-24):
  from paddleocr import PaddleOCR
  ocr = PaddleOCR(lang="vi")
  result = ocr.predict(jpg_path)
  for res in result: res.get("rec_texts")   # list[str] text nhận dạng được (score đủ ngưỡng)
Tham số GPU (device="gpu:0") CHƯA xác nhận chắc chắn tên đúng trong bản 3.7.0 — bọc try/except,
fallback về PaddleOCR(lang="vi") mặc định nếu sai.

Resume: JSONL + flush() ngay mỗi dòng, cộng restore_resume_cache() qua nhiều lần push (giống job 05/07).
"""

import os
import sys
import json
import time
import shutil
import subprocess
import zipfile
from pathlib import Path

TAG = "ocr_paddleocr"
PKG_DIR = Path("/kaggle/working/paddle_pkgs")
_ISOLATED_FLAG = "_PADDLE_PKGS_ISOLATED"


def _bootstrap_isolated_install_and_reexec() -> None:
    """Chạy 1 lần ở process GỐC (site-packages Kaggle mặc định, có torch pin cu128 dễ vỡ) — cài
    paddleocr+paddlepaddle-gpu vào PKG_DIR riêng qua `pip install --target --ignore-installed`
    (KHÔNG đụng site-packages gốc, KHÔNG cần venv/ensurepip — xem CÀI ĐẶT ở docstring đầu file), rồi
    gọi lại chính file main.py này bằng CÙNG python nhưng PYTHONPATH ưu tiên PKG_DIR. Không bao giờ
    return — luôn sys.exit() theo exit code của subprocess con."""
    print(f"[{TAG}] Cài torch (CPU-only, riêng) + paddleocr + paddlepaddle-gpu vào thư mục cô lập "
          f"{PKG_DIR} (--target --ignore-installed, không đụng site-packages gốc)...")
    PKG_DIR.mkdir(parents=True, exist_ok=True)
    # torch chỉ để modelscope.utils.torch_utils import được (is_dist()/is_master(), KHÔNG dùng để
    # chạy OCR — paddlepaddle-gpu mới là engine OCR thật). Liệt kê torch TRỰC TIẾP (không để
    # modelscope kéo theo gián tiếp) vì --ignore-installed không đảm bảo cài lại dependency bắc cầu
    # vào đúng --target (xác nhận thật qua log lần chạy trước — xem "SỬA LẦN 5" ở docstring đầu
    # file). Ép bản CPU-only qua --index-url riêng để torch KHÔNG kéo theo nhóm gói nvidia-*-cu12
    # (nguồn gốc lỗi `undefined symbol: ncclCommShrink` ở các lần sửa trước) — cài trong 1 lệnh
    # pip install duy nhất, --extra-index-url PyPI + paddle repo để paddleocr/paddlepaddle-gpu vẫn
    # resolve được (chỉ torch mới bị ép về index CPU-only).
    subprocess.run([
        sys.executable, "-m", "pip", "install", "-q",
        "--target", str(PKG_DIR),
        "--ignore-installed",
        # wheel paddlepaddle-gpu ~1.9GB — pip mặc định chỉ chờ 15s/lần đọc socket, không đủ nếu CDN
        # (paddle-whl.cdn.bcebos.com) khựng vài giây giữa chừng (đã dính ReadTimeoutError thật ở lần
        # chạy trước, không liên quan gì tới phần cách ly torch). Nới timeout + thêm retry cho bền.
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
    # không bao giờ chạy tới đây — _bootstrap_isolated_install_and_reexec() luôn sys.exit()

# ── Từ đây trở xuống CHỈ chạy trong process con (PYTHONPATH đã ưu tiên PKG_DIR) ─────────────────

# ── CHẾ ĐỘ SMOKE-TEST: đổi SMOKE_TEST = True rồi push để đo giây/frame THẬT + xem chất lượng dấu
# tiếng Việt thật trước khi chạy full.
SMOKE_TEST = True
SMOKE_TEST_NUM_VIDEOS = 2
SMOKE_TEST_NUM_IMAGES = 10

FRAMES_DATASET_REF = "kiet1106/aic26-frames"
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
_RUN_TAG = f"smoketest_{TAG}" if SMOKE_TEST else TAG
OUTPUT_DIR = Path(f"/kaggle/working/{_RUN_TAG}")
ZIP_PATH = Path(f"/kaggle/working/{_RUN_TAG}.zip")

_ENGINE = None
_debug_dumped = False


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


def load_engine():
    """Khởi tạo PaddleOCR(lang="vi") — chạy với PYTHONPATH cô lập, không còn nguy cơ phá torch gốc.
    Thử device="gpu:0" trước, CHƯA xác nhận chắc tên tham số đúng trong 3.7.0 — bọc try/except,
    fallback mặc định (PaddleOCR tự chọn CPU/GPU) nếu sai."""
    from paddleocr import PaddleOCR

    print(f"[{TAG}] tải model PaddleOCR (lang=vi, thử device='gpu:0' trước) ...")
    try:
        engine = PaddleOCR(lang="vi", device="gpu:0")
        device_used = "gpu:0"
        print(f"[{TAG}] Ready (device='gpu:0').")
    except Exception as e:
        print(f"[{TAG}] CẢNH BÁO: khởi tạo với device='gpu:0' thất bại ({type(e).__name__}: {e}) — "
              f"fallback PaddleOCR(lang='vi') mặc định (tự chọn CPU/GPU).")
        engine = PaddleOCR(lang="vi")
        device_used = "mặc định (fallback)"
        print(f"[{TAG}] Ready (fallback).")
    return engine, device_used


def ocr_frame(engine, jpg_path: Path) -> str:
    """Chạy OCR 1 ảnh, trả về text nối lại. Dump cấu trúc result 1 lần đầu ra log — phòng trường
    hợp `res.get("rec_texts")` không đúng key thật của bản paddleocr==3.7.0."""
    global _debug_dumped
    result = engine.predict(str(jpg_path))

    if not _debug_dumped:
        _debug_dumped = True
        n_res = len(result) if hasattr(result, "__len__") else -1
        first_keys = None
        if n_res > 0:
            first = result[0]
            first_keys = list(first.keys()) if hasattr(first, "keys") else dir(first)[:20]
        print(f"[{TAG}] DEBUG result type={type(result).__name__!r}, len={n_res}, "
              f"first_item_keys={first_keys}")

    texts = []
    for res in result:
        rec_texts = res.get("rec_texts") if hasattr(res, "get") else getattr(res, "rec_texts", None)
        if rec_texts:
            texts.extend(rec_texts)
    return " ".join(str(t) for t in texts).strip()


def process_video(engine, video_id: str, jpgs) -> tuple[int, int]:
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
                text = ocr_frame(engine, p)
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
    if SMOKE_TEST:
        print(f"[{TAG}] === SMOKE_TEST=True — chỉ chạy {SMOKE_TEST_NUM_VIDEOS} video x "
              f"{SMOKE_TEST_NUM_IMAGES} ảnh để ĐO GIÂY/FRAME THẬT + KIỂM TRA DẤU TIẾNG VIỆT. "
              f"Output ghi vào {OUTPUT_DIR}/ ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restored = restore_resume_cache()
    if restored:
        print(f"[{TAG}] resume: đã khôi phục {restored} file .jsonl từ dataset input trước đó")

    engine, device_used = load_engine()
    print(f"[{TAG}] device thật đã dùng: {device_used}")
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
        n_done, n_error = process_video(engine, video_id, jpgs)
        v_elapsed = time.time() - v_t0
        total_done += n_done
        total_error += n_error
        sec_per_frame = (v_elapsed / n_done) if n_done else float("nan")
        print(f"[{TAG}] video {i}/{len(videos)} ({video_id}): {n_done} frame mới, {n_error} lỗi, "
              f"{v_elapsed:.1f}s ({sec_per_frame:.3f}s/frame)")

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
        est_full_h = spf * 177_321 / 3600
        print(f"[{TAG}] >>> Giây/frame TRUNG BÌNH thật: {spf:.3f}s/frame — ước full 177.321 frame: "
              f"{est_full_h:.2f} giờ GPU (SMOKE_TEST chưa đại diện đủ — chỉ tham khảo nhanh)")


if __name__ == "__main__":
    main()
