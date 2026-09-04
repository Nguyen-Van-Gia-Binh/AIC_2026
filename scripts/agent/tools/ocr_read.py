"""
ocr_read.py — OCR thật (PaddleOCR Detection + VietOCR Recognition) chạy on-demand trên các keyframe
candidate ĐÃ được retrieval/matching chọn ra (KHÔNG precompute cho toàn bộ 177K keyframe).

Pipeline hybrid: PaddleOCR chỉ làm DETECTION (tìm vị trí có chữ, TextDetection API, model
PP-OCRv6_medium_det) + VietOCR làm RECOGNITION riêng cho tiếng Việt (vgg_transformer) — ĐÃ XÁC NHẬN
thắng rõ rệt về độ chính xác dấu tiếng Việt so với recognizer đa ngôn ngữ mặc định của PaddleOCR (xem
kaggle_jobs/06_paddleocr_ocr/check_vietnamese_vietocr.py, chạy thật 2026-08-26). Cùng logic với
scripts/run_ocr_shard_local.py (batch offline) va colab_jobs/06_paddleocr_vietocr_shard*/ — CHU Y khac
1 điểm quan trọng: ở đây Detection LUÔN chạy CPU (device="cpu"), KHÔNG thử GPU trước. Lý do: module
này nạp CHUNG process với torch/SigLIP đã giữ sẵn CUDA context (index_store.py) — paddlepaddle-gpu
trên Windows XUNG ĐỘT DLL thật sự với torch trong CÙNG 1 process (WinError 127, cudnn_cnn64_9.dll —
đã xác nhận qua test trực tiếp + issue GitHub biết trước, xem docs/decisions-log.md), còn paddlepaddle
CPU thuần (không -gpu) thì KHÔNG dùng DLL CUDA riêng nên không xung đột. VietOCR (thuần torch, dùng
CHUNG 1 torch đã import sẵn) thì AN TOÀN chạy GPU — không phải cài torch thứ 2, không xung đột.

Được dùng ở 2 chỗ:
  1. answer_qa.py — chỉ kích hoạt khi câu hỏi thực sự cần đọc chữ/số (needs_text_reading()), làm gợi
     ý CHÈN VÀO prompt cho LLM Vision, không tự động trở thành câu trả lời (vẫn qua _crosscheck_answer).
  2. pipeline_kis.py / pipeline_trake.py — sau khi đã có danh sách ứng viên, đẩy
     sách hits từ fast_retrieve() (đã matching xong bằng CLIP/SigLIP), OCR top_n candidate đầu và ĐẨY
     LÊN ĐẦU các candidate có chữ/số KHỚP THỰC SỰ với token văn bản trong query — xem rerank_by_ocr()
     và query_likely_has_readable_text() bên dưới. Chỉ kích hoạt khi query có dấu hiệu cần đọc chữ/số
     — CLIP/SigLIP giỏi về ngữ nghĩa nhưng KHÔNG đọc được chữ/số cụ thể (biển số, tỷ số, giá tiền...).

Kết quả OCR CHỈ LÀ GỢI Ý/tín hiệu phụ — không bao giờ tự thay thế kết quả CLIP/SigLIP gốc, chỉ sắp
xếp lại trong phạm vi đã matching sẵn. Nếu import/khởi tạo/OCR thất bại vì bất kỳ lý do gì, module này
KHÔNG crash pipeline — trả về rỗng/giữ nguyên thứ tự gốc và in cảnh báo (fail-soft, giống mọi chỗ khác
trong repo gọi OCR/model ngoài).

Usage:
    from scripts.agent.tools.ocr_read import read_text_from_hits, format_ocr_hint
    ocr_results = read_text_from_hits(hits, top_n=3)   # {hit_index: [text_line, ...]}
    hint_text   = format_ocr_hint(ocr_results)          # "" nếu không đọc được gì

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

# Console Windows mặc định dùng code page cp1252, không encode được chữ có dấu tiếng Việt (kết quả
# VietOCR luôn có dấu) -> UnicodeEncodeError khi print() bất kỳ dòng log/kết quả nào có dấu. Giống
# hệt index_store.py (điểm import duy nhất của module đó).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

SCORE_THRESH = 0.5  # lọc box detection điểm tin cậy thấp — giống hệt run_ocr_shard_local.py/colab_jobs

_DETECTOR = None
_RECOGNIZER = None
_ENGINE_LOAD_FAILED = False


_VIETOCR_OFFLINE_CONFIG = {
    "vocab": (
        "aAàÀảẢãÃáÁạẠăĂằẰẳẲẵẴắẮặẶâÂầẦẩẨẫẪấẤậẬbBcCdDđĐeEèÈẻẺẽẼéÉẹẸêÊềỀểỂễỄếẾệỆ"
        "fFgGhHiIìÌỉỈĩĨíÍịỊjJkKlLmMnNoOòÒỏỎõÕóÓọỌôÔồỒổỔỗỖốỐộỘơƠờỜởỞỡỠớỚợỢpPqQrR"
        "sStTuUùÙủỦũŨúÚụỤưƯừỪửỬữỮứỨựỰvVwWxXyYỳỲỷỶỹỸýÝỵỴzZ0123456789!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~ "
    ),
    "device": "cpu",
    "seq_modeling": "transformer",
    "transformer": {
        "d_model": 256,
        "nhead": 8,
        "num_encoder_layers": 6,
        "num_decoder_layers": 6,
        "dim_feedforward": 2048,
        "max_seq_length": 1024,
        "pos_dropout": 0.1,
        "trans_dropout": 0.1,
    },
    "optimizer": {"max_lr": 0.0003, "pct_start": 0.1},
    "trainer": {
        "batch_size": 32,
        "print_every": 200,
        "valid_every": 4000,
        "iters": 100000,
        "export": "./weights/transformerocr.pth",
        "checkpoint": "./checkpoint/transformerocr_checkpoint.pth",
        "log": "./train.log",
        "metrics": None,
    },
    "dataset": {
        "name": "data",
        "data_root": "./img/",
        "train_annotation": "annotation_train.txt",
        "valid_annotation": "annotation_val_small.txt",
        "image_height": 32,
        "image_min_width": 32,
        "image_max_width": 512,
    },
    "dataloader": {"num_workers": 3, "pin_memory": True},
    "aug": {"image_aug": True, "masked_language_model": True},
    "predictor": {"beamsearch": False},
    "quiet": True,
    "backbone": "vgg19_bn",
    "cnn": {
        "pretrained": False,
        "ss": [[2, 2], [2, 2], [2, 1], [2, 1], [1, 1]],
        "ks": [[2, 2], [2, 2], [2, 1], [2, 1], [1, 1]],
        "hidden": 256,
    },
}


def _find_vietocr_weights() -> Path | None:
    candidates = [
        _ROOT / "data" / "extracted" / "models" / "vietocr" / "vgg_transformer.pth",
        _ROOT / "data" / "models" / "vietocr" / "vgg_transformer.pth",
        _ROOT / "data" / "extracted" / "vgg_transformer.pth",
        Path.home() / ".cache" / "vietocr" / "vgg_transformer.pth",
    ]
    for p in candidates:
        if p.is_file() and p.stat().st_size > 10_000_000:
            return p
    return None


def ocr_health() -> tuple[bool, str]:
    """Kiểm tra tính sẵn sàng của OCR Engine (PaddleOCR Detection + VietOCR Recognition).

    Returns:
        (True, message) nếu cả detector và weights recognition đều có sẵn offline.
        (False, message) nếu thiếu dependency hoặc file weights offline.
    """
    try:
        import paddleocr  # noqa: F401
    except ImportError:
        return False, "Thiếu package paddleocr (pip install paddleocr paddlepaddle)"

    try:
        import vietocr  # noqa: F401
    except ImportError:
        return False, "Thiếu package vietocr (pip install vietocr)"

    pth = _find_vietocr_weights()
    if pth is None:
        return False, (
            "Thiếu file weights VietOCR offline 'vgg_transformer.pth' "
            "(cần chạy 'python scripts/offline/ocr/fetch_vietocr_assets.py' hoặc đặt vào data/extracted/models/vietocr/)"
        )

    return True, f"OCR Engine sẵn sàng (weights: {pth})"


def _get_engine():
    """Singleton (detector, recognizer) — nạp 1 lần/process. Trả về (None, None) nếu load thất bại
    (không retry lại trong cùng 1 process, tránh lặp lại lỗi mạng/thiếu dependency nhiều lần)."""
    global _DETECTOR, _RECOGNIZER, _ENGINE_LOAD_FAILED
    if _DETECTOR is not None or _ENGINE_LOAD_FAILED:
        return _DETECTOR, _RECOGNIZER
    try:
        import torch  # noqa: F401 — phải import trước paddleocr: trên Windows, thứ tự ngược lại có thể
                       # gây lỗi nạp DLL "shm.dll" do opencv (dependency của paddleocr qua albumentations)
                       # nạp runtime DLL trước và che khuất DLL torch cần — xác nhận bằng test trực tiếp.
        from paddleocr import TextDetection
        print("[ocr_read] Đang nạp PaddleOCR TextDetection (CPU — xem docstring đầu file về lý do "
              "không dùng GPU)...")
        # enable_mkldnn=False BẮT BUỘC: mặc định True trên CPU x86, nhưng paddlepaddle 3.3.1 CPU +
        # oneDNN backend crash trên model PP-OCRv6_medium_det với lỗi "NotImplementedError:
        # ConvertPirAttribute2RuntimeAttribute not support [pir::ArrayAttribute<pir::DoubleAttribute>]"
        # (xác nhận bằng test trực tiếp 2026-08-28) — không liên quan gì tới xung đột DLL torch/paddle
        # đã biết, đây là lỗi riêng của backend oneDNN với model này.
        _DETECTOR = TextDetection(device="cpu", enable_mkldnn=False)
        print("[ocr_read] Detector san sang (cpu, mkldnn=False).")

        from vietocr.tool.predictor import Predictor
        from vietocr.tool.config import Cfg
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        print(f"[ocr_read] Đang nạp VietOCR offline (vgg_transformer, device={device})...")

        pth = _find_vietocr_weights()
        if pth is None:
            raise FileNotFoundError(
                "Không tìm thấy weights VietOCR offline (vgg_transformer.pth). "
                "Hãy chạy 'python scripts/offline/ocr/fetch_vietocr_assets.py'"
            )

        config = dict(_VIETOCR_OFFLINE_CONFIG)
        config["weights"] = str(pth)
        config["device"] = device
        _RECOGNIZER = Predictor(Cfg(config))
        print(f"[ocr_read] Recognizer san sang (device={device}, weights={pth.name}).")
    except Exception as error:
        print(f"[ocr_read] CẢNH BÁO: không nạp được OCR engine ({type(error).__name__}: {error}) "
              f"— bỏ qua OCR cho phiên này, pipeline sẽ chạy tiếp không có gợi ý/rerank OCR.")
        _ENGINE_LOAD_FAILED = True
        _DETECTOR = None
        _RECOGNIZER = None
    return _DETECTOR, _RECOGNIZER



def _get_rotate_crop_image(img, points):
    """Thuật toán crop chuẩn của PaddleOCR — perspective-warp theo đúng 4 góc box, xoay 90° nếu box
    cao hơn rộng nhiều (chữ dọc). Giống hệt scripts/offline/ocr/run_ocr_shard_local.py / colab_jobs
    (đồng bộ có ý — xem giải thích quy ước này ở run_ocr_shard_local.py dòng 10-11)."""
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
    """Heuristic gom box thành 'hàng' theo tâm y, sort trong hàng theo x — thứ tự đọc tự nhiên.
    Giống hệt scripts/offline/ocr/run_ocr_shard_local.py / colab_jobs."""
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
    """OCR 1 ảnh bằng pipeline hybrid, trả về list dòng chữ đọc được (có thể rỗng nếu ảnh không có
    chữ hoặc OCR lỗi) — mỗi phần tử là 1 dòng/box đã nhận diện, theo thứ tự đọc tự nhiên."""
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
                print(f"[ocr_read] CẢNH BÁO: recognize 1 box lỗi trên {image_path} "
                      f"({type(error).__name__}: {error})")
                continue
            if text:
                lines.append(str(text).strip())
        return lines
    except Exception as error:
        print(f"[ocr_read] CẢNH BÁO: OCR thất bại trên {image_path} ({type(error).__name__}: {error})")
        return []


def read_text_from_hits(hits: list[dict], top_n: int = 3) -> dict[int, list[str]]:
    """
    Chạy OCR trên tối đa top_n candidate hit đầu tiên có jpg_path tồn tại trên đĩa.

    Args:
        hits:  list[dict] từ fast_retrieve()/fast_retrieve_for_video(), cần có trường 'jpg_path'.
        top_n: Số ảnh tối đa cần OCR (mặc định 3 — giới hạn chi phí/thời gian on-demand).

    Returns:
        dict[int, list[str]]: {hit_index: [text_line, ...]}. Chỉ hit đọc được >=1 dòng chữ mới có
        mặt trong dict — dùng để format_ocr_hint() phân biệt được "không OCR được gì" (dict rỗng).
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
    """Định dạng kết quả OCR thành đoạn text ngắn để chèn vào prompt Vision. Rỗng nếu không đọc
    được gì từ bất kỳ candidate nào."""
    if not ocr_results:
        return ""
    lines = []
    for hit_index in sorted(ocr_results):
        texts = ", ".join(f'"{t}"' for t in ocr_results[hit_index])
        lines.append(f"  - Candidate frame #{hit_index + 1}: {texts}")
    return "\n".join(lines)


# ─── Rerank KIS/TRAKE theo OCR ─────────────────────────────────────────────────────────────────

# Dấu hiệu query có thể cần đọc chữ/số cụ thể trên màn hình mà CLIP/SigLIP kém — dùng chung tinh
# thần với _TEXT_READING_HINTS trong qa_classify.py nhưng mở rộng thêm các từ khoá thiên về "vật thể
# có chữ" thay vì "câu hỏi về số liệu" (KIS là mô tả cảnh, không phải câu hỏi).
_TEXT_QUERY_HINTS = re.compile(
    r"(biển báo|biển số|bảng hiệu|bảng tên|dòng chữ|chữ viết|logo|thương hiệu|nhãn hiệu|tên (?:đội|"
    r"cửa hàng|công ty)|số áo|tỷ số|điểm số|giá tiền|đồng hồ|sign|banner|billboard|license plate|"
    r"jersey number|scoreboard|subtitle|caption text)",
    re.IGNORECASE,
)
# Token văn bản CỤ THỂ trong query — chuỗi trong ngoặc kép, hoặc dãy số >=2 chữ số (biển số, tỷ số,
# giá tiền, năm...). Đây là thứ OCR có thể đối chiếu TRỰC TIẾP, khác với từ khoá hint (chỉ báo "có
# khả năng cần OCR" nhưng không tự nó cho biết cần tìm CHUỖI GÌ).
_LITERAL_TOKEN_PATTERN = re.compile(r'"([^"]+)"|\'([^\']+)\'|\b(\d{2,})\b')


def query_likely_has_readable_text(query_text: str) -> bool:
    """True nếu query có dấu hiệu mô tả chữ/số hiển thị trên màn hình — đáng giá kích hoạt
    rerank_by_ocr() (tránh OCR mọi query, tốn thời gian vô ích cho đa số query chỉ mô tả ngữ nghĩa
    chung chung mà CLIP/SigLIP đã xử lý tốt)."""
    if not query_text:
        return False
    return bool(_TEXT_QUERY_HINTS.search(query_text) or _LITERAL_TOKEN_PATTERN.search(query_text))


def _extract_literal_tokens(query_text: str) -> list[str]:
    """Lấy các chuỗi/số CỤ THỂ từ query để đối chiếu trực tiếp với text OCR đọc được."""
    tokens: list[str] = []
    for m in _LITERAL_TOKEN_PATTERN.finditer(query_text or ""):
        tok = next((g for g in m.groups() if g), "")
        tok = tok.strip()
        if tok:
            tokens.append(tok)
    return tokens


# ─── Tra JSON OCR/caption offline (batch job 6/7 — merge_ocr.py / merge_captions.py), fallback OCR
# realtime khi video chưa có sẵn — xem thiết kế đã chốt với user 2026-08-28 ──────────────────────
_OCR_JSONL_DIR = _ROOT / "data" / "extracted" / "ocr_text_paddleocr"
_CAPTION_JSONL_DIR = _ROOT / "data" / "extracted" / "caption_vintern1b"
# Cache {video_id: {n: text} | None} — None nghĩa là video này CHƯA có file jsonl (chưa chạy xong
# batch job), phân biệt với {} (có file nhưng rỗng) để biết lúc nào cần fallback OCR realtime.
_OFFLINE_OCR_CACHE: dict[str, Optional[dict[int, str]]] = {}
_OFFLINE_CAPTION_CACHE: dict[str, Optional[dict[int, str]]] = {}

# Bonus tính theo TỶ LỆ % của score cao nhất trong hits (KHÔNG phải hằng số tuyệt đối) — vì các model
# retrieval khác nhau có thang điểm rất khác nhau (CLIP cosine ~0.28-0.31, SigLIP ~0.05-0.15 trong
# thực tế đã đo ở phiên này), hằng số tuyệt đối sẽ quá mạnh/quá yếu tuỳ model đang dùng.
OCR_BONUS_FRACTION = 0.15       # khớp OCR (thật/offline) — tín hiệu mạnh, phiên âm chính xác
CAPTION_BONUS_FRACTION = 0.07   # chỉ khớp caption (mô tả cảnh, không phiên âm chính xác) — tín hiệu yếu hơn


def _load_offline_text_map(video_id: str, jsonl_dir: Path, cache: dict, field: str) -> Optional[dict[int, str]]:
    """Đọc {video_id}.jsonl (1 lần/video, cache lại) -> {n: text}. Trả về None nếu file CHƯA TỒN TẠI
    (video này batch job chưa xử lý tới — cần fallback OCR realtime), {} hoặc dict đầy đủ nếu có file."""
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
    Sau khi đã có hits từ fast_retrieve() (matching xong bằng CLIP/SigLIP), cộng THÊM 1 khoản bonus
    vào score của tối đa top_n_ocr candidate đầu nếu text (OCR/caption) của candidate đó khớp THỰC SỰ
    với token văn bản cụ thể trong query, rồi sắp xếp lại theo score+bonus — "sửa sai" nhẹ cho embedding
    khi ban than no khong doc duoc chu/so chinh xac, KHONG phá vo thu tu goc mot cach vo ly khi
    chênh lệch score quá lớn (khác với bản trước đẩy lên đầu bất kể score — xem thiết kế đã chốt với
    user 2026-08-28, "cộng bonus" thay vì "đẩy lên đầu").

    Nguồn text ưu tiên theo thứ tự (mỗi candidate xét độc lập):
      1. OCR JSON offline (data/extracted/ocr_text_paddleocr/{video_id}.jsonl, từ merge_ocr.py) nếu
         video đã có sẵn (batch job đã chạy tới) — tức thời, không tốn chi phí OCR realtime.
      2. Nếu video CHƯA có OCR JSON offline -> OCR REALTIME ảnh đó (như bản trước), đảm bảo vẫn có
         tín hiệu ngay cả khi batch job chưa chạy tới video này (hiện 0/873 đã merge — 2026-08-28).
      3. Caption JSON offline (data/extracted/caption_vintern1b/{video_id}.jsonl, tu merge_captions.py)
         — CHỈ dùng khi (1)/(2) không khớp gì, cộng bonus NHỎ HƠN (CAPTION_BONUS_FRACTION < OCR_..)
         vì caption mô tả cảnh chung chung, không phiên âm chính xác ký tự.

    An toàn: nếu không có token văn bản cụ thể trong query, hoặc không candidate nào khớp, TRẢ VỀ
    HITS VỚI SCORE Y NGUYÊN (bonus=0 không đổi thứ tự) — không có rủi ro regression.

    Args:
        hits:             list[dict] từ fast_retrieve(), đã sắp xếp giảm dần theo score CLIP/SigLIP.
        query_text:       Query đã rewrite (tiếng Anh) hoặc gốc — dùng để trích token văn bản cụ thể.
        top_n_ocr:        Số candidate đầu tiên được xét OCR/caption (giới hạn chi phí OCR realtime
                          cho phần chưa có offline — xem docstring đầu file).
        match_threshold:  Ngưỡng rapidfuzz.partial_ratio (0-100) để coi là "khớp" — 85 cho phép sai
                          lệch nhỏ do OCR không hoàn hảo 100% nhưng vẫn chặn được match ngẫu nhiên.
        score_key:        Trường điểm dùng để sắp xếp và tính bonus. "score" (mặc định) = cosine;
                          "rrf_score" khi hits đến từ hybrid.hybrid_retrieve. Bonus luôn tính theo
                          TỈ LỆ của điểm cao nhất của chính trường đó nên dùng được với mọi thang đo.

    Returns:
        list[dict] cùng định dạng với hits đầu vào, cùng độ dài. Trường 'score' GIỮ NGUYÊN giá trị
        gốc từ CLIP/SigLIP (không bị ghi đè) — bonus/nguồn khớp được lưu riêng ở 'ocr_bonus'/
        'ocr_match_source' để minh bạch, chỉ thứ tự (vị trí trong list) là thay đổi.
    """
    if not hits:
        return hits
    tokens = _extract_literal_tokens(query_text)
    if not tokens:
        return hits  # không có gì cụ thể để đối chiếu -> không OCR, tránh chi phí vô ích

    try:
        from rapidfuzz import fuzz
    except Exception as error:
        print(f"[ocr_read] CẢNH BÁO: không có rapidfuzz ({type(error).__name__}: {error}) "
              f"— bỏ qua rerank_by_ocr.")
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
