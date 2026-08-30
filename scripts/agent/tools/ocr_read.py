"""
ocr_read.py — OCR that (PaddleOCR Detection + VietOCR Recognition) chay on-demand tren cac keyframe
candidate DA duoc retrieval/matching chon ra (KHONG precompute cho toan bo 177K keyframe).

Pipeline hybrid: PaddleOCR chi lam DETECTION (tim vi tri co chu, TextDetection API, model
PP-OCRv6_medium_det) + VietOCR lam RECOGNITION rieng cho tieng Viet (vgg_transformer) — DA XAC NHAN
thang ro ret ve do chinh xac dau tieng Viet so voi recognizer da ngon ngu mac dinh cua PaddleOCR (xem
kaggle_jobs/06_paddleocr_ocr/check_vietnamese_vietocr.py, chay that 2026-08-26). Cung logic voi
scripts/run_ocr_shard_local.py (batch offline) va colab_jobs/06_paddleocr_vietocr_shard*/ — CHU Y khac
1 diem quan trong: o day Detection LUON chay CPU (device="cpu"), KHONG thu GPU truoc. Ly do: module
nay nap CHUNG process voi torch/CLIP/SigLIP2 da giu san CUDA context (retrieve.py) — paddlepaddle-gpu
tren Windows XUNG DOT DLL that su voi torch trong CUNG 1 process (WinError 127, cudnn_cnn64_9.dll —
da xac nhan qua test truc tiep + issue GitHub biet truoc, xem EXPERIMENT.md), con paddlepaddle CPU
thuan (khong -gpu) thi KHONG dung DLL CUDA rieng nen khong xung dot. VietOCR (thuan torch, dung CHUNG
1 torch da import san) thi AN TOAN chay GPU — khong phai cai torch thu 2, khong xung dot.

Duoc dung o 2 cho:
  1. answer_qa.py — chi kich hoat khi cau hoi thuc su can doc chu/so (_needs_text_reading()), lam goi
     y CHEN VAO prompt cho LLM Vision, khong tu dong tro thanh cau tra loi (van qua _crosscheck_answer).
  2. pipeline_kis.py / pipeline_trake.py (nhanh "feat/ocr-matching-keyframes") — sau khi da co danh
     sach hits tu fast_retrieve() (da matching xong bang CLIP/SigLIP), OCR top_n candidate dau va DAY
     LEN DAU cac candidate co chu/so KHOP THUC SU voi token van ban trong query — xem rerank_by_ocr()
     va query_likely_has_readable_text() ben duoi. Chi kich hoat khi query co dau hieu can doc chu/so
     — CLIP/SigLIP gioi ve ngu nghia nhung KHONG doc duoc chu/so cu the (bien so, ty so, gia tien...).

Ket qua OCR CHI LA GOI Y/tin hieu phu — khong bao gio tu thay the ket qua CLIP/SigLIP goc, chi sap
xep lai trong pham vi da matching san. Neu import/khoi tao/OCR that bai vi bat ky ly do gi, module nay
KHONG crash pipeline — tra ve rong/giu nguyen thu tu goc va in canh bao (fail-soft, giong moi cho khac
trong repo goi OCR/model ngoai).

Usage:
    from scripts.agent.tools.ocr_read import read_text_from_hits, format_ocr_hint
    ocr_results = read_text_from_hits(hits, top_n=3)   # {hit_index: [text_line, ...]}
    hint_text   = format_ocr_hint(ocr_results)          # "" neu khong doc duoc gi

    from scripts.agent.tools.ocr_read import query_likely_has_readable_text, rerank_by_ocr
    if query_likely_has_readable_text(query_en):
        hits = rerank_by_ocr(hits, query_en, top_n_ocr=20)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

# Console Windows mac dinh dung code page cp1252, khong encode duoc chu co dau tieng Viet (ket qua
# VietOCR luon co dau) -> UnicodeEncodeError khi print() bat ky dong log/ket qua nao co dau. Giong
# het retrieve.py (diem import duy nhat cua module nay).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

SCORE_THRESH = 0.5  # loc box detection diem tin cay thap — giong het run_ocr_shard_local.py/colab_jobs

_DETECTOR = None
_RECOGNIZER = None
_ENGINE_LOAD_FAILED = False


def _get_engine():
    """Singleton (detector, recognizer) — nap 1 lan/process. Tra ve (None, None) neu load that bai
    (khong retry lai trong cung 1 process, tranh lap lai loi mang/thieu dependency nhieu lan)."""
    global _DETECTOR, _RECOGNIZER, _ENGINE_LOAD_FAILED
    if _DETECTOR is not None or _ENGINE_LOAD_FAILED:
        return _DETECTOR, _RECOGNIZER
    try:
        import torch  # noqa: F401 — phai import truoc paddleocr: tren Windows, thu tu nguoc lai co the
                       # gay loi nap DLL "shm.dll" do opencv (dependency cua paddleocr qua albumentations)
                       # nap runtime DLL truoc va che khuat DLL torch can — xac nhan bang test truc tiep.
        from paddleocr import TextDetection
        print("[ocr_read] Dang nap PaddleOCR TextDetection (CPU — xem docstring dau file ve ly do "
              "khong dung GPU)...")
        # enable_mkldnn=False BAT BUOC: mac dinh True tren CPU x86, nhung paddlepaddle 3.3.1 CPU +
        # oneDNN backend crash tren model PP-OCRv6_medium_det voi loi "NotImplementedError:
        # ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]"
        # (xac nhan bang test truc tiep 2026-08-28) — khong lien quan gi toi xung dot DLL torch/paddle
        # da biet, day la loi rieng cua backend oneDNN voi model nay.
        _DETECTOR = TextDetection(device="cpu", enable_mkldnn=False)
        print("[ocr_read] Detector san sang (cpu, mkldnn=False).")

        from vietocr.tool.predictor import Predictor
        from vietocr.tool.config import Cfg
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"[ocr_read] Dang nap VietOCR (vgg_transformer, device={device})...")
        config = Cfg.load_config_from_name("vgg_transformer")
        config["device"] = device
        _RECOGNIZER = Predictor(config)
        print(f"[ocr_read] Recognizer san sang (device={device}).")
    except Exception as error:
        print(f"[ocr_read] CANH BAO: khong nap duoc OCR engine ({type(error).__name__}: {error}) "
              f"— bo qua OCR cho phien nay, pipeline se chay tiep khong co goi y/rerank OCR.")
        _ENGINE_LOAD_FAILED = True
        _DETECTOR = None
        _RECOGNIZER = None
    return _DETECTOR, _RECOGNIZER


def _get_rotate_crop_image(img, points):
    """Thuat toan crop chuan cua PaddleOCR — perspective-warp theo dung 4 goc box, xoay 90° neu box
    cao hon rong nhieu (chu doc). Giong het scripts/run_ocr_shard_local.py / colab_jobs (dong bo co
    y — xem giai thich quy uoc nay o run_ocr_shard_local.py dong 10-11)."""
    import cv2
    import numpy as np
    points = points.astype(np.float32)
    img_crop_width = int(max(
        np.linalg.norm(points[0] - points[1]), np.linalg.norm(points[2] - points[3])))
    img_crop_height = int(max(
        np.linalg.norm(points[0] - points[3]), np.linalg.norm(points[1] - points[2])))
    img_crop_width = max(img_crop_width, 1)
    img_crop_height = max(img_crop_height, 1)
    pts_std = np.float32([[0, 0], [img_crop_width, 0],
                           [img_crop_width, img_crop_height], [0, img_crop_height]])
    M = cv2.getPerspectiveTransform(points, pts_std)
    dst = cv2.warpPerspective(img, M, (img_crop_width, img_crop_height),
                               borderMode=cv2.BORDER_REPLICATE, flags=cv2.INTER_CUBIC)
    h, w = dst.shape[0:2]
    if h * 1.0 / w >= 1.5:
        dst = np.rot90(dst)
    return dst


def _sort_boxes_reading_order(dt_polys):
    """Heuristic gom box thanh 'hang' theo tam y, sort trong hang theo x — thu tu doc tu nhien.
    Giong het scripts/run_ocr_shard_local.py / colab_jobs."""
    import numpy as np
    if len(dt_polys) == 0:
        return dt_polys
    boxes = [np.array(b, dtype=np.float32) for b in dt_polys]
    centers = [(b[:, 0].mean(), b[:, 1].mean()) for b in boxes]
    heights = [max(np.linalg.norm(b[0] - b[3]), np.linalg.norm(b[1] - b[2])) for b in boxes]
    avg_h = float(np.mean(heights)) if heights else 20.0
    row_tol = max(avg_h * 0.6, 10.0)

    order = sorted(range(len(boxes)), key=lambda i: centers[i][1])
    rows = []
    for i in order:
        placed = False
        for row in rows:
            if abs(centers[i][1] - centers[row[0]][1]) <= row_tol:
                row.append(i)
                placed = True
                break
        if not placed:
            rows.append([i])
    final_order = []
    for row in rows:
        final_order.extend(sorted(row, key=lambda i: centers[i][0]))
    return [dt_polys[i] for i in final_order]


def _ocr_single_image(image_path: str) -> list[str]:
    """OCR 1 anh bang pipeline hybrid, tra ve list dong chu doc duoc (co the rong neu anh khong co
    chu hoac OCR loi) — moi phan tu la 1 dong/box da nhan dien, theo thu tu doc tu nhien."""
    detector, recognizer = _get_engine()
    if detector is None:
        return []
    try:
        import cv2
        import numpy as np
        from PIL import Image

        result = detector.predict(image_path)
        if not result:
            return []
        r0 = result[0]
        dt_polys = r0.get("dt_polys") if hasattr(r0, "get") else getattr(r0, "dt_polys", None)
        dt_scores = r0.get("dt_scores") if hasattr(r0, "get") else getattr(r0, "dt_scores", None)
        if dt_polys is None or len(dt_polys) == 0:
            return []

        if dt_scores is not None and len(dt_scores) == len(dt_polys):
            keep = [i for i, s in enumerate(dt_scores) if s >= SCORE_THRESH]
            dt_polys = [dt_polys[i] for i in keep]
        if len(dt_polys) == 0:
            return []

        dt_polys = _sort_boxes_reading_order(dt_polys)

        img_bgr = cv2.imread(image_path)
        if img_bgr is None:
            return []

        lines: list[str] = []
        for box in dt_polys:
            box_arr = np.array(box, dtype=np.float32)
            crop_bgr = _get_rotate_crop_image(img_bgr, box_arr)
            crop_rgb = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2RGB)
            crop_pil = Image.fromarray(crop_rgb)
            try:
                text = recognizer.predict(crop_pil)
            except Exception as error:
                print(f"[ocr_read] CANH BAO: recognize 1 box loi tren {image_path} "
                      f"({type(error).__name__}: {error})")
                continue
            if text:
                lines.append(str(text).strip())
        return lines
    except Exception as error:
        print(f"[ocr_read] CANH BAO: OCR that bai tren {image_path} ({type(error).__name__}: {error})")
        return []


def read_text_from_hits(hits: list[dict], top_n: int = 3) -> dict[int, list[str]]:
    """
    Chay OCR tren toi da top_n candidate hit dau tien co jpg_path ton tai tren dia.

    Args:
        hits:  list[dict] tu fast_retrieve()/fast_retrieve_for_video(), can co truong 'jpg_path'.
        top_n: So anh toi da can OCR (mac dinh 3 — gioi han chi phi/thoi gian on-demand).

    Returns:
        dict[int, list[str]]: {hit_index: [text_line, ...]}. Chi hit doc duoc >=1 dong chu moi co
        mat trong dict — dung de format_ocr_hint() phan biet duoc "khong OCR duoc gi" (dict rong).
    """
    result: dict[int, list[str]] = {}
    for i, hit in enumerate(hits[:top_n]):
        jpg_path = hit.get("jpg_path")
        if jpg_path and Path(jpg_path).exists():
            lines = _ocr_single_image(jpg_path)
            if lines:
                result[i] = lines
    return result


def format_ocr_hint(ocr_results: dict[int, list[str]]) -> str:
    """Dinh dang ket qua OCR thanh doan text ngan de chen vao prompt Vision. Rong neu khong doc
    duoc gi tu bat ky candidate nao."""
    if not ocr_results:
        return ""
    lines = []
    for hit_index in sorted(ocr_results):
        texts = ", ".join(f'"{t}"' for t in ocr_results[hit_index])
        lines.append(f"  - Candidate frame #{hit_index + 1}: {texts}")
    return "\n".join(lines)


# ─── Rerank KIS/TRAKE theo OCR (nhanh feat/ocr-matching-keyframes) ─────────────────────────────

# Dau hieu query co the can doc chu/so cu the tren man hinh ma CLIP/SigLIP kem — dung chung tinh
# than voi _TEXT_READING_HINTS trong answer_qa.py nhung mo rong them cac tu khoa thien ve "vat the co
# chu" thay vi "cau hoi ve so lieu" (KIS la mo ta canh, khong phai cau hoi).
_TEXT_QUERY_HINTS = re.compile(
    r"(biển báo|biển số|bảng hiệu|bảng tên|dòng chữ|chữ viết|logo|thương hiệu|nhãn hiệu|tên (?:đội|"
    r"cửa hàng|công ty)|số áo|tỷ số|điểm số|giá tiền|đồng hồ|sign|banner|billboard|license plate|"
    r"jersey number|scoreboard|subtitle|caption text)",
    re.IGNORECASE,
)
# Token van ban CU THE trong query — chuoi trong ngoac kep, hoac day so >=2 chu so (bien so, ty so,
# gia tien, nam...). Day la thu OCR co the doi chieu TRUC TIEP, khac voi tu khoa hint (chi bao "co
# kha nang can OCR" nhung khong tu no cho biet can tim CHUOI GI).
_LITERAL_TOKEN_PATTERN = re.compile(r'"([^"]+)"|\'([^\']+)\'|\b(\d{2,})\b')


def query_likely_has_readable_text(query_text: str) -> bool:
    """True neu query co dau hieu mo ta chu/so hien thi tren man hinh — dang gia tri kich hoat
    rerank_by_ocr() (tranh OCR moi query, ton thoi gian vo ich cho da so query chi mo ta ngu nghia
    chung chung ma CLIP/SigLIP da xu ly tot)."""
    if not query_text:
        return False
    return bool(_TEXT_QUERY_HINTS.search(query_text) or _LITERAL_TOKEN_PATTERN.search(query_text))


def _extract_literal_tokens(query_text: str) -> list[str]:
    """Lay cac chuoi/so CU THE tu query de doi chieu truc tiep voi text OCR doc duoc."""
    tokens: list[str] = []
    for m in _LITERAL_TOKEN_PATTERN.finditer(query_text or ""):
        tok = next((g for g in m.groups() if g), "")
        tok = tok.strip()
        if tok:
            tokens.append(tok)
    return tokens


# ─── Tra JSON OCR/caption offline (batch job 6/7 — merge_ocr.py / merge_captions.py), fallback OCR
# realtime khi video chua co san — xem thiet ke da chot voi user 2026-08-28 ──────────────────────
_OCR_JSONL_DIR = _ROOT / "data" / "extracted" / "ocr_text_paddleocr"
_CAPTION_JSONL_DIR = _ROOT / "data" / "extracted" / "caption_vintern1b"
# Cache {video_id: {n: text} | None} — None nghia la video nay CHUA co file jsonl (chua chay xong
# batch job), phan biet voi {} (co file nhung rong) de biet luc nao can fallback OCR realtime.
_OFFLINE_OCR_CACHE: dict[str, Optional[dict[int, str]]] = {}
_OFFLINE_CAPTION_CACHE: dict[str, Optional[dict[int, str]]] = {}

# Bonus tinh theo TY LE % cua score cao nhat trong hits (KHONG phai hang so tuyet doi) — vi cac model
# retrieval khac nhau co thang diem rat khac nhau (CLIP cosine ~0.28-0.31, SigLIP2 ~0.05-0.15 trong
# thuc te da do o phien nay), hang so tuyet doi se qua manh/qua yeu tuy model dang dung.
OCR_BONUS_FRACTION = 0.15       # khop OCR (that/offline) — tin hieu manh, phien am chinh xac
CAPTION_BONUS_FRACTION = 0.07   # chi khop caption (mo ta canh, khong phien am chinh xac) — tin hieu yeu hon


def _load_offline_text_map(video_id: str, jsonl_dir: Path, cache: dict, field: str) -> Optional[dict[int, str]]:
    """Doc {video_id}.jsonl (1 lan/video, cache lai) -> {n: text}. Tra ve None neu file CHUA TON TAI
    (video nay batch job chua xu ly toi — can fallback OCR realtime), {} hoac dict day du neu co file."""
    if video_id in cache:
        return cache[video_id]
    path = jsonl_dir / f"{video_id}.jsonl"
    if not path.exists():
        cache[video_id] = None
        return None
    result: dict[int, str] = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    result[int(rec["n"])] = str(rec.get(field, "")).strip()
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    continue
    except OSError:
        cache[video_id] = None
        return None
    cache[video_id] = result
    return result


def rerank_by_ocr(
    hits: list[dict],
    query_text: str,
    top_n_ocr: int = 20,
    match_threshold: float = 85.0,
    score_key: str = "score",
) -> list[dict]:
    """
    Sau khi da co hits tu fast_retrieve() (matching xong bang CLIP/SigLIP), cong THEM 1 khoan bonus
    vao score cua toi da top_n_ocr candidate dau neu text (OCR/caption) cua candidate do khop THUC SU
    voi token van ban cu the trong query, roi sap xep lai theo score+bonus — "sua sai" nhe cho embedding
    khi ban than no khong doc duoc chu/so chinh xac, KHONG phá vo thu tu goc mot cach vo ly khi
    chenh lech score qua lon (khac voi ban truoc day len dau bat ke score — xem thiet ke da chot voi
    user 2026-08-28, "cong bonus" thay vi "day len dau").

    Nguon text uu tien theo thu tu (moi candidate xet doc lap):
      1. OCR JSON offline (data/extracted/ocr_text_paddleocr/{video_id}.jsonl, tu merge_ocr.py) neu
         video da co san (batch job da chay toi) — tuc thoi, khong ton chi phi OCR realtime.
      2. Neu video CHUA co OCR JSON offline -> OCR REALTIME anh do (nhu ban truoc), dam bao van co
         tin hieu ngay ca khi batch job chua chay toi video nay (hien 0/873 da merge — 2026-08-28).
      3. Caption JSON offline (data/extracted/caption_vintern1b/{video_id}.jsonl, tu merge_captions.py)
         — CHI dung khi (1)/(2) khong khop gi, cong bonus NHO HON (CAPTION_BONUS_FRACTION < OCR_..)
         vi caption mo ta canh chung chung, khong phien am chinh xac ky tu.

    An toan: neu khong co token van ban cu the trong query, hoac khong candidate nao khop, TRA VE
    HITS VOI SCORE Y NGUYEN (bonus=0 khong doi thu tu) — khong co rui ro regression.

    Args:
        hits:             list[dict] tu fast_retrieve(), da sap xep giam dan theo score CLIP/SigLIP.
        query_text:       Query da rewrite (tieng Anh) hoac goc — dung de trich token van ban cu the.
        top_n_ocr:        So candidate dau tien duoc xet OCR/caption (gioi han chi phi OCR realtime
                          cho phan chua co offline — xem docstring dau file).
        match_threshold:  Nguong rapidfuzz.partial_ratio (0-100) de coi la "khop" — 85 cho phep sai
                          lech nho do OCR khong hoan hao 100% nhung van chan duoc match ngau nhien.
        score_key:        Truong diem dung de sap xep va tinh bonus. "score" (mac dinh) = cosine;
                          "rrf_score" khi hits den tu retrieve.hybrid_retrieve. Bonus luon tinh theo
                          TI LE cua diem cao nhat cua chinh truong do nen dung duoc voi moi thang do.

    Returns:
        list[dict] cung dinh dang voi hits dau vao, cung do dai. Truong 'score' GIU NGUYEN gia tri
        goc tu CLIP/SigLIP (khong bi ghi de) — bonus/nguon khop duoc luu rieng o 'ocr_bonus'/
        'ocr_match_source' de minh bach, chi thu tu (vi tri trong list) la thay doi.
    """
    if not hits:
        return hits
    tokens = _extract_literal_tokens(query_text)
    if not tokens:
        return hits  # khong co gi cu the de doi chieu -> khong OCR, tranh chi phi vo ich

    try:
        from rapidfuzz import fuzz
    except Exception as error:
        print(f"[ocr_read] CANH BAO: khong co rapidfuzz ({type(error).__name__}: {error}) "
              f"— bo qua rerank_by_ocr.")
        return hits

    candidates = hits[:top_n_ocr]
    rest = hits[top_n_ocr:]
    top_score = max((float(h.get(score_key, 0.0)) for h in hits), default=0.0)

    def _any_token_matches(text: str) -> bool:
        return bool(text) and any(
            fuzz.partial_ratio(tok.lower(), text.lower()) >= match_threshold for tok in tokens
        )

    scored: list[tuple[float, dict]] = []
    n_ocr_match = 0
    n_caption_match = 0
    for hit in candidates:
        vid = hit.get("video_id", "")
        n = hit.get("n")
        jpg_path = hit.get("jpg_path")
        hit_out = dict(hit)
        bonus = 0.0
        match_source = None

        offline_ocr = _load_offline_text_map(vid, _OCR_JSONL_DIR, _OFFLINE_OCR_CACHE, "ocr_text") if vid else None
        if offline_ocr is not None and n in offline_ocr:
            ocr_text = offline_ocr[n]
        elif jpg_path and Path(jpg_path).exists():
            lines = _ocr_single_image(jpg_path)
            ocr_text = " ".join(lines)
            if lines:
                hit_out["ocr_lines"] = lines
        else:
            ocr_text = ""

        if _any_token_matches(ocr_text):
            bonus = OCR_BONUS_FRACTION * top_score
            match_source = "ocr"
            n_ocr_match += 1
        else:
            offline_caption = _load_offline_text_map(vid, _CAPTION_JSONL_DIR, _OFFLINE_CAPTION_CACHE, "caption") if vid else None
            caption_text = offline_caption.get(n, "") if offline_caption else ""
            if _any_token_matches(caption_text):
                bonus = CAPTION_BONUS_FRACTION * top_score
                match_source = "caption"
                n_caption_match += 1

        if match_source:
            hit_out["ocr_bonus"] = bonus
            hit_out["ocr_match_source"] = match_source
        scored.append((float(hit.get(score_key, 0.0)) + bonus, hit_out))

    if n_ocr_match or n_caption_match:
        print(f"[ocr_read] rerank_by_ocr: {n_ocr_match} khop OCR (+{OCR_BONUS_FRACTION*top_score:.4f}), "
              f"{n_caption_match} khop caption (+{CAPTION_BONUS_FRACTION*top_score:.4f}), token={tokens}")

    scored.sort(key=lambda pair: -pair[0])
    return [hit_out for _, hit_out in scored] + rest


# CLI test


# ─── CLI demo: đọc OCR trên ảnh thật, kiểm tra bằng mắt ────────────────────────
# Các test có hard-assert đã chuyển sang tests/unit/test_ocr_read.py. Phần dưới CỐ Ý không assert:
# OCR không đảm bảo chính xác 100% nên chỉ in ra để người chạy tự đối chiếu với GT ghi ở comment.
if __name__ == "__main__":
    _ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent

    def _demo_hit(jpg_rel_path: str, video_id: str = "", n: int = 0, score: float = 1.0) -> dict:
        return {"video_id": video_id, "n": n, "frame_idx": n, "frame_id": n + 1,
                "pts_time": 0.0, "score": score, "jpg_path": str(_ROOT_DIR / jpg_rel_path)}

    print("[ocr_read] === Demo 1: OCR ảnh thật có chữ ===")
    known_hits = [
        _demo_hit("data/extracted/keyframes/L22/L22_V001/120.jpg"),   # GT: "DIANA 1961 1997"
        _demo_hit("data/extracted/keyframes/L28/L28_V003/190.jpg"),   # GT: "AG-09399" / "AG-12627"
        _demo_hit("data/extracted/keyframes/L27/L27_V001/110.jpg"),   # GT: "CHÚA XỨ THÁNH MẪU"
    ]
    ocr_out = read_text_from_hits(known_hits, top_n=3)
    for i, hit in enumerate(known_hits):
        print(f"  candidate #{i+1} ({Path(hit['jpg_path']).name}): {ocr_out.get(i, [])}")
    print("  format_ocr_hint():")
    print(format_ocr_hint(ocr_out))

    print("[ocr_read] === Demo 2: rerank_by_ocr trên ảnh thật ===")
    hits_demo = [
        _demo_hit("data/extracted/keyframes/L27/L27_V001/110.jpg", "L27_V001", 110, score=0.30),
        _demo_hit("data/extracted/keyframes/L22/L22_V001/120.jpg", "L22_V001", 120, score=0.29),
        _demo_hit("data/extracted/keyframes/L28/L28_V003/190.jpg", "L28_V003", 190, score=0.28),
    ]
    out = rerank_by_ocr(hits_demo, 'a plaque with the year "1997" on it', top_n_ocr=3)
    print("  Thứ tự sau rerank: " + str(
        [(h["video_id"] + "/" + str(h["n"]), round(h["score"], 4),
          h.get("ocr_bonus", 0.0), h.get("ocr_match_source")) for h in out]))
    print("  Tự kiểm tra bằng mắt: L22_V001/120 (chứa '1997' theo GT) có được đẩy lên đầu không?")
