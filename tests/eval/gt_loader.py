"""
gt_loader.py — Quản lý và nạp dữ liệu ground truth từ 3 file con KIS / QA / TRAKE.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

_EVAL_DIR = Path(__file__).resolve().parent

GT_FILENAMES: Dict[str, str] = {
    "KIS": "eval_ground_truth_kis.json",
    "QA": "eval_ground_truth_qa.json",
    "TRAKE": "eval_ground_truth_trake.json",
}


def get_gt_path(query_type: str, eval_dir: Optional[Path] = None) -> Path:
    """Trả về đường dẫn file JSON của loại câu hỏi tương ứng."""
    t = str(query_type).strip().upper()
    if t not in GT_FILENAMES:
        raise ValueError(f"Không hỗ trợ type '{query_type}'. Các type hợp lệ: {list(GT_FILENAMES.keys())}")
    base_dir = Path(eval_dir).resolve() if eval_dir else _EVAL_DIR
    return base_dir / GT_FILENAMES[t]


def load_ground_truth(
    types: Optional[Union[str, Iterable[str]]] = None,
    eval_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Nạp danh sách entries ground truth từ các file con.
    
    Args:
        types: Loại câu hỏi cần nạp ('KIS', 'QA', 'TRAKE', hoặc chuỗi cách nhau dấu phẩy 'kis,qa',
               hoặc iterable ['KIS', 'TRAKE']). Nếu None hoặc 'ALL', nạp cả 3 file theo thứ tự KIS -> QA -> TRAKE.
        eval_dir: Thư mục chứa các file ground truth (mặc định tests/eval/).
    
    Returns:
        Danh sách gộp các query entries.
    """
    if types is None or (isinstance(types, str) and types.strip().upper() == "ALL"):
        selected_types = ["KIS", "QA", "TRAKE"]
    elif isinstance(types, str):
        selected_types = [t.strip().upper() for t in types.split(",") if t.strip()]
    else:
        selected_types = [str(t).strip().upper() for t in types if str(t).strip()]

    combined: List[Dict[str, Any]] = []
    base_dir = Path(eval_dir).resolve() if eval_dir else _EVAL_DIR

    for t in selected_types:
        path = get_gt_path(t, base_dir)
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"File {path} phải chứa một JSON array ở top-level")
        combined.extend(data)

    return combined


def save_ground_truth(
    entries: List[Dict[str, Any]],
    query_type: str,
    eval_dir: Optional[Path] = None,
) -> Path:
    """Ghi danh sách entries vào file con tương ứng với query_type."""
    path = get_gt_path(query_type, eval_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
