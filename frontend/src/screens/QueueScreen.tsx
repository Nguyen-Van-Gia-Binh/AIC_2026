import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { QueueRow } from "../api/client";
import { getSessionId } from "../session";

// `active` = tab Hàng đợi đang hiển thị. Vì App.tsx giữ mọi màn hình mounted (state không mất khi
// chuyển tab), cần refresh mỗi lần quay lại tab này để thấy item vừa thêm từ KIS/Q&A/TRAKE.
export default function QueueScreen({ active = true }: { active?: boolean }) {
  const [queue, setQueue] = useState<QueueRow[]>([]);
  const [status, setStatus] = useState("");
  const sessionId = getSessionId();

  async function refresh() {
    const q = await api.getQueue(sessionId);
    setQueue(q);
  }

  useEffect(() => {
    if (active) refresh();
  }, [active]);

  async function doExport() {
    try {
      const out = await api.exportZip(sessionId);
      setStatus(
        `${out.valid ? "✅" : "⚠️"} ZIP: ${out.zip_path} | ${out.csv_count} CSV | ${out.valid ? "Hợp lệ" : "Có lỗi"}` +
        (out.errors.length ? `\n${out.errors.join("\n")}` : "")
      );
    } catch (e) {
      setStatus(`❌ Lỗi: ${(e as Error).message}`);
    }
  }

  async function doClear() {
    await api.clearQueue(sessionId);
    await refresh();
    setStatus("🗑️ Hàng đợi đã được xoá.");
  }

  return (
    <div className="screen queue-screen">
      <div className="queue-header">
        <h3>Hàng đợi nộp</h3>
        <div>
          <button className="btn btn-secondary" onClick={refresh}>🔄 Refresh</button>
          <button className="btn btn-secondary" onClick={doClear}>🗑️ Xoá hàng đợi</button>
          <button className="btn btn-primary" onClick={doExport}>📦 Export ZIP</button>
        </div>
      </div>
      <table className="table">
        <thead><tr><th>query_id</th><th>loại</th><th>dòng</th></tr></thead>
        <tbody>
          {queue.map((q) => (
            <tr key={q.query_id}>
              <td className="mono">{q.query_id}</td>
              <td className="mono tag">{q.query_type.toUpperCase()}</td>
              <td className="mono">{q.rows.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <pre className="status-line">{status}</pre>
    </div>
  );
}
