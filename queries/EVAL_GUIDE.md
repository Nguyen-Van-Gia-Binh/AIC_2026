# Hướng dẫn ghi ground truth cho bộ eval Phase 6

> Xem [PLAN.md](../PLAN.md) §Phase 6 để biết bối cảnh đầy đủ. File dữ liệu thật cần điền:
> [eval_ground_truth.json](eval_ground_truth.json) (khởi tạo rỗng `[]`).

## Vì sao việc này cần người, không phải AI

AI cố vấn/agent không xem được nội dung video thật. Ground truth (video nào, frame nào đúng) chỉ
có thể lấy được bằng cách 1 người tự xem video trong `data/extracted/keyframes/{batch}/{video_id}/`
(hoặc video gốc nếu có) rồi ghi lại. Dùng
[scripts/eval/lookup_frame.py](../scripts/eval/lookup_frame.py) để tra nhanh `frame_id` từ timestamp
thay vì tự tính bằng tay từ fps.

## Cỡ mẫu đề xuất

~30 câu KIS + 10 câu QA + 10 câu TRAKE (~50 câu tổng, đủ để so sánh có ý nghĩa mà không tốn quá
nhiều thời gian ghi tay). Chọn video trải đều 10 batch `L21`–`L30` trong `data/extracted/keyframes/`,
đừng dồn hết vào 1-2 batch.

Trải phổ độ khó — giữ một số câu **dễ** (đối tượng/màu/hành động rõ, làm sanity check hệ thống chưa
hỏng), phần còn lại dồn vào các dạng **lắt léo** sau (nên có đủ, không bắt buộc đều nhau):

- Đối tượng nhỏ / khuất một phần khung hình.
- Nhiều đối tượng giống nhau chỉ khác 1 chi tiết (màu áo, số áo, loại xe).
- Hành động rất ngắn giữa video dài.
- Mô tả phụ thuộc thứ tự thời gian ("trước khi X thì Y") — quan trọng riêng cho TRAKE.
- Câu hỏi đếm số lượng (QA) — dễ sai vì phần đếm nằm ở vision LLM, không phải retrieval.
- Câu phủ định/loại trừ ("cảnh không có người").
- Câu tiếng Việt có từ địa phương/viết tắt (kiểm tra `rewrite.py` dịch có giữ đúng ý).
- Ảnh dễ đánh lừa CLIP (phản chiếu gương, ảnh lồng trong ảnh/màn hình TV trong khung).

## Quy trình ghi 1 câu

1. Xem video/lướt keyframe, chọn 1 khoảnh khắc rõ ràng, nghĩ ra câu mô tả (KIS) hoặc câu hỏi (QA)
   hoặc chuỗi N khoảnh khắc (TRAKE).
2. Ghi lại thời điểm (giây) của khoảnh khắc đó.
3. Chạy `lookup_frame.py` để ra `frame_id` gần nhất + gợi ý khoảng `[gt_frame_start, gt_frame_end]`:

   ```
   .venv\Scripts\python.exe scripts\eval\lookup_frame.py L21_V001 25.0
   ```

   Khoảng gợi ý mặc định khá rộng (tới keyframe lân cận) — nên tự thu hẹp lại bằng mắt (xem ảnh in
   ra ở cột "ảnh") cho khớp đúng lúc khoảnh khắc bắt đầu/kết thúc, giống cách BTC định nghĩa `[s, e]`
   trong `docs/Thong tin vong So tuyen AIC2026.md` §2.1 — khoảng càng sát thật càng đo baseline chính
   xác, khoảng quá rộng sẽ làm mọi model "ăn điểm dễ" và mất khả năng phân biệt model mạnh/yếu.
4. Thêm 1 object vào mảng trong `eval_ground_truth.json` theo đúng schema bên dưới.

## Schema

Field chung cho cả 3 loại: `query_id` (duy nhất, ví dụ `"e-kis-001"`), `type`
(`"KIS"`/`"QA"`/`"TRAKE"`), `text_vi`, `text_en` (English — dùng để retrieve, cùng quy ước
`queries/sample_queries.json`), `difficulty_tags` (mảng string tuỳ chọn, ví dụ
`["small_object", "counting"]` — dùng để soi kết quả theo từng dạng lắt léo sau này, không bắt buộc).

### KIS

```jsonc
{
  "query_id": "e-kis-001",
  "type": "KIS",
  "text_vi": "...",
  "text_en": "...",
  "difficulty_tags": [],
  "gt_video_id": "L21_V001",     // không có .mp4
  "gt_frame_start": 532,          // frame_id = frame_idx + 1, giống mọi nơi khác trong repo
  "gt_frame_end": 859
}
```

### QA

```jsonc
{
  "query_id": "e-qa-001",
  "type": "QA",
  "text_vi": "...",
  "text_en": "...",
  "question": "How many people are on stage?",   // câu hỏi tiếng Anh, khớp field "question" của sample_queries.json
  "difficulty_tags": ["counting"],
  "gt_video_id": "L22_V010",
  "gt_frame_start": 100,
  "gt_frame_end": 120,
  "gt_answer": "3"    // lưu để dùng SAU — Phase 6 KHÔNG dùng field này để tính điểm (xem PLAN.md
                       // lý do: answer do LLM sinh, không phản ánh chất lượng retrieval đang so sánh)
}
```

### TRAKE

```jsonc
{
  "query_id": "e-trake-001",
  "type": "TRAKE",
  "text_vi": "...",
  "text_en": "...",
  "difficulty_tags": ["temporal_order"],
  "gt_video_id": "L25_V003",
  "events": [
    {"text_en": "athlete takes off from the ground", "gt_frame_start": 95,  "gt_frame_end": 105},
    {"text_en": "athlete clears over the bar at peak height", "gt_frame_start": 145, "gt_frame_end": 155},
    {"text_en": "athlete lands on the mat", "gt_frame_start": 195, "gt_frame_end": 205}
  ]
}
```

> ⚠️ 3 khối JSON trên chỉ là **VÍ DỤ MINH HOẠ format — KHÔNG PHẢI ground truth thật**. Đừng copy
> nguyên giá trị số vào `eval_ground_truth.json`, chỉ copy đúng cấu trúc field rồi điền số thật của
> bạn sau khi tự xem video.

## Sau khi ghi xong (dù chưa đủ 50 câu)

Không cần đợi ghi đủ hết mới chạy thử — `scripts/eval/run_eval.py` chạy được ngay cả khi
`eval_ground_truth.json` mới có vài dòng, hữu ích để phát hiện lỗi format sớm:

```
.venv\Scripts\python.exe scripts\eval\run_eval.py
```
