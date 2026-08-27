import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { QueueRow } from "../api/client";
import { getSessionId } from "../session";
import type { ChatMessage, InspectState } from "../types/chat";
import {
  buildAssistantMessage,
  makeLoadingMessage,
  makeUserMessage,
  pickScenario,
} from "../mock/chatScenarios";
import ChatHeader from "../components/chat/ChatHeader";
import ChatTimeline from "../components/chat/ChatTimeline";
import ChatInput from "../components/chat/ChatInput";
import ChatDrawer from "../components/chat/ChatDrawer";

// Man Chat — GIAI DOAN 1 (Mock-First): du lieu tu fixture tinh (src/mock/chatScenarios.ts), video
// + thumbnail + hang doi la THAT. Router LLM / pipeline se noi o Giai doan 2 ma khong doi cau truc
// component nay (chi thay buildAssistantMessage bang api.chatMessage).
type TaskType = "kis" | "qa" | "trake";

export default function ChatScreen({ active }: { active: boolean }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inspect, setInspect] = useState<InspectState | null>(null);
  const [queryId, setQueryId] = useState("chat-query-001");
  const [toast, setToast] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(""), 3000);
    return () => clearTimeout(id);
  }, [toast]);

  function send(text: string) {
    const hasPrior = messages.some((m) => m.role === "assistant" && m.status === "done");
    const prev = [...messages].reverse().find((m) => m.role === "assistant" && m.status === "done");
    const loading = makeLoadingMessage();
    setMessages((list) => [...list, makeUserMessage(text), loading]);
    setBusy(true);
    // Gia do tre pipeline. Giai doan 2: thay bang `await api.chatMessage(getSessionId(), text, queryId)`.
    setTimeout(() => {
      const reply = buildAssistantMessage(pickScenario(text, hasPrior), prev);
      setMessages((list) => list.map((m) => (m.id === loading.id ? { ...reply, id: loading.id } : m)));
      setBusy(false);
    }, 500);
  }

  function reset() {
    setMessages([]);
    setInspect(null);
  }

  function openInspect(messageId: string, resultIndex: number, taskType: TaskType) {
    const msg = messages.find((m) => m.id === messageId);
    if (!msg) return;
    let videoId = "";
    let frameId = 0;
    let frameIdx = 0;
    let ptsTime: number | undefined;
    if (taskType === "kis" && msg.kisHits?.[resultIndex]) {
      const h = msg.kisHits[resultIndex];
      ({ video_id: videoId, frame_id: frameId, frame_idx: frameIdx, pts_time: ptsTime } = h);
    } else if (taskType === "qa" && msg.qaHits?.[resultIndex]) {
      const h = msg.qaHits[resultIndex];
      ({ video_id: videoId, frame_id: frameId, frame_idx: frameIdx, pts_time: ptsTime } = h);
    } else if (taskType === "trake" && msg.trakeResult?.events[resultIndex]) {
      const e = msg.trakeResult.events[resultIndex];
      videoId = msg.trakeResult.video_id;
      frameId = e.frame_id;
      frameIdx = e.frame_idx;
      ptsTime = e.pts_time ?? (e.frame_id - 1) / msg.trakeResult.fps;
    } else {
      return;
    }
    setInspect({ open: true, videoId, frameId, frameIdx, ptsTime, messageId, resultIndex, taskType });
  }

  // Ghi frame dang tua o Drawer vao dung phan tu ket qua + danh dau edited (spec §3.2).
  function commitFrame(frameId: number, frameIdx: number, ptsTime: number) {
    if (!inspect) return;
    const { messageId, resultIndex, taskType } = inspect;
    setMessages((list) =>
      list.map((m) => {
        if (m.id !== messageId) return m;
        if (taskType === "kis" && m.kisHits) {
          return {
            ...m,
            kisHits: m.kisHits.map((h, i) =>
              i === resultIndex ? { ...h, frame_id: frameId, frame_idx: frameIdx, pts_time: ptsTime, edited: true } : h
            ),
          };
        }
        if (taskType === "qa" && m.qaHits) {
          return {
            ...m,
            qaHits: m.qaHits.map((h, i) =>
              i === resultIndex ? { ...h, frame_id: frameId, frame_idx: frameIdx, pts_time: ptsTime, edited: true } : h
            ),
          };
        }
        if (taskType === "trake" && m.trakeResult) {
          return {
            ...m,
            trakeResult: {
              ...m.trakeResult,
              events: m.trakeResult.events.map((e, i) =>
                i === resultIndex ? { ...e, frame_id: frameId, frame_idx: frameIdx, pts_time: ptsTime, edited: true } : e
              ),
            },
          };
        }
        return m;
      })
    );
  }

  function setQaAnswer(messageId: string, a: string) {
    setMessages((list) =>
      list.map((m) =>
        m.id === messageId
          ? { ...m, qaAnswer: a, qaHits: m.qaHits?.map((h) => ({ ...h, answer: a })) }
          : m
      )
    );
  }

  function setTrakeFrame(messageId: string, index: number, frameId: number) {
    setMessages((list) =>
      list.map((m) => {
        if (m.id !== messageId || !m.trakeResult) return m;
        const fps = m.trakeResult.fps;
        return {
          ...m,
          trakeResult: {
            ...m.trakeResult,
            events: m.trakeResult.events.map((e, i) =>
              i === index
                ? {
                    ...e,
                    frame_id: frameId,
                    frame_idx: Math.max(0, frameId - 1),
                    pts_time: Number.isFinite(frameId) ? Math.max(0, (frameId - 1) / fps) : e.pts_time,
                    edited: true,
                  }
                : e
            ),
          },
        };
      })
    );
  }

  async function submitToQueue(messageId: string) {
    const msg = messages.find((m) => m.id === messageId);
    if (!msg) return;
    const qid = queryId.trim() || "chat-query-001";
    let row: QueueRow;

    if (msg.trace?.task_type === "kis" && msg.kisHits?.length) {
      for (const h of msg.kisHits) {
        if (!Number.isInteger(h.frame_id) || h.frame_id <= 0) {
          setToast(`⚠️ frame_id không hợp lệ ở ${h.video_id}: ${h.frame_id}`);
          return;
        }
      }
      row = {
        query_id: qid,
        query_type: "kis",
        rows: msg.kisHits.map((h) => ({ video_id: h.video_id, frame_id: h.frame_id })),
      };
    } else if (msg.trace?.task_type === "qa" && msg.qaHits?.length) {
      const answer = (msg.qaAnswer ?? "").trim();
      if (!answer) {
        setToast("⚠️ Đáp án đang trống — điền đáp án trước khi chốt.");
        return;
      }
      for (const h of msg.qaHits) {
        if (!Number.isInteger(h.frame_id) || h.frame_id <= 0) {
          setToast(`⚠️ frame_id không hợp lệ ở ${h.video_id}: ${h.frame_id}`);
          return;
        }
      }
      row = {
        query_id: qid,
        query_type: "qa",
        answer,
        rows: msg.qaHits.map((h) => ({ video_id: h.video_id, frame_id: h.frame_id, answer })),
      };
    } else if (msg.trace?.task_type === "trake" && msg.trakeResult?.events.length) {
      const nums = msg.trakeResult.events.map((e) => e.frame_id);
      if (nums.some((n) => !Number.isInteger(n) || n <= 0)) {
        setToast(`⚠️ TRAKE có frame_id không phải số nguyên dương: ${nums.join(" | ")}`);
        return;
      }
      row = {
        query_id: qid,
        query_type: "trake",
        rows: [{ video_id: msg.trakeResult.video_id, frame_ids: nums }],
      };
    } else {
      setToast("⚠️ Chưa có kết quả để chốt.");
      return;
    }

    try {
      await api.addToQueue(getSessionId(), row);
      setToast(`✅ Đã thêm ${qid} vào Hàng đợi (${row.rows.length} dòng)`);
    } catch (e) {
      setToast(`❌ Lỗi khi thêm: ${(e as Error).message}`);
    }
  }

  return (
    <div className="screen chat-screen">
      <ChatHeader queryId={queryId} onQueryIdChange={setQueryId} onReset={reset} />
      <ChatTimeline
        messages={messages}
        onInspect={openInspect}
        onSubmitQueue={submitToQueue}
        onQaAnswerChange={setQaAnswer}
        onTrakeSetFrame={setTrakeFrame}
      />
      <ChatInput disabled={busy} onSend={send} />

      <ChatDrawer
        inspect={active ? inspect : null}
        onClose={() => setInspect(null)}
        onCommitFrame={commitFrame}
        onSubmitQueue={() => inspect && submitToQueue(inspect.messageId)}
      />

      {toast && <div className="chat-toast">{toast}</div>}
    </div>
  );
}
