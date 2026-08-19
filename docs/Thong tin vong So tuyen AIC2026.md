# HỘI THI THỬ THÁCH TRÍ TUỆ NHÂN TẠO THÀNH PHỐ HỒ CHÍ MINH NĂM 2026

## 1. Nội dung các truy vấn vòng sơ tuyển

### 1.1. Truy vấn dạng 1: Tìm kiếm chính xác theo văn bản (Textual Known Item Search – Textual KIS)

Đây là nhiệm vụ tìm kiếm sự kiện dựa trên mô tả bằng văn bản.

- **Nội dung truy vấn**: Ban giám khảo cung cấp một mô tả bằng ngôn ngữ tự nhiên về một sự kiện. Các đội dự thi cần định vị chính xác đoạn video chứa sự kiện bằng cách chỉ ra một khung hình bất kỳ thuộc đoạn video đó. Ở vòng sơ tuyển, nội dung đoạn mô tả được cung cấp sẵn và trọn vẹn.
- **Ví dụ**: Truy vấn "Tìm video về một diễn giả mặc áo đỏ phát biểu tại một cuộc họp báo ngoài trời, phía sau có nhiều cây xanh." — Kết quả nộp: `video_id = video_abc(.mp4)`, `frame_id = 1500`.

### 1.2. Truy vấn dạng 2: Truy vấn dạng Hỏi–Đáp (Q&A)

Đây là nhiệm vụ tìm kiếm sự kiện và trích xuất thông tin cụ thể từ video.

- **Nội dung truy vấn**: Ban giám khảo cung cấp một mô tả bằng ngôn ngữ tự nhiên của một sự kiện và một câu hỏi về thông tin trong sự kiện này. Các đội dự thi cần tìm ra chính xác khoảnh khắc liên quan và trả lời câu hỏi. Câu trả lời có thể bằng tiếng Việt hoặc tiếng Anh.
- **Ví dụ**: Truy vấn "Trong video về lễ trao giải thưởng âm nhạc, có bao nhiêu người lên sân khấu để nhận giải thưởng lớn nhất?" — Kết quả nộp: `video_id = video_xyz(.mp4)`, `frame_id = 3450`, `answer = "5"` hoặc `"Năm"`.

### 1.3. Truy vấn dạng 3: Truy xuất và căn chỉnh sự kiện video theo thời gian (Temporal Retrieval and Alignment of Key Events – TRAKE)

Đây là một nhiệm vụ phức hợp đòi hỏi độ chính xác cao trong cả việc truy xuất video và căn chỉnh thời gian của các khoảnh khắc quan trọng.

TRAKE nhằm đánh giá khả năng của một hệ thống trong việc hiểu sâu sắc nội dung video một cách toàn diện, từ bối cảnh chung cho đến từng khoảnh khắc chi tiết. Nhiệm vụ yêu cầu hệ thống không chỉ tìm kiếm một video phù hợp từ một kho dữ liệu lớn mà còn phải xác định chính xác các khoảnh khắc ngữ nghĩa (semantic keyframe) của một chuỗi sự kiện có cấu trúc bên trong video đó. Nhiệm vụ được chia thành hai giai đoạn:

- **Giai đoạn 1 – Truy xuất (Retrieval)**: Từ một thư viện video lớn, tìm ra một video duy nhất chứa chuỗi sự kiện khớp nhất với truy vấn.
- **Giai đoạn 2 – Căn chỉnh (Alignment)**: Đối với video đã truy xuất, xác định chính xác một khung hình (semantic keyframe) duy nhất cho mỗi giai đoạn của chuỗi sự kiện.

> **Lưu ý**: "Khung hình ngữ nghĩa" (semantic keyframe) trong truy vấn này là khoảnh khắc mang ý nghĩa về nội dung, khác với "I-Frame" là khung hình kỹ thuật trong các thuật toán nén video đã được cung cấp cho các đội thi.

**Ví dụ – hành động "Nhảy cao"**: chuỗi sự kiện gồm 4 khoảnh khắc:

1. **Event 1 – Chạy đà (Approach)**: khoảnh khắc bàn chân đầu tiên chạm đất và bước qua khỏi vạch xuất phát.
2. **Event 2 – Giậm nhảy (Take-off)**: khoảnh khắc đầu tiên bàn chân của chân giậm nhảy rời hoàn toàn khỏi mặt đất.
3. **Event 3 – Bay qua xà (Clearance)**: khoảnh khắc phần hông của vận động viên ở vị trí cao nhất so với xà ngang.
4. **Event 4 – Tiếp đất (Landing)**: khoảnh khắc đầu tiên bất kỳ bộ phận nào của lưng (từ vai đến hông) bắt đầu chạm vào đệm.

## 2. Phương pháp đánh giá vòng sơ tuyển

Đối với mỗi truy vấn, đội thi được gửi tối đa 100 câu trả lời. Mỗi câu trả lời sẽ được chấm một điểm gọi là **Điểm Tương Quan (R-Score)** — thang đo độ chính xác nhận giá trị từ 0 đến 1 (1: hoàn toàn chính xác; 0: không chính xác; giá trị trung gian, ví dụ 0.7: chính xác một phần). Điểm cuối cùng cho mỗi truy vấn (**Final Score**, mục 2.2) không chỉ dựa trên một câu trả lời duy nhất, mà là trung bình của những câu trả lời tốt nhất ở nhiều vị trí xếp hạng khác nhau.

### 2.1. Điểm Tương Quan (R-Score)

Cách tính R-Score khác nhau tùy theo từng loại truy vấn:

#### 2.1.1. Truy vấn Textual KIS

- **Định dạng trả lời** ($r_i$): `<video_id>, <frame_id>`
- **Điều kiện**: câu trả lời được xem là chính xác nếu khớp video ($v_i = GT_v$) và frame_id nằm trong khoảng đáp án đúng ($id_i \in [s, e]$).

$$
R\text{-}Score(r_i) = \mathbb{I}(v_i = GT_v \ \land\ id_i \in [s, e])
$$

Trong đó $\mathbb{I}(\cdot)$ là hàm chỉ thị, trả về 1 nếu điều kiện đúng và 0 nếu sai.

- **Ví dụ**: câu hỏi "Tìm cảnh một người đang mở laptop trong kho video." Đáp án đúng của BTC: video `L01_V001`, khung hình từ 500 đến 510.
  - `L01_V001, 505` → Đúng! R-Score = 1.
  - `L01_V001, 600` → Sai! Khung hình không nằm trong khoảng cho phép. R-Score = 0.
  - `L02_V003, 505` → Sai! Sai video. R-Score = 0.

#### 2.1.2. Truy vấn Q&A (Visual Question Answering)

- **Định dạng trả lời** ($r_i$): `<video_id>, <frame_id>, <answer>`
- **Điều kiện**: câu trả lời được xem là chính xác nếu khớp video ($v_i = GT_v$), frame_id nằm trong khoảng đáp án đúng ($id_i \in [s, e]$), và answer khớp với đáp án về mặt ngữ nghĩa ($a_i = GT_a$).

$$
R\text{-}Score(r_i) = \mathbb{I}(v_i = GT_v \ \land\ id_i \in [s, e] \ \land\ a_i = GT_a)
$$

- **Ví dụ**: câu hỏi "Trong video quay cảnh bữa tiệc, người phụ nữ mặc váy đỏ đang cầm ly màu gì?" Đáp án đúng của BTC: video `L05_V005`, khung hình 800 đến 900, answer là "màu xanh".
  - `L05_V005, 888, màu xanh` → Hoàn hảo! R-Score = 1.
  - `L05_V005, 888, màu trắng` → Sai answer. R-Score = 0.
  - `L06_V007, 888, màu xanh` → Sai video. R-Score = 0.

#### 2.1.3. Truy vấn TRAKE (Temporal-alignment)

- **Định dạng trả lời** ($r_i$): `<video_id>, <frame_id₁>, ..., <frame_idₙ>`
- **Điều kiện tiên quyết**: nếu video_id nộp không khớp với đáp án ($v_i \neq GT_v$), truy vấn nhận 0 điểm ngay lập tức. Nếu đúng video, điểm được tính bằng tỉ lệ khung hình khớp với đáp án; N là tổng số khoảnh khắc trong truy vấn.

$$
R\text{-}Score(r_i) =
\begin{cases}
\dfrac{1}{N}\displaystyle\sum_{j=1}^{N} \mathbb{I}\big(id_{i,j} \in [s_j, e_j]\big) & \text{nếu } v_i = GT_v \\[2mm]
0 & \text{nếu } v_i \neq GT_v
\end{cases}
$$

Với mỗi khoảnh khắc thứ j trong chuỗi sự kiện, đáp án quy định một đoạn khung hình $[s_j, e_j]$ tương ứng với khoảnh khắc ngữ nghĩa đó — cùng nguyên tắc xác định đoạn $[s, e]$ như ở truy vấn Textual KIS và Q&A. Lưu ý là đoạn ứng với khoảnh khắc ngữ nghĩa này thường rất ngắn, thông thường là dưới 10 frame. Một khung hình nộp ($id_{i,j}$) được coi là khớp nếu nằm trong đoạn $[s_j, e_j]$ này.

- **Ví dụ**: câu hỏi "Tìm 4 khoảnh khắc chính khi vận động viên thực hiện cú nhảy: (1) giậm nhảy, (2) bay qua xà, (3) tiếp đất, (4) đứng dậy." Đáp án đúng của BTC: video `L10_V010`, mỗi khoảnh khắc được xác định bằng một đoạn khung hình:
  - Khoảnh khắc 1 (giậm nhảy): đáp án trong đoạn [95, 105].
  - Khoảnh khắc 2 (bay qua xà): đáp án trong đoạn [145, 155].
  - Khoảnh khắc 3 (tiếp đất): đáp án trong đoạn [195, 205].
  - Khoảnh khắc 4 (đứng dậy): đáp án trong đoạn [245, 255].
- **Câu trả lời của đội thi**: `L10_V010, 101, 156, 203, 251`
  - Video: đúng `L10_V010`.
  - Khoảnh khắc 1: $101 \in [95, 105]$ → Đúng.
  - Khoảnh khắc 2: $156 \notin [145, 155]$ → Sai.
  - Khoảnh khắc 3: $203 \in [195, 205]$ → Đúng.
  - Khoảnh khắc 4: $251 \in [245, 255]$ → Đúng.
  - Kết quả: khớp 3 trên 4 khoảnh khắc → R-Score = 3/4 = 0.75.

### 2.2. Điểm Cuối Cùng (Final Score)

Điểm Cuối Cùng được tính dựa trên những câu trả lời tốt nhất của đội thi ở các mốc xếp hạng (top) khác nhau. Với mỗi ngưỡng $k \in \{1, 5, 20, 50, 100\}$, hệ thống xác định Top-k R-Score ($R@k$): điểm R-Score cao nhất trong k câu trả lời đầu tiên.

$$
R@k = \max_{1 \le i \le k} \{R\text{-}Score(r_i)\}
$$

Điểm Cuối Cùng là trung bình cộng của 5 giá trị $R@k$ nói trên:

$$
Final\ Score = \frac{1}{5} \sum_{k \in \{1,5,20,50,100\}} R@k
$$

- **Ví dụ**: đội thi nộp 100 câu trả lời cho một truy vấn. Câu trả lời đầu tiên có R-Score = 0.5; câu trả lời ở vị trí số 3 có R-Score = 0.8 (cao nhất trong 100z câu); câu trả lời ở vị trí số 15 có R-Score = 0.6; các câu trả lời còn lại thấp hơn.
  - Top 1 = 0.5 (câu trả lời đầu tiên).
  - Top 5 = Top 20 = Top 50 = Top 100 = 0.8 (câu số 3 vẫn là cao nhất trong mọi ngưỡng từ 5 trở lên).
  - Final Score = (0.5 + 0.8 + 0.8 + 0.8 + 0.8) / 5 = **0.74 điểm**.

Cách tính điểm này khuyến khích đội thi không chỉ tìm ra một câu trả lời đúng, mà còn phải xếp nó ở những vị trí đầu tiên trong danh sách trả lời của mình!

## 3. Thông tin dữ liệu vòng sơ tuyển – Đợt 1

Dữ liệu cung cấp cho các đội thi để làm quen với bài toán là một phần dữ liệu từ cuộc thi AIC 2026, gồm các thành phần sau:

- **Videos**: Chứa video được cung cấp.
- **Keyframes**: Chứa tất cả keyframe được trích xuất từ video được cung cấp ở trên. Keyframe được lưu trong thư mục tương ứng với tên file video — ví dụ, các keyframe của video `L01_V001.mp4` được lưu trong thư mục `L01_V001`. Tên các file keyframe được đặt theo thứ tự tăng dần; vị trí (frame index) tương ứng của mỗi keyframe được ghi trong file metadata.
- **Objects**: Chứa file JSON liệt kê tất cả vật thể (object) phát hiện được từ mô hình Faster R-CNN pretrained trên OpenImages V4. Chi tiết định dạng kết quả phát hiện vật thể có thể xem ví dụ tại hướng dẫn của TensorFlow. Tên file JSON tương ứng với tên file keyframe — ví dụ, keyframe `L01_V001/0000.jpg` sẽ có file JSON chứa thông tin object là `L01_V001/0000.json`.
- **CLIP features**: Chứa CLIP features (trích xuất từ mô hình `clip-ViT-B-32`) của tất cả các khung hình trong thư mục Keyframes. Toàn bộ CLIP features của các keyframe được lưu trong một file `.npy` duy nhất, với thứ tự các vector feature tăng dần tương ứng với chỉ số của keyframe.
- **Metadata**: Thông tin metadata của video được lấy từ YouTube của kênh cung cấp dữ liệu. Metadata của mỗi video là một file JSON có tên tương ứng với tên file video — ví dụ, video `L01_V001.mp4` sẽ có file metadata là `L01_V001.json`. Một số video trong dữ liệu cung cấp có thể không có file metadata tương ứng.

**Download dữ liệu tại link**: https://docs.google.com/spreadsheets/d/1rfn1fieTThS_Ki3SIoJ6uXOx2AhMq7wGCak6W4jZyZM/edit?usp=sharing

**Lưu ý**:

- Dữ liệu thi chính thức là Video; các thành phần còn lại (Keyframes, Objects, CLIP features, Metadata) chỉ nhằm mục đích cung cấp thêm thông tin hoặc hỗ trợ xây dựng giải pháp mẫu cho thí sinh.
- Đây cũng là dữ liệu batch 1 của AIC 2025. Dữ liệu đầy đủ của vòng sơ tuyển AIC 2026 sẽ bao gồm thêm dữ liệu batch 2, dự kiến được thông báo cho các đội thi trong thời gian tới.

## 4. Hướng dẫn nộp bài sơ tuyển (BTC công bố 2026-08-20)

> Nguồn: tài liệu "Hướng dẫn nộp bài sơ tuyển" chính thức của BTC. §1/§2 ở trên định nghĩa NỘI
> DUNG truy vấn và cách TÍNH ĐIỂM; mục này định nghĩa QUY TRÌNH và ĐỊNH DẠNG file nộp thực tế —
> đây là tài liệu tham chiếu chính cho `scripts/submit/build_submission.py` và
> `scripts/submit/validate_submission.py`.

### 4.1. Gói truy vấn

BTC cung cấp truy vấn theo nhiều đợt, mỗi đợt là 1 gói gồm nhiều file `.txt`, tên file quy ước
theo hậu tố loại truy vấn:

- Hậu tố `-kis` → Textual KIS
- Hậu tố `-qa` → Q&A
- Hậu tố `-trake` → TRAKE

Ví dụ đợt 1: `query-1-kis.txt`, `query-2-kis.txt`, `query-3-qa.txt`, `query-4-trake.txt`.

**Quan trọng**: file CSV nộp lại phải **giữ nguyên tên gốc**, chỉ đổi đuôi `.txt` → `.csv` (ví dụ
`query-1-kis.txt` → `query-1-kis.csv`). Đây là cách hệ thống BTC khớp file nộp với truy vấn tương
ứng — sai tên file gần như chắc chắn nghĩa là truy vấn đó không được chấm.

### 4.2. Định dạng từng dòng CSV theo loại truy vấn

Tối đa **100 dòng/file** (không tính header — **không có header row**, dòng đầu tiên đã là dữ liệu).

**Textual KIS** — `<video_id>, <frame_idx>`:

```
L00_V000,1234
L00_V055,5555
L01_V028,25300
```

**Q&A** — `<video_id>, <frame_idx>, <answer>`:

```
L01_V028,3450,5
L02_V011,1200,Năm người
L03_V005,2800,"Màu đỏ, rất đẹp"
L04_V012,4100,"Anh ấy nói ""Tuyệt vời"""
```

- `answer` tối đa **100 ký tự**, tiếng Việt hoặc tiếng Anh, so khớp theo ngữ nghĩa.
- Ngoặc kép quanh `answer` chỉ **bắt buộc** khi answer chứa dấu phẩy, dấu ngoặc kép, hoặc xuống
  dòng (dấu ngoặc kép bên trong answer phải escape bằng cách nhân đôi: `""`). Answer đơn giản
  không cần ngoặc kép, nhưng bọc ngoặc kép cho TẤT CẢ answer cũng được chấp nhận.

**TRAKE** — `<video_id>, <frame_id_1>, ..., <frame_id_N>` (mỗi dòng là 1 phương án dự đoán TRỌN
VẸN cho cả chuỗi N sự kiện — không phải 1 dòng/event):

```
L10_V001,1200,1850,2100,2450
L10_V001,1180,1820,2080,2420
L11_V003,5100,5700,6200,6800
```

- Số lượng frame_id trên mỗi dòng phải khớp đúng số event N của truy vấn.
- Thứ tự frame_id phải theo đúng thứ tự thời gian của các event.

### 4.3. Quy tắc CSV chung

- Encoding: UTF-8. Delimiter: dấu phẩy. Line ending: CRLF hoặc LF đều được.
- **Không có header row.**
- `video_id`: không kèm đuôi `.mp4`.
- `frame_id`/`frame_idx`: số nguyên, so sánh dưới dạng số nguyên (không khoảng trắng thừa).
- **File phải là `.csv` thật** (text thuần, mở bằng Notepad đọc được) — không phải `.xlsx`/`.xls`
  đổi đuôi. BTC nhấn mạnh đây là lỗi rất phổ biến khi xuất file từ Excel/Google Sheets.

### 4.4. Cấu trúc file ZIP nộp bài

**Bắt buộc** có 1 thư mục tên `submission/` bên trong ZIP chứa toàn bộ CSV — **không được nén
trực tiếp các file CSV vào gốc ZIP**:

```
submission/
├── query-1-kis.csv
├── query-2-kis.csv
├── query-3-qa.csv
└── query-4-trake.csv
```

Tên file zip tùy chọn (khuyến nghị chỉ dùng chữ/số, ví dụ `team_ABC_round1.zip`), nhưng cấu trúc
thư mục `submission/` bên trong là bắt buộc.

### 4.5. Quy trình nộp & tính điểm

- Đăng nhập bằng tài khoản BTC đã cấp, nộp file `.zip` trực tiếp trên hệ thống thi — không đăng ký
  thêm ở đâu khác.
- **Tối đa 3 lần nộp cho mỗi gói truy vấn**; kết quả dùng để xếp hạng là **lần nộp CUỐI CÙNG**
  (không phải điểm cao nhất trong 3 lần).
- **Nộp sai định dạng vẫn tính là 1 lần nộp** — không được hoàn lại lượt.
- **Public Leaderboard chỉ tính trên 50% đáp án của BTC** (điểm hiển thị lúc thi có nhiễu).
  **Private Leaderboard** (kết quả xếp hạng thật của vòng sơ tuyển) tính trên **100% đáp án**, dựa
  trên lần nộp cuối cùng.
- Mỗi đội chỉ dùng 1 tài khoản duy nhất để nộp.

### 4.6. Checklist trước khi nộp

- [ ] File có đuôi `.csv` thật (mở bằng Notepad thấy text thuần, không phải `.xlsx`/`.xls`)
- [ ] Tên file khớp đúng tên truy vấn gốc BTC cấp (`query-N-kis/qa/trake.csv`)
- [ ] Không có header row
- [ ] `video_id` không có `.mp4`
- [ ] Q&A: answer ≤ 100 ký tự
- [ ] TRAKE: đúng số frame_id theo N event, đúng thứ tự thời gian
- [ ] ZIP chứa thư mục `submission/` (không nén CSV trực tiếp vào gốc ZIP)
- [ ] Đã chạy `scripts/submit/validate_submission.py` và PASS trước khi nộp thật

## 5. Lịch trình các vòng thi (cập nhật 2026-08-20 — trạng thái "Nháp", có thể còn thay đổi)

| Vòng              | Mở                   | Đóng                | Trạng thái    |
| ------------------ | --------------------- | --------------------- | --------------- |
| Vòng thử nghiệm | 08:00 Ngày 20/8/2026 | 19:30 Ngày 21/8/2026 | Nháp           |
| Sơ tuyển đợt 1 | 19:30 Ngày 21/8/2026 | 22:30 Ngày 21/8/2026 | Nháp           |
| Sơ tuyển đợt 2 | 19:30 Ngày 28/8/2026 | 22:30 Ngày 28/8/2026 | Nháp           |
| Sơ tuyển đợt 3 | 19:30 Ngày 04/9/2026 | 22:30 Ngày 04/9/2026 | Nháp nếu cần |

**Lưu ý quan trọng**:

- Mỗi đợt sơ tuyển thật chỉ mở **3 tiếng** (19:30–22:30), không phải cả ngày. Thao tác chậm/lúng
  túng trong 3 tiếng này mất điểm trực tiếp, không có bù giờ.
- **Vòng thử nghiệm đóng đúng lúc Sơ tuyển đợt 1 mở** (cùng mốc 19:30 21/8/2026) — nghĩa là toàn bộ
  thời gian từ 08:00 20/8 đến 19:30 21/8 là cơ hội DUY NHẤT để tập dượt luồng thao tác thật (search
  → rà soát → sửa tay → add to queue → export → nộp thử) trước khi vòng tính điểm đầu tiên mở ngay
  sau đó, không có khoảng đệm.
- Trạng thái cả bảng đang là "Nháp" — cần xác nhận lại với BTC/hệ thống thi trước khi coi là lịch
  chính thức không đổi.
