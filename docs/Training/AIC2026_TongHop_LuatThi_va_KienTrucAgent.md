# AIC HCMC 2026 — Tài liệu tổng hợp: Luật thi vòng sơ tuyển & Kiến trúc AI Agent cho hệ thống tìm kiếm video

> Tài liệu này gộp hai nguồn: (1) thông tin chính thức về vòng sơ tuyển AIC2026, và (2) nội dung buổi tập huấn "Kiến trúc Agentic AI và Ứng dụng LLM trong hệ thống tìm kiếm" (Hồ Lê Minh Quân, ĐH Khoa học Tự nhiên, ĐHQG-HCM). Phần 3 liên hệ trực tiếp hai nguồn này vào hệ thống baseline CLIP ViT-B/32 đang xây dựng.

---

## Phần 1 — Luật thi vòng sơ tuyển AIC2026

### 1.1. Ba dạng truy vấn

| Dạng | Nhiệm vụ | Định dạng trả lời |
|---|---|---|
| **Textual KIS** | Định vị chính xác video/khung hình khớp với mô tả văn bản | `<video_id>, <frame_id>` |
| **Q&A** | Tìm khoảnh khắc liên quan **và** trả lời câu hỏi về nội dung sự kiện đó | `<video_id>, <frame_id>, <answer>` |
| **TRAKE** | Truy xuất video **và** căn chỉnh một chuỗi khoảnh khắc ngữ nghĩa (semantic keyframe) theo thời gian | `<video_id>, <frame_id₁>, ..., <frame_idₙ>` |

TRAKE gồm 2 giai đoạn: **Retrieval** (tìm đúng 1 video trong kho lớn) → **Alignment** (xác định đúng 1 khung hình ngữ nghĩa cho từng giai đoạn của chuỗi sự kiện, ví dụ 4 khoảnh khắc của động tác nhảy cao: chạy đà → giậm nhảy → bay qua xà → tiếp đất).

### 1.2. Cách chấm điểm

**R-Score** — điểm tương quan cho từng câu trả lời, từ 0 đến 1:

- *Textual KIS*: $R\text{-}Score = \mathbb{I}(v_i = GT_v \land id_i \in [s,e])$ — đúng video và frame nằm trong khoảng đáp án mới được 1 điểm, sai thì 0, không có điểm trung gian.
- *Q&A*: thêm điều kiện `answer` phải khớp ngữ nghĩa với đáp án đúng — thiếu 1 trong 3 điều kiện (video / frame / answer) là 0 điểm.
- *TRAKE*: nếu sai video → 0 điểm ngay lập tức. Nếu đúng video, điểm = tỉ lệ số khoảnh khắc khớp trên tổng N khoảnh khắc, mỗi khoảnh khắc có một đoạn $[s_j, e_j]$ riêng (thường dưới 10 frame — độ chính xác temporal đòi hỏi rất cao).

**Final Score** — mỗi truy vấn được nộp tối đa 100 câu trả lời (có thứ tự ưu tiên). Với $k \in \{1,5,20,50,100\}$, lấy $R@k$ = R-Score cao nhất trong k câu đầu, rồi:

$$Final\ Score = \frac{1}{5}\sum_{k} R@k$$

→ **Hệ quả quan trọng cho chiến lược nộp bài**: không chỉ cần tìm ra câu trả lời đúng, mà càng xếp nó ở vị trí cao (top-1, top-5) thì điểm càng lợi. Điều này trực tiếp thưởng cho việc **cải thiện ranking/reranking**, không chỉ recall.

### 1.3. Dữ liệu cung cấp (Đợt 1)

| Thành phần | Nội dung |
|---|---|
| Videos | Video gốc (dữ liệu thi chính thức) |
| Keyframes | Trích theo thư mục cùng tên video, thứ tự tăng dần |
| Objects | JSON kết quả Faster R-CNN (pretrained trên OpenImages V4), 1 file/keyframe |
| CLIP features | Vector `clip-ViT-B-32` cho toàn bộ keyframe, gộp trong 1 file `.npy` |
| Metadata | JSON metadata YouTube theo video (không phải video nào cũng có) |

Lưu ý: đây là dữ liệu batch 1 của AIC 2025 tái sử dụng; batch 2 của AIC2026 sẽ được bổ sung sau.

---

## Phần 2 — Kiến trúc Agentic AI & LLM trong hệ thống tìm kiếm

*(Tóm tắt nội dung Tập huấn Buổi 3)*

### 2.1. Khái niệm nền

- **LLM**: mô hình dự đoán token tiếp theo dựa trên xác suất chuỗi. Mạnh về hiểu/sinh ngôn ngữ, nhưng **phản xạ một chiều** — không tự hành động lên môi trường nếu không được "gắn" thêm cơ chế.
- **AI Agent** (định nghĩa tổng quát): hệ thống tự chủ **cảm nhận (perceive)** → **hành động (act)** lên môi trường để đạt mục tiêu. Agent phi-ngôn ngữ đã tồn tại từ lâu (AlphaGo, thuật toán A*, xe tự lái) — cái mới là dùng **LLM làm "bộ não"** để suy luận và điều phối.
- **AI Agent + LLM**: LLM cho agent khả năng dùng ngôn ngữ để **suy luận và giao tiếp** — hiểu chỉ dẫn tốt hơn (in-context learning), và tự phản tư/điều chỉnh kế hoạch (reflection pattern: generate → reflect → re-plan).
- **Action Space khi có LLM**: Internal Action (suy nghĩ nội tại), Self-reflection, Multimodal Perception.
- **Dòng phát triển**: Logical Agent (rule-based, knowledge base) → Neural Agent (deep learning end-to-end) → **Language Agent** (LLM làm lõi lập luận, có thể tích hợp thêm Multimodal Agent cho thị giác/âm thanh).

### 2.2. Ba nền tảng cốt lõi của AI Agent

**a) Reasoning (Suy luận)**
- Hệ thống 1 (Intuitive) vs Hệ thống 2 (Reasoning): nhanh-song song-tự động vs chậm-tuần tự-có kiểm soát. Các dòng model reasoning hiện tại (o1/o3, Gemini Thinking) tích hợp "tư duy ngầm" trước khi xuất câu trả lời cuối, giúp giảm lỗi logic.
- Ba chiến lược suy luận:
  - **Input-Output (IO)**: trả lời trực tiếp, không phân tích sâu.
  - **Chain of Thought (CoT)**: suy luận theo 1 chuỗi tuyến tính — có hệ thống hơn nhưng rủi ro "đi lệch hướng một lần là sai luôn".
  - **Tree of Thoughts (ToT)**: tạo nhiều nhánh suy nghĩ song song, tự đánh giá và **backtrack** để chọn nhánh tối ưu — tốn chi phí hơn nhưng bền vững hơn với bài toán phức tạp/nhiều bước.

**b) Memory (Bộ nhớ)** — 3 loại phân theo nội dung, độc lập với cách triển khai:

| Loại | Ghi nhớ (Write) | Đọc lại (Read) | Ví dụ |
|---|---|---|---|
| Episodic (hồi tưởng) | Append-only event stream | Điểm heuristic (recency × importance × relevance) | Generative Agents (Park et al., 2023) |
| Semantic (ngữ nghĩa) | LLM suy luận/tổng hợp từ sự kiện thành "reflection" | Truy xuất tri thức đã tổng hợp | — |
| Procedural (thủ tục) | Lưu kỹ năng | Tái sử dụng kỹ năng đã học | Voyager (Wang et al., 2023) |

- **HippoRAG**: lấy cảm hứng từ cơ chế hippocampus của não người — thay vì retrieval "phẳng" như RAG thông thường, xây dựng đồ thị tri thức liên kết thực thể (knowledge graph) để trả lời được các câu hỏi multi-hop mà RAG truyền thống bỏ sót.

**c) Planning (Lập kế hoạch)** — cho mục tiêu G, tìm chuỗi hành động dẫn tới trạng thái thoả điều kiện đích:
- **Reactive**: nhanh, dễ triển khai, nhưng tham lam/thiển cận (không nhìn trước).
- **Tree search với tương tác thật**: khám phá có hệ thống, nhưng chậm và có thể thực hiện hành động không thể đảo ngược trên môi trường thật.
- **Model-based planning (World Model)**: mô phỏng $\hat{T}: S \times A \to S$ (dự đoán trạng thái kế tiếp từ trạng thái + hành động hiện tại) để "tưởng tượng trước" hậu quả — nhanh hơn, an toàn hơn, nhưng cần xây được world model đủ tốt (ví dụ: LLM dự đoán trang web sẽ trông ra sao sau một cú click, trước khi thực sự click).

### 2.3. Ứng dụng thực tế (đáng chú ý nhất cho bài toán video retrieval)

- **Coding Agent / Computer Use Agent / Robot Agent**: minh hoạ khung Agent–Environment–Observation Space–Action Space chung cho mọi loại agent.
- **VideoQA (khung STAR — Spatiotemporal Reasoning)**: một **LLM Planner điều phối một bộ tool** (temporal-grounding, image-caption, frame-selector, OCR, summarizer) theo vòng lặp: xác định đoạn thời gian liên quan → chọn khung hình → đọc chữ/mô tả trong khung hình → tổng hợp câu trả lời. **Đây gần như là bản thiết kế mẫu cho module Q&A của một hệ thống thi như AIC2026.**
- **QA trong Lifelog Retrieval (MemoriEase)**: Agent hội thoại kết hợp RAG trên kho ảnh egocentric khổng lồ — index bằng embedding (CLIP/BLIP-2) + metadata có cấu trúc trên Elasticsearch, sau đó rerank/reader để sinh câu trả lời từ lịch sử hội thoại nhiều lượt. **Kiến trúc này gần như song song với pipeline CLIP + Elasticsearch hybrid mà đề bài AIC2026 gợi ý.**

### 2.4. Kết luận — Hướng phát triển tương lai của AI Agent (theo slide)

Năm hướng nghiên cứu mở mà bài trình bày nêu ra, kèm câu hỏi mở tương ứng:

1. **Lập kế hoạch dài hạn (Advanced Planning)** — làm sao lập kế hoạch phân cấp (hierarchical) thay vì chỉ yêu cầu suông một LLM? (Tìm kiếm) trong cây kế hoạch nên đi xa tới đâu? Cần hàm giá trị/mô hình phần thưởng nào để đánh giá một kế hoạch *chưa hoàn chỉnh*?
2. **Tổng hợp dữ liệu đa nguồn (Data Synthesis)** — dữ liệu Internet chủ yếu là *sản phẩm* của quá trình cảm nhận–quyết định–thực thi, chứ không phản ánh chính quá trình đó; dùng LLM để tổng hợp dữ liệu là cách khám phá lại (một phần) các quá trình ẩn này.
3. **Học liên tục (Continuous Learning)** — lĩnh vực đang chuyển từ "ra lệnh điều khiển" sang "sao chép hành vi/tinh chỉnh có giám sát", nhưng sao chép hành vi thường không đủ cho agent tổng quát — agent cần tự khám phá môi trường và học từ thử–sai, kéo theo thách thức về action space mở, reward model, và an toàn.
4. **An toàn hệ thống (AI Safety)** — nghiên cứu an toàn agent đang tụt hậu so với tốc độ triển khai. Agent ngôn ngữ vừa kế thừa toàn bộ rủi ro của LLM (thiên vị, ảo giác, quyền riêng tư, minh bạch), vừa khuếch đại một số rủi ro cũ (mất việc làm), vừa tạo ra rủi ro hoàn toàn mới — đặc biệt là **hành động không thể đảo ngược**.
5. **Giao diện tác tử–máy tính (Agent-Computer Interface, ACI)** — cần thiết kế ACI với mức đầu tư ngang với thiết kế HCI (giao diện người-máy) cổ điển. Câu hỏi mở về hợp tác người–agent: cách tốt nhất để con người và AI làm việc cùng nhau là gì (so sánh Devin/Cursor/GitHub Copilot)? Phần lớn benchmark agent hiện nay giả định vận hành hoàn toàn tự động, bỏ qua yếu tố con người trong vòng lặp.

---

## Phần 3 — Liên hệ trực tiếp: áp dụng kiến trúc Agentic AI vào hệ thống AIC2026

Nguyên tắc nền (theo khung "Building Effective AI Agents" của Anthropic): **luôn thử phương án đơn giản nhất trước** — chỉ thêm agent/nhiều bước khi thực sự đo được là nó cải thiện kết quả. Không phải cả 3 dạng truy vấn đều cần agent.

### 3.1. Textual KIS — Workflow đơn giản là đủ, chưa cần Agent

Task có cấu trúc cố định: encode query → tìm k láng giềng gần nhất trong không gian CLIP → (tuỳ chọn) rerank bằng object detection/OCR. Đây là **workflow tuyến tính** (prompt chaining ở mức đơn giản nhất, thậm chí không cần LLM). Đầu tư agent phức tạp ở đây thường không đáng — nên dồn effort vào backbone thị giác mạnh hơn (SigLIP2/BEiT-3/EVA-CLIP) và reranking bằng object/OCR trước.

### 3.2. Q&A — Nơi mô hình Orchestrator + Tool-use (giống STAR/MemoriEase) phát huy giá trị nhất

Q&A đòi hỏi: định vị khoảnh khắc **và** trích xuất thông tin cụ thể (màu sắc, số lượng, chữ trên biển hiệu...) — số bước cần thiết **không đoán trước được** tuỳ câu hỏi (có câu chỉ cần nhìn keyframe, có câu cần OCR, có câu cần đếm object qua nhiều frame). Đây đúng là điều kiện để chọn **Orchestrator-workers pattern**:

- Orchestrator (LLM, ví dụ Qwen2.5-VL hoặc Vintern-1B) nhận câu hỏi → quyết định gọi tool nào trong số: object-detection JSON có sẵn, OCR (PARSeq/Gemini OCR), ASR (Whisper), CLIP re-search cho đoạn lân cận.
- Tương tự STAR framework: temporal-grounding trước (thu hẹp đoạn video) rồi mới gọi các tool chi tiết hơn trên các frame ứng viên, tránh chạy VQA nặng trên toàn bộ video.
- Thiết kế tool nên theo nguyên tắc ACI trong skill kiến trúc agent: mô tả tool đủ rõ để LLM không phải đoán định dạng input/output, đặt giới hạn số vòng lặp gọi tool để kiểm soát chi phí/latency.

### 3.3. TRAKE — Workflow có cấu trúc (không phải Agent tự do)

Số lượng và thứ tự các "khoảnh khắc ngữ nghĩa" thường **đã biết trước** trong truy vấn (ví dụ 4 giai đoạn của một cú nhảy) → đây là task tách được thành **chuỗi bước cố định** → phù hợp **prompt chaining có gate kiểm tra giữa các bước** hơn là để LLM tự quyết định số bước. Ý tưởng liên hệ:
- Giai đoạn 1 (Retrieval video): dùng pipeline giống Textual KIS.
- Giai đoạn 2 (Alignment): với video đã xác định, chạy N lần dò tìm frame — mỗi lần ứng với một khoảnh khắc trong chuỗi sự kiện đã biết trước, có thể dùng ý tưởng "world model" ở mức nhẹ: dự đoán khoảng thời gian khả dĩ chứa khoảnh khắc kế tiếp dựa trên khoảnh khắc trước đó, thay vì tìm kiếm toàn bộ video lại từ đầu — vì đoạn đáp án đúng thường rất hẹp (dưới 10 frame), sai số thời gian ảnh hưởng điểm trực tiếp.

### 3.4. Memory — gợi ý cho hạ tầng vector DB/Elasticsearch

- Xem CLIP features + FAISS/Milvus hiện có như một dạng **semantic memory** (tri thức đã được index sẵn).
- Object JSON + OCR/ASR kết quả có thể đưa vào **Elasticsearch dạng structured metadata**, đúng mô hình hybrid mà MemoriEase minh hoạ — cho phép lọc/rerank kết hợp similarity search với điều kiện chính xác (ví dụ "có object = person AND OCR chứa số áo X").
- Nếu về sau muốn hệ thống "nhớ" các truy vấn/phản hồi đã xử lý trong phiên làm việc (ví dụ để tinh chỉnh lại kết quả theo phản hồi giám khảo mô phỏng) — đó là lúc cân nhắc **episodic memory** kiểu append-only log.

### 3.5. Liên hệ 5 hướng phát triển tương lai với roadmap của bạn

| Hướng (slide) | Liên hệ cụ thể với hệ thống AIC2026 |
|---|---|
| Advanced Planning | Chủ yếu liên quan đến TRAKE — nếu sau này muốn agent tự quyết định số khoảnh khắc/thứ tự dò tìm thay vì cố định như đề xuất ở 3.3, đây là lúc cần world model/hàm giá trị đánh giá "kế hoạch dò tìm" từng phần. |
| Data Synthesis | Có thể dùng LLM để sinh thêm cặp (query, video, frame) giả lập từ metadata/OCR/object JSON có sẵn, phục vụ fine-tune hoặc test nội bộ trước khi có bộ query thật từ BTC. |
| Continuous Learning | Đúng tinh thần "đo–sửa–đo" đã đặt ra: log lại toàn bộ câu trả lời/­điểm R-Score qua các lần thử để dần hiệu chỉnh ngưỡng/chiến lược rerank, thay vì đoán một lần rồi thôi. |
| AI Safety | Rủi ro chính ở đây là **ảo giác của VQA/LLM trong module Q&A** (trả lời sai nhưng tự tin) — nên có bước kiểm tra chéo (ví dụ đối chiếu answer với OCR/object detection) trước khi nộp, vì sai `answer` khiến R-Score về thẳng 0 dù frame/video đúng. |
| ACI | Áp dụng ngay khi thiết kế tool cho Orchestrator ở mục 3.2: đặt tên tool/tham số rõ ràng, định dạng gần với thứ LLM đã quen (markdown hơn JSON), và luôn có giới hạn số vòng lặp — tránh để chi phí/latency vượt quá thời gian cho phép của vòng thi. |

---

## Ghi chú

Tài liệu này được tổng hợp từ 2 nguồn cung cấp: file luật thi AIC2026 (project) và slide tập huấn Buổi 3 (PDF tải lên). Phần 3 là phần diễn giải/đề xuất áp dụng, chưa phải quyết định kiến trúc cuối cùng — nên được kiểm chứng bằng thực nghiệm time-boxed (2–3 ngày/nhánh) theo đúng phương pháp đo–sửa–đo đã đặt ra ban đầu, trước khi đầu tư sâu vào agent/orchestrator.
