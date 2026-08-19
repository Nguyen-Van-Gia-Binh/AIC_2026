"""
validate_submission.py — Kiểm tra file submission trước khi nộp cho BTC.

Kiểm tra tất cả rules từ tài liệu BTC AIC2026 (docs/Thong tin vong So tuyen AIC2026.md §4):
  ✅ Encoding UTF-8
  ✅ video_id không có .mp4
  ✅ frame_id là số nguyên >= 1
  ✅ Không quá 100 dòng mỗi file
  ✅ Q&A: answer tối đa 100 ký tự
  ✅ ZIP hợp lệ, chứa CSV nằm trong thư mục con "submission/"
  ✅ Format đúng theo loại query (KIS / Q&A / TRAKE)

Usage:
    python scripts/submit/validate_submission.py path/to/submission.zip
    python scripts/submit/validate_submission.py path/to/query-1-kis.csv
"""

from __future__ import annotations

import csv
import sys
import zipfile
from pathlib import Path


# ─── Validators ───────────────────────────────────────────────────────────────

class ValidationError(Exception):
    pass


def _detect_query_type(stem: str) -> str:
    """
    Đoán loại query từ tên file (bỏ đuôi). BTC đặt tên theo hậu tố nối bằng "-"
    (vd. "query-1-kis"); vẫn nhận diện thêm hậu tố "_" để tương thích ngược với quy
    ước nội bộ cũ. Không đoán được → mặc định "kis" (gọi nơi khác tự cảnh báo).
    """
    low = stem.lower()
    for sep in ("-", "_"):
        if low.endswith(f"{sep}kis"):
            return "kis"
        if low.endswith(f"{sep}qa"):
            return "qa"
        if low.endswith(f"{sep}trake"):
            return "trake"
    return "kis"


def _validate_rows(rows: list[list[str]], query_type: str) -> tuple[list[str], list[str]]:
    """
    Kiểm tra nội dung 1 danh sách dòng CSV đã parse, theo đúng rule của `query_type`.
    Dùng chung cho cả `validate_csv_file` (đọc từ đĩa) và `validate_zip` (đọc từ ZIP).

    Returns:
        (errors, warnings)
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Kiểm tra tối đa 100 dòng
    if len(rows) > 100:
        errors.append(f"❌ Quá 100 dòng: có {len(rows)} dòng (BTC giới hạn 100)")

    for i, row in enumerate(rows, 1):
        if not row:
            warnings.append(f"⚠️  Dòng {i}: rỗng, bỏ qua")
            continue

        # video_id không có .mp4
        video_id = row[0].strip()
        if video_id.lower().endswith(".mp4"):
            errors.append(f"❌ Dòng {i}: video_id có đuôi .mp4 → '{video_id}' (phải bỏ .mp4)")

        if query_type == "kis":
            if len(row) < 2:
                errors.append(f"❌ Dòng {i}: KIS cần ít nhất 2 cột (video_id, frame_id), có {len(row)}")
                continue
            try:
                fid = int(row[1].strip())
                if fid < 1:
                    errors.append(f"❌ Dòng {i}: frame_id={fid} < 1 (BTC đếm frame từ 1)")
            except ValueError:
                errors.append(f"❌ Dòng {i}: frame_id không phải số nguyên → '{row[1]}'")

        elif query_type == "qa":
            if len(row) < 3:
                errors.append(f"❌ Dòng {i}: Q&A cần ít nhất 3 cột (video_id, frame_id, answer), có {len(row)}")
                continue
            try:
                fid = int(row[1].strip())
                if fid < 1:
                    errors.append(f"❌ Dòng {i}: frame_id={fid} < 1")
            except ValueError:
                errors.append(f"❌ Dòng {i}: frame_id không phải số nguyên → '{row[1]}'")
            answer = row[2]
            if not answer.strip():
                warnings.append(f"⚠️  Dòng {i}: answer rỗng")
            elif len(answer) > 100:
                errors.append(f"❌ Dòng {i}: answer dài {len(answer)} ký tự > 100 ký tự cho phép (BTC §4.2)")

        elif query_type == "trake":
            if len(row) < 2:
                errors.append(f"❌ Dòng {i}: TRAKE cần ít nhất 2 cột, có {len(row)}")
                continue
            for j, val in enumerate(row[1:], 1):
                try:
                    fid = int(val.strip())
                    if fid < 1:
                        errors.append(f"❌ Dòng {i}, frame_id #{j}: {fid} < 1")
                except ValueError:
                    errors.append(f"❌ Dòng {i}, frame_id #{j}: không phải số nguyên → '{val}'")

    return errors, warnings


def validate_csv_file(csv_path: Path, query_type: str = "auto") -> list[str]:
    """
    Validate 1 file CSV.

    Args:
        csv_path:   Path tới file CSV.
        query_type: "kis", "qa", "trake", hoặc "auto" (đoán từ tên file).

    Returns:
        list[str]: Danh sách lỗi tìm thấy (rỗng = không có lỗi).
    """
    # 1. Kiểm tra encoding UTF-8
    try:
        content = csv_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        return [f"❌ Encoding không phải UTF-8: {e}"]  # không thể tiếp tục

    # 2. Đoán loại query từ tên file nếu "auto"
    extra_warnings = []
    if query_type == "auto":
        query_type = _detect_query_type(csv_path.stem)
        if not any(csv_path.stem.lower().endswith(f"{sep}{query_type}") for sep in ("-", "_")):
            extra_warnings.append(f"⚠️  Không đoán được loại query từ tên '{csv_path.name}', giả định KIS")

    # 3. Parse CSV
    rows = list(csv.reader(content.splitlines()))
    if len(rows) == 0:
        return ["❌ File rỗng"]

    # 4-5. Kiểm tra số dòng + từng dòng theo loại query
    errors, warnings = _validate_rows(rows, query_type)

    for w in extra_warnings + warnings:
        print(f"  {w}")

    return errors


def validate_zip(zip_path: Path) -> tuple[list[str], list[str]]:
    """
    Validate file ZIP submission.

    Returns:
        (all_errors, all_warnings) — lists of strings
    """
    all_errors = []
    all_warnings = []

    # 1. Kiểm tra ZIP hợp lệ
    if not zipfile.is_zipfile(zip_path):
        return [f"❌ Không phải file ZIP hợp lệ: {zip_path}"], []

    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        csv_names = [n for n in names if n.endswith(".csv")]

        if not csv_names:
            all_errors.append("❌ ZIP không chứa file CSV nào")
            return all_errors, []

        print(f"  [ZIP] Chứa {len(csv_names)} file CSV: {csv_names}")

        # 2. Kiểm tra CSV nằm trong thư mục con "submission/" (bắt buộc theo BTC §4.4,
        #    không được nén CSV thẳng vào gốc ZIP).
        for csv_name in csv_names:
            normalized = csv_name.replace("\\", "/")
            if not normalized.startswith("submission/"):
                all_errors.append(
                    f"❌ {csv_name}: CSV không nằm trong thư mục 'submission/' bên trong ZIP "
                    f"(BTC bắt buộc, xem §4.4) — không được nén CSV thẳng vào gốc ZIP"
                )

        # 3. Validate nội dung từng CSV theo đúng loại query (đoán từ tên file)
        for csv_name in csv_names:
            data = zf.read(csv_name).decode("utf-8", errors="replace")
            rows = list(csv.reader(data.splitlines()))
            if len(rows) == 0:
                all_errors.append(f"❌ {csv_name}: File rỗng")
                continue

            stem = Path(csv_name).stem
            query_type = _detect_query_type(stem)
            errors, warnings = _validate_rows(rows, query_type)
            all_errors.extend(f"{csv_name}: {e}" for e in errors)
            all_warnings.extend(f"{csv_name}: {w}" for w in warnings)

        for w in all_warnings:
            print(f"  {w}")

    return all_errors, all_warnings


def validate_file(path: Path) -> bool:
    """
    Validate 1 file (ZIP hoặc CSV). In kết quả ra terminal.

    Returns:
        True nếu không có lỗi, False nếu có lỗi.
    """
    print(f"\n{'='*60}")
    print(f"Validating: {path}")
    print("="*60)

    if path.suffix.lower() == ".zip":
        errors, _ = validate_zip(path)
    else:
        errors = validate_csv_file(path)

    if errors:
        print(f"\n❌ Tìm thấy {len(errors)} lỗi:")
        for e in errors:
            print(f"  {e}")
        return False
    else:
        print(f"\n✅ Hợp lệ! Không tìm thấy lỗi nào.")
        return True


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Nếu không truyền argument, tự tìm file mới nhất trong submissions/
        sub_dir = Path(__file__).resolve().parent.parent.parent / "submissions"
        files = sorted(sub_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            files = sorted(sub_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            print("Sử dụng: python validate_submission.py <file.zip hoặc file.csv>")
            print(f"Không tìm thấy file nào trong {sub_dir}")
            sys.exit(1)
        target = files[0]
        print(f"[auto] Chọn file mới nhất: {target}")
    else:
        target = Path(sys.argv[1])
        if not target.exists():
            print(f"❌ Không tìm thấy file: {target}")
            sys.exit(1)

    ok = validate_file(target)
    sys.exit(0 if ok else 1)
