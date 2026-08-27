# Chat Screen UI & Interaction Architecture — Design Spec

> **Ngày tạo:** 2026-08-28  
> **Trạng thái:** Đã thống nhất thiết kế qua Brainstorming (Chờ phê duyệt spec trước khi lập kế hoạch triển khai)  
> **Mục tiêu:** Xây dựng màn hình Chat tương tác đa tác vụ (KIS / Q&A / TRAKE) với mô hình Full-height Chat + Drawer linh hoạt và Unified Video Verifier.

---

## 1. Bối cảnh & Mục tiêu

Trong hệ thống tìm kiếm video cho AIC 2026, người dùng cần một giao diện hội thoại tự nhiên (Chat) đóng vai trò trợ lý thông minh:
1. **Tiếp nhận câu hỏi ngôn ngữ tự nhiên** mà không bắt người dùng phải tự phân loại sang các tab KIS/Q&A/TRAKE thủ công.
2. **Hiển thị kết quả trực quan dạng Rich Card Đa Tầng**: thể hiện quá trình suy luận (Agent Trace), đáp án tổng hợp (cho Q&A), dải keyframe ứng viên (cho KIS) hoặc chuỗi hành động tuần tự (cho TRAKE).
3. **Đồng bộ cơ chế kiểm chứng Video Verifier**: Bất kể tác vụ nào, khi bấm vào thumbnail đều mở Drawer bên phải với trình phát video kiểm chứng, cho phép tua từng frame (`[A]/[D]`), cập nhật lại frame_id vào kết quả và chốt nộp bài trực tiếp vào hàng đợi (`Queue`).

> 💡 **Chiến lược triển khai Mock-First (Test giao diện trước, nối pipeline sau)**:
> - **Giai đoạn 1**: Xây dựng toàn bộ giao diện Chat Frontend hoàn chỉnh với **dữ liệu Mock tương tác thực tế** (sử dụng video_id/keyframe thật trong dataset để `VideoVerifier` tua video được thật 100%). Người dùng có thể trải nghiệm, test phím tắt, test mở Drawer, sửa frame và chốt hàng đợi ngay trên trình duyệt.
> - **Giai đoạn 2**: Nối API Backend (`scripts/api/routers/chat.py` và Router LLM / LangGraph) vào UI mà không làm thay đổi cấu trúc component frontend.

---

## 2. Kiến trúc Giao diện & Component Frontend

### 2.1 Cấu trúc phân cấp Component

```
frontend/src/
 ├── App.tsx                        # Kích hoạt tab "Chat" (bỏ disabled)
 ├── api/client.ts                  # Bổ sung client method api.chatMessage(...)
 ├── screens/
 │    └── ChatScreen.tsx            # Màn hình Chat chính (quản lý state messages & inspectState)
 └── components/chat/
      ├── ChatHeader.tsx            # Header phiên (Query ID, Model/Quota status, Nút Reset)
      ├── ChatTimeline.tsx          # Vùng cuộn danh sách tin nhắn hội thoại
      ├── ChatBubble.tsx            # Bong bóng tin nhắn (User vs Assistant Rich Card)
      │    ├── AgentTraceAccordion.tsx # Xem các bước suy luận của Router/VLM/OCR
      │    ├── KisResultCards.tsx   # Dải/lưới keyframe ứng viên cho KIS
      │    ├── QaResultBanner.tsx   # Khung đáp án + frame chứng cứ cho Q&A
      │    └── TrakeSequenceView.tsx# Dòng thời gian mốc tuần tự cho TRAKE
      ├── ChatDrawer.tsx            # Slide-over Drawer bên phải (chứa VideoVerifier & sync controls)
      └── ChatInput.tsx             # Textarea tự co giãn, chip tác vụ nhanh, phím tắt Enter
```

### 2.2 Schema Dữ liệu (TypeScript Interfaces)

```typescript
// frontend/src/types/chat.ts (hoặc định nghĩa trong api/client.ts)

export interface AgentTrace {
  task_type: "kis" | "qa" | "trake" | "clarify";
  confidence: number;            // 0.0 -> 1.0 (vd: 0.94)
  rewritten_query?: string;      // Query đã dịch sang tiếng Anh cho CLIP
  n_loops?: number;              // Số vòng reflection (QA)
  thoughts: string[];            // Các bước suy luận hiển thị trong accordion
}

export interface ChatMessage {
  id: string;                    // UUID
  role: "user" | "assistant";
  content: string;               // Văn bản trả lời chính
  timestamp: string;             // HH:mm:ss
  status: "loading" | "done" | "error";
  errorMessage?: string;
  
  // Dữ liệu chuyên biệt khi Assistant trả lời
  trace?: AgentTrace;
  kisHits?: Hit[];               // Danh sách frame cho KIS
  qaHits?: QaHit[];              // Danh sách frame + câu trả lời cho QA
  qaAnswer?: string;             // Đáp án chung của QA
  trakeResult?: {                // Kết quả TRAKE
    video_id: string;
    events: {
      event_idx: number;
      query: string;
      frame_id: number;
      frame_idx: number;
      pts_time?: number;
      score: number;
    }[];
  };
}

export interface InspectState {
  open: boolean;
  videoId: string;
  frameId: number;
  frameIdx: number;
  ptsTime?: number;
  messageId: string;
  resultIndex: number;           // Vị trí của card/mốc đang soi (#1, #2, hoặc Mốc 1)
  taskType: "kis" | "qa" | "trake";
}
```

---

## 3. Thiết kế Tương tác & Hành vi (Interaction Design)

### 3.1 Luồng Chat & Phản hồi Đa Lượt (Multi-turn)
1. **Lượt đầu tiên**: Người dùng nhập query ➔ Agent phân loại (Router LLM) ➔ Chạy pipeline tương ứng ➔ Trả về Rich Card.
2. **Lượt tiếp theo (Feedback / Sửa đổi)**:
   - Nếu người dùng nhập câu bổ sung (vd: *"Tìm lại với video L21 thôi"*, *"Mốc 2 bị lệch quanh giây 25"*, *"Đổi đáp án thành màu đỏ"*):
   - Router nhận diện là **lượt tiếp nối** của phiên hiện tại ➔ Kế thừa context và tái sử dụng tham số `feedback` để tinh chỉnh kết quả mà không cần bắt đầu lại từ đầu.
3. **Nút Reset Session**: Xóa lịch sử hiển thị và đặt lại trạng thái phiên ở Backend khi bắt đầu câu hỏi thi mới.

### 3.2 Luồng Kiểm chứng Unified Video Verifier (Drawer)
1. Người dùng bấm vào bất kỳ thumbnail nào trên ChatBubble (ở KIS, QA hay TRAKE).
2. Drawer trượt ra từ bên phải:
   - Nhúng trực tiếp `<VideoVerifier />` với `videoId`, `frameId`, `ptsTime`.
   - Phím tắt `[A]` (lùi frame), `[D]` (tiến frame), `[Space]` (phát video).
   - Dải keyframe của video bên dưới video player để cuộn và nhảy nhanh.
3. **Cập nhật Frame vào kết quả**:
   - Người dùng bấm `[📌 Cập nhật Frame {id} vào vị trí #{rank}]`.
   - State `messages` trong `ChatScreen` cập nhật ngay lập tức `frame_id`, `frame_idx`, `pts_time` cho card đó.
   - Thumbnail tương ứng trên bong bóng chat cập nhật tức thì kèm nhãn xanh lá `[Đã chỉnh sửa]`.

### 3.3 Luồng Chốt Hàng Đợi Nộp Bài (Queue Submission)
1. Nút `[📥 Chốt vào Hàng đợi nộp]` xuất hiện cả trên Bong bóng Chat và trong Drawer.
2. Khi bấm, hệ thống:
   - Validate định dạng `video_id`, `frame_id` (số nguyên dương) và `answer` (nếu là Q&A).
   - Gọi `POST /api/queue/{session_id}/add` với payload `QueueRow`.
   - Hiển thị Toast thông báo thành công `✅ Đã thêm {query_id} vào Hàng đợi ({n} dòng)`.
   - Tab "Hàng đợi" trên thanh menu cập nhật badge đếm số dòng sẵn sàng xuất ZIP/CSV.

---

## 4. Backend API Contract

### 4.1 Endpoint `POST /api/chat/{session_id}/message`
- **Request Body**:
  ```json
  {
    "message": "Tìm video người áo vàng đi xe đạp qua ngã tư...",
    "query_id": "chat-query-001"
  }
  ```
- **Xử lý**:
  - Router LLM: Phân loại task (`kis` / `qa` / `trake` / `feedback`).
  - Gọi pipeline tương ứng (`run_kis` / `run_qa` / `run_trake`).
  - Lưu trạng thái phiên trong `scripts/api/state.py`.
- **Response**:
  ```json
  {
    "reply": "Đã tìm thấy các phân cảnh phù hợp...",
    "task_type": "kis",
    "trace": {
      "task_type": "kis",
      "confidence": 0.95,
      "rewritten_query": "person in yellow shirt riding bicycle crossing intersection",
      "n_loops": 0,
      "thoughts": [
        "Router phân loại: KIS (Sự kiện trực quan đơn lẻ)",
        "Rewrite query sang tiếng Anh cho CLIP: 'person in yellow shirt...'",
        "Truy vấn CLIP và áp dụng Risk-aware ranking"
      ]
    },
    "kis_hits": [
      { "video_id": "L05_V021", "frame_id": 840, "frame_idx": 839, "pts_time": 33.6, "score": 0.912 }
    ]
  }
  ```

---

## 5. Quy trình Kiểm thử & Xác thực (Verification)

1. **Kiểm tra Giao diện (Frontend Layout)**:
   - Kích hoạt tab Chat trong `App.tsx`.
   - Kiểm tra hiển thị Rich Card của 3 dạng bài (KIS, QA, TRAKE) với dữ liệu mẫu và dữ liệu thật.
   - Kiểm tra cơ chế mở/đóng Drawer êm ái, không làm mất dòng cuộn tin nhắn.
2. **Kiểm tra Tương tác Video Verifier**:
   - Bấm vào thumbnail KIS/QA/TRAKE ➔ Drawer mở đúng video_id và đúng frame.
   - Tua frame bằng phím `[A]`/`[D]` ➔ Bấm cập nhật frame ➔ Xác nhận card ngoài chat cập nhật frame mới.
3. **Kiểm tra Chốt Hàng Đợi**:
   - Bấm nộp từ Chat ➔ Chuyển qua tab "Hàng đợi" kiểm tra dòng submission được tạo chính xác với đầy đủ metadata.
4. **Kiểm tra Phản hồi Đa Lượt**:
   - Gửi query tiếp nối ➔ Xác minh context được giữ và phản hồi đúng logic.
