import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api/client";
import type { Hit, NeighborFrame } from "../api/client";
import Thumb from "./Thumb";
import VideoVerifier from "./VideoVerifier";
import type { VideoVerifierHandle } from "./VideoVerifier";

// Man chi tiet 1 keyframe (KIS): trinh phat video la chinh (tua toi timestamp keyframe, co phim
// tat) + dai keyframe lan can de doi nhanh frame + bang metadata. Nut "Them vao danh sach" them
// frame DANG CHON (mac dinh la keyframe goc; bam 1 o trong dai lan can de doi).
export default function KeyframeDetail({
  hit,
  onBack,
  onAddToShortlist,
}: {
  hit: Hit;
  onBack: () => void;
  onAddToShortlist: (h: Hit) => void;
}) {
  const [neighbors, setNeighbors] = useState<NeighborFrame[]>([]);
  const [selected, setSelected] = useState<Hit>(hit);
  const vvRef = useRef<VideoVerifierHandle>(null);

  useEffect(() => {
    setSelected(hit);
    api
      .keyframeNeighbors(hit.video_id, hit.frame_idx, 5)
      .then(setNeighbors)
      .catch(() => setNeighbors([]));
  }, [hit.video_id, hit.frame_idx]);

  function pickNeighbor(n: NeighborFrame) {
    // Dung score cua hit goc (o lan can khong co score — chi la frame ke) de van xep hang duoc.
    setSelected({ ...n, score: hit.score });
    vvRef.current?.seek(n.pts_time);
  }

  const metaRows = useMemo(
    () => [
      ["video_id", selected.video_id],
      ["frame_id", String(selected.frame_id)],
      ["frame_idx", String(selected.frame_idx)],
      ["pts_time", `${selected.pts_time.toFixed(1)}s`],
      ["score", selected.score.toFixed(4)],
    ],
    [selected]
  );

  return (
    <div className="screen detail-screen">
      <div className="detail-header">
        <button className="btn btn-secondary" onClick={onBack}>
          ← Về kết quả
        </button>
        <span className="mono tag">
          {selected.video_id} · frame {selected.frame_id}
        </span>
        <span className="mono tag tag-accent-2">score {selected.score.toFixed(4)}</span>
      </div>

      <div className="detail-body">
        <VideoVerifier
          ref={vvRef}
          videoId={hit.video_id}
          startTime={hit.pts_time}
        />

        <div className="detail-strip">
          {neighbors.map((n) => (
            <button
              key={n.frame_id}
              className={`strip-frame ${n.frame_id === selected.frame_id ? "current" : ""}`}
              onClick={() => pickNeighbor(n)}
              title={`Đến frame ${n.frame_id} (t=${n.pts_time.toFixed(1)}s)`}
            >
              <Thumb videoId={n.video_id} frameIdx={n.frame_idx} label={`${n.frame_id}`} />
            </button>
          ))}
        </div>

        <div className="detail-meta">
          {metaRows.map(([k, v]) => (
            <div key={k}>
              <span>{k}</span>
              <span className="mono">{v}</span>
            </div>
          ))}
        </div>

        <button className="btn btn-primary btn-block" onClick={() => onAddToShortlist(selected)}>
          Thêm frame {selected.frame_id} vào danh sách
        </button>
      </div>
    </div>
  );
}
