"""
Load embedding index + text encoder cho NHIỀU model khác nhau (clip_vitb32 / vitl14 / siglip /
dfn / ...), phục vụ scripts/eval/run_eval.py (Phase 6 — so baseline retrieval).

Cố ý KHÔNG import/sửa scripts/index.py hay scripts/agent/tools/retrieve.py (đường dẫn production
KIS/QA/TRAKE, đang được dùng tập dượt thật trong Vòng thử nghiệm) — chấp nhận trùng ~20 dòng logic
build-index để đổi lấy rủi ro bằng 0 cho pipeline sản xuất. Xem PLAN.md Phase 6.

Mỗi model cần 2 thứ, tách riêng theo `MODEL_REGISTRY`:
  - features_dir_name: thư mục .npy ảnh đã encode sẵn (từ kaggle_jobs/, xem kaggle_jobs/README.md)
  - build_encoder: hàm trả về encode(texts) -> vector, DÙNG CHUNG không gian với ảnh đã encode

Usage (smoke-test, không cần eval set):
    .venv\\Scripts\\python.exe scripts\\eval\\multi_index.py clip_vitb32 vitl14
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "extracted"
_MAPKF_DIR = _DATA_DIR / "map-keyframes"


def load_feature_index(features_dir: Path) -> tuple[np.ndarray, pd.DataFrame]:
    """Lặp lại logic build_index() của scripts/index.py, nhận features_dir tuỳ ý thay vì hardcode
    clip-features-32 — xem docstring module."""
    npy_files = sorted(features_dir.glob("*.npy"))
    if not npy_files:
        raise FileNotFoundError(
            f"Không thấy .npy nào trong {features_dir} — đã giải nén data/raw/features_*.zip chưa?"
        )

    vec_chunks = []
    meta_rows = []
    for npy_path in npy_files:
        video_id = npy_path.stem
        csv_path = _MAPKF_DIR / f"{video_id}.csv"
        if not csv_path.exists():
            print(f"[multi_index] WARN: thiếu map-keyframes cho {video_id}, bỏ qua")
            continue

        feats = np.load(npy_path).astype(np.float32)
        df = pd.read_csv(csv_path)
        n_rows = min(len(df), len(feats))
        if len(df) != len(feats):
            print(f"[multi_index] WARN: {video_id}: csv={len(df)} dòng != npy={len(feats)} vector, "
                  f"cắt còn {n_rows}")

        chunk = feats[:n_rows]
        norms = np.linalg.norm(chunk, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        chunk = chunk / norms
        vec_chunks.append(chunk)

        for i in range(n_rows):
            row = df.iloc[i]
            frame_idx = int(row["frame_idx"])
            meta_rows.append({
                "video_id": video_id,
                "n": int(row["n"]),
                "pts_time": float(row["pts_time"]),
                "frame_idx": frame_idx,
                "frame_id": frame_idx + 1,
            })

    matrix = np.concatenate(vec_chunks, axis=0)
    meta = pd.DataFrame(meta_rows)
    assert len(meta) == matrix.shape[0], "meta và matrix lệch số dòng"

    # Fail loud nếu .npy hỏng (NaN) — XÁC NHẬN THẬT đã gặp case này (2026-08-20, features_jina):
    # toàn bộ 873/873 file NaN 100% (bit pattern float16 0x7FFF ở MỌI giá trị, MỌI video — không
    # phải corrupt ngẫu nhiên lúc giải nén, mà encode-time bug thật, nhiều khả năng float16 overflow
    # trên GPU Kaggle, xem kaggle_jobs/README.md). Không âm thầm cho qua vì cosine similarity với
    # NaN vẫn chạy không lỗi nhưng ra score=nan cho MỌI kết quả — sai hoàn toàn mà không ai biết nếu
    # không check ở đây.
    n_nan_rows = int(np.isnan(matrix).any(axis=1).sum())
    if n_nan_rows > 0:
        raise RuntimeError(
            f"[{features_dir.name}] {n_nan_rows}/{len(matrix)} vector chứa NaN — dữ liệu .npy hỏng "
            f"(gặp thật với features_jina: encode-time bug, không phải lỗi giải nén). Không dùng "
            f"được cho tới khi encode lại. Xem PLAN.md Phase 6 / kaggle_jobs/README.md."
        )
    return matrix, meta


def _extract_embedding(out, model, projection_attr: Optional[str]):
    """Rút tensor embedding từ output của get_text_features(), dựa vào SHAPE thật lúc runtime thay
    vì đoán tên field/API — học từ bài học kaggle_jobs/README.md mục "Cập nhật 5" (đoán sai liên
    tiếp 2 lần cấu trúc ModelOutput giữa các bản `transformers` khác nhau khi encode ảnh; ở đây áp
    dụng luôn phòng hờ cho nhánh encode text, dù nhánh này thường ổn định hơn)."""
    import torch
    if isinstance(out, torch.Tensor):
        candidate = out
    else:
        candidate = None
        for field_name in ("text_embeds", "pooler_output", "last_hidden_state"):
            val = getattr(out, field_name, None)
            if val is not None:
                candidate = val
                break
        if candidate is None:
            raise TypeError(f"Không rút được embedding từ kiểu {type(out)}")
        if candidate.dim() == 3:  # last_hidden_state (batch, seq, dim) -> lấy token đầu
            candidate = candidate[:, 0, :]
    if projection_attr is not None:
        proj_dim = getattr(getattr(model, "config", None), "projection_dim", None)
        if proj_dim is not None and candidate.shape[-1] != proj_dim:
            proj = getattr(model, projection_attr, None)
            if proj is not None:
                candidate = proj(candidate)
    return candidate


def _build_clip_vitb32_encoder() -> Callable[[list[str]], np.ndarray]:
    """Baseline hiện tại — cùng model/API với scripts/agent/tools/retrieve.py, chỉ tách encoder
    riêng để dùng qua giao diện MODEL_REGISTRY chung."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("clip-ViT-B-32")

    def encode(texts: list[str]) -> np.ndarray:
        vecs = model.encode(list(texts), normalize_embeddings=True)
        return np.asarray(vecs, dtype=np.float32)
    return encode


def _build_vitl14_encoder() -> Callable[[list[str]], np.ndarray]:
    import torch
    from transformers import CLIPModel, CLIPProcessor
    model_id = "openai/clip-vit-large-patch14"
    print(f"[multi_index]   tải {model_id} (lần đầu sẽ tải checkpoint ~1.7GB)...")
    model = CLIPModel.from_pretrained(model_id)
    model.eval()
    processor = CLIPProcessor.from_pretrained(model_id)

    def encode(texts: list[str]) -> np.ndarray:
        inputs = processor(text=list(texts), return_tensors="pt", padding=True, truncation=True)
        with torch.no_grad():
            out = model.get_text_features(**inputs)
        vec = _extract_embedding(out, model, projection_attr="text_projection")
        vec = torch.nn.functional.normalize(vec, dim=-1)
        return vec.numpy().astype(np.float32)
    return encode


def _build_siglip_encoder() -> Callable[[list[str]], np.ndarray]:
    import torch
    from transformers import SiglipModel, AutoProcessor
    model_id = "google/siglip-so400m-patch14-384"
    print(f"[multi_index]   tải {model_id} (lần đầu sẽ tải checkpoint vài GB)...")
    model = SiglipModel.from_pretrained(model_id)
    model.eval()
    processor = AutoProcessor.from_pretrained(model_id)

    def encode(texts: list[str]) -> np.ndarray:
        # SigLIP huấn luyện với padding cố định "max_length" (64 token) — khác CLIP thường.
        inputs = processor(text=list(texts), return_tensors="pt", padding="max_length", truncation=True)
        with torch.no_grad():
            out = model.get_text_features(**inputs)
        vec = _extract_embedding(out, model, projection_attr=None)
        vec = torch.nn.functional.normalize(vec, dim=-1)
        return vec.numpy().astype(np.float32)
    return encode


def _build_siglip2_encoder() -> Callable[[list[str]], np.ndarray]:
    """SigLIP2 base — bản cải tiến của SigLIP v1 đang dùng (siglip), Google công bố cải thiện rõ
    khả năng đa ngôn ngữ. features_siglip2/*.npy do người dùng tự encode ngoài repo (không qua
    kaggle_jobs/), KHÔNG rõ chắc chắn model_id/độ phân giải gốc — chỉ biết dim=768 (loại trừ
    so400m, dim 1152). Đoán google/siglip2-base-patch16-384 (cùng độ phân giải 384 với job siglip
    hiện có trong kaggle_jobs/02_siglip). Tự kiểm chứng bằng R@k của run_eval.py: nếu 'siglip2' ra
    điểm gần 0 so với 'siglip' đang có điểm thật -> model_id đoán sai, đổi sang biến thể khác
    (patch16-256/224) rồi thử lại."""
    import torch
    from transformers import AutoModel, AutoProcessor
    model_id = "google/siglip2-base-patch16-384"
    print(f"[multi_index]   tải {model_id} (lần đầu sẽ tải checkpoint vài trăm MB)...")
    model = AutoModel.from_pretrained(model_id)
    model.eval()
    processor = AutoProcessor.from_pretrained(model_id)

    def encode(texts: list[str]) -> np.ndarray:
        # Giống SigLIP v1: huấn luyện với padding cố định "max_length".
        inputs = processor(text=list(texts), return_tensors="pt", padding="max_length", truncation=True)
        with torch.no_grad():
            out = model.get_text_features(**inputs)
        vec = _extract_embedding(out, model, projection_attr=None)
        vec = torch.nn.functional.normalize(vec, dim=-1)
        return vec.numpy().astype(np.float32)
    return encode


def _build_dfn_encoder() -> Callable[[list[str]], np.ndarray]:
    import torch
    import open_clip
    model_name = "ViT-H-14-quickgelu"
    pretrained = "dfn5b"
    print(f"[multi_index]   tải {model_name} (pretrained={pretrained}, checkpoint vài GB)...")
    model, _, _ = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    model.eval()
    tokenizer = open_clip.get_tokenizer(model_name)

    def encode(texts: list[str]) -> np.ndarray:
        tokens = tokenizer(list(texts))
        with torch.no_grad():
            vec = model.encode_text(tokens)
        vec = torch.nn.functional.normalize(vec, dim=-1)
        return vec.numpy().astype(np.float32)
    return encode


def _patch_missing_clip_loss() -> None:
    """jina-clip-v2 (trust_remote_code=True) làm `from transformers.models.clip.modeling_clip import
    (..., clip_loss)` — transformers>=5.x đã bỏ hàm nội bộ `clip_loss` này -> ImportError ngay lúc
    AutoModel.from_pretrained() import module tuỳ biến của Jina, XÁC NHẬN THẬT bằng smoke-test local
    (2026-08-20, transformers==5.15.0). Giống hệt lỗi đã gặp khi encode ảnh trên Kaggle (xem
    kaggle_jobs/03_jina/main.py:_patch_missing_clip_loss() + kaggle_jobs/README.md mục "Cập nhật 6").
    `clip_loss` chỉ dùng lúc HUẤN LUYỆN (return_loss=True) — encode_text()/encode_image() không bao
    giờ chạy nhánh đó, nên chỉ cần vá lại đúng công thức gốc (ổn định nhiều năm của CLIP) vào module
    trước khi Jina import, không cần hạ version transformers (tránh phá vitl14/siglip đang chạy tốt
    ở 5.15.0). Copy nguyên logic từ kaggle_jobs/03_jina/main.py, giữ 1 bản riêng ở đây vì 2 file cố
    ý không import lẫn nhau (module này chạy local, kaggle_jobs/ chạy trên Kaggle)."""
    import transformers.models.clip.modeling_clip as _clip_modeling
    if hasattr(_clip_modeling, "clip_loss"):
        return
    import torch
    import torch.nn.functional as F

    def _contrastive_loss(logits):
        return F.cross_entropy(logits, torch.arange(len(logits), device=logits.device))

    def _clip_loss(similarity):
        caption_loss = _contrastive_loss(similarity)
        image_loss = _contrastive_loss(similarity.t())
        return (caption_loss + image_loss) / 2.0

    _clip_modeling.clip_loss = _clip_loss
    print("[multi_index]   đã vá clip_loss còn thiếu trong transformers.models.clip.modeling_clip "
          "(chỉ cần cho import, không dùng tới khi chỉ encode text)")


def _build_jina_encoder() -> Callable[[list[str]], np.ndarray]:
    """jina-clip-v2 dùng trust_remote_code=True (modeling tuỳ biến riêng, KHÔNG phải CLIPModel/
    SiglipModel chuẩn của transformers) — model có sẵn hàm tiện lợi model.encode_text(texts) trả
    thẳng embedding, không đi qua get_text_features()/_extract_embedding() như vitl14/siglip. Xem
    kaggle_jobs/03_jina/main.py (bên đó dùng encode_image() cùng model, cùng API family)."""
    import torch
    from transformers import AutoModel
    model_id = "jinaai/jina-clip-v2"
    print(f"[multi_index]   tải {model_id} (lần đầu sẽ tải checkpoint ~1-2GB, trust_remote_code=True)...")
    _patch_missing_clip_loss()
    try:
        model = AutoModel.from_pretrained(
            model_id, trust_remote_code=True, torch_dtype="float32", use_flash_attn=False
        )
    except TypeError:
        # bản model card cũ hơn không nhận kwarg use_flash_attn — xem kaggle_jobs/03_jina/main.py
        model = AutoModel.from_pretrained(model_id, trust_remote_code=True, torch_dtype="float32")
    model.eval()

    def encode(texts: list[str]) -> np.ndarray:
        with torch.no_grad():
            vecs = model.encode_text(list(texts))
        vecs = np.asarray(vecs, dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms
    return encode


@dataclass
class ModelSpec:
    tag: str
    features_dir_name: str  # thư mục con dưới data/extracted/
    build_encoder: Callable[[], Callable[[list[str]], np.ndarray]]


MODEL_REGISTRY: dict[str, ModelSpec] = {
    "clip_vitb32": ModelSpec("clip_vitb32", "clip-features-32", _build_clip_vitb32_encoder),
    "vitl14":      ModelSpec("vitl14",      "features_vitl14",  _build_vitl14_encoder),
    "siglip":      ModelSpec("siglip",      "features_siglip",  _build_siglip_encoder),
    "siglip2":     ModelSpec("siglip2",     "features_siglip2", _build_siglip2_encoder),
    "dfn":         ModelSpec("dfn",         "features_dfn",     _build_dfn_encoder),
    "jina":        ModelSpec("jina",        "features_jina",    _build_jina_encoder),
}

_INDEX_CACHE: dict[str, tuple[np.ndarray, pd.DataFrame]] = {}
_ENCODER_CACHE: dict[str, Callable[[list[str]], np.ndarray]] = {}


def get_index(tag: str) -> tuple[np.ndarray, pd.DataFrame]:
    if tag not in _INDEX_CACHE:
        spec = MODEL_REGISTRY[tag]
        features_dir = _DATA_DIR / spec.features_dir_name
        print(f"[multi_index] Build index '{tag}' từ {features_dir} ...")
        matrix, meta = load_feature_index(features_dir)
        print(f"[multi_index] '{tag}': {len(meta)} keyframe, chiều {matrix.shape[1]}")
        _INDEX_CACHE[tag] = (matrix, meta)
    return _INDEX_CACHE[tag]


def get_encoder(tag: str) -> Callable[[list[str]], np.ndarray]:
    if tag not in _ENCODER_CACHE:
        spec = MODEL_REGISTRY[tag]
        print(f"[multi_index] Load text encoder '{tag}' ...")
        _ENCODER_CACHE[tag] = spec.build_encoder()
    return _ENCODER_CACHE[tag]


def retrieve(tag: str, query_text: str, top_k: int = 100) -> pd.DataFrame:
    """Top-k keyframe gần nhất với query_text trong không gian embedding của model `tag`."""
    matrix, meta = get_index(tag)
    encoder = get_encoder(tag)
    q_vec = encoder([query_text])[0]
    if q_vec.shape[0] != matrix.shape[1]:
        raise RuntimeError(
            f"[{tag}] text encoder ra chiều {q_vec.shape[0]}, ma trận ảnh chiều {matrix.shape[1]} "
            f"— 2 bên không cùng không gian embedding, kiểm tra lại checkpoint/API."
        )
    top_k = min(top_k, len(meta))
    scores = matrix @ q_vec
    top_idx = np.argsort(-scores)[:top_k]
    out = meta.iloc[top_idx].copy().reset_index(drop=True)
    out["score"] = scores[top_idx]
    out["rank"] = np.arange(1, len(out) + 1)
    return out


if __name__ == "__main__":
    import sys
    tags = sys.argv[1:] or list(MODEL_REGISTRY.keys())
    sample_text = "a person walking on the street"
    for tag in tags:
        print(f"\n=== smoke-test: {tag} ===")
        hits = retrieve(tag, sample_text, top_k=3)
        for _, row in hits.iterrows():
            print(f"  #{int(row['rank'])}  {row['video_id']}  frame_id={int(row['frame_id'])}  "
                  f"score={row['score']:.4f}")
    print("\nXONG.")
