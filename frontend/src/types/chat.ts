// Kieu du lieu cho man Chat (KIS/Q&A/TRAKE trong 1 hoi thoai). Bam theo spec
// docs/superpowers/specs/2026-08-28-chat-screen-ui-design.md §2.2.
//
// Giai doan 1 (hien tai): fixture tinh o src/mock/chatScenarios.ts dung cac kieu nay.
// Giai doan 2: response cua POST /api/chat/{session_id}/message map thang vao ChatMessage.
import type { Hit, QaHit } from "../api/client";

export interface AgentTrace {
  task_type: "kis" | "qa" | "trake" | "clarify";
  confidence: number; // 0.0 -> 1.0
  rewritten_query?: string; // query da dich sang tieng Anh cho CLIP
  n_loops?: number; // so vong reflection (Q&A)
  thoughts: string[]; // cac buoc suy luan hien trong accordion
}

// 1 moc su kien cua ket qua TRAKE trong chat (khac TrakeCandidate ben api/client: co san
// event_idx + query + pts_time de hien timeline day du, va sua tay tung moc).
export interface TrakeEvent {
  event_idx: number;
  query: string;
  frame_id: number;
  frame_idx: number;
  pts_time?: number;
  score: number;
  edited?: boolean; // true sau khi nguoi dung chinh frame trong Drawer (spec §3.2)
}

// Hit + co edited de hien nhan xanh "Da chinh sua" tren bong bong chat.
export type ChatHit = Hit & { edited?: boolean };
export type ChatQaHit = QaHit & { edited?: boolean };

export interface ChatMessage {
  id: string; // UUID
  role: "user" | "assistant";
  content: string; // van ban tra loi chinh
  timestamp: string; // HH:mm:ss
  status: "loading" | "done" | "error";
  errorMessage?: string;

  // Du lieu chuyen biet khi assistant tra loi
  trace?: AgentTrace;
  kisHits?: ChatHit[]; // KIS
  qaHits?: ChatQaHit[]; // Q&A: frame chung cu
  qaAnswer?: string; // Q&A: dap an chung (sua duoc o QaResultBanner)
  trakeResult?: {
    video_id: string;
    fps: number; // hang so trong 1 video — quy doi frame_id <-> giay
    events: TrakeEvent[];
  };
}

export interface InspectState {
  open: boolean;
  videoId: string;
  frameId: number;
  frameIdx: number;
  ptsTime?: number;
  messageId: string;
  resultIndex: number; // vi tri card/moc dang soi (#1, #2, hoac Moc 1)
  taskType: "kis" | "qa" | "trake";
}
