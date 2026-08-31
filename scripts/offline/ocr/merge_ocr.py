"""
scripts/offline/ocr/merge_ocr.py — Hợp nhất & kiểm định kết quả OCR (PaddleOCR detect + VietOCR recognize) từ
3 shard Colab (colab_jobs/06_paddleocr_vietocr_shard{0,1,2}/notebook.ipynb).

Quy trình:
  1. Quét các thư mục / zip output tải về từ 3 tài khoản Google (Drive):
     - data/extracted/ocr_shard0/ (hoặc .zip)
     - data/extracted/ocr_shard1/ (hoặc .zip)
     - data/extracted/ocr_shard2/ (hoặc .zip)
  2. Giải nén (nếu là zip) và chuyển toàn bộ file {video_id}.jsonl vào:
     data/extracted/ocr_text_paddleocr/
  3. Kiểm tra tính toàn vẹn (Sanity Check):
     - Đảm bảo đủ 873/873 video (KHÔNG dùng manifest lọc như merge_captions.py — OCR chạy trên TOÀN
       BỘ keyframe, không phải tập con đã lọc, nên đối chiếu trực tiếp với map-keyframes/).
     - Kiểm tra từng dòng JSON: schema {"n": int, "ocr_text": str} (ocr_text CÓ THỂ rỗng — ảnh không
       có chữ là bình thường, không phải lỗi, khác caption luôn phải có nội dung).
     - Vì chia shard theo round-robin (KHÔNG dùng manifest như caption), 1 video_id CHỈ nên xuất hiện
       ở ĐÚNG 1 trong 3 shard — cảnh báo nếu trùng lặp (dấu hiệu chạy nhầm/copy nhầm giữa các shard).
  4. Đóng gói toàn bộ thành data/extracted/ocr_text_paddleocr.zip để lưu trữ & sẵn sàng nạp vào
     Elasticsearch qua scripts/index_ocr_es.py --ocr-jsonl-dir.

Usage:
  .venv\\Scripts\\python.exe scripts\\preprocess\\ocr\\merge_ocr.py
"""

import sys
import json
import zipfile
import shutil
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = ROOT / "data"
EXTRACTED_DIR = DATA_DIR / "extracted"
DEST_DIR = EXTRACTED_DIR / "ocr_text_paddleocr"
FINAL_ZIP = EXTRACTED_DIR / "ocr_text_paddleocr.zip"
MAPKF_DIR = EXTRACTED_DIR / "map-keyframes"


def extract_zips():
    """Tự động giải nén bất kỳ file zip nào của shard OCR tìm thấy."""
    for p in DATA_DIR.rglob("*ocr*shard*.zip"):
        extract_target = p.parent / p.stem
        if not extract_target.exists():
            print(f"[merge_ocr] Đang giải nén: {p.name} -> {extract_target.name}/")
            extract_target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(p, "r") as zf:
                zf.extractall(extract_target)


def main():
    print("=" * 70)
    print("BẮT ĐẦU HỢP NHẤT DỮ LIỆU OCR TỪ CÁC SHARD COLAB")
    print("=" * 70)

    extract_zips()
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # Tìm file .jsonl — CHỈ trong thư mục có tên chứa cả "ocr" và "shard" (vd ocr_shard0,
    # ocr_text_paddleocr_vietocr_shard1), KHÔNG quét toàn bộ data/ như merge_captions.py — tránh vô
    # tình gom nhầm caption_shard*/ (field "caption", không phải "ocr_text", cùng nằm chung dưới
    # data/extracted/) vào đây. GHI NHỚ shard nào chứa video_id nào để phát hiện trùng lặp (round
    # -robin không nên trùng, đáng cảnh báo nếu có sai sót khi tải/copy nhầm giữa 3 tài khoản).
    jsonl_sources: dict[str, list[Path]] = {}
    for d in DATA_DIR.rglob("*"):
        if not d.is_dir():
            continue
        name_lower = d.name.lower()
        if "ocr" not in name_lower or "shard" not in name_lower:
            continue
        if DEST_DIR in d.parents or d == DEST_DIR:
            continue
        for p in d.glob("*.jsonl"):
            jsonl_sources.setdefault(p.stem, []).append(p)

    print(f"[merge_ocr] Tìm thấy {len(jsonl_sources)} video_id có file .jsonl từ các nguồn shard.")

    duplicated = {vid: paths for vid, paths in jsonl_sources.items() if len(paths) > 1}
    if duplicated:
        print(f"⚠️ CẢNH BÁO: {len(duplicated)} video_id xuất hiện ở NHIỀU HƠN 1 shard (dùng file "
              f"đầu tiên tìm thấy, kiểm tra lại xem có tải/copy nhầm giữa 3 tài khoản không):")
        for vid, paths in list(duplicated.items())[:10]:
            print(f"   {vid}: {[str(p) for p in paths]}")

    copied = 0
    for vid_id, src_paths in sorted(jsonl_sources.items()):
        dst_path = DEST_DIR / f"{vid_id}.jsonl"
        shutil.copy2(src_paths[0], dst_path)
        copied += 1

    print(f"[merge_ocr] Đã hợp nhất {copied} file vào: {DEST_DIR}")

    print("\n" + "-" * 70)
    print("KIỂM ĐỊNH TÍNH TOÀN VẸN (SANITY CHECK)")
    print("-" * 70)

    merged_files = sorted(DEST_DIR.glob("*.jsonl"))
    merged_vids = {p.stem for p in merged_files}

    expected_vids = set()
    if MAPKF_DIR.exists():
        expected_vids = {p.stem for p in MAPKF_DIR.glob("*.csv")}
        print(f"[Check] Đối chiếu với map-keyframes/: {len(expected_vids)} video (TOÀN BỘ, không "
              f"lọc — OCR chạy hết mọi keyframe, khác caption chỉ chạy tập con đã lọc).")
    else:
        print("[WARN] Không thấy data/extracted/map-keyframes/ để đối chiếu.")

    missing_vids = expected_vids - merged_vids if expected_vids else set()
    if missing_vids:
        print(f"⚠️ CẢNH BÁO: còn thiếu {len(missing_vids)} video chưa có OCR:")
        print(f"   {sorted(missing_vids)[:15]} ...")
    else:
        print(f"✅ ĐẦY ĐỦ: đã có đủ {len(merged_vids)}/873 video!")

    total_valid_frames = 0
    total_empty_ocr = 0
    total_corrupt_lines = 0

    for jsonl_path in merged_files:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    n_val = data.get("n")
                    ocr_val = data.get("ocr_text", "")
                    if n_val is None:
                        total_corrupt_lines += 1
                        continue
                    if not str(ocr_val).strip():
                        total_empty_ocr += 1
                    total_valid_frames += 1
                except Exception:
                    total_corrupt_lines += 1

    print(f"📊 Tổng keyframe hợp lệ: {total_valid_frames:,} frame")
    print(f"   (trong đó {total_empty_ocr:,} frame không có chữ — BÌNH THƯỜNG nếu ảnh không có "
          f"text, không phải lỗi)")
    if total_corrupt_lines > 0:
        print(f"❌ Dòng JSON hỏng: {total_corrupt_lines}")

    print("\n" + "-" * 70)
    print(f"Đang đóng gói toàn bộ vào: {FINAL_ZIP} ...")
    FINAL_ZIP.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(FINAL_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in merged_files:
            zf.write(f, arcname=f"ocr_text_paddleocr/{f.name}")

    zip_size_mb = FINAL_ZIP.stat().st_size / 1e6
    print(f"✅ HOÀN TẤT! File zip tổng: {FINAL_ZIP} ({zip_size_mb:.1f} MB)")
    print(f"   Dùng cho Elasticsearch: --ocr-jsonl-dir {DEST_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
