import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { TrakeCandidate, QueueRow } from "../api/client";
import { getSessionId } from "../session";
import Thumb from "../components/Thumb";
import RewriteChips from "../components/RewriteChips";
import TopKSlider from "../components/TopKSlider";
import TrakeKeyframeDetail from "../components/TrakeKeyframeDetail";

// Man TRAKE: header 2 cot (mo ta tong quat + chip rewrite | danh sach khoanh khac danh so) + thanh
// dieu khien (slider top-k video + Run). Ket qua = cac the video xep doc, KEO-THA doi thu tu uu tien;
// than moi the la dai timeline N moc (thumbnail + o sua frame_id + canh bao lech thu tu). Bam 1 moc
// -> soi video (TrakeKeyframeDetail). Widget "Chot bai" noi co dinh goc duoi-phai (Ctrl/Cmd + Enter).
type Detail = { card: number; moment: number };

export default function TrakeScreen({ active }: { active: boolean }) {
  const [globalQuery, setGlobalQuery] = useState("");
  const [eventsText, setEventsText] = useState("");
  const [topKVideo, setTopKVideo] = useState(5);
  const [candidates, setCandidates] = useState<TrakeCandidate[]>([]);
  // Sua tay frame_id tung moc, key theo video_id -> mang chuoi (song song voi c.frame_ids).
  const [fidEdits, setFidEdits] = useState<Record<string, string[]>>({});
  // fps tung video ung vien (hang so trong 1 video) — dung quy doi frame_id <-> giay.
  const [fpsByVideo, setFpsByVideo] = useState<Record<string, number>>({});
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const [queryId, setQueryId] = useState("");
  const [submitMsg, setSubmitMsg] = useState("");
  const [dragFrom, setDragFrom] = useState<number | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);

  const events = eventsText.split("\n").map((e) => e.trim()).filter(Boolean);

  function fidsOf(c: TrakeCandidate): string[] {
    return fidEdits[c.video_id] ?? c.frame_ids.map(String);
  }

  async function run() {
    if (!globalQuery.trim() || events.length === 0) {
      setStatus("⚠️ Cần mô tả tổng quát và ít nhất 1 khoảnh khắc.");
      return;
    }
    setLoading(true);
    setStatus("⏳ Đang tìm video ứng viên + căn từng khoảnh khắc…");
    try {
      const out = await api.trakeRun(globalQuery, events, topKVideo);
      setCandidates(out.candidates);
      setFidEdits(
        Object.fromEntries(out.candidates.map((c) => [c.video_id, c.frame_ids.map(String)]))
      );
      setDetail(null);
      // Nap fps cho tung video (song song) — fallback 25 neu loi.
      const metas = await Promise.all(
        out.candidates.map((c) =>
          api
            .videoMeta(c.video_id)
            .then((m) => [c.video_id, m.fps > 0 ? m.fps : 25] as const)
            .catch(() => [c.video_id, 25] as const)
        )
      );
      setFpsByVideo(Object.fromEntries(metas));
      const best = out.candidates[0];
      setStatus(
        best
          ? `✅ ${out.candidates.length} video ứng viên · tốt nhất: ${best.video_id} (${best.frame_ids.join(", ")})`
          : "⚠️ Không tìm được chuỗi khoảnh khắc hợp lệ."
      );
    } catch (e) {
      setStatus(`❌ Lỗi: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }

  function setFid(videoId: string, k: number, val: string) {
    setFidEdits((m) => {
      const base = m[videoId] ?? candidates.find((c) => c.video_id === videoId)?.frame_ids.map(String) ?? [];
      const arr = base.slice();
      arr[k] = val;
      return { ...m, [videoId]: arr };
    });
  }

  function reorder(from: number, to: number) {
    setCandidates((list) => {
      if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) return list;
      const next = list.slice();
      const [it] = next.splice(from, 1);
      next.splice(to, 0, it);
      return next;
    });
    setDragFrom(to);
  }

  function move(i: number, dir: -1 | 1) {
    reorder(i, i + dir);
  }

  // Kiem tra 1 video: dung so moc + toan so nguyen duong. Tra ve {nums} hoac {error}.
  function validateRow(c: TrakeCandidate): { nums: number[] } | { error: string } {
    const raw = fidsOf(c);
    if (raw.length !== events.length || raw.some((t) => t.trim() === "")) {
      const filled = raw.filter((t) => t.trim() !== "").length;
      return { error: `${c.video_id}: cần đúng ${events.length} frame_id (đang có ${filled}).` };
    }
    const nums = raw.map((t) => Number(t.trim()));
    if (nums.some((n) => !Number.isInteger(n) || n <= 0)) {
      return { error: `${c.video_id}: có frame_id không phải số nguyên dương — ${raw.join(" | ")}` };
    }
    return { nums };
  }

  async function submitRows(rows: TrakeCandidate[], label: string) {
    if (rows.length === 0) {
      setSubmitMsg("⚠️ Chưa có kết quả.");
      return;
    }
    const built: { video_id: string; frame_ids: number[] }[] = [];
    for (const c of rows) {
      const v = validateRow(c);
      if ("error" in v) {
        setSubmitMsg(`⚠️ ${v.error}`);
        return;
      }
      built.push({ video_id: c.video_id, frame_ids: v.nums });
    }
    const qid = queryId.trim() || "trake-query-001";
    const row: QueueRow = { query_id: qid, query_type: "trake", rows: built };
    try {
      await api.addToQueue(getSessionId(), row);
      const msg = `✅ Đã thêm ${qid} — ${label} (${built.length} dòng, hạng 1 = ${built[0].video_id}).`;
      setSubmitMsg(msg);
      setStatus(msg);
    } catch (e) {
      setSubmitMsg(`❌ Lỗi khi thêm: ${(e as Error).message}`);
    }
  }

  // Chot toan bo — ghi nhan dung thu tu cac the video da keo-tha.
  function addToQueue() {
    submitRows(candidates, "toàn bộ theo thứ tự đã sắp");
  }

  // Nop rieng 1 video (ghi de query_id bang dung 1 dong video nay).
  function submitOne(i: number) {
    const c = candidates[i];
    if (c) submitRows([c], `RIÊNG ${c.video_id} (ghi đè, chỉ 1 video)`);
  }

  function commitMoment(cardIdx: number, k: number, frameId: number) {
    const c = candidates[cardIdx];
    if (!c) return;
    setFid(c.video_id, k, String(frameId));
    setStatus(`✓ ${c.video_id} · Mốc ${k + 1} → frame ${frameId}`);
  }

  // Ctrl/Cmd + Enter = Chot & Nop vao hang doi (chi khi dang o tab TRAKE, khong o man soi chi tiet).
  const submitRef = useRef(addToQueue);
  useEffect(() => {
    submitRef.current = addToQueue;
  });
  useEffect(() => {
    if (!active || detail !== null) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        submitRef.current();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active, detail]);

  if (detail && candidates[detail.card]) {
    const c = candidates[detail.card];
    const k = detail.moment;
    const raw = fidsOf(c);
    const at = (j: number) => Number((raw[j] ?? "").trim()) || c.frame_ids[j];
    return (
      <TrakeKeyframeDetail
        videoId={c.video_id}
        fps={fpsByVideo[c.video_id] ?? 25}
        momentIdx={k}
        nMoments={c.frame_ids.length}
        eventText={events[k] ?? ""}
        frameId={at(k)}
        prevFrameId={k > 0 ? at(k - 1) : null}
        nextFrameId={k < c.frame_ids.length - 1 ? at(k + 1) : null}
        onBack={() => setDetail(null)}
        onCommit={(fid) => commitMoment(detail.card, k, fid)}
      />
    );
  }

  return (
    <div className="screen trake-screen">
      <div className="trake-header">
        <div className="trake-col">
          <div className="field">
            <label>Mô tả tổng quát chuỗi sự kiện (để tìm video)</label>
            <textarea
              className="input"
              value={globalQuery}
              onChange={(e) => setGlobalQuery(e.target.value)}
            />
          </div>
          <RewriteChips
            query={globalQuery}
            onPick={setGlobalQuery}
            note="Gợi ý chỉ áp cho mô tả tổng quát (dùng chọn video) — từng khoảnh khắc vẫn do pipeline tự rewrite."
          />
        </div>

        <div className="trake-col">
          <div className="field">
            <label>
              Danh sách khoảnh khắc — mỗi dòng 1 mốc, theo thứ tự{" "}
              <span className="trake-events-count">({events.length} mốc)</span>
            </label>
            <textarea
              className="input"
              rows={6}
              value={eventsText}
              onChange={(e) => setEventsText(e.target.value)}
            />
          </div>
          {events.length > 0 && (
            <div className="trake-events-preview">
              <ol>
                {events.map((ev, i) => (
                  <li key={i}>{ev}</li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </div>

      <div className="trake-controls">
        <TopKSlider
          label="Top-k video"
          value={topKVideo}
          min={3}
          max={10}
          step={1}
          onChange={setTopKVideo}
        />
        <button className="btn btn-primary" onClick={run} disabled={loading}>
          {loading ? "Đang chạy…" : "🎬 Run TRAKE"}
        </button>
      </div>
      <p className="status-line">{status}</p>

      {candidates.length === 0 ? (
        <div className="kis-empty">
          <h2>Chưa có kết quả TRAKE</h2>
          <p className="text-muted">
            Nhập mô tả tổng quát + danh sách khoảnh khắc, chọn top-k video rồi bấm Run TRAKE. Mỗi
            video ứng viên là 1 thẻ — kéo-thả để đổi thứ tự ưu tiên, bấm 1 mốc để soi video.
          </p>
        </div>
      ) : (
        <div className="trake-cards">
          {candidates.map((c, i) => {
            const raw = fidsOf(c);
            const fps = fpsByVideo[c.video_id] ?? 25;
            return (
              <div
                key={c.video_id}
                className={`trake-card ${dragFrom === i ? "dragging" : ""}`}
                onDragOver={(e) => {
                  if (dragFrom === null || dragFrom === i) return;
                  e.preventDefault();
                  reorder(dragFrom, i);
                }}
              >
                <div className="trake-card-head">
                  <span
                    className="trake-drag"
                    draggable
                    onDragStart={() => setDragFrom(i)}
                    onDragEnd={() => setDragFrom(null)}
                    title="Kéo để đổi thứ tự ưu tiên"
                  >
                    ⋮⋮
                  </span>
                  <span className="trake-badge mono">#{i + 1}</span>
                  <span className="mono">{c.video_id}</span>
                  <span className="mono text-muted">score {c.score.toFixed(4)}</span>
                  <span className="trake-order-btns">
                    <button className="btn btn-secondary" disabled={i === 0} onClick={() => move(i, -1)}>
                      ▲
                    </button>
                    <button
                      className="btn btn-secondary"
                      disabled={i === candidates.length - 1}
                      onClick={() => move(i, 1)}
                    >
                      ▼
                    </button>
                  </span>
                  <button className="btn btn-secondary trake-submit-one" onClick={() => submitOne(i)}>
                    🚀 Nộp riêng video này
                  </button>
                </div>

                <div className="trake-timeline">
                  {c.frame_ids.map((origFid, k) => {
                    const val = raw[k] ?? String(origFid);
                    const num = Number(val.trim());
                    const valid = Number.isInteger(num) && num > 0;
                    const prev = k > 0 ? Number((raw[k - 1] ?? "").trim()) : null;
                    const outOfOrder =
                      valid && prev !== null && Number.isInteger(prev) && num < prev;
                    const secs = valid ? (num - 1) / fps : null;
                    return (
                      <div
                        key={k}
                        className={`trake-moment ${outOfOrder ? "invalid" : ""}`}
                      >
                        <span className="trake-moment-title" title={events[k] ?? ""}>
                          Mốc {k + 1}
                          {events[k] ? `: ${events[k]}` : ""}
                        </span>
                        <button
                          className="trake-moment-thumb"
                          onClick={() => setDetail({ card: i, moment: k })}
                          title="Bấm để soi video tại mốc này"
                        >
                          {/* frame_idx = frame_id - 1 (BTC dem tu 1) — chi de LAY ANH */}
                          <Thumb
                            videoId={c.video_id}
                            frameIdx={(valid ? num : origFid) - 1}
                            label={`${k + 1}`}
                          />
                        </button>
                        <div className="trake-moment-foot">
                          <input
                            className="input frame-input"
                            type="number"
                            min={1}
                            value={val}
                            onChange={(e) => setFid(c.video_id, k, e.target.value)}
                          />
                          <span className="mono">{secs !== null ? `${secs.toFixed(1)}s` : "—"}</span>
                        </div>
                        {outOfOrder && <span className="trake-warn">⚠️ Lệch thứ tự</span>}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {candidates.length > 0 && (
        <div className="trake-submit-bar">
          <input
            className="input"
            placeholder="Query ID (VD: query-3-trake)"
            value={queryId}
            onChange={(e) => setQueryId(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === "Enter") addToQueue();
            }}
          />
          <button className="btn btn-primary" onClick={addToQueue}>
            🚀 Chốt &amp; Nộp vào hàng đợi
          </button>
          {submitMsg && <span className="trake-submit-msg">{submitMsg}</span>}
        </div>
      )}
    </div>
  );
}
