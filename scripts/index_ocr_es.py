"""
index_ocr_es.py — Đẩy dữ liệu OCR + caption vào Elasticsearch (agent/tools/es_index.py) để phục vụ
tìm kiếm/lọc metadata. Có 2 chế độ:

  1. LIVE (mặc định): tự gọi Qwen2.5-VL (agent/tools/vlm_ocr_caption.py) trên từng keyframe local —
     dùng để test nhanh vài ảnh, KHÔNG dùng cho full corpus (xem cảnh báo hiệu năng bên dưới).
  2. --from-jsonl-dir <thư mục>: đọc kết quả .jsonl đã sinh sẵn (vd tải về từ
     kaggle_jobs/05_qwen_vl_ocr_caption/ sau khi chạy trên Kaggle GPU) rồi index thẳng vào ES —
     KHÔNG load lại Qwen2.5-VL, chạy nhanh, không cần GPU. Đây là đường dùng THẬT cho full corpus,
     vì chế độ LIVE trên CPU không khả thi ở quy mô 177K keyframe.

Đây là BATCH JOB riêng, chạy tay khi cần (re)build lại index OCR/caption — giống scripts/index.py
(build index CLIP) về vai trò, nhưng KHÔNG import/sửa index.py: script này không cần ma trận
embedding CLIP, chỉ cần metadata keyframe (video_id/n/frame_idx/pts_time/đường dẫn ảnh), nên tự
quét map-keyframes/ + keyframes/ trực tiếp để tránh tải thừa .npy nặng.

CẢNH BÁO HIỆU NĂNG (chế độ LIVE): Qwen2.5-VL-3B trên CPU khá chậm (xem cảnh báo "CHƯA KIỂM CHỨNG"
trong agent/tools/vlm_ocr_caption.py) — chạy hết 177.321 keyframe trên máy không có GPU nhiều khả
năng mất rất nhiều giờ/ngày. Dùng --video-id/--limit để test trước. Cho full corpus, dùng
kaggle_jobs/05_qwen_vl_ocr_caption/ (chạy trên Kaggle GPU, theo đúng quy ước ở
kaggle_jobs/README.md — Claude không tự push job GPU thật) rồi tải .jsonl về và chạy chế độ
--from-jsonl-dir ở đây.

Resume: --no-skip-existing để tắt (mặc định BẬT resume) — bỏ qua frame đã có document trong ES
(kiểm tra theo id "{video_id}_{n}") để chạy lại an toàn sau khi bị đứt giữa chừng (lỗi mạng, Ctrl+C,
hết pin...), không tốn lại thời gian gọi model/index cho frame đã xong.

Usage (PowerShell):
    # Chế độ LIVE — test nhỏ, KHÔNG dùng cho full corpus:
    .venv\\Scripts\\python.exe scripts\\index_ocr_es.py --video-id L21_V001   # test 1 video
    .venv\\Scripts\\python.exe scripts\\index_ocr_es.py --limit 20            # test 20 frame đầu

    # Chế độ từ output Kaggle job (đường dùng thật cho full corpus) — giải nén
    # ocr_caption_qwen25vl.zip tải về từ Kaggle vào 1 thư mục rồi trỏ tới đó:
    .venv\\Scripts\\python.exe scripts\\index_ocr_es.py --from-jsonl-dir data\\extracted\\ocr_caption_qwen25vl
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import pandas as pd

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

DATA_DIR = _SCRIPTS_DIR.parent / "data" / "extracted"
MAPKF_DIR = DATA_DIR / "map-keyframes"
KEYFRAMES_DIR = DATA_DIR / "keyframes"


def _iter_keyframes(video_id_filter: str | None = None):
    """Quét map-keyframes/*.csv + keyframes/ — cùng quy ước dò đường dẫn ảnh (lồng batch trước,
    fallback phẳng) như scripts/index.py:build_index(), viết lại riêng ở đây vì script này không
    cần ma trận embedding. Yield dict: {video_id, n, frame_idx, pts_time, jpg_path}."""
    csv_files = sorted(MAPKF_DIR.glob("*.csv"))
    if video_id_filter:
        csv_files = [p for p in csv_files if p.stem == video_id_filter]
        if not csv_files:
            raise FileNotFoundError(f"Không thấy map-keyframes cho video_id={video_id_filter!r}")

    for csv_path in csv_files:
        video_id = csv_path.stem
        df = pd.read_csv(csv_path)
        batch = video_id.split("_")[0]
        kf_dir_nested = KEYFRAMES_DIR / batch / video_id
        kf_dir_flat = KEYFRAMES_DIR / video_id
        kf_dir = kf_dir_nested if kf_dir_nested.is_dir() else kf_dir_flat
        for _, row in df.iterrows():
            n = int(row["n"])
            jpg_path = kf_dir / f"{n:03d}.jpg"
            if not jpg_path.exists():
                continue
            yield {
                "video_id": video_id,
                "n": n,
                "frame_idx": int(row["frame_idx"]),
                "pts_time": float(row["pts_time"]),
                "jpg_path": jpg_path,
            }


def _load_meta_map(video_id: str) -> dict[int, dict]:
    """Đọc 1 file map-keyframes/{video_id}.csv, trả về {n: {frame_idx, pts_time}} — dùng ở chế độ
    --from-jsonl-dir để tra frame_idx/pts_time cho từng dòng .jsonl (file .jsonl từ Kaggle job chỉ
    có n, không có frame_idx/pts_time vì job đó không cần 2 cột này để OCR/caption)."""
    csv_path = MAPKF_DIR / f"{video_id}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Không thấy map-keyframes cho video_id={video_id!r}: {csv_path}")
    df = pd.read_csv(csv_path)
    return {
        int(row["n"]): {"frame_idx": int(row["frame_idx"]), "pts_time": float(row["pts_time"])}
        for _, row in df.iterrows()
    }


def run_live(args) -> None:
    """Chế độ LIVE — tự gọi Qwen2.5-VL cho từng keyframe (test nhỏ, xem cảnh báo hiệu năng ở
    docstring đầu file)."""
    from agent.tools.vlm_ocr_caption import describe_frame
    from agent.tools.es_index import ensure_index, index_frame, frame_exists

    ensure_index()

    skip_existing = not args.no_skip_existing
    frames = _iter_keyframes(args.video_id)
    if args.limit:
        frames = itertools.islice(frames, args.limit)

    n_done = 0
    n_skipped = 0
    n_error = 0
    t0 = time.time()
    for i, fr in enumerate(frames, start=1):
        doc_id = f"{fr['video_id']}_{fr['n']}"
        if skip_existing and frame_exists(fr["video_id"], fr["n"]):
            n_skipped += 1
            continue
        try:
            result = describe_frame(str(fr["jpg_path"]))
        except Exception as e:
            print(f"[index_ocr_es] LỖI ở {doc_id}: {e}")
            n_error += 1
            continue
        index_frame(
            video_id=fr["video_id"],
            n=fr["n"],
            frame_idx=fr["frame_idx"],
            pts_time=fr["pts_time"],
            ocr_text=result["ocr_text"],
            caption=result["caption"],
        )
        n_done += 1
        if i % 20 == 0:
            elapsed = time.time() - t0
            print(f"[index_ocr_es] {i} frame đã xử lý (mới: {n_done}, skip: {n_skipped}, "
                  f"lỗi: {n_error}), {elapsed:.0f}s trôi qua")

    print(f"[index_ocr_es] XONG. Mới index: {n_done}, bỏ qua (đã có sẵn): {n_skipped}, "
          f"lỗi: {n_error}")


def run_from_jsonl(args) -> None:
    """Chế độ --from-jsonl-dir — đọc .jsonl đã sinh sẵn (vd từ kaggle_jobs/05_qwen_vl_ocr_caption/,
    xem docstring đầu file), KHÔNG load Qwen2.5-VL, chỉ tra cứu metadata + gọi es_index.index_frame().
    Đây là đường DÙNG THẬT cho full corpus."""
    from agent.tools.es_index import ensure_index, index_frame, frame_exists

    ensure_index()

    jsonl_dir = Path(args.from_jsonl_dir)
    if not jsonl_dir.is_dir():
        raise FileNotFoundError(f"--from-jsonl-dir không phải thư mục hợp lệ: {jsonl_dir}")

    jsonl_files = sorted(jsonl_dir.glob("*.jsonl"))
    if args.video_id:
        jsonl_files = [p for p in jsonl_files if p.stem == args.video_id]
        if not jsonl_files:
            raise FileNotFoundError(f"Không thấy {args.video_id}.jsonl trong {jsonl_dir}")
    if not jsonl_files:
        raise FileNotFoundError(f"Không thấy file .jsonl nào trong {jsonl_dir}")

    skip_existing = not args.no_skip_existing
    n_done = 0
    n_skipped = 0
    n_bad_line = 0
    t0 = time.time()
    total_indexed = 0

    for jsonl_path in jsonl_files:
        video_id = jsonl_path.stem
        meta_map = _load_meta_map(video_id)

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    n = int(rec["n"])
                except (json.JSONDecodeError, KeyError, ValueError):
                    # dòng bị cắt giữa chừng do Kaggle kernel bị ngắt đột ngột lúc đang ghi — bỏ
                    # qua, không fail cả file (cùng cách xử lý với process_video() bên phía
                    # kaggle_jobs/05_qwen_vl_ocr_caption/main.py).
                    n_bad_line += 1
                    continue

                if n not in meta_map:
                    print(f"[index_ocr_es] CẢNH BÁO: {video_id} n={n} không có trong "
                          f"map-keyframes, bỏ qua dòng này")
                    continue

                if skip_existing and frame_exists(video_id, n):
                    n_skipped += 1
                    continue

                meta = meta_map[n]
                index_frame(
                    video_id=video_id,
                    n=n,
                    frame_idx=meta["frame_idx"],
                    pts_time=meta["pts_time"],
                    ocr_text=str(rec.get("ocr_text", "")).strip(),
                    caption=str(rec.get("caption", "")).strip(),
                )
                n_done += 1
                total_indexed += 1
                if args.limit and total_indexed >= args.limit:
                    break
        if args.limit and total_indexed >= args.limit:
            break

    elapsed = time.time() - t0
    print(f"[index_ocr_es] XONG (from-jsonl-dir). Mới index: {n_done}, bỏ qua (đã có sẵn): "
          f"{n_skipped}, dòng hỏng bỏ qua: {n_bad_line}, {elapsed:.0f}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", default=None, help="Chỉ xử lý 1 video (vd L21_V001)")
    parser.add_argument("--limit", type=int, default=None, help="Giới hạn số keyframe (để test)")
    parser.add_argument(
        "--no-skip-existing", action="store_true",
        help="Không bỏ qua frame đã có trong ES (mặc định BẬT resume, sẽ bỏ qua)",
    )
    parser.add_argument(
        "--from-jsonl-dir", default=None,
        help="Đọc .jsonl đã sinh sẵn (vd tải từ Kaggle job) thay vì tự gọi Qwen2.5-VL — "
             "xem docstring đầu file",
    )
    args = parser.parse_args()

    if args.from_jsonl_dir:
        run_from_jsonl(args)
    else:
        run_live(args)


if __name__ == "__main__":
    main()
