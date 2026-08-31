"""
split_eval_gt.py — Tách file eval_ground_truth.json thành 3 file con theo dạng bài KIS / QA / TRAKE.

Đảm bảo nguyên tắc PHI HUỶ DIỆT (non-destructive):
- Giữ nguyên 100% nội dung gốc của từng entry (không thay đổi giá trị, không tự sửa lỗi).
- Bảo toàn thứ tự xuất hiện gốc trong từng loại.
- Ghi ra UTF-8 chuẩn (ensure_ascii=False, indent=2).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Dict, List


def split_ground_truth(
    source_path: Path | str,
    output_dir: Path | str | None = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Đọc file ground truth tổng hợp và tách thành 3 mảng KIS, QA, TRAKE.
    
    Nếu output_dir được chỉ định, ghi ra:
      - {output_dir}/eval_ground_truth_kis.json
      - {output_dir}/eval_ground_truth_qa.json
      - {output_dir}/eval_ground_truth_trake.json
    """
    src = Path(source_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"Không tìm thấy file ground truth: {src}")

    raw_data = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(raw_data, list):
        raise ValueError(f"Dữ liệu ground truth phải là list các entry, nhận được: {type(raw_data)}")

    buckets: Dict[str, List[Dict[str, Any]]] = {
        "KIS": [],
        "QA": [],
        "TRAKE": [],
    }

    for idx, entry in enumerate(raw_data):
        entry_type = str(entry.get("type", "")).upper()
        if entry_type in buckets:
            buckets[entry_type].append(entry)
        else:
            raise ValueError(f"Entry index {idx} ({entry.get('query_id')}) có type không hợp lệ: {entry_type}")

    if output_dir:
        out_path = Path(output_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        kis_file = out_path / "eval_ground_truth_kis.json"
        qa_file = out_path / "eval_ground_truth_qa.json"
        trake_file = out_path / "eval_ground_truth_trake.json"

        kis_file.write_text(json.dumps(buckets["KIS"], ensure_ascii=False, indent=2), encoding="utf-8")
        qa_file.write_text(json.dumps(buckets["QA"], ensure_ascii=False, indent=2), encoding="utf-8")
        trake_file.write_text(json.dumps(buckets["TRAKE"], ensure_ascii=False, indent=2), encoding="utf-8")

    return buckets


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Tách eval_ground_truth.json thành 3 file KIS/QA/TRAKE.")
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(__file__).resolve().parent / "eval_ground_truth.json",
        help="Đường dẫn file eval_ground_truth.json nguồn",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="Thư mục xuất 3 file con (mặc định cùng thư mục với script)",
    )
    args = parser.parse_args()

    buckets = split_ground_truth(args.source, args.out_dir)
    total = sum(len(v) for v in buckets.values())
    print(f"[OK] Da tach thanh cong {total} entries tu {args.source.name}:")
    print(f"   - KIS:   {len(buckets['KIS'])} entries -> {args.out_dir / 'eval_ground_truth_kis.json'}")
    print(f"   - QA:    {len(buckets['QA'])} entries -> {args.out_dir / 'eval_ground_truth_qa.json'}")
    print(f"   - TRAKE: {len(buckets['TRAKE'])} entries -> {args.out_dir / 'eval_ground_truth_trake.json'}")


if __name__ == "__main__":
    main()
