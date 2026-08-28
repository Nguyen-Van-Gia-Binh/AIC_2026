import type { AgentTrace } from "../../types/chat";

// Accordion xem cac buoc suy luan cua Agent (Router/VLM/OCR). Gap mac dinh, bam de mo.
export default function AgentTraceAccordion({ trace }: { trace: AgentTrace }) {
  return (
    <details className="chat-trace">
      <summary>
        <span className="mono tag">{trace.task_type.toUpperCase()}</span>
        <span className="chat-trace-conf">tin cay {(trace.confidence * 100).toFixed(0)}%</span>
        {typeof trace.n_loops === "number" && trace.n_loops > 0 && (
          <span className="text-muted">· {trace.n_loops} vong AI</span>
        )}
        <span className="chat-trace-toggle">xem suy luan</span>
      </summary>
      <div className="chat-trace-body">
        {trace.rewritten_query && (
          <p className="chat-trace-rw">
            <span className="text-muted">query (EN): </span>
            <span className="mono">{trace.rewritten_query}</span>
          </p>
        )}
        <ol>
          {trace.thoughts.map((th, i) => (
            <li key={i}>{th}</li>
          ))}
        </ol>
      </div>
    </details>
  );
}
