"""
scripts/preprocess/captions/merge_captions.py — Hợp nhất & Kiểm định kết quả Caption từ 3 Shard Kaggle.

Quy trình:
  1. Quét các thư mục / zip output tải về từ 3 tài khoản Kaggle:
     - data/extracted/caption_shard0/ (hoặc caption_vintern1b_shard0.zip)
     - data/extracted/caption_shard1/ (hoặc caption_vintern1b_shard1.zip)
     - data/extracted/caption_shard2/ (hoặc caption_vintern1b_shard2.zip)
  2. Giải nén và chuyển toàn bộ file {video_id}.jsonl vào:
     data/extracted/caption_vintern1b/
  3. Kiểm tra tính toàn vẹn (Sanity Check):
     - Đảm bảo đủ 873/873 video (đối chiếu danh sách chuẩn).
     - Kiểm tra từng dòng JSON: schema {"n": int, "caption": str}, caption không rỗng.
     - So sánh số lượng frame thực tế thu được so với manifest đã lọc.
  4. Đóng gói toàn bộ thành data/extracted/caption_vintern1b.zip để lưu trữ & sẵn sàng nạp vào Elasticsearch.

Usage:
  .venv\\Scripts\\python.exe scripts\\preprocess\\captions\\merge_captions.py
"""

import sys
import json
import zipfile
import shutil
from pathlib import Path
import pandas as pd

# Thiết lập UTF-8 cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = ROOT / "data"
EXTRACTED_DIR = DATA_DIR / "extracted"
DEST_DIR = EXTRACTED_DIR / "caption_vintern1b"
FINAL_ZIP = EXTRACTED_DIR / "caption_vintern1b.zip"
MANIFEST_ALL_CSV = DATA_DIR / "manifests" / "manifest_all_selected_frames.csv"

SHARD_SEARCH_PATHS = [
    # Cấu trúc tải chuẩn
    DATA_DIR / "extracted" / "caption_shard0",
    DATA_DIR / "extracted" / "caption_shard1",
    DATA_DIR / "extracted" / "caption_shard2",
    DATA_DIR / "extracted" / "caption_vintern1b_shard0",
    DATA_DIR / "extracted" / "caption_vintern1b_shard1",
    DATA_DIR / "extracted" / "caption_vintern1b_shard2",
    DATA_DIR / "caption_shard0",
    DATA_DIR / "caption_shard1",
    DATA_DIR / "caption_shard2",
]


def extract_zips():
    """Tự động giải nén bất kỳ file zip nào của shard tìm thấy."""
    for p in DATA_DIR.rglob("*caption*shard*.zip"):
        extract_target = p.parent / p.stem
        if not extract_target.exists():
            print(f"[Merge] Đang giải nén: {p.name} -> {extract_target.name}/")
            extract_target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(p, "r") as zf:
                zf.extractall(extract_target)


def main():
    print("=" * 70)
    print("🔄 BẮT ĐẦU HỢP NHẤT DỮ LIỆU CAPTION TỪ CÁC SHARD")
    print("=" * 70)

    extract_zips()
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # Tìm tất cả file .jsonl từ các thư mục shard — GHI NHỚ shard nào chứa video_id nào để phát
    # hiện trùng lặp (vd tải/upload nhầm shard giữa 3 tài khoản, hoặc phải chạy backup 1 shard ở
    # nơi khác vì hết giờ Colab — dễ vô tình chạy trùng hoặc gộp nhầm 2 nguồn cho cùng video_id).
    #
    # CHỈ quét thư mục có "caption" trong tên (giống cách merge_ocr.py chỉ quét thư mục có
    # "ocr"+"shard") — KHÔNG quét rglob rộng toàn bộ data/, vì data/extracted/ocr_shard*/ cũng chứa
    # file {video_id}.jsonl (schema {"n","ocr_text"} khác hẳn {"n","caption"}) và trùng tên video_id
    # với caption_shard* ở phần lớn trường hợp (cả 2 đều round-robin trên cùng 873 video) — rglob
    # rộng từng lấy nhầm 10 video từ ocr_shard1/ vào danh sách nguồn caption (phát hiện thật
    # 2026-08-28 qua chính cảnh báo trùng lặp bên dưới, may mắn thứ tự quét vẫn chọn đúng file caption
    # — nhưng không đảm bảo, phải lọc rõ theo tên thư mục thay vì trông cậy thứ tự rglob).
    jsonl_sources: dict[str, list[Path]] = {}
    for d in DATA_DIR.rglob("*"):
        if not d.is_dir() or "caption" not in d.name.lower():
            continue
        if DEST_DIR in d.parents or d == DEST_DIR:
            continue
        for p in d.glob("*.jsonl"):
            vid_id = p.stem
            jsonl_sources.setdefault(vid_id, []).append(p)

    print(f"[Merge] Tìm thấy {len(jsonl_sources)} video_id có file .jsonl từ các nguồn shard.")

    duplicated = {vid: paths for vid, paths in jsonl_sources.items() if len(paths) > 1}
    if duplicated:
        print(f"⚠️ CẢNH BÁO: {len(duplicated)} video_id xuất hiện ở NHIỀU HƠN 1 shard (dùng file "
              f"đầu tiên tìm thấy, kiểm tra lại xem có tải/copy nhầm giữa các tài khoản không):")
        for vid, paths in list(duplicated.items())[:10]:
            print(f"   {vid}: {[str(p) for p in paths]}")

    # Sao chép vào thư mục đích
    copied = 0
    for vid_id, src_paths in sorted(jsonl_sources.items()):
        dst_path = DEST_DIR / f"{vid_id}.jsonl"
        shutil.copy2(src_paths[0], dst_path)
        copied += 1

    print(f"[Merge] Đã hợp nhất {copied} file vào: {DEST_DIR}")

    # Kiểm tra tính toàn vẹn (Sanity Check)
    print("\n" + "-" * 70)
    print("🔍 KIỂM ĐỊNH TÍNH TOÀN VẸN DỮ LIỆU (SANITY CHECK)")
    print("-" * 70)

    merged_files = sorted(DEST_DIR.glob("*.jsonl"))
    merged_vids = {p.stem for p in merged_files}

    expected_vids = set()
    expected_frames = {}
    if MANIFEST_ALL_CSV.exists():
        df_manifest = pd.read_csv(MANIFEST_ALL_CSV)
        expected_vids = set(df_manifest["video_id"].unique())
        for vid, group in df_manifest.groupby("video_id"):
            expected_frames[vid] = set(group["n"].tolist())
        print(f"[Check] Đối chiếu với manifest chuẩn: {len(expected_vids)} video.")
    else:
        print("[WARN] Không thấy manifest_all_selected_frames.csv để đối chiếu chi tiết.")

    missing_vids = expected_vids - merged_vids if expected_vids else set()
    if missing_vids:
        print(f"⚠️ CẢNH BÁO: Còn thiếu {len(missing_vids)} video chưa có caption:")
        print(f"   {sorted(list(missing_vids))[:15]} ...")
    else:
        print(f"✅ ĐẦY ĐỦ: Đã có đủ {len(merged_vids)}/873 video!")

    total_valid_frames = 0
    total_empty_captions = 0
    total_corrupt_lines = 0

    for jsonl_path in merged_files:
        vid = jsonl_path.stem
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    n_val = data.get("n")
                    cap_val = data.get("caption", "").strip()
                    if n_val is None or not cap_val:
                        total_empty_captions += 1
                    else:
                        total_valid_frames += 1
                except Exception:
                    total_corrupt_lines += 1

    print(f"📊 Tổng keyframe hợp lệ: {total_valid_frames:,} frames")
    if total_empty_captions > 0:
        print(f"⚠️ Frame có caption rỗng: {total_empty_captions}")
    if total_corrupt_lines > 0:
        print(f"❌ Dòng JSON hỏng: {total_corrupt_lines}")

    # Đóng gói file ZIP tổng
    print("\n" + "-" * 70)
    print(f"📦 Đang đóng gói toàn bộ vào: {FINAL_ZIP} ...")
    FINAL_ZIP.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(FINAL_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in merged_files:
            zf.write(f, arcname=f"caption_vintern1b/{f.name}")

    zip_size_mb = FINAL_ZIP.stat().st_size / 1e6
    print(f"✅ HOÀN TẤT! File zip tổng: {FINAL_ZIP} ({zip_size_mb:.1f} MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
