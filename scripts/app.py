"""
Demo tìm kiếm keyframe bằng văn bản (Textual KIS baseline).

Chạy:  .venv\\Scripts\\python.exe scripts\\app.py
Mở trình duyệt tại địa chỉ Gradio in ra (mặc định http://127.0.0.1:7860)

Lưu ý: model 'clip-ViT-B-32' hiểu tiếng Anh tốt nhất. Nếu câu hỏi thi bằng tiếng Việt,
nên dịch sang tiếng Anh trước khi gõ vào ô tìm kiếm (bước dịch này để thủ công ở bản demo,
sẽ tự động hoá sau).
"""

import numpy as np
import gradio as gr
from sentence_transformers import SentenceTransformer

from index import build_index

print("Đang dựng index từ dữ liệu đã tải...")
MATRIX, META = build_index()
print(f"Index sẵn sàng: {len(META)} keyframe / {META['video_id'].nunique()} video.")

print("Đang tải model CLIP text encoder (clip-ViT-B-32)...")
MODEL = SentenceTransformer("clip-ViT-B-32")
print("Model sẵn sàng.")


def search(query: str, top_k: int):
    if not query.strip():
        return [], "Nhập câu mô tả cảnh cần tìm (tiếng Anh cho kết quả tốt nhất)."

    q_vec = MODEL.encode([query], normalize_embeddings=True)[0].astype(np.float32)
    scores = MATRIX @ q_vec  # cosine similarity vì cả 2 bên đều đã L2-normalize
    top_idx = np.argsort(-scores)[: int(top_k)]

    gallery = []
    lines = []
    for rank, idx in enumerate(top_idx, start=1):
        row = META.iloc[idx]
        score = scores[idx]
        caption = f"#{rank} | {row['video_id']} | t={row['pts_time']:.1f}s | score={score:.3f}"
        lines.append(caption)
        if isinstance(row["jpg_path"], str):
            gallery.append((row["jpg_path"], caption))

    status = "\n".join(lines)
    if not gallery:
        status = ("(Không có ảnh xem trước cho các kết quả này — video chưa được tải về máy.\n"
                   "Danh sách kết quả:)\n") + status
    return gallery, status


with gr.Blocks(title="AIC25 Search Demo") as demo:
    gr.Markdown("## Demo tìm keyframe bằng văn bản (baseline CLIP)")
    gr.Markdown(
        f"Index hiện có **{len(META)}** keyframe trên **{META['video_id'].nunique()}** video "
        f"(toàn bộ dataset). Ảnh xem trước chỉ có cho video đã tải "
        f"(**{META['jpg_path'].notna().sum()}** keyframe)."
    )
    with gr.Row():
        query_box = gr.Textbox(label="Câu mô tả (nên gõ tiếng Anh)", scale=4,
                                placeholder="e.g. a group of cyclists racing on a road")
        k_slider = gr.Slider(minimum=5, maximum=100, value=20, step=5, label="Top-k")
    search_btn = gr.Button("Tìm kiếm", variant="primary")

    gallery_out = gr.Gallery(label="Kết quả (có ảnh)", columns=5, height=500)
    status_out = gr.Textbox(label="Danh sách đầy đủ (video_id, thời điểm, điểm số)", lines=15)

    search_btn.click(search, inputs=[query_box, k_slider], outputs=[gallery_out, status_out])
    query_box.submit(search, inputs=[query_box, k_slider], outputs=[gallery_out, status_out])

if __name__ == "__main__":
    demo.launch()
