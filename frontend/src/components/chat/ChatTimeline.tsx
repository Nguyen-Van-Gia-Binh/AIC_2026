import { useEffect, useRef } from "react";
import type { ChatMessage } from "../../types/chat";
import ChatBubble from "./ChatBubble";

// Vung cuon danh sach tin nhan. Tu cuon xuong day khi co them message.
export default function ChatTimeline({
  messages,
  onInspect,
  onSubmitQueue,
  onQaAnswerChange,
  onTrakeSetFrame,
}: {
  messages: ChatMessage[];
  onInspect: (messageId: string, resultIndex: number, taskType: "kis" | "qa" | "trake") => void;
  onSubmitQueue: (messageId: string) => void;
  onQaAnswerChange: (messageId: string, a: string) => void;
  onTrakeSetFrame: (messageId: string, index: number, frameId: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <div className="chat-timeline" ref={ref}>
        <div className="kis-empty">
          <h2>Trợ lý tìm video AIC</h2>
          <p className="text-muted">
            Nhập câu hỏi bằng ngôn ngữ tự nhiên — hệ thống tự phân loại KIS / Q&amp;A / TRAKE, hiển
            thị kết quả dạng thẻ, bấm thumbnail để mở trình kiểm chứng video bên phải.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-timeline" ref={ref}>
      {messages.map((m) => (
        <ChatBubble
          key={m.id}
          msg={m}
          onInspect={(i, t) => onInspect(m.id, i, t)}
          onSubmitQueue={() => onSubmitQueue(m.id)}
          onQaAnswerChange={(a) => onQaAnswerChange(m.id, a)}
          onTrakeSetFrame={(i, fid) => onTrakeSetFrame(m.id, i, fid)}
        />
      ))}
    </div>
  );
}
