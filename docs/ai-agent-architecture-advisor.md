---
name: ai-agent-architecture-advisor
description: Đề xuất kiến trúc phù hợp cho hệ thống có dùng LLM/AI agent — quyết định giữa "workflow" (đường code định sẵn) và "agent" (LLM tự điều khiển), và chọn pattern cụ thể (prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer). Dùng skill này bất cứ khi nào người dùng đang thiết kế/lên kế hoạch một sản phẩm, tính năng, đồ án, hoặc bài thi có tích hợp LLM/AI agent/chatbot/tool-calling — kể cả khi họ chỉ mô tả bài toán (ví dụ "hệ thống chấm điểm tự động", "chatbot hỗ trợ khách hàng", "agent xử lý dữ liệu IoT") mà không dùng đúng thuật ngữ "kiến trúc" hay "architecture". Dựa trên bài viết "Building Effective AI Agents" của Anthropic (12/2024).
---

# AI Agent Architecture Advisor

Skill này giúp đề xuất kiến trúc hệ thống LLM/agent phù hợp với một bài toán cụ thể, dựa trên các pattern mà Anthropic quan sát được là hiệu quả nhất trong thực tế triển khai với khách hàng: **đơn giản, có thể ghép (composable), không cần framework phức tạp**.

Khi skill này được kích hoạt, đừng chỉ liệt kê lại các pattern bên dưới — hãy dùng chúng như một khung hỏi-đáp để đi đến một đề xuất kiến trúc cụ thể cho đúng bài toán người dùng đang có.

## Quy trình đề xuất (làm theo thứ tự)

1. **Làm rõ bài toán trước khi đề xuất kiến trúc.** Cần biết: input/output là gì, task có thể tách thành các bước con rõ ràng không, có cần gọi tool/API bên ngoài không, độ mở của task (số bước có đoán trước được không), yêu cầu về độ trễ/chi phí, và mức độ "tin tưởng" có thể giao cho LLM tự quyết định.

2. **Luôn thử phương án đơn giản nhất trước.** Trước khi đề xuất bất kỳ pattern nhiều bước nào, hỏi: một lời gọi LLM đơn (kèm retrieval/RAG và vài ví dụ mẫu trong prompt — few-shot) có giải quyết được không? Nếu có, đề xuất dừng ở đó. Agentic system đánh đổi latency và chi phí để lấy khả năng xử lý task tốt hơn — chỉ tăng độ phức tạp khi việc đó *thực sự* cải thiện kết quả, và nên đo lường để chứng minh điều đó chứ không phải đoán.

3. **Phân loại: Workflow hay Agent?**
   - Chọn **Workflow** (LLM + tool chạy theo đường code định sẵn) khi: task có cấu trúc rõ ràng, các bước có thể liệt kê trước, cần tính dự đoán được (predictability) và nhất quán.
   - Chọn **Agent** (LLM tự quyết định các bước và cách dùng tool, tự kiểm soát quá trình) khi: task mở, số bước không đoán trước được, cần độ linh hoạt cao, và có thể chấp nhận rủi ro/chi phí cao hơn để đổi lấy điều đó. Agent phù hợp khi vận hành trong môi trường đáng tin cậy (trusted environment) vì rủi ro lỗi có thể dồn tích qua nhiều bước.

4. **Nếu là Workflow — chọn đúng pattern** (xem bảng quyết định bên dưới). Có thể kết hợp nhiều pattern với nhau, không cần chọn đúng một cái.

5. **Nếu là Agent — nhắc các lưu ý triển khai** (mục "Thiết kế Agent" bên dưới), đặc biệt là ACI (agent-computer interface) vì đây là điểm hay bị bỏ qua nhất.

6. **Trình bày đề xuất ngắn gọn**: kiến trúc nào, vì sao (map lại đúng đặc điểm bài toán họ mô tả), và một cảnh báo/đánh đổi (trade-off) cụ thể nếu có. Không cần liệt kê hết mọi pattern nếu không liên quan.

## Bảng quyết định cho Workflow

| Đặc điểm bài toán | Pattern phù hợp |
|---|---|
| Task tách được thành chuỗi bước cố định, bước sau phụ thuộc output bước trước; cần độ chính xác cao hơn là tốc độ | **Prompt chaining** (có thể chèn "gate" kiểm tra giữa các bước) |
| Có nhiều *loại* input khác biệt nhau, mỗi loại cần xử lý/prompt riêng để tối ưu | **Routing** (phân loại rồi rẽ nhánh; có thể route việc dễ cho model nhỏ/rẻ, việc khó cho model mạnh) |
| Các phần việc độc lập, có thể chạy song song để tiết kiệm thời gian (sectioning); hoặc cần nhiều lần thử/nhiều góc nhìn để tăng độ tin cậy (voting) | **Parallelization** |
| Task phức tạp mà *không đoán trước được* cần bao nhiêu subtask hay subtask gồm những gì (số file cần sửa, số nguồn cần tra cứu...) | **Orchestrator-workers** (một LLM trung tâm chia việc động, giao cho worker, rồi tổng hợp) |
| Có tiêu chí đánh giá rõ ràng, và việc lặp lại có phản hồi (feedback) chứng minh cải thiện được chất lượng output | **Evaluator-optimizer** (một LLM tạo, một LLM chấm + góp ý, lặp lại) |

Ghi chú phân biệt quan trọng: **Orchestrator-workers** trông giống **Parallelization/sectioning** nhưng khác ở chỗ subtask *không* được định sẵn — orchestrator tự quyết định dựa trên input cụ thể.

## Thiết kế Agent (khi đã xác định cần Agent thực thụ)

Về bản chất, agent thường chỉ là "LLM dùng tool trong một vòng lặp, dựa trên phản hồi thực tế từ môi trường (ground truth — kết quả tool call, kết quả chạy code...) để đánh giá tiến độ". Vì vậy việc thiết kế tool quan trọng ngang với việc viết prompt.

3 nguyên tắc cốt lõi cần nhắc khi đề xuất agent:

1. **Đơn giản (simplicity)** — không thêm tool/bước thừa.
2. **Minh bạch (transparency)** — để lộ rõ các bước lên kế hoạch của agent (không giấu reasoning), giúp debug và giúp người dùng tin tưởng.
3. **ACI (agent-computer interface)** — đầu tư cho tài liệu và test tool kỹ như đầu tư cho HCI (giao diện người dùng). Cụ thể:
   - Đặt mình vào vị trí model: mô tả tool có đủ rõ để không cần đoán không? Nên có ví dụ dùng, edge case, format input.
   - Đặt tên tham số/tool sao cho khó hiểu nhầm — như viết docstring cho một dev mới vào team.
   - Chọn định dạng gần với thứ model đã quen thấy trên internet (vd: markdown thường dễ hơn JSON có escaping).
   - "Poka-yoke" tool — thiết kế sao cho khó dùng sai (ví dụ: bắt buộc absolute filepath thay vì relative để tránh lỗi khi agent đổi thư mục làm việc).
   - Luôn có stopping condition (giới hạn số vòng lặp) và điểm dừng để con người review/feedback, đặc biệt ở các quyết định rủi ro cao.

Cảnh báo cần nhắc: agent có chi phí và độ trễ cao hơn workflow, và lỗi có thể dồn tích qua nhiều bước — nên khuyến nghị test kỹ trong môi trường sandbox trước khi để agent thao tác trên hệ thống thật.

## Khi framework được nhắc tới

Nếu người dùng hỏi có nên dùng framework agent (LangChain, Claude Agent SDK, Rivet, Vellum, hoặc tương đương) hay tự code:
- Framework giúp bắt đầu nhanh (gọi LLM, parse tool, chain calls) nhưng dễ tạo lớp trừu tượng che khuất prompt/response thật → khó debug, và dễ khiến người mới hiểu sai "bên dưới đang chạy gì".
- Đề xuất mặc định: bắt đầu bằng cách gọi thẳng LLM API — nhiều pattern ở trên chỉ cần vài chục dòng code. Nếu vẫn muốn dùng framework, nhấn mạnh cần hiểu rõ cơ chế bên dưới trước khi dùng.

## Nguồn

Bài viết gốc: "Building Effective AI Agents" — Anthropic Engineering, 12/2024. https://www.anthropic.com/engineering/building-effective-agents
