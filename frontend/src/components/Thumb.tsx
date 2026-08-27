import { useEffect, useState } from "react";
import { api } from "../api/client";

// Thumbnail anh keyframe that. Goi GET /api/images/{video_id}/{frame_idx} qua proxy Vite.
// Neu backend tra 404 (anh chua giai nen / khong co dong) -> hien o fallback soc + dau canh bao,
// khong vo layout.
type Props = {
  videoId: string;
  frameIdx: number;
  className?: string;
  label?: string; // chu de len goc duoi-trai (vd. "#3", "frame 14851")
};

export default function Thumb({ videoId, frameIdx, className, label }: Props) {
  const [failed, setFailed] = useState(false);

  // Reset trang thai loi khi doi sang keyframe khac (component bi tai su dung qua .map()).
  useEffect(() => {
    setFailed(false);
  }, [videoId, frameIdx]);

  return (
    <div className={`thumb ${className ?? ""}`.trim()}>
      {failed ? (
        <div className="thumb-fallback" title={`Ảnh chưa giải nén hoặc không tìm thấy: ${videoId} #${frameIdx}`}>
          <span>⚠</span>
        </div>
      ) : (
        <img
          className="thumb-img"
          src={api.imageUrl(videoId, frameIdx)}
          alt={`${videoId} #${frameIdx}`}
          loading="lazy"
          draggable={false}
          onError={() => setFailed(true)}
        />
      )}
      {label && <span className="thumb-label mono">{label}</span>}
    </div>
  );
}
