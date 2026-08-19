"""
build_submission.py — Tạo file CSV + ZIP đúng format BTC AIC2026.

Rules từ tài liệu BTC (docs/Thong tin vong So tuyen AIC2026.md §4):
  - video_id:  KHÔNG có .mp4 (ví dụ: "L21_V001")
  - frame_id:  bắt đầu từ 1 (không phải 0)
  - Tối đa:    100 câu trả lời mỗi query
  - Encoding:  UTF-8
  - Format KIS:   video_id, frame_id
  - Format Q&A:   video_id, frame_id, answer
  - Format TRAKE: video_id, frame_id1, frame_id2, ..., frame_idN (1 dòng = 1 phương án
    trọn vẹn cho cả N mốc, không phải 1 dòng/mốc)
  - Tên file CSV PHẢI giữ nguyên tên file truy vấn gốc BTC cấp, chỉ đổi đuôi
    (vd. "query-1-kis.txt" -> "query-1-kis.csv") — không tự ghép hậu tố.
  - ZIP nộp bài bắt buộc có thư mục con "submission/" chứa toàn bộ CSV, không được nén
    CSV thẳng vào gốc ZIP.

Sử dụng:
    python scripts/submit/build_submission.py
hoặc trong code:
    from scripts.submit.build_submission import build_kis_csv, build_zip_submission
"""

from __future__ import annotations

import csv
import io
import os
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent
SUBMISSIONS_DIR = _ROOT / "submissions"
SUBMISSIONS_DIR.mkdir(exist_ok=True)


# ─── Builder Functions ─────────────────────────────────────────────────────────

def _resolve_csv_filename(filename: str) -> str:
    """
    Chuẩn hoá tên file CSV đích theo đúng yêu cầu BTC: giữ NGUYÊN tên file truy vấn
    gốc, chỉ đổi đuôi thành .csv — không tự ghép hậu tố loại truy vấn.

    Chấp nhận cả tên đã có đuôi (".txt" — lỡ dán nguyên tên BTC cấp, hoặc ".csv") lẫn
    tên không đuôi, luôn trả về đúng 1 đuôi ".csv" duy nhất.
    Ví dụ: "query-1-kis" -> "query-1-kis.csv"; "query-1-kis.txt" -> "query-1-kis.csv".
    """
    stem = filename
    for ext in (".txt", ".csv"):
        if stem.lower().endswith(ext):
            stem = stem[: -len(ext)]
            break
    return f"{stem}.csv"


def build_kis_csv(
    filename: str,
    results: list[dict],
    output_dir: Path = SUBMISSIONS_DIR,
) -> Path:
    """
    Tạo CSV cho truy vấn KIS.

    Args:
        filename: Tên file truy vấn gốc BTC cấp, ví dụ "query-1-kis" (có hoặc không
                  đuôi .txt/.csv đều được) — CSV xuất ra sẽ giữ đúng tên này, chỉ đổi
                  đuôi thành .csv, theo yêu cầu BTC.
        results:  list[dict] từ run_kis(), mỗi item có video_id và frame_id.
                  Tối đa 100 dòng sẽ được ghi (theo rule BTC).
        output_dir: Thư mục đầu ra.

    Returns:
        Path tới file CSV đã tạo.
    """
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / _resolve_csv_filename(filename)

    rows = results[:100]  # hard cap
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for r in rows:
            vid = r["video_id"].replace(".mp4", "")  # chắc chắn không có .mp4
            fid = int(r["frame_id"])                  # đảm bảo là int >= 1
            writer.writerow([vid, fid])

    print(f"[build] KIS CSV: {out_path}  ({len(rows)} rows)")
    return out_path


def build_qa_csv(
    filename: str,
    results: list[dict],
    output_dir: Path = SUBMISSIONS_DIR,
) -> Path:
    """
    Tạo CSV cho truy vấn Q&A.

    Args:
        filename: Tên file truy vấn gốc BTC cấp, ví dụ "query-2-qa" — xem
                  `build_kis_csv` để biết quy tắc đổi đuôi.
        results:  list[dict], phải có thêm key 'answer' (str).
    """
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / _resolve_csv_filename(filename)

    rows = results[:100]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for r in rows:
            vid    = r["video_id"].replace(".mp4", "")
            fid    = int(r["frame_id"])
            answer = str(r.get("answer", ""))
            writer.writerow([vid, fid, answer])

    print(f"[build] Q&A CSV: {out_path}  ({len(rows)} rows)")
    return out_path


def build_trake_csv(
    filename: str,
    results: list[dict],
    output_dir: Path = SUBMISSIONS_DIR,
) -> Path:
    """
    Tạo CSV cho truy vấn TRAKE.

    Args:
        filename: Tên file truy vấn gốc BTC cấp, ví dụ "query-3-trake" — xem
                  `build_kis_csv` để biết quy tắc đổi đuôi.
        results:  list[dict], mỗi item là 1 phương án dự đoán TRỌN VẸN cho cả chuỗi
                  N sự kiện (1 dòng CSV = 1 phương án, không phải 1 dòng/event):
          video_id (str): video được chọn
          frame_ids (list[int]): danh sách frame_id cho từng khoảnh khắc theo thứ tự
    """
    output_dir.mkdir(exist_ok=True)
    out_path = output_dir / _resolve_csv_filename(filename)

    rows = results[:100]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for r in rows:
            vid       = r["video_id"].replace(".mp4", "")
            frame_ids = [int(fid) for fid in r["frame_ids"]]
            writer.writerow([vid] + frame_ids)

    print(f"[build] TRAKE CSV: {out_path}  ({len(rows)} rows)")
    return out_path


def build_zip_submission(
    csv_files: list[Path],
    tag: str = "",
    output_dir: Path = SUBMISSIONS_DIR,
) -> Path:
    """
    Gom các file CSV vào 1 file ZIP để nộp.

    BTC bắt buộc CSV nằm trong 1 thư mục con "submission/" bên trong ZIP — không được
    nén CSV thẳng vào gốc ZIP (docs/Thong tin vong So tuyen AIC2026.md §4.4).

    Args:
        csv_files: Danh sách path tới các file CSV.
        tag:       Nhãn tùy chọn thêm vào tên file (ví dụ "v1", "day1").
        output_dir: Thư mục đầu ra.

    Returns:
        Path tới file zip đã tạo.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    zip_path = output_dir / f"submission{suffix}_{ts}.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for csv_path in csv_files:
            zf.write(csv_path, arcname=f"submission/{csv_path.name}")

    size_kb = zip_path.stat().st_size / 1024
    print(f"[build] ZIP: {zip_path}  ({len(csv_files)} files, {size_kb:.1f} KB)")
    return zip_path


# ─── Demo CLI ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # Import pipeline KIS để demo end-to-end
    _SCRIPTS = Path(__file__).resolve().parent.parent
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))

    from agent.pipeline_kis import run_kis

    demo_queries = [
        ("query-1-kis", "a person giving a speech at a podium"),
        ("query-2-kis", "children playing soccer on a green field"),
    ]

    csv_files = []
    for qid, qtext in demo_queries:
        print(f"\n[demo] Xử lý: {qid!r} — {qtext!r}")
        hits = run_kis(qtext, top_k=5)
        csv_path = build_kis_csv(qid, hits)
        csv_files.append(csv_path)

        # In preview
        print(f"  Nội dung CSV ({csv_path.name}):")
        with open(csv_path, encoding="utf-8") as f:
            for line in f:
                print(f"    {line.rstrip()}")

    zip_path = build_zip_submission(csv_files, tag="demo")
    print(f"\n[demo] Done! ZIP tại: {zip_path}")
