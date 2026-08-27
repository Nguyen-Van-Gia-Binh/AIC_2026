// Fixture tinh + "router gia" cho man Chat — GIAI DOAN 1 (test giao dien truoc, chua noi Agent).
//
// 3 kich ban (KIS / Q&A / TRAKE) dung video_id + frame_idx THAT trong dataset (tra tu
// data/extracted/map-keyframes/) de VideoVerifier tua video that va Thumb tai anh that.
//   frame_id = frame_idx + 1 (BTC dem tu 1).
//
// GIAI DOAN 2: thay `buildAssistantMessage` bang `await api.chatMessage(sessionId, text, queryId)`
// va map response -> ChatMessage. Cau truc component frontend giu nguyen.
import type { ChatMessage } from "../types/chat";

function uid(): string {
  return typeof crypto !== "undefined" && crypto.randomUUID
    ? crypto.randomUUID()
    : `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function now(): string {
  return new Date().toLocaleTimeString("vi-VN", { hour12: false });
}

// ── Kich ban KIS: L21_V001, fps 30 ──────────────────────────────────────────
const KIS_HITS = [
  { video_id: "L21_V001", frame_idx: 711, frame_id: 712, pts_time: 23.7, score: 0.912 },
  { video_id: "L21_V001", frame_idx: 2288, frame_id: 2289, pts_time: 76.2667, score: 0.874 },
  { video_id: "L21_V001", frame_idx: 4308, frame_id: 4309, pts_time: 143.6, score: 0.851 },
];

// ── Kich ban Q&A: L22_V001, fps 30 ──────────────────────────────────────────
const QA_ANSWER = "3";
const QA_HITS = [
  { video_id: "L22_V001", frame_idx: 560, frame_id: 561, pts_time: 18.6667, score: 0.889, answer: QA_ANSWER },
  { video_id: "L22_V001", frame_idx: 1704, frame_id: 1705, pts_time: 56.8, score: 0.842, answer: QA_ANSWER },
  { video_id: "L22_V001", frame_idx: 4140, frame_id: 4141, pts_time: 138.0, score: 0.826, answer: QA_ANSWER },
];

// ── Kich ban TRAKE: L25_V001, fps 25 ────────────────────────────────────────
const TRAKE_FPS = 25;
const TRAKE_EVENTS = [
  { event_idx: 0, query: "nguoi dung day khoi ghe", frame_idx: 644, frame_id: 645, pts_time: 25.76, score: 0.83 },
  { event_idx: 1, query: "buoc toi phia truoc", frame_idx: 1583, frame_id: 1584, pts_time: 63.32, score: 0.79 },
  { event_idx: 2, query: "quay dau nhin lai", frame_idx: 1898, frame_id: 1899, pts_time: 75.96, score: 0.77 },
];

export type ScenarioKind = "kis" | "qa" | "trake" | "feedback";

// Router gia: doan task_type bang keyword thuan (khong LLM). hasPrior = da co it nhat 1 luot
// assistant truoc do -> cho phep nhan dien "luot tiep noi" (spec §3.1).
export function pickScenario(text: string, hasPrior: boolean): ScenarioKind {
  const t = text.toLowerCase();
  const looksFeedback =
    hasPrior &&
    (t.length < 40 ||
      /\blai\b|\bmoc\b|\bmốc\b|đáp án|dap an|\bl2\d|\bl\d{2}_v/.test(t)) &&
    !/tìm|tim|chuỗi|chuoi/.test(t);
  if (looksFeedback) return "feedback";
  if (/\?|bao nhiêu|bao nhieu|mấy|may |màu gì|mau gi|đáp án|dap an|là ai|la ai/.test(t)) return "qa";
  if (/chuỗi|chuoi|lần lượt|lan luot|\bmốc\b|\bmoc\b|sau đó|sau do|trình tự|trinh tu/.test(t))
    return "trake";
  return "kis";
}

// Tao message assistant tu kich ban. prev = message assistant gan nhat (cho nhanh "feedback").
export function buildAssistantMessage(kind: ScenarioKind, prev?: ChatMessage): ChatMessage {
  const base = { id: uid(), role: "assistant" as const, timestamp: now(), status: "done" as const };

  if (kind === "feedback") {
    // Giu context: phat lai ket qua truoc + ghi chu da nhan dien luot tiep noi.
    const carried: Partial<ChatMessage> = prev
      ? {
          trace: prev.trace && {
            ...prev.trace,
            thoughts: [
              "Router: nhan dien LUOT TIEP NOI cua phien hien tai — khong chay lai tu dau.",
              "Ke thua context + tham so `feedback` de tinh chinh ket qua.",
              ...prev.trace.thoughts,
            ],
          },
          kisHits: prev.kisHits,
          qaHits: prev.qaHits,
          qaAnswer: prev.qaAnswer,
          trakeResult: prev.trakeResult,
        }
      : {};
    return {
      ...base,
      content: prev
        ? "Da ghi nhan phan hoi va tinh chinh lai ket qua gan nhat (giu nguyen phien lam viec)."
        : "Chua co ket qua nao truoc do de tinh chinh — hay mo ta su kien can tim.",
      ...carried,
    };
  }

  if (kind === "qa") {
    return {
      ...base,
      content: `Dap an: ${QA_ANSWER}. Cac frame chung cu ben duoi (bam de soi video kiem chung).`,
      trace: {
        task_type: "qa",
        confidence: 0.9,
        rewritten_query: "how many people are wearing yellow shirts in the scene",
        n_loops: 1,
        thoughts: [
          "Router phan loai: Q&A (cau hoi can dap an tong hop).",
          "Rewrite query sang tieng Anh cho CLIP + trich vung anh lien quan.",
          "VLM dem doi tuong tren top frame, cross-check 1 vong reflection -> dap an on dinh.",
        ],
      },
      qaAnswer: QA_ANSWER,
      qaHits: QA_HITS.map((h) => ({ ...h })),
    };
  }

  if (kind === "trake") {
    return {
      ...base,
      content: "Chuoi 3 moc hanh dong tren video L25_V001 (bam 1 moc de soi & chinh frame).",
      trace: {
        task_type: "trake",
        confidence: 0.86,
        rewritten_query: "person stands up, walks forward, then turns head back",
        n_loops: 0,
        thoughts: [
          "Router phan loai: TRAKE (chuoi hanh dong tuan tu).",
          "Tach mo ta thanh 3 moc, rewrite tung moc sang tieng Anh.",
          "Chon video tot nhat roi can tung moc theo thu tu thoi gian tang dan.",
        ],
      },
      trakeResult: {
        video_id: "L25_V001",
        fps: TRAKE_FPS,
        events: TRAKE_EVENTS.map((e) => ({ ...e })),
      },
    };
  }

  // kind === "kis"
  return {
    ...base,
    content: "Da tim thay cac phan canh phu hop nhat (bam thumbnail de mo video kiem chung).",
    trace: {
      task_type: "kis",
      confidence: 0.94,
      rewritten_query: "person speaking at an outdoor press conference, blue logo behind",
      n_loops: 0,
      thoughts: [
        "Router phan loai: KIS (su kien truc quan don le).",
        "Rewrite query sang tieng Anh cho CLIP: 'person speaking at an outdoor press conference...'.",
        "Truy van CLIP + ap Risk-aware ranking -> xep hang cac keyframe ung vien.",
      ],
    },
    kisHits: KIS_HITS.map((h) => ({ ...h })),
  };
}

export function makeUserMessage(text: string): ChatMessage {
  return { id: uid(), role: "user", content: text, timestamp: now(), status: "done" };
}

export function makeLoadingMessage(): ChatMessage {
  return { id: uid(), role: "assistant", content: "", timestamp: now(), status: "loading" };
}
