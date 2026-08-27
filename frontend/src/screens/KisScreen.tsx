import { useState } from "react";
import { api } from "../api/client";
import type { Hit, QueueRow } from "../api/client";
import { getSessionId } from "../session";
import KeyframeDetail from "../components/KeyframeDetail";
import Thumb from "../components/Thumb";
import RewriteChips from "../components/RewriteChips";
import TopKSlider from "../components/TopKSlider";

// Luoi ket qua KIS = danh sach nop luon (khong con cot "Danh sach nop" rieng ben trai):
//  - moi card mang thu hang #i+1, keo tha truc tiep tren luoi de doi uu tien
//  - nut x tren card de loai khoi danh sach nop
//  - bam card -> mo video kiem chung, tu do "Cap nhat vi tri #i" ghi de frame moi vao dung card
//  - o Query ID + nut "Them vao hang doi" nam o thanh noi co dinh goc duoi-phai (khong phai cuon
//    len dau trang de nop)
type RankedHit = Hit & { _key: string };

export default function KisScreen() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(20);
  const [hits, setHits] = useState<RankedHit[]>([]);
  const [status, setStatus] = useState("");
  const [submitMsg, setSubmitMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [detailIdx, setDetailIdx] = useState<number | null>(null);
  const [queryId, setQueryId] = useState("");

  async function runSearch() {
    if (!query.trim()) {
      setStatus("⚠️ Nhập query trước khi tìm.");
      return;
    }
    setLoading(true);
    try {
      const { hits: raw } = await api.kisSearch(query, topK);
      setHits(raw.map((h, i) => ({ ...h, _key: `${h.video_id}-${h.frame_id}-${i}` })));
      setDetailIdx(null);
      setStatus(`✅ Tìm thấy ${raw.length} kết quả | điểm cao nhất = ${raw[0]?.score.toFixed(4) ?? "-"}`);
    } catch (e) {
      setStatus(`❌ Lỗi: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  function reorder(from: number, to: number) {
    if (from === to) return;
    setHits((list) => {
      const next = list.slice();
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
    setDragFrom(to);
  }

  function removeAt(i: number) {
    setHits((list) => list.filter((_, k) => k !== i));
  }

  function updateHitAt(i: number, patch: Partial<Hit>) {
    setHits((list) => list.map((h, k) => (k === i ? { ...h, ...patch } : h)));
  }

  async function addToQueue() {
    if (hits.length === 0) {
      setSubmitMsg("⚠️ Chưa có kết quả để nộp.");
      return;
    }
    // Kiem tra frame_id (giong _df_to_submission_rows ben app.py cu): phai la so nguyen duong.
    const rows: { video_id: string; frame_id: number }[] = [];
    for (const h of hits) {
      if (!Number.isInteger(h.frame_id) || h.frame_id <= 0) {
        setSubmitMsg(`⚠️ frame_id không hợp lệ ở ${h.video_id}: ${h.frame_id}`);
        return;
      }
      rows.push({ video_id: h.video_id, frame_id: h.frame_id });
    }
    const qid = queryId.trim() || "kis-query-001";
    const row: QueueRow = { query_id: qid, query_type: "kis", rows };
    try {
      await api.addToQueue(getSessionId(), row);
      const msg = `✅ Đã thêm ${qid} (${rows.length} dòng · hạng 1 = ${hits[0].video_id}/${hits[0].frame_id}).`;
      setSubmitMsg(msg);
      setStatus(msg);
    } catch (e) {
      setSubmitMsg(`❌ Lỗi khi thêm: ${(e as Error).message}`);
    }
  }

  if (detailIdx !== null && hits[detailIdx]) {
    const idx = detailIdx;
    return (
      <KeyframeDetail
        hit={hits[idx]}
        rank={idx + 1}
        onBack={() => setDetailIdx(null)}
        onUpdateFrame={(h) =>
          updateHitAt(idx, { frame_id: h.frame_id, frame_idx: h.frame_idx, pts_time: h.pts_time })
        }
      />
    );
  }

  return (
    <div className="screen kis-screen">
      <div className="topbar">
        <input
          className="input search-input"
          placeholder="VD: một người đang phát biểu tại cuộc họp báo ngoài trời, phía sau có logo màu xanh…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runSearch()}
        />
        <button className="btn btn-primary" onClick={runSearch} disabled={loading}>
          {loading ? "Đang tìm…" : "Tìm"}
        </button>
      </div>

      <RewriteChips query={query} onPick={setQuery} />
      <TopKSlider label="Số kết quả (top-k)" value={topK} min={5} max={100} step={5} onChange={setTopK} />

      <p className="status-line">{status}</p>

      {hits.length === 0 ? (
        <div className="kis-empty">
          <h2>Bạn cần tìm ảnh nào?</h2>
          <p className="text-muted">
            Mô tả cảnh bằng tiếng Việt hoặc tiếng Anh. Lưới kết quả cũng chính là danh sách nộp —
            kéo thả để đổi thứ hạng, bấm 1 ảnh để mở video kiểm chứng.
          </p>
        </div>
      ) : (
        <>
          <p className="text-muted kis-hint">
            Kéo thả card để đổi thứ hạng — hạng #1 là đáp án chính khi nộp. Bấm card để mở video &amp; sửa
            frame. Nút × để loại khỏi danh sách.
          </p>
          <div className="kis-grid">
            {hits.map((h, i) => (
              <div
                key={h._key}
                className={`kis-card ${dragFrom === i ? "dragging" : ""}`}
                draggable
                onDragStart={() => setDragFrom(i)}
                onDragEnter={() => dragFrom !== null && reorder(dragFrom, i)}
                onDragOver={(e) => e.preventDefault()}
                onDragEnd={() => setDragFrom(null)}
                onClick={() => setDetailIdx(i)}
              >
                <Thumb videoId={h.video_id} frameIdx={h.frame_idx} />
                <span className="mono card-rank">#{i + 1}</span>
                <button
                  className="card-remove"
                  title="Loại khỏi danh sách nộp"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeAt(i);
                  }}
                >
                  ×
                </button>
                <div className="card-caption">
                  <span>
                    {h.video_id} · {h.frame_id}
                  </span>
                  <span className="text-muted">{h.score.toFixed(3)}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {hits.length > 0 && (
        <div className="kis-submit-bar">
          <input
            className="input"
            placeholder="Query ID (VD: query-1-kis)"
            value={queryId}
            onChange={(e) => setQueryId(e.target.value)}
          />
          <button className="btn btn-primary" onClick={addToQueue}>
            Thêm vào hàng đợi
          </button>
          {submitMsg && <span className="kis-submit-msg">{submitMsg}</span>}
        </div>
      )}
    </div>
  );
}
