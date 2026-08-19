"""
AIC2026 Search & Submit Tool — Human-in-the-loop submission UI.

Chạy:  .venv\\Scripts\\python.exe scripts\\app.py
Mở:    http://127.0.0.1:7860

4 tabs:
  KIS    — Textual KIS search + gallery + editable results
  Q&A    — Pipeline Q&A + answer + editable
  TRAKE  — Multi-event alignment + editable frame IDs
  Export — Queue manager → Export ZIP 1-click
"""
from __future__ import annotations

import sys
import warnings
import logging
from pathlib import Path

# ─── Suppress noisy warnings ───────────────────────────────────────────────────
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("litellm").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

# ─── Path setup ────────────────────────────────────────────────────────────────
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

# ─── Imports (heavy — load once at startup) ────────────────────────────────────
import gradio as gr
import pandas as pd

print("[app] Loading index + CLIP model (one-time)...")
from agent.tools.retrieve import fast_retrieve, fast_retrieve_for_video
print("[app] Ready.")

# ─── Helpers ───────────────────────────────────────────────────────────────────

def _hits_to_df(hits: list[dict], extra_cols: dict | None = None) -> pd.DataFrame:
    """Convert retrieve hits to display DataFrame."""
    rows = []
    for h in hits:
        row = {
            "video_id":  h["video_id"],
            "frame_id":  h["frame_id"],
            "pts_time":  round(h["pts_time"], 1),
            "score":     round(h["score"], 4),
        }
        if extra_cols:
            row.update(extra_cols)
        rows.append(row)
    return pd.DataFrame(rows)


def _hits_to_gallery(hits: list[dict], max_img: int = 30) -> list[tuple]:
    """Build gallery items (image_path, caption) from hits."""
    items = []
    for i, h in enumerate(hits[:max_img], 1):
        cap = f"#{i} {h['video_id']} | frame {h['frame_id']} | t={h['pts_time']:.1f}s | {h['score']:.3f}"
        jpg = h.get("jpg_path")
        if jpg and Path(jpg).exists():
            items.append((jpg, cap))
    return items


def _df_to_submission_rows(df: pd.DataFrame, query_type: str, answer: str = "") -> list[dict]:
    """Convert edited DataFrame to submission queue rows."""
    rows = []
    for i, (_, r) in enumerate(df.iterrows(), 1):
        try:
            frame_id = int(r["frame_id"])
        except (TypeError, ValueError):
            raise ValueError(f"Dòng {i} (video_id={r.get('video_id')}): frame_id không hợp lệ.")
        row = {
            "video_id":   str(r["video_id"]).replace(".mp4", ""),
            "frame_id":   frame_id,
            "query_type": query_type,
        }
        if query_type == "qa":
            row["answer"] = answer
        rows.append(row)
    return rows


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — KIS
# ═══════════════════════════════════════════════════════════════════════════════

def kis_search(query: str, top_k: int, auto_translate: bool) -> tuple:
    """Run KIS search and return gallery + dataframe."""
    if not query.strip():
        return [], pd.DataFrame(), "⚠️ Nhập query trước."

    query_used = query
    status_parts = []

    if auto_translate:
        try:
            from agent.tools.rewrite import rewrite_query
            query_used = rewrite_query(query)
            status_parts.append(f"🌐 Translated: **{query_used}**")
        except Exception as e:
            status_parts.append(f"⚠️ Translate failed: {e}. Using original.")

    hits = fast_retrieve(query_used, top_k=int(top_k))
    gallery = _hits_to_gallery(hits)
    df = _hits_to_df(hits)
    status_parts.append(f"✅ Found **{len(hits)}** results | top score = {hits[0]['score']:.4f}")
    return gallery, df, "\n\n".join(status_parts)


def kis_add_to_queue(df: pd.DataFrame, query_id: str, queue: list) -> tuple:
    """Add KIS results to submission queue."""
    if df is None or len(df) == 0:
        return queue, "⚠️ Chưa có kết quả để thêm."
    query_id = query_id.strip() or "kis_query_001"
    try:
        rows = _df_to_submission_rows(df, "kis")
    except ValueError as e:
        return queue, f"⚠️ {e}"
    queue = [q for q in queue if q.get("_query_id") != query_id]  # replace if exists
    queue.append({"_query_id": query_id, "_type": "kis", "_rows": rows})
    return queue, f"✅ Đã thêm **{query_id}** ({len(rows)} rows) vào queue. Tổng: {len(queue)} query."


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Q&A
# ═══════════════════════════════════════════════════════════════════════════════

def qa_run(query: str, question: str, top_k: int) -> tuple:
    """Run Q&A pipeline and return results."""
    if not query.strip():
        return [], pd.DataFrame(), "", 0.0, "⚠️ Nhập query trước."
    try:
        from agent.pipeline_qa import run_qa
        out = run_qa(query, question=question or None, top_k=int(top_k))
        hits = out["results"]
        gallery = _hits_to_gallery(hits[:10])
        df = _hits_to_df(hits[:100])
        answer = out["answer"]
        conf = out["confidence"]
        status = (
            f"✅ Answer: **{answer}** | Confidence: {conf:.0%} | "
            f"Method: {out['best_hit'].get('method', '?') if isinstance(out.get('best_hit'), dict) else '?'} | "
            f"Loops: {out['n_loops']}"
        )
        return gallery, df, answer, conf, status
    except Exception as e:
        return [], pd.DataFrame(), "", 0.0, f"❌ Lỗi: {e}"


def qa_add_to_queue(df: pd.DataFrame, answer: str, query_id: str, queue: list) -> tuple:
    """Add Q&A results to queue."""
    if df is None or len(df) == 0:
        return queue, "⚠️ Chưa có kết quả."
    query_id = query_id.strip() or "qa_query_001"
    try:
        rows = _df_to_submission_rows(df, "qa", answer=answer)
    except ValueError as e:
        return queue, f"⚠️ {e}"
    queue = [q for q in queue if q.get("_query_id") != query_id]
    queue.append({"_query_id": query_id, "_type": "qa", "_rows": rows, "_answer": answer})
    return queue, f"✅ Đã thêm **{query_id}** QA ({len(rows)} rows). Tổng: {len(queue)} query."


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRAKE
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_events(events_text: str) -> list[str]:
    """Tách ô Events (mỗi dòng = 1 khoảnh khắc) thành list, bỏ dòng trống."""
    return [e.strip() for e in events_text.strip().splitlines() if e.strip()]


def trake_run(global_query: str, events_text: str, top_k_video: int) -> tuple:
    """Run TRAKE pipeline. events_text: one event per line."""
    if not global_query.strip():
        return pd.DataFrame(), "⚠️ Nhập global query trước."
    events = _parse_events(events_text)
    if not events:
        return pd.DataFrame(), "⚠️ Nhập ít nhất 1 event."
    try:
        from agent.pipeline_trake import run_trake
        out = run_trake(global_query, events, top_k_video=int(top_k_video), top_k_frame=10)
        results = out["results"]

        # Build display DF: 1 row per candidate video
        rows = []
        for r in results:
            fids = " | ".join(str(f) for f in r["frame_ids"])
            rows.append({
                "video_id":  r["video_id"],
                "frame_ids": fids,
                "score":     round(r["score"], 4),
            })
        df = pd.DataFrame(rows)
        best = out["best"]
        status = (
            f"✅ Best: **{best.get('video_id')}** | "
            f"Frames: {best.get('frame_ids')} | "
            f"Score: {best.get('score', 0):.4f} | "
            f"{len(events)} events aligned"
        )
        return df, status
    except Exception as e:
        return pd.DataFrame(), f"❌ Lỗi: {e}"


def trake_add_to_queue(df: pd.DataFrame, query_id: str, events_text: str, queue: list) -> tuple:
    """Add TRAKE result to queue (top-1 video only, with all frame_ids)."""
    if df is None or len(df) == 0:
        return queue, "⚠️ Chưa có kết quả."
    n_events = len(_parse_events(events_text))
    if n_events == 0:
        return queue, "⚠️ Không xác định được số mốc kỳ vọng (ô Events trống) — không thể thêm vào hàng đợi."
    query_id = query_id.strip() or "trake_query_001"

    # Parse frame_ids từ cột "frame_ids" (string "1 | 2 | 3"), chặn nếu thiếu mốc so với số event
    submission_rows = []
    problems = []
    for _, r in df.iterrows():
        video_id = str(r["video_id"]).replace(".mp4", "")
        fids_raw = str(r.get("frame_ids", ""))
        fids = [int(f.strip()) for f in fids_raw.split("|") if f.strip().isdigit()]
        if len(fids) != n_events:
            problems.append(f"{video_id} có {len(fids)}/{n_events} frame_id hợp lệ")
            continue
        submission_rows.append({
            "video_id":  video_id,
            "frame_ids": fids,
            "query_type": "trake",
        })

    if problems:
        return queue, "⚠️ Thiếu mốc, chưa thêm vào hàng đợi:\n" + "\n".join(f"- {p}" for p in problems)

    queue = [q for q in queue if q.get("_query_id") != query_id]
    queue.append({"_query_id": query_id, "_type": "trake", "_rows": submission_rows})
    return queue, f"✅ Đã thêm **{query_id}** TRAKE ({len(submission_rows)} rows). Tổng: {len(queue)} query."


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def export_show_queue(queue: list) -> tuple:
    """Display current submission queue."""
    if not queue:
        return pd.DataFrame(), "📭 Queue trống. Thêm kết quả từ các tab KIS/Q&A/TRAKE."
    rows = []
    for item in queue:
        rows.append({
            "query_id":  item["_query_id"],
            "type":      item["_type"].upper(),
            "n_rows":    len(item["_rows"]),
        })
    df = pd.DataFrame(rows)
    return df, f"📋 Queue: **{len(queue)}** query, sẵn sàng export."


def export_zip(queue: list) -> tuple:
    """Build submission CSVs + ZIP from queue."""
    if not queue:
        return None, "⚠️ Queue trống."

    from submit.build_submission import (
        build_kis_csv, build_qa_csv, build_trake_csv, build_zip_submission
    )
    from submit.validate_submission import validate_file

    out_dir = _SCRIPTS.parent / "submissions"
    csv_files = []
    errors = []

    for item in queue:
        qid   = item["_query_id"]
        qtype = item["_type"]
        rows  = item["_rows"]
        try:
            if qtype == "kis":
                # Convert to hit-like list
                hits = [{"video_id": r["video_id"], "frame_id": r["frame_id"],
                         "frame_idx": r["frame_id"] - 1, "pts_time": 0.0,
                         "score": 1.0, "jpg_path": None} for r in rows]
                csv_files.append(build_kis_csv(qid, hits, output_dir=out_dir))

            elif qtype == "qa":
                hits = [{"video_id": r["video_id"], "frame_id": r["frame_id"],
                         "frame_idx": r["frame_id"] - 1, "pts_time": 0.0,
                         "score": 1.0, "answer": r.get("answer", "N/A"), "jpg_path": None}
                        for r in rows]
                csv_files.append(build_qa_csv(qid, hits, output_dir=out_dir))

            elif qtype == "trake":
                csv_files.append(build_trake_csv(qid, rows, output_dir=out_dir))

        except Exception as e:
            errors.append(f"❌ {qid}: {e}")

    if not csv_files:
        return None, "❌ Không tạo được CSV nào.\n" + "\n".join(errors)

    zip_path = build_zip_submission(csv_files, tag="manual")
    ok = validate_file(zip_path)
    msg_parts = [
        f"{'✅' if ok else '⚠️'} ZIP: `{zip_path.name}`",
        f"📁 Path: `{zip_path}`",
        f"📊 {len(csv_files)} CSVs | Validate: {'PASS' if ok else 'FAIL'}",
    ]
    if errors:
        msg_parts.append("⚠️ Lỗi:\n" + "\n".join(errors))
    return str(zip_path), "\n\n".join(msg_parts)


def export_clear_queue() -> tuple:
    return [], pd.DataFrame(), "🗑️ Queue đã được xóa."


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD UI
# ═══════════════════════════════════════════════════════════════════════════════

_CSS = """
.tab-header { font-size: 1.05em; font-weight: 600; margin-bottom: 8px; }
.status-box textarea { font-family: monospace; font-size: 0.88em; }
footer { display: none !important; }
"""

with gr.Blocks(title="AIC2026 Search & Submit") as demo:

    # ── Global state ──────────────────────────────────────────────────────────
    submission_queue = gr.State([])

    # ── Header ────────────────────────────────────────────────────────────────
    gr.Markdown(
        "# 🎬 AIC2026 Search & Submit Tool\n"
        "> **Human-in-the-loop**: Tìm kiếm → Xem → Sửa tay → Export ZIP"
    )

    with gr.Tabs():

        # ════════════════════════════════════════════════════════════
        # TAB 1: KIS
        # ════════════════════════════════════════════════════════════
        with gr.TabItem("🔍 KIS — Textual Search"):
            gr.Markdown("### Tìm keyframe theo mô tả văn bản")
            with gr.Row():
                with gr.Column(scale=4):
                    kis_query = gr.Textbox(
                        label="Mô tả cảnh cần tìm",
                        placeholder="VD: Một người đang phát biểu tại cuộc họp báo ngoài trời",
                        lines=2,
                    )
                with gr.Column(scale=1):
                    kis_topk    = gr.Slider(5, 100, value=20, step=5, label="Top-k")
                    kis_auto_tr = gr.Checkbox(value=True, label="🌐 Auto-translate VN→EN")

            kis_search_btn = gr.Button("🔍 Search", variant="primary", size="lg")

            kis_gallery = gr.Gallery(
                label="Kết quả (keyframes có ảnh)",
                columns=5,
                height=380,
                show_label=True,
            )
            kis_status = gr.Markdown("_Nhấn Search để bắt đầu._")
            kis_df = gr.Dataframe(
                label="📋 Kết quả (chỉnh sửa được — xóa/reorder trước khi Add)",
                interactive=True,
                wrap=True,
            )
            with gr.Row():
                kis_qid = gr.Textbox(
                    label="Query ID (tên file CSV, khớp với file BTC cung cấp)",
                    placeholder="VD: query_1_kis",
                    scale=3,
                )
                kis_add_btn = gr.Button("➕ Add to Submission Queue", scale=1)
            kis_queue_status = gr.Markdown()

            # Events
            kis_search_btn.click(
                kis_search,
                inputs=[kis_query, kis_topk, kis_auto_tr],
                outputs=[kis_gallery, kis_df, kis_status],
            )
            kis_query.submit(
                kis_search,
                inputs=[kis_query, kis_topk, kis_auto_tr],
                outputs=[kis_gallery, kis_df, kis_status],
            )
            kis_add_btn.click(
                kis_add_to_queue,
                inputs=[kis_df, kis_qid, submission_queue],
                outputs=[submission_queue, kis_queue_status],
            )

        # ════════════════════════════════════════════════════════════
        # TAB 2: Q&A
        # ════════════════════════════════════════════════════════════
        with gr.TabItem("❓ Q&A — Question Answering"):
            gr.Markdown("### Tìm keyframe + trả lời câu hỏi về nội dung")
            with gr.Row():
                with gr.Column(scale=3):
                    qa_query = gr.Textbox(
                        label="Mô tả cảnh (để tìm kiếm)",
                        placeholder="VD: Người phụ nữ mặc áo đỏ đang nhận giải thưởng trên sân khấu",
                        lines=2,
                    )
                    qa_question = gr.Textbox(
                        label="Câu hỏi cụ thể (để trích xuất answer)",
                        placeholder="VD: Màu sắc của bó hoa mà người đó cầm là gì?",
                        lines=2,
                    )
                with gr.Column(scale=1):
                    qa_topk = gr.Slider(5, 50, value=20, step=5, label="Top-k retrieve")

            qa_run_btn = gr.Button("🤖 Run Q&A Pipeline", variant="primary", size="lg")

            with gr.Row():
                with gr.Column(scale=2):
                    qa_gallery = gr.Gallery(
                        label="Top frames",
                        columns=3,
                        height=300,
                    )
                with gr.Column(scale=1):
                    qa_answer_box = gr.Textbox(
                        label="💡 Answer (chỉnh sửa được)",
                        lines=3,
                        interactive=True,
                    )
                    qa_conf = gr.Number(label="Confidence", precision=2, interactive=False)
                    qa_status = gr.Markdown("_Nhấn Run để bắt đầu._")

            qa_df = gr.Dataframe(
                label="📋 Top-100 rows để nộp (có thể xóa/reorder)",
                interactive=True,
                wrap=True,
            )
            with gr.Row():
                qa_qid     = gr.Textbox(label="Query ID", placeholder="VD: query_2_qa", scale=3)
                qa_add_btn = gr.Button("➕ Add to Queue", scale=1)
            qa_queue_status = gr.Markdown()

            # Events
            qa_run_btn.click(
                qa_run,
                inputs=[qa_query, qa_question, qa_topk],
                outputs=[qa_gallery, qa_df, qa_answer_box, qa_conf, qa_status],
            )
            qa_add_btn.click(
                qa_add_to_queue,
                inputs=[qa_df, qa_answer_box, qa_qid, submission_queue],
                outputs=[submission_queue, qa_queue_status],
            )

        # ════════════════════════════════════════════════════════════
        # TAB 3: TRAKE
        # ════════════════════════════════════════════════════════════
        with gr.TabItem("🎬 TRAKE — Event Sequence"):
            gr.Markdown(
                "### Tìm video + căn chỉnh chuỗi khoảnh khắc theo thứ tự thời gian\n"
                "_Mỗi dòng trong ô Events = 1 khoảnh khắc ngữ nghĩa, theo thứ tự xảy ra._"
            )
            with gr.Row():
                with gr.Column(scale=3):
                    trake_global = gr.Textbox(
                        label="Mô tả tổng quát chuỗi sự kiện (để tìm video)",
                        placeholder="VD: An athlete performing a high jump in a stadium competition",
                        lines=2,
                    )
                    trake_events = gr.Textbox(
                        label="Danh sách khoảnh khắc (mỗi dòng = 1 khoảnh khắc, theo thứ tự)",
                        placeholder=(
                            "athlete running during approach run\n"
                            "athlete jumping over the high bar at peak\n"
                            "athlete landing on the mat after clearing"
                        ),
                        lines=6,
                    )
                with gr.Column(scale=1):
                    trake_topk_video = gr.Slider(3, 10, value=5, step=1, label="Top-k videos")

            trake_run_btn = gr.Button("🎬 Run TRAKE Pipeline", variant="primary", size="lg")
            trake_status  = gr.Markdown("_Nhấn Run để bắt đầu._")
            trake_df = gr.Dataframe(
                label="📋 Video candidates + aligned frame_ids (chỉnh sửa được)",
                interactive=True,
                wrap=True,
            )
            gr.Markdown(
                "_💡 Cột **frame_ids**: dạng `40530 | 40727 | 40895` — "
                "tương ứng với từng khoảnh khắc. Sửa tay nếu cần._"
            )
            with gr.Row():
                trake_qid     = gr.Textbox(label="Query ID", placeholder="VD: query_3_trake", scale=3)
                trake_add_btn = gr.Button("➕ Add to Queue", scale=1)
            trake_queue_status = gr.Markdown()

            # Events
            trake_run_btn.click(
                trake_run,
                inputs=[trake_global, trake_events, trake_topk_video],
                outputs=[trake_df, trake_status],
            )
            trake_add_btn.click(
                trake_add_to_queue,
                inputs=[trake_df, trake_qid, trake_events, submission_queue],
                outputs=[submission_queue, trake_queue_status],
            )

        # ════════════════════════════════════════════════════════════
        # TAB 4: EXPORT
        # ════════════════════════════════════════════════════════════
        with gr.TabItem("📦 Export — Nộp bài"):
            gr.Markdown(
                "### Tổng hợp và xuất file ZIP để nộp lên Codabench\n"
                "_Kiểm tra danh sách query → Export ZIP → Upload lên Codabench._"
            )

            export_refresh_btn = gr.Button("🔄 Refresh Queue", variant="secondary")
            export_queue_df = gr.Dataframe(
                label="📋 Submission Queue",
                interactive=False,
                wrap=True,
            )
            export_queue_info = gr.Markdown("_Nhấn Refresh để xem queue hiện tại._")

            gr.Markdown("---")
            with gr.Row():
                export_zip_btn   = gr.Button("📦 Export ZIP", variant="primary", size="lg", scale=2)
                export_clear_btn = gr.Button("🗑️ Clear Queue", variant="stop", scale=1)

            export_zip_path = gr.Textbox(
                label="📁 Đường dẫn file ZIP (copy để upload lên Codabench)",
                interactive=False,
                lines=1,
            )
            export_status = gr.Markdown()

            # Events
            export_refresh_btn.click(
                export_show_queue,
                inputs=[submission_queue],
                outputs=[export_queue_df, export_queue_info],
            )
            export_zip_btn.click(
                export_zip,
                inputs=[submission_queue],
                outputs=[export_zip_path, export_status],
            )
            export_clear_btn.click(
                export_clear_queue,
                outputs=[submission_queue, export_queue_df, export_queue_info],
            )


# ─── Launch ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    port = int(os.getenv("GRADIO_PORT", 7860))
    print(f"\n[app] Starting AIC2026 Search & Submit Tool on port {port}...")
    demo.launch(
        server_port=port,
        share=False,
        inbrowser=True,   # tu dong mo trinh duyet
        theme=gr.themes.Soft(primary_hue="blue", neutral_hue="slate"),
        css=_CSS,
    )
