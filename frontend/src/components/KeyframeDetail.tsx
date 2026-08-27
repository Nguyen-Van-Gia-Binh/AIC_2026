import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Hit, NeighborFrame } from "../api/client";
import Thumb from "./Thumb";

// Man chi tiet 1 keyframe (mockup 1c): dai frame lan can trong cung video + nut them vao shortlist.
export default function KeyframeDetail({
  hit, onBack, onAddToShortlist,
}: {
  hit: Hit;
  onBack: () => void;
  onAddToShortlist: (h: Hit) => void;
}) {
  const [neighbors, setNeighbors] = useState<NeighborFrame[]>([]);

  useEffect(() => {
    api.keyframeNeighbors(hit.video_id, hit.frame_idx, 5).then(setNeighbors).catch(() => setNeighbors([]));
  }, [hit.video_id, hit.frame_idx]);

  return (
    <div className="screen detail-screen">
      <div className="detail-header">
        <button className="btn btn-secondary" onClick={onBack}>← Về kết quả</button>
        <span className="mono tag">{hit.video_id} · frame {hit.frame_id}</span>
        <span className="mono tag tag-accent-2">score {hit.score.toFixed(4)}</span>
      </div>
      <div className="detail-body">
        <div className="detail-player">
          <Thumb
            videoId={hit.video_id}
            frameIdx={hit.frame_idx}
            label={`keyframe ${hit.video_id} #${hit.frame_id}`}
          />
        </div>
        <div className="detail-strip">
          {neighbors.map((n) => (
            <div
              key={n.frame_id}
              className={`strip-frame ${n.frame_id === hit.frame_id ? "current" : ""}`}
            >
              <Thumb videoId={n.video_id} frameIdx={n.frame_idx} label={`${n.frame_id}`} />
            </div>
          ))}
        </div>
        <div className="detail-meta">
          <div><span>video_id</span><span className="mono">{hit.video_id}</span></div>
          <div><span>frame_id</span><span className="mono">{hit.frame_id}</span></div>
          <div><span>pts_time</span><span className="mono">{hit.pts_time.toFixed(1)}s</span></div>
        </div>
        <button className="btn btn-primary btn-block" onClick={() => onAddToShortlist(hit)}>
          Thêm vào danh sách
        </button>
      </div>
    </div>
  );
}
