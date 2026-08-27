import { useState } from "react";
import { api } from "../api/client";
import type { TrakeCandidate, QueueRow } from "../api/client";
import { getSessionId } from "../session";
import Thumb from "../components/Thumb";
import RewriteChips from "../components/RewriteChips";
import TopKSlider from "../components/TopKSlider";

export default function TrakeScreen() {
  const [globalQuery, setGlobalQuery] = useState("");
  const [eventsText, setEventsText] = useState("");
  const [topKVideo, setTopKVideo] = useState(5);
  const [candidates, setCandidates] = useState<TrakeCandidate[]>([]);
  // Sua tay frame_id tung moc, key theo video_id -> mang chuoi (song song voi c.frame_ids).
  const [fidEdits, setFidEdits] = useState<Record<string, string[]>>({});
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
      setFidEdits(
        Object.fromEntries(out.candidates.map((c) => [c.video_id, c.frame_ids.map(String)]))
      );
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

  function setFid(videoId: string, k: number, val: string) {
    setFidEdits((m) => {
      const arr = (m[videoId] ?? []).slice();
      arr[k] = val;
      return { ...m, [videoId]: arr };
    });
  }

  async function addToQueue() {
    const best = candidates[0];
    if (!best) {
      setStatus("⚠️ Chưa có kết quả.");
      return;
    }
    const nEvents = parseEvents().length;
    const raw = fidEdits[best.video_id] ?? best.frame_ids.map(String);
    // Chan giong trake_add_to_queue ben app.py cu: du so moc + toan so nguyen.
    if (raw.length !== nEvents || raw.some((t) => t.trim() === "")) {
      setStatus(`⚠️ ${best.video_id}: cần đúng ${nEvents} frame_id (đang có ${raw.filter((t) => t.trim() !== "").length}).`);
      return;
    }
    const nums = raw.map((t) => Number(t.trim()));
    if (nums.some((n) => !Number.isInteger(n) || n <= 0)) {
      setStatus(`⚠️ ${best.video_id}: có frame_id không phải số nguyên dương: ${raw.join(" | ")}`);
      return;
    }
    const qid = queryId.trim() || "trake-query-001";
    const row: QueueRow = {
      query_id: qid,
      query_type: "trake",
      rows: [{ video_id: best.video_id, frame_ids: nums }],
    };
    await api.addToQueue(getSessionId(), row);
    setStatus(`✅ Đã thêm ${qid} vào hàng đợi (${nums.join(" | ")}).`);
  }

  return (
    <div className="screen trake-screen">
      <div className="field">
        <label>Mô tả tổng quát chuỗi sự kiện</label>
        <textarea className="input" value={globalQuery} onChange={(e) => setGlobalQuery(e.target.value)} />
      </div>
      <RewriteChips
        query={globalQuery}
        onPick={setGlobalQuery}
        note="Gợi ý chỉ áp cho mô tả tổng quát (dùng chọn video) — từng khoảnh khắc vẫn do pipeline tự rewrite."
      />
      <div className="field">
        <label>Danh sách khoảnh khắc (mỗi dòng 1 khoảnh khắc, theo thứ tự)</label>
        <textarea className="input" rows={6} value={eventsText} onChange={(e) => setEventsText(e.target.value)} />
      </div>
      <TopKSlider label="Top-k video" value={topKVideo} min={3} max={10} step={1} onChange={setTopKVideo} />
      <button className="btn btn-primary" onClick={run} disabled={loading}>
        {loading ? "Đang chạy…" : "Run TRAKE"}
      </button>
      <p className="status-line">{status}</p>

      {candidates.length > 0 && (
        <>
          <table className="table trake-table">
            <thead><tr><th>video_id</th><th>chuỗi khoảnh khắc (sửa frame_id được)</th><th>score</th></tr></thead>
            <tbody>
              {candidates.map((c) => (
                <tr key={c.video_id}>
                  <td className="mono">{c.video_id}</td>
                  <td>
                    <div className="trake-fids">
                      {c.frame_ids.map((fid, k) => (
                        <div key={k} className="trake-fid">
                          {/* frame_idx = frame_id - 1 (BTC dem frame tu 1) — chi de LAY ANH */}
                          <Thumb videoId={c.video_id} frameIdx={(Number(fidEdits[c.video_id]?.[k] ?? fid) || fid) - 1} label={`${k + 1}`} />
                          <input
                            className="input frame-input"
                            type="number"
                            min={1}
                            value={fidEdits[c.video_id]?.[k] ?? String(fid)}
                            onChange={(e) => setFid(c.video_id, k, e.target.value)}
                          />
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
          <button className="btn btn-primary" onClick={addToQueue}>Thêm vào hàng đợi (video tốt nhất)</button>
        </>
      )}
    </div>
  );
}
