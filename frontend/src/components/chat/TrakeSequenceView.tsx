import Thumb from "../Thumb";
import type { TrakeEvent } from "../../types/chat";

// Dong thoi gian N moc tuan tu cho TRAKE. Sua frame_id truc tiep; vien do + "⚠️ Lech thu tu"
// khi frame_k < frame_{k-1} (khong don dieu tang) — bam 1 moc de soi video.
export default function TrakeSequenceView({
  videoId,
  fps,
  events,
  onInspect,
  onSetFrame,
}: {
  videoId: string;
  fps: number;
  events: TrakeEvent[];
  onInspect: (index: number) => void;
  onSetFrame: (index: number, frameId: number) => void;
}) {
  return (
    <div className="chat-trake-seq">
      {events.map((ev, k) => {
        const num = ev.frame_id;
        const valid = Number.isInteger(num) && num > 0;
        const prev = k > 0 ? events[k - 1].frame_id : null;
        const outOfOrder = valid && prev !== null && Number.isInteger(prev) && num < prev;
        const secs = valid ? (num - 1) / fps : null;
        return (
          <div key={k} className={`chat-moment ${outOfOrder ? "invalid" : ""}`}>
            <span className="chat-moment-title" title={ev.query}>
              Mốc {k + 1}
              {ev.query ? `: ${ev.query}` : ""}
            </span>
            <button
              className="chat-moment-thumb"
              onClick={() => onInspect(k)}
              title="Bấm để soi video tại mốc này"
            >
              <Thumb videoId={videoId} frameIdx={(valid ? num : 1) - 1} label={`${k + 1}`} />
            </button>
            <div className="chat-moment-foot">
              <input
                className="input frame-input"
                type="number"
                min={1}
                value={Number.isFinite(num) ? num : ""}
                onChange={(e) => onSetFrame(k, Number(e.target.value))}
              />
              <span className="mono">{secs !== null ? `${secs.toFixed(1)}s` : "—"}</span>
            </div>
            {ev.edited && <span className="chat-edited-badge">Đã chỉnh sửa</span>}
            {outOfOrder && <span className="chat-warn">⚠️ Lệch thứ tự</span>}
          </div>
        );
      })}
    </div>
  );
}
