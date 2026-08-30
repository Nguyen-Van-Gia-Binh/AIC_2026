"""
index_ocr_es.py — Đẩy dữ liệu OCR + caption vào Elasticsearch (scripts/offline/ocr/es_index.py) để phục vụ
tìm kiếm/lọc metadata. Có 3 chế độ:

  1. LIVE (mặc định): tự gọi Qwen2.5-VL (scripts/offline/ocr/vlm_ocr_caption.py) trên từng keyframe local —
     dùng để test nhanh vài ảnh, KHÔNG dùng cho full corpus (xem cảnh báo hiệu năng bên dưới).
  2. --from-jsonl-dir <thư mục>: đọc kết quả .jsonl ĐÃ GHÉP SẴN ocr_text+caption (vd tải về từ
     kaggle_jobs/05_qwen_vl_ocr_caption/ — job cũ, 1 model VLM ra cả 2 trường cùng lúc) rồi index
     thẳng vào ES — KHÔNG load lại VLM, chạy nhanh, không cần GPU.
  3. --ocr-jsonl-dir <thư mục> [--caption-jsonl-dir <thư mục>]: đọc 2 NGUỒN RIÊNG rồi ghép theo "n"
     trước khi index — kiến trúc HIỆN TẠI (thay thế job 05 cũ): OCR toàn bộ keyframe từ
     kaggle_jobs/06_paddleocr_ocr*/ ({"n","ocr_text"}) + caption CHỈ trên tập frame đã lọc từ
     kaggle_jobs/07_vintern_caption*/ ({"n","caption"}). Ghép theo UNION các "n" xuất hiện ở 1 trong
     2 nguồn (OCR phủ hết 177K frame, caption chỉ phủ tập con đã lọc — frame không có caption vẫn
     được index với caption="", KHÔNG bỏ sót vì OCR-only vẫn tìm kiếm được). --caption-jsonl-dir có
     thể bỏ trống nếu muốn index OCR trước, bổ sung caption sau bằng cách chạy lại (không skip vì
     `frame_exists` coi doc đã có là xong — xem ghi chú --no-skip-existing bên dưới nếu cần ghi đè).

Đây là BATCH JOB riêng, chạy tay khi cần (re)build lại index OCR/caption — giống scripts/index.py
(build index CLIP) về vai trò, nhưng KHÔNG import/sửa index.py: script này không cần ma trận
embedding CLIP, chỉ cần metadata keyframe (video_id/n/frame_idx/pts_time/đường dẫn ảnh), nên tự
quét map-keyframes/ + keyframes/ trực tiếp để tránh tải thừa .npy nặng.

CẢNH BÁO HIỆU NĂNG (chế độ LIVE): Qwen2.5-VL-3B trên CPU khá chậm (xem cảnh báo "CHƯA KIỂM CHỨNG"
trong scripts/offline/ocr/vlm_ocr_caption.py) — chạy hết 177.321 keyframe trên máy không có GPU nhiều khả
năng mất rất nhiều giờ/ngày. Dùng --video-id/--limit để test trước. Cho full corpus, dùng chế độ 3
(--ocr-jsonl-dir/--caption-jsonl-dir, đường dùng thật hiện tại) hoặc chế độ 2 cũ.

Resume: --no-skip-existing để tắt (mặc định BẬT resume) — bỏ qua frame đã có document trong ES
(kiểm tra theo id "{video_id}_{n}") để chạy lại an toàn sau khi bị đứt giữa chừng (lỗi mạng, Ctrl+C,
hết pin...), không tốn lại thời gian gọi model/index cho frame đã xong.

Usage (PowerShell):
    # Chế độ LIVE — test nhỏ, KHÔNG dùng cho full corpus:
    .venv\\Scripts\\python.exe scripts\\index_ocr_es.py --video-id L21_V001   # test 1 video
    .venv\\Scripts\\python.exe scripts\\index_ocr_es.py --limit 20            # test 20 frame đầu

    # Chế độ 3 — đường dùng THẬT hiện tại, ghép OCR (job 6) + caption (job 7) đã tải về + giải nén:
    .venv\\Scripts\\python.exe scripts\\index_ocr_es.py ^
        --ocr-jsonl-dir data\\extracted\\ocr_text_paddleocr ^
        --caption-jsonl-dir data\\extracted\\caption_vintern1b

    # Chế độ 2 (cũ) — từ output kaggle_jobs/05_qwen_vl_ocr_caption/ (đã ghép sẵn 1 nguồn):
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

# Chi dat REPO ROOT len sys.path — khong bao gio dat scripts/ (se nap module duoi hai ten,
# nap index/model hai ban). Xem docs/decisions-log.md.
_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DATA_DIR = _ROOT / "data" / "extracted"
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
    from scripts.offline.ocr.vlm_ocr_caption import describe_frame
    from scripts.offline.ocr.es_index import ensure_index, index_frame, frame_exists

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
    from scripts.offline.ocr.es_index import ensure_index, index_frame, frame_exists

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


def _load_n_text_map(jsonl_path: Path, field: str) -> tuple[dict[int, str], int, int]:
    """Đọc 1 file .jsonl dạng {"n": int, <field>: str} (output kaggle_jobs/06.../07...), trả về
    ({n: text}, số dòng hỏng bị bỏ qua, số dòng "n" TRÙNG LẶP trong cùng file). Dùng chung cho cả
    ocr_text và caption vì 2 job ghi cùng 1 schema tối giản (chỉ khác tên field).

    Trùng "n" trong CÙNG 1 file có thể xảy ra nếu cơ chế resume bị lỗi (vd chạy backup ở nơi khác
    — xem PLAN.md — ghi tiếp vào đúng file thay vì file mới, hoặc 2 tiến trình vô tình ghi cùng lúc
    vào 1 file). Giữ dòng XUẤT HIỆN SAU CÙNG (giả định là bản mới/đúng hơn, giống hành vi resume vốn
    có — dòng ghi sau luôn coi là cập nhật), chỉ đếm + cảnh báo ở nơi gọi, không tự fail cả file."""
    result: dict[int, str] = {}
    n_bad = 0
    n_dup = 0
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                n = int(rec["n"])
            except (json.JSONDecodeError, KeyError, ValueError):
                # dòng bị cắt giữa chừng do Kaggle kernel bị ngắt đột ngột lúc đang ghi — cùng cách
                # xử lý với run_from_jsonl() ở trên, không fail cả file.
                n_bad += 1
                continue
            if n in result:
                n_dup += 1
            result[n] = str(rec.get(field, "")).strip()
    return result, n_bad, n_dup


def _merge_ocr_caption(
    ocr_map: dict[int, str], caption_map: dict[int, str]
) -> list[tuple[int, str, str]]:
    """Ghép 2 map {n: text} theo UNION các "n" (KHÔNG phải intersection) — OCR chạy trên TOÀN BỘ
    keyframe, caption chỉ chạy trên tập con đã lọc (Semantic Manifest Filtering), nên 1 "n" có thể
    chỉ xuất hiện ở 1 trong 2 nguồn. Union đảm bảo frame chỉ có OCR (không có caption) vẫn được ghép
    ra (caption="") thay vì bị bỏ sót nếu lỡ dùng intersection. Trả về list đã sort theo "n" tăng
    dần, tách riêng khỏi run_from_split_jsonl() để test được độc lập, không cần Elasticsearch."""
    all_n = sorted(set(ocr_map.keys()) | set(caption_map.keys()))
    return [(n, ocr_map.get(n, ""), caption_map.get(n, "")) for n in all_n]


def run_from_split_jsonl(args) -> None:
    """Chế độ 3 (--ocr-jsonl-dir/--caption-jsonl-dir) — đường dùng THẬT hiện tại, xem docstring đầu
    file. OCR là nguồn CHÍNH (danh sách video_id lấy từ đây, vì OCR phủ toàn bộ 177K keyframe);
    caption chỉ bổ sung nếu có file {video_id}.jsonl trùng tên bên caption-jsonl-dir."""
    from scripts.offline.ocr.es_index import ensure_index, index_frame, frame_exists

    ensure_index()

    ocr_dir = Path(args.ocr_jsonl_dir)
    if not ocr_dir.is_dir():
        raise FileNotFoundError(f"--ocr-jsonl-dir không phải thư mục hợp lệ: {ocr_dir}")
    caption_dir = Path(args.caption_jsonl_dir) if args.caption_jsonl_dir else None
    if caption_dir is not None and not caption_dir.is_dir():
        raise FileNotFoundError(f"--caption-jsonl-dir không phải thư mục hợp lệ: {caption_dir}")

    ocr_files = sorted(ocr_dir.glob("*.jsonl"))
    if args.video_id:
        ocr_files = [p for p in ocr_files if p.stem == args.video_id]
        if not ocr_files:
            raise FileNotFoundError(f"Không thấy {args.video_id}.jsonl trong {ocr_dir}")
    if not ocr_files:
        raise FileNotFoundError(f"Không thấy file .jsonl nào trong {ocr_dir}")

    skip_existing = not args.no_skip_existing
    n_done = 0
    n_skipped = 0
    n_bad_line = 0
    n_dup_line = 0
    n_no_caption = 0
    total_indexed = 0
    t0 = time.time()

    for ocr_path in ocr_files:
        video_id = ocr_path.stem
        meta_map = _load_meta_map(video_id)

        ocr_map, bad_ocr, dup_ocr = _load_n_text_map(ocr_path, "ocr_text")
        n_bad_line += bad_ocr
        n_dup_line += dup_ocr
        if dup_ocr:
            print(f"[index_ocr_es] CẢNH BÁO: {video_id} có {dup_ocr} dòng \"n\" trùng lặp trong "
                  f"{ocr_path.name} (giữ dòng xuất hiện sau cùng) — kiểm tra lại có chạy trùng/ghi "
                  f"nhầm vào cùng file không.")

        caption_map: dict[int, str] = {}
        if caption_dir is not None:
            caption_path = caption_dir / f"{video_id}.jsonl"
            if caption_path.exists():
                caption_map, bad_cap, dup_cap = _load_n_text_map(caption_path, "caption")
                n_bad_line += bad_cap
                n_dup_line += dup_cap
                if dup_cap:
                    print(f"[index_ocr_es] CẢNH BÁO: {video_id} có {dup_cap} dòng \"n\" trùng lặp "
                          f"trong {caption_path.name} (giữ dòng xuất hiện sau cùng).")

        for n, ocr_text, caption in _merge_ocr_caption(ocr_map, caption_map):
            if n not in meta_map:
                print(f"[index_ocr_es] CẢNH BÁO: {video_id} n={n} không có trong "
                      f"map-keyframes, bỏ qua dòng này")
                continue
            if not caption:
                n_no_caption += 1
            if skip_existing and frame_exists(video_id, n):
                n_skipped += 1
                continue

            meta = meta_map[n]
            index_frame(
                video_id=video_id,
                n=n,
                frame_idx=meta["frame_idx"],
                pts_time=meta["pts_time"],
                ocr_text=ocr_text,
                caption=caption,
            )
            n_done += 1
            total_indexed += 1
            if args.limit and total_indexed >= args.limit:
                break
        if args.limit and total_indexed >= args.limit:
            break

    elapsed = time.time() - t0
    print(f"[index_ocr_es] XONG (ocr+caption split). Mới index: {n_done}, bỏ qua (đã có sẵn): "
          f"{n_skipped}, thiếu caption (đã index caption=\"\"): {n_no_caption}, "
          f"dòng hỏng bỏ qua: {n_bad_line}, dòng \"n\" trùng lặp: {n_dup_line}, {elapsed:.0f}s")


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
        help="[Chế độ 2, cũ] Đọc .jsonl ĐÃ GHÉP SẴN ocr_text+caption (vd output "
             "kaggle_jobs/05_qwen_vl_ocr_caption/) — xem docstring đầu file",
    )
    parser.add_argument(
        "--ocr-jsonl-dir", default=None,
        help="[Chế độ 3, đường dùng thật hiện tại] Thư mục .jsonl OCR (output "
             "kaggle_jobs/06_paddleocr_ocr*/, {\"n\",\"ocr_text\"}) — nguồn chính, quyết định danh "
             "sách video xử lý",
    )
    parser.add_argument(
        "--caption-jsonl-dir", default=None,
        help="[Chế độ 3] Thư mục .jsonl caption (output kaggle_jobs/07_vintern_caption*/, "
             "{\"n\",\"caption\"}) — ghép theo \"n\" với --ocr-jsonl-dir, có thể bỏ trống",
    )
    args = parser.parse_args()

    if args.from_jsonl_dir and args.ocr_jsonl_dir:
        parser.error("Chỉ dùng 1 trong 2: --from-jsonl-dir (chế độ 2, cũ) HOẶC --ocr-jsonl-dir "
                      "(chế độ 3, hiện tại) — không dùng cùng lúc.")
    if args.caption_jsonl_dir and not args.ocr_jsonl_dir:
        parser.error("--caption-jsonl-dir chỉ có tác dụng cùng --ocr-jsonl-dir.")

    if args.ocr_jsonl_dir:
        run_from_split_jsonl(args)
    elif args.from_jsonl_dir:
        run_from_jsonl(args)
    else:
        run_live(args)


if __name__ == "__main__":
    main()
