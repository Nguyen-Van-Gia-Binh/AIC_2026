"""
Kaggle GPU job — OCR (trích văn bản) SHARD 1 / 3 keyframe AIC2026 bằng PaddleOCR (lang="vi").
Sinh ra từ kaggle_jobs/06_paddleocr_ocr/main.py (đã xác nhận CHẠY ĐƯỢC THẬT qua SMOKE_TEST — status
COMPLETE, 0.308s/frame, xem docstring gốc để biết lịch sử 5 lần sửa NCCL/cách ly torch) — 3 shard
này CHỈ thêm bước lọc video theo SHARD_IDX (round-robin, KHÔNG cần manifest riêng vì OCR chạy hết mọi
frame của video được giao, không lọc theo semantic như job caption 07). Mỗi file main.py trong 3
thư mục shard là 1 BẢN SAO ĐỘC LẬP — sửa gì ở kaggle_jobs/06_paddleocr_ocr/main.py thì phải tự chép
lại sang cả 3 thư mục này (giống quy ước đã có sẵn ở 07_vintern_caption_shard0/1/2/).

Phần OCR chất lượng dấu tiếng Việt: dùng kaggle_jobs/06_paddleocr_ocr/check_vietnamese.py (file
RIÊNG, dán thẳng vào 1 kernel web để kiểm tra nhanh) — không phải mục đích của 3 file shard này.

Chia shard: 873 video (đã sort theo video_id) chia round-robin videos[SHARD_IDX::3] -> mỗi shard
đúng 291 video — round-robin thay vì cắt liền khối để tránh lệch tải giữa các shard do các batch
L21-L30 có số video rất chênh lệch (L26 riêng đã chiếm 498/873 video).

Input dataset: kiet1106/aic26-frames.
Output (trong /kaggle/working/, tải về bằng `kaggle kernels output`):
  ocr_text_paddleocr_shard1/{video_id}.jsonl -> 1 dòng JSON/frame: {"n": int, "ocr_text": str}
  ocr_text_paddleocr_shard1.zip
Resume: JSONL + flush() ngay mỗi dòng, cộng restore_resume_cache() qua nhiều lần push.
"""

import os
import sys
import json
import time
import shutil
import subprocess
import zipfile
from pathlib import Path

TAG = "ocr_paddleocr_shard1"
SHARD_IDX = 1
TOTAL_SHARDS = 3
PKG_DIR = Path("/kaggle/working/paddle_pkgs")
_ISOLATED_FLAG = "_PADDLE_PKGS_ISOLATED"


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

# Bật True để tự smoke-test riêng shard này (2 video x 10 ảnh) trước khi chạy full — khuyên dùng nếu
# đây là lần push đầu tiên của shard này.
SMOKE_TEST = False
SMOKE_TEST_NUM_VIDEOS = 2
SMOKE_TEST_NUM_IMAGES = 10

FRAMES_DATASET_REF = "kiet1106/aic26-frames"
_FRAMES_OWNER, FRAMES_DATASET_SLUG = FRAMES_DATASET_REF.split("/")
INPUT_BASE = Path("/kaggle/input")
_RUN_TAG = f"smoketest_{TAG}" if SMOKE_TEST else TAG
OUTPUT_DIR = Path(f"/kaggle/working/{_RUN_TAG}")
ZIP_PATH = Path(f"/kaggle/working/{_RUN_TAG}.zip")

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


def list_videos_for_shard(root: Path):
    if not root.exists():
        root = resolve_keyframes_root()
    if not root.exists():
        contents = [str(x) for x in list(INPUT_BASE.rglob("*"))[:30]] if INPUT_BASE.exists() else []
        raise FileNotFoundError(f"Không thấy ảnh trong {INPUT_BASE}. Các file tìm thấy: {contents}")

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

    # round-robin theo SHARD_IDX trên danh sách ĐÃ SORT toàn bộ 873 video — khớp đúng danh sách
    # video_id thấy được trên mọi máy (không phụ thuộc thứ tự rglob), nên 3 shard không trùng/sót
    # video nào miễn TOTAL_SHARDS giống nhau ở cả 3 file.
    return all_videos[SHARD_IDX::TOTAL_SHARDS]


def load_engine():
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
    print(f"[{TAG}] ======================================================")
    print(f"[{TAG}] KHỞI CHẠY SHARD {SHARD_IDX} / {TOTAL_SHARDS}")
    if SMOKE_TEST:
        print(f"[{TAG}] === SMOKE_TEST=True — chỉ chạy {SMOKE_TEST_NUM_VIDEOS} video x "
              f"{SMOKE_TEST_NUM_IMAGES} ảnh. Output ghi vào {OUTPUT_DIR}/ ===")
    print(f"[{TAG}] ======================================================")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    restored = restore_resume_cache()
    if restored:
        print(f"[{TAG}] resume: đã khôi phục {restored} file .jsonl từ dataset input trước đó")

    engine, device_used = load_engine()
    print(f"[{TAG}] device thật đã dùng: {device_used}")
    input_root = resolve_keyframes_root()
    print(f"[{TAG}] keyframes root: {input_root}")
    videos = list_videos_for_shard(input_root)
    print(f"[{TAG}] số video thuộc shard {SHARD_IDX}: {len(videos)}")
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
        n_done, n_error = process_video(engine, video_id, jpgs)
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
    print(f"[{TAG}] HOÀN THÀNH SHARD {SHARD_IDX}! {total_done} frame mới, {total_error} lỗi, "
          f"{elapsed/3600:.2f} giờ. Zip: {ZIP_PATH} ({size_mb:.1f} MB)")
    if total_done:
        spf = elapsed / total_done
        print(f"[{TAG}] >>> {spf:.3f}s/frame trung bình — ước cả shard "
              f"({total_frames_target:,} frame): {spf * total_frames_target / 3600:.2f} giờ GPU.")


if __name__ == "__main__":
    main()
