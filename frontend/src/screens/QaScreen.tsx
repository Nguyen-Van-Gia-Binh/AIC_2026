import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { QaHit, QueueRow } from "../api/client";
import { getSessionId } from "../session";
import Thumb from "../components/Thumb";
import RewriteChips from "../components/RewriteChips";
import TopKSlider from "../components/TopKSlider";
import QaKeyframeDetail from "../components/QaKeyframeDetail";

// Man Q&A: header 3 vung (mo ta canh + chip rewrite | cau hoi + dap an chung | slider + Run +
// trang thai). Luoi ket qua full-width cung chinh la danh sach nop. Bam card -> soi video. Widget
// "Chot bai" noi co dinh goc duoi-phai (Ctrl/Cmd + Enter).
type RankedQaHit = QaHit & { _key: string };

export default function QaScreen({ active }: { active: boolean }) {
  const [query, setQuery] = useState("");
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState(20);
  const [hits, setHits] = useState<RankedQaHit[]>([]);
  const [answer, setAnswer] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [nLoops, setNLoops] = useState(0);
  const [status, setStatus] = useState("");
  const [submitMsg, setSubmitMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [queryId, setQueryId] = useState("");
  const [detailIdx, setDetailIdx] = useState<number | null>(null);
  const [dragFrom, setDragFrom] = useState<number | null>(null);

  async function run() {
    if (!query.trim()) {
      setStatus("⚠️ Nhập query trước.");
      return;
    }
    setLoading(true);
    try {
      const out = await api.qaRun(query, question || query, topK);
      setHits(out.hits.map((h, i) => ({ ...h, _key: `${h.video_id}-${h.frame_id}-${i}` })));
      setAnswer(out.answer);
      setConfidence(out.confidence);
      setNLoops(out.n_loops);
      setDetailIdx(null);
      setStatus(`✅ Độ tin cậy: ${(out.confidence * 100).toFixed(0)}% · Số vòng AI: ${out.n_loops}`);
    } catch (e) {
      setStatus(`❌ Lỗi: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  // Sua dap an chung -> tu dong ap cho moi card (moi hit giu .answer rieng de hien nhan tren card).
  function setCommonAnswer(a: string) {
    setAnswer(a);
    setHits((list) => list.map((h) => ({ ...h, answer: a })));
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

  function moveToFront(i: number) {
    setHits((list) => {
      if (i <= 0 || i >= list.length) return list;
      const next = list.slice();
      const [it] = next.splice(i, 1);
      next.unshift(it);
      return next;
    });
    setDetailIdx(0);
  }

  function updateHitAt(i: number, patch: Partial<QaHit>) {
    setHits((list) => list.map((h, k) => (k === i ? { ...h, ...patch } : h)));
  }

  async function addToQueue() {
    if (hits.length === 0) {
      setSubmitMsg("⚠️ Chưa có kết quả.");
      return;
    }
    if (!answer.trim()) {
      setSubmitMsg("⚠️ Đáp án đang trống — điền đáp án chung trước khi chốt.");
      return;
    }
    for (const h of hits) {
      if (!Number.isInteger(h.frame_id) || h.frame_id <= 0) {
        setSubmitMsg(`⚠️ frame_id không hợp lệ ở ${h.video_id}: ${h.frame_id}`);
        return;
      }
    }
    const qid = queryId.trim() || "qa-query-001";
    const row: QueueRow = {
      query_id: qid,
      query_type: "qa",
      answer,
      rows: hits.map((h) => ({
        video_id: h.video_id,
        frame_id: h.frame_id,
        answer: h.answer || answer,
      })),
    };
    try {
      await api.addToQueue(getSessionId(), row);
      const msg = `✅ Đã thêm ${qid} (${hits.length} dòng · đáp án "${answer}" · hạng 1 = ${hits[0].video_id}/${hits[0].frame_id}).`;
      setSubmitMsg(msg);
      setStatus(msg);
    } catch (e) {
      setSubmitMsg(`❌ Lỗi khi thêm: ${(e as Error).message}`);
    }
  }

  // Ctrl/Cmd + Enter = Chot & them vao hang doi (chi khi dang o tab Q&A, khong o man soi chi tiet).
  const submitRef = useRef(addToQueue);
  useEffect(() => {
    submitRef.current = addToQueue;
  });
  useEffect(() => {
    if (!active || detailIdx !== null) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        submitRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, detailIdx]);

  if (detailIdx !== null && hits[detailIdx]) {
    const idx = detailIdx;
    return (
      <QaKeyframeDetail
        hit={hits[idx]}
        rank={idx + 1}
        answer={answer}
        onBack={() => setDetailIdx(null)}
        onUpdateFrame={(h) =>
          updateHitAt(idx, {
            frame_id: h.frame_id,
            frame_idx: h.frame_idx,
            pts_time: h.pts_time,
            answer: h.answer, // "Cap nhat frame & dap an" -> card nay doi ca dap an rieng
          })
        }
        onSetRank1={() => moveToFront(idx)}
        onApplyAnswerToAll={(a) => setCommonAnswer(a)}
      />
    );
  }

  return (
    <div className="screen qa-screen">
      <div className="qa-header">
        <div className="qa-col">
          <div className="field">
            <label>Mô tả cảnh (để tìm kiếm)</label>
            <textarea className="input" value={query} onChange={(e) => setQuery(e.target.value)} />
          </div>
          <RewriteChips query={query} question={question} onPick={setQuery} />
        </div>

        <div className="qa-col">
          <div className="field">
            <label>Câu hỏi cụ thể</label>
            <textarea
              className="input"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
          </div>
          <div className="field">
            <label>Đáp án chung (sửa ở đây tự cập nhật mọi card)</label>
            <input
              className="input answer-input"
              value={answer}
              onChange={(e) => setCommonAnswer(e.target.value)}
            />
          </div>
        </div>

        <div className="qa-run-col">
          <TopKSlider
            label="Top-k truy xuất"
            value={topK}
            min={5}
            max={50}
            step={5}
            onChange={setTopK}
          />
          <button className="btn btn-primary" onClick={run} disabled={loading}>
            {loading ? "Đang chạy…" : "Run Q&A"}
          </button>
          {(confidence > 0 || nLoops > 0) && (
            <div className="confidence-bar">
              <div style={{ width: `${confidence * 100}%` }} />
            </div>
          )}
          <p className="status-line">{status}</p>
        </div>
      </div>

      {hits.length === 0 ? (
        <div className="kis-empty">
          <h2>Chưa có kết quả Q&amp;A</h2>
          <p className="text-muted">
            Nhập mô tả cảnh + câu hỏi, chọn top-k rồi bấm Run Q&amp;A. Lưới kết quả cũng là danh sách
            nộp — bấm 1 card để soi video, đặt Rank #1 hoặc đồng bộ đáp án.
          </p>
        </div>
      ) : (
        <>
          <p className="text-muted kis-hint">
            Kéo thả card để đổi thứ hạng — hạng #1 là đáp án chính khi nộp. Bấm card để soi
            video &amp; sửa frame. Nút × để loại khỏi danh sách.
          </p>
          <div className="qa-grid">
            {hits.map((h, i) => (
              <div
                key={h._key}
                className={`qa-card ${dragFrom === i ? "dragging" : ""}`}
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
                <span className="mono card-score">{h.score.toFixed(3)}</span>
                <div className="card-caption">
                  <div className="cc-row">
                    <span>
                      {h.video_id} · {h.frame_id}
                    </span>
                  </div>
                  <div className="cc-answer">💬 {h.answer || answer || "—"}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {hits.length > 0 && (
        <div className="qa-submit-bar">
          <input
            className="input"
            placeholder="Query ID (VD: query-2-qa)"
            value={queryId}
            onChange={(e) => setQueryId(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === "Enter") addToQueue();
            }}
          />
          <button className="btn btn-primary" onClick={addToQueue}>
            🚀 Chốt &amp; Thêm vào hàng đợi
          </button>
          {submitMsg && <span className="qa-submit-msg">{submitMsg}</span>}
        </div>
      )}
    </div>
  );
}
