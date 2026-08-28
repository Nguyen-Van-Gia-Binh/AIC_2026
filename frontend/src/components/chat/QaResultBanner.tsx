import Thumb from "../Thumb";
import type { ChatQaHit } from "../../types/chat";

// Khung dap an Q&A + dai frame chung cu. Sua dap an chung -> day len ChatScreen (dong bo moi card).
export default function QaResultBanner({
  answer,
  hits,
  onAnswerChange,
  onInspect,
}: {
  answer: string;
  hits: ChatQaHit[];
  onAnswerChange: (a: string) => void;
  onInspect: (index: number) => void;
}) {
  return (
    <div className="chat-qa-banner">
      <label className="chat-qa-answer">
        <span className="text-muted">Đáp án</span>
        <input
          className="input answer-input"
          value={answer}
          onChange={(e) => onAnswerChange(e.target.value)}
          placeholder="Nhập đáp án…"
        />
      </label>
      <div className="chat-kis-strip">
        {hits.map((h, i) => (
          <button
            key={`${h.video_id}-${h.frame_id}-${i}`}
            className="chat-kis-card"
            onClick={() => onInspect(i)}
            title={`${h.video_id} · frame ${h.frame_id} · ${h.pts_time.toFixed(1)}s`}
          >
            <Thumb videoId={h.video_id} frameIdx={h.frame_idx} label={`#${i + 1}`} />
            <span className="chat-card-meta mono">
              {h.video_id} · {h.frame_id}
            </span>
            {h.edited && <span className="chat-edited-badge">Đã chỉnh sửa</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
