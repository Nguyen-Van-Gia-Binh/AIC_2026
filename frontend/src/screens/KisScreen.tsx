import { useState } from "react";
import { api } from "../api/client";
import type { Hit, QueueRow } from "../api/client";
import { getSessionId } from "../session";
import KeyframeDetail from "../components/KeyframeDetail";
import Thumb from "../components/Thumb";

type ShortlistItem = Hit & { _key: string };

export default function KisScreen() {
  const [query, setQuery] = useState("");
  const [topK] = useState(20);
  const [hits, setHits] = useState<Hit[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [shortlist, setShortlist] = useState<ShortlistItem[]>([]);
  // Toa do dong dang keo (drag) trong shortlist — logic reorder giong het mockup 1b (onDragStart/
  // onDragEnter/onDragOver/onDragEnd), chuyen tu JS thuan sang React state.
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [detail, setDetail] = useState<Hit | null>(null);
  const [queryId, setQueryId] = useState("");

  async function runSearch() {
    if (!query.trim()) {
      setStatus("⚠️ Nhập query trước khi tìm.");
      return;
    }
    setLoading(true);
    try {
      const { hits } = await api.kisSearch(query, topK);
      setHits(hits);
      setShortlist(hits.slice(0, 5).map((h, i) => ({ ...h, _key: `${h.video_id}-${h.frame_id}-${i}` })));
      setStatus(`✅ Tìm thấy ${hits.length} kết quả | điểm cao nhất = ${hits[0]?.score.toFixed(4) ?? "-"}`);
    } catch (e) {
      setStatus(`❌ Lỗi: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  function reorderShortlist(from: number, to: number) {
    if (from === to) return;
    setShortlist((list) => {
      const next = list.slice();
      const [item] = next.splice(from, 1);
      next.splice(to, 0, item);
      return next;
    });
  }

  function removeFromShortlist(key: string) {
    setShortlist((list) => list.filter((h) => h._key !== key));
  }

  async function addToQueue() {
    if (shortlist.length === 0) {
      setStatus("⚠️ Chưa có kết quả để thêm.");
      return;
    }
    const qid = queryId.trim() || "kis-query-001";
    const row: QueueRow = {
      query_id: qid,
      query_type: "kis",
      rows: shortlist.map((h) => ({ video_id: h.video_id, frame_id: h.frame_id })),
    };
    await api.addToQueue(getSessionId(), row);
    setStatus(`✅ Đã thêm ${qid} (${shortlist.length} dòng) vào hàng đợi.`);
  }

  if (detail) {
    return (
      <KeyframeDetail
        hit={detail}
        onBack={() => setDetail(null)}
        onAddToShortlist={(h) => {
          setShortlist((list) => [...list, { ...h, _key: `${h.video_id}-${h.frame_id}-${list.length}` }]);
          setDetail(null);
        }}
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
      <p className="status-line">{status}</p>

      {hits.length === 0 ? (
        <div className="kis-empty">
          <h2>Bạn cần tìm ảnh nào?</h2>
          <p className="text-muted">
            Mô tả cảnh bằng tiếng Việt hoặc tiếng Anh. Nhấn Tìm để truy vấn qua chỉ mục CLIP.
          </p>
        </div>
      ) : (
        <div className="kis-body">
          <aside className="shortlist-panel">
            <h4>Danh sách nộp</h4>
            <p className="text-muted">Kéo để đổi thứ tự — hạng 1 là đáp án chính khi nộp.</p>
            <div className="shortlist-list">
              {shortlist.map((h, i) => (
                <div
                  key={h._key}
                  className={`shortlist-row ${dragFrom === i ? "dragging" : ""}`}
                  draggable
                  onDragStart={() => setDragFrom(i)}
                  onDragEnter={() => dragFrom !== null && reorderShortlist(dragFrom, i)}
                  onDragOver={(e) => e.preventDefault()}
                  onDragEnd={() => setDragFrom(null)}
                >
                  <span className="mono rank">{i + 1}</span>
                  <div className="shortlist-thumb">
                    <Thumb videoId={h.video_id} frameIdx={h.frame_idx} />
                  </div>
                  <div className="shortlist-meta">
                    <div className="mono">{h.video_id}</div>
                    <div className="mono text-muted">frame {h.frame_id} · {h.pts_time.toFixed(1)}s</div>
                  </div>
                  <span className="mono score">{h.score.toFixed(4)}</span>
                  <button className="remove-btn" onClick={() => removeFromShortlist(h._key)}>×</button>
                </div>
              ))}
            </div>
            <div className="field">
              <label>Query ID (giữ nguyên tên BTC cấp)</label>
              <input className="input" placeholder="VD: query-1-kis" value={queryId} onChange={(e) => setQueryId(e.target.value)} />
            </div>
            <button className="btn btn-primary btn-block" onClick={addToQueue}>Thêm vào hàng đợi</button>
          </aside>

          <div className="kis-grid">
            {hits.map((h, i) => (
              <div key={`${h.video_id}-${h.frame_id}`} className="kis-card" onClick={() => setDetail(h)}>
                <Thumb videoId={h.video_id} frameIdx={h.frame_idx} />
                <span className="mono card-rank">#{i + 1}</span>
                <span className="mono card-score">{h.score.toFixed(3)}</span>
                <div className="card-caption">
                  <span>{h.video_id}</span>
                  <span className="text-muted">{h.frame_id}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
