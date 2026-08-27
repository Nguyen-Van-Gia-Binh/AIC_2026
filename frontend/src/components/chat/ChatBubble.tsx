import type { ChatMessage } from "../../types/chat";
import AgentTraceAccordion from "./AgentTraceAccordion";
import KisResultCards from "./KisResultCards";
import QaResultBanner from "./QaResultBanner";
import TrakeSequenceView from "./TrakeSequenceView";

// 1 bong bong tin nhan. User = bong bong phai gon. Assistant = Rich Card: van ban + trace +
// khoi ket qua theo task_type + nut chot hang doi.
export default function ChatBubble({
  msg,
  onInspect,
  onSubmitQueue,
  onQaAnswerChange,
  onTrakeSetFrame,
}: {
  msg: ChatMessage;
  onInspect: (resultIndex: number, taskType: "kis" | "qa" | "trake") => void;
  onSubmitQueue: () => void;
  onQaAnswerChange: (a: string) => void;
  onTrakeSetFrame: (index: number, frameId: number) => void;
}) {
  if (msg.role === "user") {
    return (
      <div className="chat-bubble user">
        <p>{msg.content}</p>
        <span className="chat-time mono">{msg.timestamp}</span>
      </div>
    );
  }

  if (msg.status === "loading") {
    return (
      <div className="chat-bubble assistant">
        <div className="chat-skeleton">
          <span />
          <span />
          <span />
        </div>
      </div>
    );
  }

  if (msg.status === "error") {
    return (
      <div className="chat-bubble assistant">
        <p className="chat-error">⚠️ {msg.errorMessage ?? "Có lỗi khi xử lý."}</p>
      </div>
    );
  }

  const task = msg.trace?.task_type;
  const hasResult =
    (msg.kisHits && msg.kisHits.length > 0) ||
    (msg.qaHits && msg.qaHits.length > 0) ||
    (msg.trakeResult && msg.trakeResult.events.length > 0);

  return (
    <div className="chat-bubble assistant">
      <p>{msg.content}</p>
      {msg.trace && <AgentTraceAccordion trace={msg.trace} />}

      {task === "kis" && msg.kisHits && (
        <KisResultCards hits={msg.kisHits} onInspect={(i) => onInspect(i, "kis")} />
      )}
      {task === "qa" && msg.qaHits && (
        <QaResultBanner
          answer={msg.qaAnswer ?? ""}
          hits={msg.qaHits}
          onAnswerChange={onQaAnswerChange}
          onInspect={(i) => onInspect(i, "qa")}
        />
      )}
      {task === "trake" && msg.trakeResult && (
        <TrakeSequenceView
          videoId={msg.trakeResult.video_id}
          fps={msg.trakeResult.fps}
          events={msg.trakeResult.events}
          onInspect={(i) => onInspect(i, "trake")}
          onSetFrame={onTrakeSetFrame}
        />
      )}

      {hasResult && (
        <div className="chat-bubble-actions">
          <button className="btn btn-primary" onClick={onSubmitQueue}>
            📥 Chốt vào Hàng đợi nộp
          </button>
          <span className="chat-time mono">{msg.timestamp}</span>
        </div>
      )}
    </div>
  );
}
