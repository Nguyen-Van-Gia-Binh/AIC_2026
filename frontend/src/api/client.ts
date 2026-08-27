// client.ts — wrapper fetch() goi backend qua proxy /api/* (xem vite.config.ts).
export type Hit = {
  video_id: string;
  frame_id: number;
  frame_idx: number;
  pts_time: number;
  score: number;
};

export type QaHit = Hit & { answer: string };

export type NeighborFrame = {
  video_id: string;
  frame_id: number;
  frame_idx: number;
  pts_time: number;
};

export type TrakeCandidate = {
  video_id: string;
  frame_ids: number[];
  score: number;
};

export type QueueRow = {
  query_id: string;
  query_type: "kis" | "qa" | "trake";
  rows: Record<string, unknown>[];
  answer?: string | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  // URL anh keyframe that (backend serve file .jpg tu data/extracted/keyframes/).
  // Khong fetch o day — tra ve string de gan thang vao <img src>.
  imageUrl: (videoId: string, frameIdx: number) =>
    `/api/images/${encodeURIComponent(videoId)}/${frameIdx}`,

  // URL video goc .mp4 (backend serve kem Range -> <video> tua duoc). Gan thang vao <video src>.
  videoUrl: (videoId: string) => `/api/videos/${encodeURIComponent(videoId)}`,

  // fps + duration cua video — dung cho buoc tua theo frame trong VideoVerifier.
  videoMeta: (videoId: string) =>
    request<{ fps: number; duration: number | null }>(
      `/videos/${encodeURIComponent(videoId)}/meta`
    ),

  rewrite: (query: string, question?: string) =>
    request<{ candidates: string[] }>("/rewrite", {
      method: "POST",
      body: JSON.stringify({ query, question }),
    }),

  kisSearch: (query: string, top_k = 20) =>
    request<{ hits: Hit[] }>("/kis/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k }),
    }),

  keyframeNeighbors: (video_id: string, frame_idx: number, window = 5) =>
    request<NeighborFrame[]>(
      `/keyframes/${video_id}/neighbors?frame_idx=${frame_idx}&window=${window}`
    ),

  qaRun: (query: string, question: string, top_k = 20, query_en?: string) =>
    request<{ hits: QaHit[]; answer: string; confidence: number; n_loops: number }>("/qa/run", {
      method: "POST",
      body: JSON.stringify({ query, question, top_k, query_en }),
    }),

  trakeRun: (query: string, events: string[], top_k_video = 5, query_en?: string) =>
    request<{ candidates: TrakeCandidate[]; n_events: number }>("/trake/run", {
      method: "POST",
      body: JSON.stringify({ query, events, top_k_video, query_en }),
    }),

  getQueue: (sessionId: string) => request<QueueRow[]>(`/queue/${sessionId}`),

  addToQueue: (sessionId: string, row: QueueRow) =>
    request<QueueRow[]>(`/queue/${sessionId}/add`, {
      method: "POST",
      body: JSON.stringify(row),
    }),

  removeFromQueue: (sessionId: string, queryId: string) =>
    request<QueueRow[]>(`/queue/${sessionId}/${queryId}`, { method: "DELETE" }),

  clearQueue: (sessionId: string) => request<QueueRow[]>(`/queue/${sessionId}`, { method: "DELETE" }),

  exportZip: (sessionId: string) =>
    request<{ zip_path: string; valid: boolean; csv_count: number; errors: string[] }>(
      `/export/${sessionId}`,
      { method: "POST" }
    ),
};
