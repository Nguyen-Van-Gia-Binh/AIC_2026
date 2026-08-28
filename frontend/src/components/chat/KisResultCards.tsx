import Thumb from "../Thumb";
import type { ChatHit } from "../../types/chat";

// Dai/luoi keyframe ung vien cho KIS trong bong bong chat. Bam 1 thumbnail -> mo Drawer soi video.
export default function KisResultCards({
  hits,
  onInspect,
}: {
  hits: ChatHit[];
  onInspect: (index: number) => void;
}) {
  return (
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
            {h.video_id} · {h.frame_id} · {h.score.toFixed(3)}
          </span>
          {h.edited && <span className="chat-edited-badge">Đã chỉnh sửa</span>}
        </button>
      ))}
    </div>
  );
}
