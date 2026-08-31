"""
score_pipelines.py — Final Score BTC THẬT của cả hệ thống: chạy trọn pipeline production
(run_kis / run_qa / run_trake) trên tests/eval/eval_ground_truth.json rồi chấm đúng công thức
docs/Thong tin vong So tuyen AIC2026.md §2.1–2.2.

Khác tests/eval/run_eval.py (bake-off backbone, retrieval-only, không LLM): file này đi qua
retrieve + rerank + DP + LLM answer + OCR + crosscheck — tức là đúng cái sẽ được nộp. Đánh đổi:
chậm, cần OPENROUTER_API_KEY (hoặc GEMINI_API_KEY ở AIC_MODE=test), và QA/TRAKE có biến thiên LLM
giữa các lần chạy (nên chạy 2–3 lần).

Chấm điểm:
  - R-Score mỗi câu trả lời r_i:
      KIS   (§2.1.1): I(video == GT ∧ frame ∈ [s,e])
      QA    (§2.1.2): I(video == GT ∧ frame ∈ [s,e] ∧ answer_matches(answer, gt_answers))
      TRAKE (§2.1.3): 0 nếu video != GT; ngược lại (1/N) Σ_j I(frame_ids[j] ∈ [s_j, e_j])
  - R@k = max R-Score trong k câu đầu (k ∈ {1,5,20,50,100});  Final = (1/5) Σ_k R@k
  - answer_matches: chuẩn hoá (casefold + gộp whitespace + bỏ dấu câu/nháy 2 đầu) rồi khớp nếu
    answer sinh ra TRÙNG / CHỨA / là CON của bất kỳ phần tử gt_answers nào (substring 2 chiều).

Usage:
    .venv\\Scripts\\python.exe tests\\Test\\score_pipelines.py                     # cả 3 loại
    .venv\\Scripts\\python.exe tests\\Test\\score_pipelines.py --types kis --limit 5
    .venv\\Scripts\\python.exe tests\\Test\\score_pipelines.py --no-rewrite         # bỏ LLM rewrite cho ổn định/nhanh
    .venv\\Scripts\\python.exe tests\\Test\\score_pipelines.py --self-test          # chỉ test answer_matches, không cần data/API
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_ROOT = Path(__file__).resolve().parents[2]  # tests/e2e/ -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_EVAL_SET_PATH = _ROOT / "tests" / "eval" / "eval_ground_truth.json"
_DEFAULT_OUT = _ROOT / "docs" / "reports" / "eval_e2e_scores.md"
_DEFAULT_BASELINE = _ROOT / "tests" / "e2e" / "e2e_baseline.json"

K_VALUES = [1, 5, 20, 50, 100]

# Nguong canh bao suy thoai diem (BAN DAC TA §6): Final moi thap hon baseline qua muc nay => bao dong.
# 0.01 tren thang Final (= trung binh 5 moc R@k) tuong duong ~1/3 cau tren bo 33 cau — du nho de bat
# duoc suy thoai that, du lon de khong bao dong vi dao dong LLM giua 2 lan chay.
REGRESSION_TOLERANCE = 0.01


# ─── So khớp answer ───────────────────────────────────────────────────────────
def normalize_answer(s: str) -> str:
    s = str(s).strip().casefold()
    s = re.sub(r"\s+", " ", s)
    return s.strip(" \t\r\n.,;:!?\"'()[]{}")


def answer_matches(produced: str, gt_answers: list[str]) -> bool:
    """True nếu (sau chuẩn hoá) produced TRÙNG / CHỨA / là CON của bất kỳ phần tử gt_answers nào."""
    p = normalize_answer(produced)
    if not p:
        return False
    for raw in gt_answers or []:
        g = normalize_answer(raw)
        if g and (p == g or g in p or p in g):
            return True
    return False


# ─── Chấm điểm ───────────────────────────────────────────────────────────────
def _r_at_k(rscores_in_order: list[float]) -> dict[int, float]:
    return {k: (max(rscores_in_order[:k]) if rscores_in_order[:k] else 0.0) for k in K_VALUES}


def _final(r_at_k: dict[int, float]) -> float:
    return sum(r_at_k[k] for k in K_VALUES) / len(K_VALUES)


def _in_window(fid: int, s: int, e: int) -> bool:
    lo, hi = (s, e) if s <= e else (e, s)
    return lo <= fid <= hi


def score_kis(run_kis, q: dict) -> dict[int, float]:
    results = run_kis(q["text_en"], top_k=100)
    gt, s, e = q["gt_video_id"], int(q["gt_frame_start"]), int(q["gt_frame_end"])
    rscores = [
        1.0 if (r["video_id"] == gt and _in_window(int(r["frame_id"]), s, e)) else 0.0
        for r in results
    ]
    return _r_at_k(rscores)


def score_qa(run_qa, q: dict) -> tuple[dict[int, float], str, bool]:
    question = q.get("question") or q["text_en"]
    out = run_qa(q.get("text_vi") or q["text_en"], question=question, top_k=100)
    answer = out.get("answer", "")
    gt_list = q.get("gt_answers")
    if not gt_list and "gt_answer" in q:
        gt_list = [q["gt_answer"]]
    ans_ok = answer_matches(answer, gt_list or [])
    gt, s, e = q["gt_video_id"], int(q["gt_frame_start"]), int(q["gt_frame_end"])
    rscores = [
        1.0 if (ans_ok and r["video_id"] == gt and _in_window(int(r["frame_id"]), s, e)) else 0.0
        for r in out["results"]
    ]
    return _r_at_k(rscores), answer, ans_ok


def score_trake(run_trake, q: dict) -> dict[int, float]:
    events = q["events"]
    out = run_trake(q["text_en"], [ev["text_en"] for ev in events])
    gt = q["gt_video_id"]
    n = len(events)
    rscores = []
    for r in out["results"]:
        if r["video_id"] != gt:
            rscores.append(0.0)
            continue
        hit = sum(
            1 for j, fid in enumerate(r["frame_ids"])
            if j < n and _in_window(int(fid), int(events[j]["gt_frame_start"]), int(events[j]["gt_frame_end"]))
        )
        rscores.append(hit / n)
    return _r_at_k(rscores)


# ─── Bảng markdown ───────────────────────────────────────────────────────────
def _mean_dict(dicts: list[dict[int, float]]) -> dict[int, float]:
    if not dicts:
        return {k: float("nan") for k in K_VALUES}
    return {k: sum(d[k] for d in dicts) / len(dicts) for k in K_VALUES}


def format_markdown(by_type: dict[str, list[dict[int, float]]]) -> str:
    lines = [
        "# Final Score BTC end-to-end — tests/e2e/score_pipelines.py\n",
        "Chạy trọn pipeline production (retrieve + rerank + DP + LLM answer/crosscheck) rồi chấm "
        "đúng §2.1–2.2. `Final` = (1/5)·Σ R@k. **Cảnh báo:** QA đi qua vision LLM nên điểm dao động "
        "giữa các lần chạy (chạy 2–3 lần lấy khoảng); `run_trake` mặc định `top_k_video=20` nên "
        "`results` ≤ 20 hàng → R@50 = R@100 = R@20 cho TRAKE.\n",
    ]
    groups = [("ALL", "ALL")] + [(t, t) for t in ("KIS", "QA", "TRAKE") if by_type.get(t)]
    header = "| nhóm | n | " + " | ".join(f"R@{k}" for k in K_VALUES) + " | **Final** |"
    sep = "|---" * (len(K_VALUES) + 3) + "|"
    lines += [header, sep]
    all_rows = [d for t in ("KIS", "QA", "TRAKE") for d in by_type.get(t, [])]
    for label, key in groups:
        rows = all_rows if key == "ALL" else by_type.get(key, [])
        if not rows:
            continue
        m = _mean_dict(rows)
        cells = " | ".join(f"{m[k]:.3f}" for k in K_VALUES)
        lines.append(f"| {label} | {len(rows)} | {cells} | **{_final(m):.3f}** |")
    return "\n".join(lines) + "\n"


# ─── Regression Guard (BAN DAC TA §6, Tang 2) ────────────────────────────────
def summarize_finals(by_type: dict[str, list[dict[int, float]]]) -> dict[str, float]:
    """{nhom: Final} cho ALL/KIS/QA/TRAKE — dang gon de luu baseline va so sanh giua cac lan chay."""
    finals: dict[str, float] = {}
    all_rows = [d for t in ("KIS", "QA", "TRAKE") for d in by_type.get(t, [])]
    if all_rows:
        finals["ALL"] = _final(_mean_dict(all_rows))
    for t in ("KIS", "QA", "TRAKE"):
        if by_type.get(t):
            finals[t] = _final(_mean_dict(by_type[t]))
    return finals


def check_regression(
    finals: dict[str, float], baseline_path: Path, tolerance: float = REGRESSION_TOLERANCE
) -> bool:
    """So Final moi voi baseline da luu. Tra ve True neu CO suy thoai (de main() thoat code 1).

    Chua co file baseline => khong coi la loi, chi nhac cach tao (lan chay dau tien).
    """
    if not baseline_path.exists():
        print(f"[score_pipelines] Chua co baseline ({baseline_path.name}) — chay lai voi "
              f"--save-baseline de chot moc so sanh cho cac lan sau.")
        return False

    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        print(f"[score_pipelines] Khong doc duoc baseline ({type(error).__name__}: {error}) — bo qua so sanh.")
        return False

    base_finals = baseline.get("finals", {})
    print(f"\n[score_pipelines] === Regression Guard (baseline {baseline.get('saved_at', '?')}) ===")

    # ALL cua lan chay nay chi so sanh duoc voi ALL cua baseline khi CUNG mot tap loai truy van.
    # Chay --types qa roi so ALL (chi 5 cau QA) voi ALL cua baseline (38 cau ca 3 loai) se luon
    # bao suy thoai gia — da xay ra that o P2.1 ngay 2026-08-31.
    types_now = {g for g in finals if g != "ALL"}
    types_base = {g for g in base_finals if g != "ALL"}
    bo_qua_all = types_now != types_base
    if bo_qua_all and "ALL" in finals:
        print(f"  ALL  : {finals['ALL']:.3f}  (BO QUA so sanh — lan nay chay {sorted(types_now)} "
              f"con baseline gom {sorted(types_base)}; hai con so ALL khong cung don vi)")

    regressed = False
    for group, value in finals.items():
        if group == "ALL" and bo_qua_all:
            continue
        if group not in base_finals:
            print(f"  {group:5s}: {value:.3f}  (baseline chua co nhom nay)")
            continue
        delta = value - base_finals[group]
        if delta < -tolerance:
            regressed = True
            flag = f"CANH BAO: thap hon baseline qua {tolerance}"
        elif delta > tolerance:
            flag = "tot hon baseline"
        else:
            flag = "trong nguong dao dong"
        print(f"  {group:5s}: {value:.3f}  (baseline {base_finals[group]:.3f}, "
              f"delta {delta:+.3f}) — {flag}")

    if regressed:
        print("[score_pipelines] CO SUY THOAI DIEM so voi baseline — khong nop ban nay truoc khi "
              "tim ra nguyen nhan (xem EXPERIMENT.md).")
    return regressed


def save_baseline(finals: dict[str, float], by_type: dict, baseline_path: Path, note: str = "") -> None:
    """Ghi Final hien tai lam moc so sanh cho cac lan chay sau."""
    import time
    payload = {
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": note,
        "n_by_type": {t: len(rows) for t, rows in by_type.items() if rows},
        "finals": finals,
    }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[score_pipelines] Da luu baseline -> {baseline_path}")


# ─── Self-test ───────────────────────────────────────────────────────────────
def _run_self_tests() -> None:
    assert answer_matches("Có 15 giải khuyến khích", ["15"]) is True
    assert answer_matches("15", ["15", "mười lăm"]) is True
    assert answer_matches("mười lăm", ["15", "mười lăm", "fifteen"]) is True
    assert answer_matches("màu trắng", ["màu xanh"]) is False
    assert answer_matches("", ["3"]) is False
    assert answer_matches("Phú Sĩ.", ["Phú Sĩ", "Phu Si"]) is True
    assert _r_at_k([0.0, 0.5, 0.0, 1.0]) == {1: 0.0, 5: 1.0, 20: 1.0, 50: 1.0, 100: 1.0}
    assert abs(_final({1: 0.5, 5: 0.8, 20: 0.8, 50: 0.8, 100: 0.8}) - 0.74) < 1e-9
    # Regression Guard: phat hien tut qua nguong, bo qua dao dong nho, khong co baseline thi khong loi.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        base_path = Path(tmp) / "baseline.json"
        assert check_regression({"ALL": 0.5}, base_path) is False, "Chua co baseline -> khong bao loi"
        by_type_fake = {"KIS": [{k: 1.0 for k in K_VALUES}]}
        save_baseline({"ALL": 0.500, "KIS": 0.600}, by_type_fake, base_path)
        assert check_regression({"ALL": 0.495, "KIS": 0.600}, base_path) is False, "Tut 0.005 < nguong -> khong bao"
        assert check_regression({"ALL": 0.480, "KIS": 0.600}, base_path) is True, "Tut 0.02 > nguong -> phai bao"
        assert check_regression({"ALL": 0.600, "KIS": 0.700}, base_path) is False, "Tot hon -> khong bao"
    assert summarize_finals({"KIS": [{k: 1.0 for k in K_VALUES}]}) == {"ALL": 1.0, "KIS": 1.0}
    print("[score_pipelines] self-test PASS")


# ─── Main ────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--types", type=str, default="kis,qa,trake",
                        help="Danh sách loại cần chấm, cách nhau dấu phẩy (kis/qa/trake)")
    parser.add_argument("--limit", type=int, default=0, help="Chỉ chấm N câu đầu mỗi loại (0 = tất cả)")
    parser.add_argument("--no-rewrite", action="store_true",
                        help="Thay rewrite_query bằng identity (text_en đã là tiếng Anh) — ổn định/nhanh")
    parser.add_argument("--eval-set", type=Path, default=_EVAL_SET_PATH)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--baseline", type=Path, default=_DEFAULT_BASELINE,
                        help="File baseline de so sanh chong suy thoai diem (BAN DAC TA §6)")
    parser.add_argument("--save-baseline", action="store_true",
                        help="Ghi ket qua lan chay nay lam baseline moi (chi lam khi da hai long)")
    parser.add_argument("--no-guard", action="store_true",
                        help="Bo qua Regression Guard (chi in bang diem)")
    args = parser.parse_args()

    if args.self_test:
        _run_self_tests()
        return

    # import config trước — nó load .env và lọc placeholder key; đừng tự đọc os.getenv (chưa load .env).
    from scripts.agent import config as _config
    if not (_config.OPENROUTER_API_KEYS or _config.GEMINI_API_KEYS):
        raise SystemExit(
            "[score_pipelines] Cần OPENROUTER_API_KEY (hoặc GEMINI_API_KEY khi AIC_MODE=test) trong "
            ".env — pipeline QA/TRAKE gọi LLM. Copy .env.example -> .env và điền key thật."
        )

    want = {t.strip().upper() for t in args.types.split(",") if t.strip()}
    eval_set = json.loads(args.eval_set.read_text(encoding="utf-8"))

    from scripts.agent.pipeline_kis import run_kis
    from scripts.agent.pipeline_qa import run_qa
    from scripts.agent.pipeline_trake import run_trake

    if args.no_rewrite:
        import scripts.agent.pipeline_qa as _qa_mod
        import scripts.agent.pipeline_trake as _trake_mod
        _identity = lambda text, *a, **k: text  # noqa: E731
        _qa_mod.rewrite_query = _identity
        _trake_mod.rewrite_query = _identity
        print("[score_pipelines] --no-rewrite: rewrite_query -> identity (chỉ trong tiến trình này)")

    by_type: dict[str, list[dict[int, float]]] = {"KIS": [], "QA": [], "TRAKE": []}
    for q in eval_set:
        qtype = q.get("type")
        if qtype not in want:
            continue
        if args.limit and len(by_type.get(qtype, [])) >= args.limit:
            continue
        qid = q.get("query_id", "?")
        if qtype == "KIS":
            rk = score_kis(run_kis, q)
            print(f"[score_pipelines] {qid} (KIS)  Final={_final(rk):.3f}  R@1={rk[1]:.0f}")
            by_type["KIS"].append(rk)
        elif qtype == "QA":
            rk, ans, ok = score_qa(run_qa, q)
            print(f"[score_pipelines] {qid} (QA)   Final={_final(rk):.3f}  answer={ans!r} match={ok}")
            by_type["QA"].append(rk)
        elif qtype == "TRAKE":
            rk = score_trake(run_trake, q)
            print(f"[score_pipelines] {qid} (TRAKE) Final={_final(rk):.3f}")
            by_type["TRAKE"].append(rk)

    table = format_markdown(by_type)
    print("\n" + table)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(table, encoding="utf-8")
    print(f"[score_pipelines] Đã ghi {args.out}")

    # ─── Regression Guard (BẢN ĐẶC TẢ §6, Tầng 2) ────────────────────────────
    finals = summarize_finals(by_type)
    if args.save_baseline:
        save_baseline(finals, by_type, args.baseline, note=f"types={args.types} limit={args.limit}")
    if not args.no_guard and check_regression(finals, args.baseline):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
