"""
normalize_gt.py — Chuyển bộ ground truth từ format NGƯỜI GHI (v2) sang format HARNESS ĐỌC (v1).

Vì sao có 2 format: người ngồi xem video chỉ tự nhiên ghi được "khoảnh khắc ở keyframe nào" bằng
tiếng Việt. Còn `run_eval.py` / `score_pipelines.py` cần `text_en` (SigLIP mạnh trên tiếng Anh) và
cần một KHOẢNG `[gt_frame_start, gt_frame_end]` để chấm R@k. Thay vì bắt người ghi tự dịch và tự
nghĩ ra khoảng, script này làm phần máy làm được.

    v2 (người ghi)                          v1 (harness)
    ------------------------------------    ------------------------------------
    {"entries": [...]}                      [...]                (mảng ở top-level)
    query_text                              text_vi + text_en    (text_en dịch máy)
    gt_frame: 305                           gt_frame_start = gt_frame_end = 305
    events[].gt_frame                       events[].gt_frame_start/end

KHÔNG TỰ NỚI KHOẢNG. Mặc định `[gt_frame, gt_frame]` — đúng MỘT keyframe, chặt nhất. Nới rộng làm
điểm dễ ăn hơn ⇒ mọi model đều trông giỏi ⇒ mất khả năng phân biệt model tốt/xấu. Chỉ khi người ghi
tự tay nhập thêm `gt_frame_end` (vì thật sự có nhiều keyframe liền kề cùng thể hiện khoảnh khắc)
thì khoảng mới rộng ra. Script không đoán. Xem EVAL_GUIDE.md.

Usage:
    # Chỉ kiểm tra, không ghi gì — chạy cái này TRƯỚC khi gán nhãn nhiều
    .venv\\Scripts\\python.exe tests\\eval\\normalize_gt.py tests\\eval\\eval_ground_truth_v2_template.json --check

    # Chuyển sang format harness
    .venv\\Scripts\\python.exe tests\\eval\\normalize_gt.py <v2.json> --out <v1.json>

    # Chuyển rồi nối thẳng vào bộ eval chính (báo lỗi nếu trùng query_id)
    .venv\\Scripts\\python.exe tests\\eval\\normalize_gt.py <v2.json> --merge tests\\eval\\eval_ground_truth.json

    # Không gọi mạng (dịch máy) — dùng khi chỉ muốn kiểm tra cấu trúc
    ... --no-translate
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # tests/eval/ -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_MAP_KEYFRAMES = _ROOT / "data" / "extracted" / "map-keyframes"

# Danh sách tag độ khó chuẩn — NGUỒN SỰ THẬT DUY NHẤT.
# tests/unit/test_eval_ground_truth.py import lại từ đây, đừng chép thành bản thứ hai.
#
# 11 tag đầu đang được dùng trong eval_ground_truth.json (2026-08-31); 4 tag cuối là các dạng khó
# EVAL_GUIDE.md có nêu nhưng bộ hiện tại chưa có câu nào — để sẵn cho câu mới.
TAG_CHUAN = {
    "temporal_order",        # mô tả phụ thuộc thứ tự thời gian ("trước khi X thì Y")
    "multi_similar_object",  # nhiều đối tượng giống nhau, chỉ khác 1 chi tiết
    "action_sequence",       # chuỗi động tác nối tiếp (chủ yếu TRAKE)
    "small_object",          # đối tượng nhỏ / khuất một phần khung hình
    "short_action",          # hành động rất ngắn giữa video dài
    "fine_detail",           # phải nhìn chi tiết nhỏ mới phân biệt được
    "naming",                # đòi tên riêng / danh từ định danh cụ thể
    "easy_sanity_check",     # câu dễ, để phát hiện hệ thống hỏng
    "counting",              # đếm số lượng (điểm yếu của vision LLM)
    "multi_object",          # nhiều loại đối tượng cùng lúc trong khung
    "image_in_image",        # ảnh lồng trong ảnh / màn hình TV trong khung
    "text_in_frame",         # phải đọc chữ/số in trong khung (cần OCR)
    "negation",              # câu phủ định/loại trừ ("cảnh không có người")
    "local_dialect",         # từ địa phương/viết tắt (thử sức rewrite.py)
    "chart_reading",         # phải đọc biểu đồ/đồ thị
}


# ─── Đọc / ghi ─────────────────────────────────────────────────────────────────

def load_entries(path: Path) -> list[dict]:
    """Nhận cả 2 dạng: v2 `{"entries": [...]}` và v1 `[...]` (mảng trần)."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        entries = data.get("entries")
        if entries is None:
            raise SystemExit(f"[normalize_gt] {path.name}: dict ở top-level nhưng không có khoá 'entries'")
        return entries
    if isinstance(data, list):
        return data
    raise SystemExit(f"[normalize_gt] {path.name}: top-level phải là mảng hoặc {{'entries': [...]}}")


def _valid_frame_ids(video_id: str) -> set[int] | None:
    """Tập frame_id hợp lệ của 1 video (frame_id = frame_idx + 1 — xem index_store.row_to_hit()).

    Trả None nếu không có file map-keyframes (chưa giải nén data/) — khi đó bỏ qua kiểm tra này
    thay vì báo sai cho người dùng.
    """
    path = _MAP_KEYFRAMES / f"{video_id}.csv"
    if not path.exists():
        return None
    import pandas as pd
    df = pd.read_csv(path)
    return {int(v) + 1 for v in df["frame_idx"]}


# ─── Chuyển đổi ────────────────────────────────────────────────────────────────

def _to_en(text_vi: str, translate: bool) -> str:
    """Dịch máy VN→EN. KHÔNG dùng LLM: phải tất định, nếu không thì thước đo tự co giãn."""
    if not translate or not text_vi.strip():
        return ""
    from scripts.agent.tools.translate_raw import translate_raw
    return translate_raw(text_vi)


def _window(entry: dict, key_start: str = "gt_frame_start", key_end: str = "gt_frame_end") -> tuple[int, int]:
    """Suy ra [start, end]. Mặc định = đúng 1 keyframe. KHÔNG tự nới."""
    if key_start in entry and key_end in entry:
        return int(entry[key_start]), int(entry[key_end])
    frame = entry.get("gt_frame")
    if frame is None:
        raise KeyError("gt_frame")
    start = int(frame)
    end = int(entry.get(key_end, start))  # chỉ rộng ra nếu người ghi TỰ nhập gt_frame_end
    return start, end


def convert_entry(entry: dict, translate: bool = True) -> dict:
    """Một entry v2 -> một entry v1. Giữ nguyên mọi field harness cần."""
    qtype = str(entry.get("type", "")).upper()
    text_vi = entry.get("text_vi") or entry.get("query_text") or ""
    text_en = entry.get("text_en") or _to_en(text_vi, translate)

    out: dict = {
        "query_id": entry.get("query_id"),
        "type": qtype,
        "text_vi": text_vi,
        "text_en": text_en,
        "difficulty_tags": entry.get("difficulty_tags", []),
        "gt_video_id": entry.get("gt_video_id"),
    }
    # Đánh dấu câu tiếng Anh do máy dịch, chưa có người duyệt — xem EVAL_GUIDE.md §text_en.
    if not entry.get("text_en"):
        out["text_en_reviewed"] = False

    if qtype == "TRAKE":
        events = []
        for ev in entry.get("events", []):
            s, e = _window(ev)
            events.append({
                "text_en": ev.get("text_en") or ev.get("text_vi") or "",
                "gt_frame_start": s,
                "gt_frame_end": e,
            })
        out["events"] = events
    else:
        s, e = _window(entry)
        out["gt_frame_start"] = s
        out["gt_frame_end"] = e

    if qtype == "QA":
        out["question"] = entry.get("question", "")
        out["gt_answers"] = entry.get("gt_answers", [])

    return out


# ─── Kiểm tra ──────────────────────────────────────────────────────────────────

def check_entries(entries: list[dict]) -> list[str]:
    """Trả về danh sách vấn đề (rỗng = sạch). Không ném lỗi — in hết một lượt cho người dùng."""
    issues: list[str] = []
    seen: dict[str, int] = {}

    for i, e in enumerate(entries):
        qid = e.get("query_id") or f"(khong co query_id, vi tri {i})"
        if e.get("status") == "unresolved":
            continue

        if e.get("query_id"):
            if e["query_id"] in seen:
                issues.append(f"{qid}: query_id TRUNG voi entry o vi tri {seen[e['query_id']]}")
            seen[e["query_id"]] = i
        else:
            issues.append(f"vi tri {i}: thieu query_id")

        qtype = str(e.get("type", "")).upper()
        if qtype not in ("KIS", "QA", "TRAKE"):
            issues.append(f"{qid}: type='{e.get('type')}' khong hop le (KIS/QA/TRAKE)")
            continue

        if not (e.get("text_vi") or e.get("query_text")):
            issues.append(f"{qid}: thieu text_vi/query_text")

        vid = e.get("gt_video_id")
        if not vid:
            issues.append(f"{qid}: thieu gt_video_id")
            continue
        if ".mp4" in str(vid):
            issues.append(f"{qid}: gt_video_id='{vid}' khong duoc chua duoi .mp4")

        valid = _valid_frame_ids(vid)
        if valid is None and _MAP_KEYFRAMES.exists():
            issues.append(f"{qid}: khong tim thay map-keyframes cho video '{vid}'")

        if qtype == "TRAKE":
            evs = e.get("events") or []
            if not evs:
                issues.append(f"{qid}: TRAKE nhung 'events' rong")
            for j, ev in enumerate(evs):
                try:
                    s, en = _window(ev)
                except KeyError:
                    issues.append(f"{qid}: events[{j}] thieu gt_frame (hoac gt_frame_start/end)")
                    continue
                if valid and s not in valid:
                    issues.append(f"{qid}: events[{j}] gt_frame={s} KHONG trung keyframe nao cua {vid}")
                if en < s:
                    issues.append(f"{qid}: events[{j}] gt_frame_end < gt_frame_start")
        else:
            try:
                s, en = _window(e)
            except KeyError:
                issues.append(f"{qid}: thieu gt_frame (hoac gt_frame_start/end)")
                s = en = None
            if s is not None:
                if valid and s not in valid:
                    issues.append(f"{qid}: gt_frame={s} KHONG trung keyframe nao cua {vid} "
                                  f"— he thong chi tra ve duoc frame_id cua keyframe, cau nay se "
                                  f"vinh vien 0 diem. Dung lookup_frame.py de tra dung keyframe.")
                if en < s:
                    issues.append(f"{qid}: gt_frame_end < gt_frame_start")

        if qtype == "QA":
            if not e.get("question"):
                issues.append(f"{qid}: QA nhung thieu 'question'")
            if not e.get("gt_answers"):
                issues.append(f"{qid}: QA nhung thieu 'gt_answers' (mang cac cach dien dat chap nhan duoc)")
            elif not isinstance(e["gt_answers"], list):
                issues.append(f"{qid}: 'gt_answers' phai la MANG, khong phai string")

        la = [t for t in e.get("difficulty_tags", []) if t not in TAG_CHUAN]
        if la:
            issues.append(f"{qid}: tag ngoai danh sach chuan: {la} — xem TAG_CHUAN trong normalize_gt.py")

    return issues


# ─── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", type=Path, help="File ground truth format nguoi ghi (v2) hoac v1")
    p.add_argument("--check", action="store_true", help="Chi kiem tra, khong ghi gi")
    p.add_argument("--out", type=Path, default=None, help="Ghi ket qua v1 ra file nay")
    p.add_argument("--merge", type=Path, default=None,
                   help="Noi vao bo eval co san (bao loi neu trung query_id)")
    p.add_argument("--no-translate", action="store_true",
                   help="Khong goi dich may (dung khi chi muon kiem tra cau truc / khong co mang)")
    args = p.parse_args()

    entries = load_entries(args.input)
    n_bo = sum(1 for e in entries if e.get("status") == "unresolved")
    print(f"[normalize_gt] {args.input.name}: {len(entries)} entry"
          + (f" ({n_bo} danh dau 'unresolved', se bo qua)" if n_bo else ""))

    issues = check_entries(entries)
    if issues:
        print(f"\n[normalize_gt] === {len(issues)} VAN DE ===")
        for msg in issues:
            print(f"  - {msg}")
    else:
        print("[normalize_gt] Khong phat hien van de.")

    if args.check:
        return 1 if issues else 0

    if issues:
        print("\n[normalize_gt] Con van de o tren — sua xong roi chay lai. Khong ghi file nao.")
        return 1

    usable = [e for e in entries if e.get("status") != "unresolved"]
    converted = [convert_entry(e, translate=not args.no_translate) for e in usable]
    print(f"[normalize_gt] Da chuyen {len(converted)} entry sang format harness.")

    if args.merge:
        existing = load_entries(args.merge)
        seen = {e.get("query_id") for e in existing}
        trung = sorted({c["query_id"] for c in converted if c["query_id"] in seen})
        if trung:
            raise SystemExit(f"[normalize_gt] query_id da ton tai trong {args.merge.name}: {trung}")
        merged = existing + converted
        args.merge.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[normalize_gt] Da noi vao {args.merge} -> tong {len(merged)} cau.")

    if args.out:
        args.out.write_text(json.dumps(converted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[normalize_gt] Da ghi {args.out}")

    if not args.merge and not args.out:
        print("[normalize_gt] Khong co --out hay --merge nen khong ghi gi. Them mot trong hai de luu.")
    return 0


# Bo test: tests/unit/test_normalize_gt.py

if __name__ == "__main__":
    raise SystemExit(main())
