import { useState } from "react";
import { api } from "../api/client";
import type { QaHit, QueueRow } from "../api/client";
import { getSessionId } from "../session";
import Thumb from "../components/Thumb";

export default function QaScreen() {
  const [query, setQuery] = useState("");
  const [question, setQuestion] = useState("");
  const [topK] = useState(20);
  const [hits, setHits] = useState<QaHit[]>([]);
  const [answer, setAnswer] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [queryId, setQueryId] = useState("");

  async function run() {
    if (!query.trim()) {
      setStatus("⚠️ Nhập query trước.");
      return;
    }
    setLoading(true);
    try {
      const out = await api.qaRun(query, question || query, topK);
      setHits(out.hits);
      setAnswer(out.answer);
      setConfidence(out.confidence);
      setStatus(`✅ Độ tin cậy: ${(out.confidence * 100).toFixed(0)}% | Số vòng: ${out.n_loops}`);
    } catch (e) {
      setStatus(`❌ Lỗi: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  async function addToQueue() {
    if (hits.length === 0) {
      setStatus("⚠️ Chưa có kết quả.");
      return;
    }
    const qid = queryId.trim() || "qa-query-001";
    const row: QueueRow = {
      query_id: qid,
      query_type: "qa",
      answer,
      rows: hits.map((h) => ({ video_id: h.video_id, frame_id: h.frame_id, answer })),
    };
    await api.addToQueue(getSessionId(), row);
    setStatus(`✅ Đã thêm ${qid} (${hits.length} dòng) vào hàng đợi.`);
  }

  return (
    <div className="screen qa-screen">
      <div className="field">
        <label>Mô tả cảnh (để tìm kiếm)</label>
        <textarea className="input" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      <div className="field">
        <label>Câu hỏi cụ thể</label>
        <textarea className="input" value={question} onChange={(e) => setQuestion(e.target.value)} />
      </div>
      <button className="btn btn-primary" onClick={run} disabled={loading}>
        {loading ? "Đang chạy…" : "Run Q&A"}
      </button>
      <p className="status-line">{status}</p>

      {hits.length > 0 && (
        <div className="qa-body">
          <div className="qa-frame">
            <Thumb
              videoId={hits[0].video_id}
              frameIdx={hits[0].frame_idx}
              label={`${hits[0].video_id} · ${hits[0].frame_id}`}
            />
          </div>
          <div className="qa-side">
            <label>Đáp án (sửa được)</label>
            <input className="input answer-input" value={answer} onChange={(e) => setAnswer(e.target.value)} />
            <div className="confidence-bar"><div style={{ width: `${confidence * 100}%` }} /></div>
            <div className="field">
              <label>Query ID</label>
              <input className="input" placeholder="VD: query-2-qa" value={queryId} onChange={(e) => setQueryId(e.target.value)} />
            </div>
            <button className="btn btn-primary btn-block" onClick={addToQueue}>Chốt đáp án</button>
          </div>
        </div>
      )}
    </div>
  );
}
