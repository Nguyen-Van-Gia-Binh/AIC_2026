import { useState } from "react";
import { api } from "../api/client";
import type { TrakeCandidate, QueueRow } from "../api/client";
import { getSessionId } from "../session";
import Thumb from "../components/Thumb";

export default function TrakeScreen() {
  const [globalQuery, setGlobalQuery] = useState("");
  const [eventsText, setEventsText] = useState("");
  const [topKVideo] = useState(5);
  const [candidates, setCandidates] = useState<TrakeCandidate[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [queryId, setQueryId] = useState("");

  function parseEvents(): string[] {
    return eventsText.split("\n").map((e) => e.trim()).filter(Boolean);
  }

  async function run() {
    const events = parseEvents();
    if (!globalQuery.trim() || events.length === 0) {
      setStatus("⚠️ Cần global query và ít nhất 1 event.");
      return;
    }
    setLoading(true);
    try {
      const out = await api.trakeRun(globalQuery, events, topKVideo);
      setCandidates(out.candidates);
      const best = out.candidates[0];
      setStatus(best
        ? `✅ Tốt nhất: ${best.video_id} | frame_ids: ${best.frame_ids.join(", ")}`
        : "⚠️ Không tìm được chuỗi hợp lệ.");
    } catch (e) {
      setStatus(`❌ Lỗi: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function addToQueue() {
    const best = candidates[0];
    if (!best) {
      setStatus("⚠️ Chưa có kết quả.");
      return;
    }
    const qid = queryId.trim() || "trake-query-001";
    const row: QueueRow = {
      query_id: qid,
      query_type: "trake",
      rows: [{ video_id: best.video_id, frame_ids: best.frame_ids }],
    };
    await api.addToQueue(getSessionId(), row);
    setStatus(`✅ Đã thêm ${qid} vào hàng đợi.`);
  }

  return (
    <div className="screen trake-screen">
      <div className="field">
        <label>Mô tả tổng quát chuỗi sự kiện</label>
        <textarea className="input" value={globalQuery} onChange={(e) => setGlobalQuery(e.target.value)} />
      </div>
      <div className="field">
        <label>Danh sách khoảnh khắc (mỗi dòng 1 khoảnh khắc, theo thứ tự)</label>
        <textarea className="input" rows={6} value={eventsText} onChange={(e) => setEventsText(e.target.value)} />
      </div>
      <button className="btn btn-primary" onClick={run} disabled={loading}>
        {loading ? "Đang chạy…" : "Run TRAKE"}
      </button>
      <p className="status-line">{status}</p>

      {candidates.length > 0 && (
        <>
          <table className="table trake-table">
            <thead><tr><th>video_id</th><th>chuỗi khoảnh khắc</th><th>score</th></tr></thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.video_id}>
                  <td className="mono">{c.video_id}</td>
                  <td>
                    <div className="trake-strip">
                      {c.frame_ids.map((fid, k) => (
                        <div key={`${fid}-${k}`} className="trake-strip-item">
                          {/* frame_idx = frame_id - 1 (BTC dem frame tu 1) — chi de LAY ANH hien thi */}
                          <Thumb videoId={c.video_id} frameIdx={fid - 1} label={`${k + 1}`} />
                          <span className="mono text-muted">{fid}</span>
                        </div>
                      ))}
                    </div>
                  </td>
                  <td className="mono">{c.score.toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="field">
            <label>Query ID</label>
            <input className="input" placeholder="VD: query-3-trake" value={queryId} onChange={(e) => setQueryId(e.target.value)} />
          </div>
          <button className="btn btn-primary" onClick={addToQueue}>Thêm vào hàng đợi</button>
        </>
      )}
    </div>
  );
}
