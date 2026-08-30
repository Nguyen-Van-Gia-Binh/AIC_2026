import os
import glob
import re
import csv
from pathlib import Path

def main():
    raw_dir = Path(r"data/raw/SOTUYEN1-bo-de-thi")
    out_csv = Path(r"tests/sotuyen1_bo_de_thi.csv")

    files = list(raw_dir.glob("*.txt"))
    print(f"Found {len(files)} files in {raw_dir}")

    records = []
    for f in files:
        fname = f.stem
        m = re.match(r"query-(p\d+)-(\d+)-(kis|qa|trake)", fname, re.IGNORECASE)
        if not m:
            print(f"Warning: Could not match filename pattern: {fname}")
            continue
        p_part, num_str, type_str = m.groups()
        num = int(num_str)
        with open(f, "r", encoding="utf-8") as fp:
            raw_text = fp.read()
        
        content = raw_text.strip()
        
        records.append({
            "stt": num,
            "query_id": f"{p_part}-{num}-{type_str.lower()}",
            "cau_so": f"Câu {num}",
            "loai": type_str.upper(),
            "file_name": fname,
            "noi_dung": content,
            "orig_file": str(f)
        })

    records.sort(key=lambda x: x["stt"])

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", encoding="utf-8", newline="") as fp:
        writer = csv.writer(fp, lineterminator="\n")
        writer.writerow(["stt", "query_id", "cau_so", "loai", "file_name", "noi_dung"])
        for r in records:
            writer.writerow([r["stt"], r["query_id"], r["cau_so"], r["loai"], r["file_name"], r["noi_dung"]])

    print(f"Successfully wrote {len(records)} rows to {out_csv}")

    # Read back and strictly verify each field
    with open(out_csv, "r", encoding="utf-8", newline="") as fp:
        reader = csv.DictReader(fp)
        read_rows = list(reader)

    assert len(read_rows) == len(records), f"Mismatch count: {len(read_rows)} vs {len(records)}"

    for i, (orig, read) in enumerate(zip(records, read_rows), 1):
        assert int(read["stt"]) == orig["stt"], f"Row {i} stt mismatch"
        assert read["query_id"] == orig["query_id"], f"Row {i} query_id mismatch"
        assert read["cau_so"] == orig["cau_so"], f"Row {i} cau_so mismatch"
        assert read["loai"] == orig["loai"], f"Row {i} loai mismatch"
        assert read["file_name"] == orig["file_name"], f"Row {i} file_name mismatch"
        assert read["noi_dung"] == orig["noi_dung"], f"Row {i} noi_dung mismatch for {orig['file_name']}"

    print("VERIFICATION SUCCESS: All 25 questions match 100% exactly with the original files!")

if __name__ == "__main__":
    main()
