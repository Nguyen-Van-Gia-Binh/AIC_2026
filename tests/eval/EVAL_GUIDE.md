# Hướng dẫn ghi ground truth

> File dữ liệu: 3 file con [eval_ground_truth_kis.json](eval_ground_truth_kis.json), [eval_ground_truth_qa.json](eval_ground_truth_qa.json), [eval_ground_truth_trake.json](eval_ground_truth_trake.json) (91 câu tính đến 2026-08-31).
> Bối cảnh vì sao cần mở rộng: [PLAN.md](../../PLAN.md) §10.2 và
> [spec Pha 2 §5](../../docs/superpowers/specs/2026-08-31-phase2-behavior-fixes-design.md).

## Vì sao việc này cần người, không phải AI

AI không xem được nội dung video. Ground truth (video nào, keyframe nào đúng) chỉ có thể lấy bằng
cách **một người tự xem** rồi ghi lại.

⚠️ **Cảnh báo vòng tròn — quan trọng nhất trong tài liệu này.** Được phép dùng hệ thống (hoặc VLM)
để **đề xuất ứng viên**, nhưng **mắt người phải xác nhận** trước khi ghi vào ground truth. Nếu lấy
thẳng kết quả hệ thống làm đáp án thì bộ eval chỉ đang đo lại chính hệ thống — nó sẽ luôn cho điểm
cao và không bao giờ phát hiện được lỗi.

## Hai format — ghi bằng cái nào

Có **hai** format, cố ý:

| | Format người ghi (v2) | Format harness (v1) |
|---|---|---|
| Bạn ghi bằng cái này | ✅ | ❌ |
| `run_eval.py` / `score_pipelines.py` đọc | ❌ | ✅ |
| Bọc ngoài | `{"entries": [...]}` | mảng JSON trần |
| Câu truy vấn | `query_text` (tiếng Việt) | `text_vi` + `text_en` |
| Vị trí đúng | `gt_frame` (một số) | `gt_frame_start` + `gt_frame_end` |

Chuyển đổi bằng [normalize_gt.py](normalize_gt.py) — nó dịch máy sang tiếng Anh và dựng khoảng cho
bạn. **Bạn không cần tự dịch, không cần tự nghĩ ra khoảng.**

```
# Kiểm tra trước (chạy sớm và chạy thường xuyên — đừng gán 50 câu rồi mới kiểm tra)
.venv\Scripts\python.exe tests\eval\normalize_gt.py <file cua ban>.json --check

# Chuyển rồi tự động phân loại nối vào 3 file con tương ứng trong tests/eval/
.venv\Scripts\python.exe tests\eval\normalize_gt.py <file cua ban>.json --merge tests\eval
```

### Vì sao schema có `text_en`

SigLIP được huấn luyện trên tiếng Anh — đưa tiếng Việt vào thì retrieval kém hẳn. Nên câu tiếng Anh
phải tồn tại ở đâu đó. Câu hỏi là *dịch lúc đo hay đóng băng sẵn*.

Chọn **đóng băng sẵn**: dịch bằng LLM lúc đo thì mỗi lần chạy ra một câu khác nhau ⇒ điểm nhảy vì lý
do không liên quan tới thứ đang đo. Một thước đo tự co giãn thì không đo được gì.

`text_vi` là **sự thật** (thứ BTC đưa). `text_en` là **biến đối chứng đông cứng**.

> **Giới hạn phải biết:** `tests/e2e/score_pipelines.py` chấm KIS bằng `run_kis(q["text_en"])` —
> **luôn** trên tiếng Anh đã dịch sẵn, không bao giờ trên tiếng Việt. Nghĩa là con số KIS đang đo
> một bài **dễ hơn** bài thi thật. Chấp nhận được vì đúng quy trình thật (KIS dịch ở tầng UI và
> người dùng duyệt câu rewrite bằng mắt trước khi chạy) — nhưng đó là **giả định**, không phải sự
> thật hiển nhiên.

`normalize_gt.py` đánh dấu `"text_en_reviewed": false` cho câu do máy dịch. Đọc lại và sửa nếu bản
dịch sai ý — máy dịch hay hỏng ở từ địa phương và tên riêng.

## Quy trình A — có video trước, nghĩ câu hỏi sau

Dùng khi tự tạo câu mới (chủ yếu cho QA/TRAKE, hai loại đề thi cho quá ít câu).

1. Lướt keyframe trong `data/extracted/keyframes/{batch}/{video_id}/`, chọn một khoảnh khắc rõ ràng.
2. Ghi lại thời điểm (giây).
3. Tra keyframe tương ứng:
   ```
   .venv\Scripts\python.exe tests\eval\lookup_frame.py L21_V001 25.0
   ```
4. Ghi một entry theo schema bên dưới, `gt_frame` = `frame_id` của keyframe vừa tra.

## Quy trình B — có câu hỏi trước, đi tìm video

**Đây là chiều bạn dùng cho 79 câu đề thi thật.** Khó hơn quy trình A nhiều.

Nguồn câu hỏi có sẵn:

| Nguồn | Số câu | KIS | QA | TRAKE |
|---|---|---|---|---|
| `tests/data/thunghiem_bo_de_thi.csv` | 24 | 18 | 3 | 3 |
| `tests/data/sotuyen1_bo_de_thi.csv` | 25 | 20 | 4 | 1 |
| `data/extracted/Bo_De_Thi_Dot2/*.txt` | 30 | 19 | 9 | 2 |

Các bước:

1. Chạy chính hệ thống với câu đó (UI, hoặc `pipeline_kis.py "<query>"`) để **lấy danh sách ứng
   viên**. Đây là chỗ duy nhất được dùng hệ thống.
2. **Mở video xem tận mắt** để xác nhận. Không tin thứ hạng — video đúng có thể ở hạng 40.
3. Xác nhận rồi thì tra keyframe: bấm vào ứng viên trong UI, hoặc dùng `lookup_frame.py`.
4. Nếu **tìm không ra** sau khi đã cố: ghi `"status": "unresolved"` và **để nguyên**. Đừng đoán.
   `normalize_gt.py` bỏ qua các câu này, không tính vào mẫu.

   ```jsonc
   { "query_id": "p1-7-kis", "type": "KIS", "query_text": "...", "status": "unresolved" }
   ```

   Đề thi có thể trỏ tới video **không nằm** trong `L21`–`L30` mà bạn có. Đó không phải lỗi của bạn.

## Đánh dấu KEYFRAME, không đánh dấu mốc thời gian tuỳ ý

Đây là chỗ dễ sai nhất, và sai thì hỏng câu.

Hệ thống **chỉ trả về được `frame_id` của keyframe** — nó không trả về frame bất kỳ trong video.
Nếu khoảng bạn ghi không chứa keyframe nào, câu đó **vĩnh viễn 0 điểm dù retrieval hoàn hảo**.

Chuyện này đã thật sự xảy ra: câu `kis-001` trong file template ghi `gt_frame: 305` cho `L24_V035`,
nhưng `L24_V035` không có keyframe nào ở `frame_id` 305.

Luôn dùng `lookup_frame.py` để lấy con số, đừng tự tính từ giây × fps. `normalize_gt.py --check` sẽ
bắt lỗi này, nhưng bắt sớm bằng `lookup_frame.py` thì đỡ mất công hơn.

## Không tự nới khoảng

Mặc định `normalize_gt.py` sinh `[gt_frame, gt_frame]` — **đúng một keyframe, chặt nhất**.

Nới rộng khoảng làm điểm **dễ ăn hơn** ⇒ mọi model đều trông giỏi ⇒ mất khả năng phân biệt model
mạnh/yếu, đúng thứ bộ eval sinh ra để làm.

Chỉ thêm `gt_frame_end` khi **thật sự có nhiều keyframe liền kề cùng thể hiện khoảnh khắc đó**, và
bạn đã nhìn từng ảnh một. Script không đoán hộ.

> `widen_gt_windows.py` vẫn còn trong repo nhưng **không nằm trong quy trình chuẩn nữa**. Nó nới
> theo cơ học tới keyframe lân cận mà không biết khoảnh khắc thật kết thúc ở đâu. Chỉ dùng khi bạn
> hiểu rõ mình đang đánh đổi cái gì.

## Cỡ mẫu

Sai số chuẩn của R@k (tỷ lệ, ở mức khó nhất p ≈ 0,5):

| n | sai số |
|---|---|
| 10 | ±16 điểm % |
| 20 | ±11 điểm % |
| 30 | ±9 điểm % |
| 80 | ±5,6 điểm % |

Nói cách khác: với 10 câu, một thay đổi phải cải thiện **hơn 16 điểm %** thì mới phân biệt được với
nhiễu. Hầu hết cải tiến không đạt mức đó.

Mục tiêu:

| | Hiện có | Từ đề thi | Tự viết thêm | Đích |
|---|---|---|---|---|
| KIS | 23 | +57 | 0 | **80** |
| Q&A | 5 | +16 | +9 | **30** |
| TRAKE | 10 | +6 | +14 | **30** |
| | **38** | **+79** | **+23** | **140** |

**Đừng bịa thêm câu "cho đa dạng".** 79 câu đề thi *chính là* phân phối thật của BTC — đó là giá trị
không thay thế được của chúng. Bịa thêm câu theo cảm tính sẽ kéo bộ đo lệch khỏi phân phối thật.

Chỗ cần trải rộng là **nhãn độ khó** (để soi breakdown) và 23 câu tự viết cho QA/TRAKE — hai loại mà
đề thi cho quá ít. Với 23 câu đó, nên trải đều các dạng khó trong bảng tag bên dưới.

## Nhãn độ khó

Danh sách cố định. Nguồn sự thật duy nhất: `TAG_CHUAN` trong [normalize_gt.py](normalize_gt.py).
Tag tự do làm việc gom nhóm breakdown mất ý nghĩa (mỗi câu một tag riêng thì không có nhóm nào để so).

| Tag | Nghĩa |
|---|---|
| `easy_sanity_check` | Câu dễ, để phát hiện hệ thống hỏng |
| `small_object` | Đối tượng nhỏ / khuất một phần khung hình |
| `multi_similar_object` | Nhiều đối tượng giống nhau, chỉ khác 1 chi tiết (màu áo, số áo) |
| `multi_object` | Nhiều loại đối tượng cùng lúc trong khung |
| `fine_detail` | Phải nhìn chi tiết nhỏ mới phân biệt được |
| `short_action` | Hành động rất ngắn giữa video dài |
| `action_sequence` | Chuỗi động tác nối tiếp (chủ yếu TRAKE) |
| `temporal_order` | Phụ thuộc thứ tự thời gian ("trước khi X thì Y") |
| `counting` | Đếm số lượng — điểm yếu của vision LLM |
| `naming` | Đòi tên riêng / danh từ định danh cụ thể |
| `text_in_frame` | Phải đọc chữ/số in trong khung (cần OCR) |
| `chart_reading` | Phải đọc biểu đồ/đồ thị |
| `image_in_image` | Ảnh lồng trong ảnh / màn hình TV trong khung |
| `negation` | Câu phủ định/loại trừ ("cảnh không có người") |
| `local_dialect` | Từ địa phương/viết tắt — thử sức `rewrite.py` |

## Schema (format người ghi)

Bọc ngoài: `{"entries": [ ... ]}`. Field chung: `query_id` (duy nhất trong **toàn bộ** bộ eval),
`type` (`KIS`/`QA`/`TRAKE`), `query_text` (tiếng Việt), `difficulty_tags`, `gt_video_id`
(không có `.mp4`).

### KIS

```jsonc
{
  "query_id": "p1-1-kis",
  "type": "KIS",
  "query_text": "Cảnh quay một nhóm hơn 5 người xếp thành hàng tập thể dục...",
  "difficulty_tags": ["multi_similar_object"],
  "gt_video_id": "L21_V001",
  "gt_frame": 532
}
```

### QA

```jsonc
{
  "query_id": "p1-3-qa",
  "type": "QA",
  "query_text": "Hình ảnh một con cá được đặt lên cân...",
  "question": "Con số hiển thị cuối cùng trên cân là bao nhiêu?",
  "difficulty_tags": ["counting", "text_in_frame"],
  "gt_video_id": "L22_V010",
  "gt_frame": 100,
  "gt_answers": ["3", "ba", "three"]
}
```

`gt_answers` là **mảng** các cách diễn đạt chấp nhận được. `score_pipelines.py` chấm theo luật BTC
§2.1.2: đáp án pipeline sinh ra tính đúng nếu (sau chuẩn hoá) **trùng / chứa / là con** của bất kỳ
phần tử nào trong mảng. Ghi rộng tay: `"15"`, `"mười lăm"`, `"15 người"`.

`run_eval.py` **không** đọc field này — nó chỉ đo retrieval.

### TRAKE

```jsonc
{
  "query_id": "p1-4-trake",
  "type": "TRAKE",
  "query_text": "4 cảnh này xảy ra liên tiếp nhau...",
  "difficulty_tags": ["temporal_order", "action_sequence"],
  "gt_video_id": "L25_V003",
  "events": [
    {"text_en": "athlete takes off from the ground", "gt_frame": 95},
    {"text_en": "athlete clears over the bar", "gt_frame": 145},
    {"text_en": "athlete lands on the mat", "gt_frame": 195}
  ]
}
```

> ⚠️ Các khối JSON trên là **VÍ DỤ MINH HOẠ FORMAT**, không phải ground truth thật. Copy cấu trúc
> field, đừng copy giá trị số.

## Chạy thử

Không cần đợi ghi đủ — `--check` chạy được với một câu:

```
.venv\Scripts\python.exe tests\eval\normalize_gt.py <file>.json --check   # kiểm tra format
.venv\Scripts\python.exe tests\eval\run_eval.py                           # so backbone, không LLM
.venv\Scripts\python.exe tests\e2e\score_pipelines.py --types kis         # Final Score thật, 0 đồng
```
