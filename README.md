# Football data analyst

Công cụ lấy thống kê đường chuyền của một cầu thủ trên SofaScore, tính độ dài chuyền, rồi vẽ hướng chuyền trên nửa sân đối phương.

## Chuẩn bị

Cần Python 3.12 và Google Chrome cài tại `C:\Program Files\Google\Chrome\Application\chrome.exe`.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Luồng thực hiện

1. **Cào dữ liệu** bằng `services/crawl-raw-data.py`. Script mở Chrome, vào SofaScore, lấy danh sách trận trong một giải, rồi lưu thống kê từng trận thành file JSON.
2. **Tính độ dài chuyền** bằng `services/distance-pass-player.py` trên một folder trong `output`.
3. **Vẽ bản đồ hướng chuyền** bằng `services/pass-hard.py`. Ảnh nằm trong `img/map`.

`output/` và `img/` không được đưa vào git.

## 1. Cào dữ liệu

Sửa các hằng ở đầu `services/crawl-raw-data.py`:

| Hằng | Ý nghĩa |
|---|---|
| `PLAYER_ID` | Id cầu thủ trên SofaScore. Florian Wirtz là `1019322`. |
| `UNIQUE_TOURNAMENT_ID` | Id giải. `17` Premier League, `16` World Cup 2026, `10783` Nations League. |
| `MATCH_LIMIT` | Số trận có thống kê cần lưu. Lấy từ trận mới nhất. Nếu giải không đủ trận, script lưu phần còn lại và chạy tiếp. |
| `OUTPUT_DIR` | Thư mục JSON đầu ra. Mỗi trận một file, tên theo dạng `Đội nhà vs Đội khách.json`. |

```powershell
.\.venv\Scripts\python.exe services\crawl-raw-data.py
```

Chrome sẽ mở một cửa sổ riêng (không dùng profile Chrome đang dùng hằng ngày). Nếu SofaScore hiện captcha, xác nhận trên cửa sổ đó. Cửa sổ tự đóng khi xong.

Trận chưa có rating breakdown bị bỏ qua. Muốn cào giải khác thì đổi `UNIQUE_TOURNAMENT_ID` và `OUTPUT_DIR`, rồi chạy lại.

## 2. Độ dài đường chuyền

Sửa đầu `services/distance-pass-player.py`:

| Hằng | Ý nghĩa |
|---|---|
| `DATA_DIR` | Một folder trong `output`. Mỗi lần chạy chỉ tính folder đó. |
| `MATCH_LIMIT` | Số file JSON đầu tiên theo tên. `None` để lấy hết. |

```powershell
.\.venv\Scripts\python.exe services\distance-pass-player.py
```

Script in, cho từng trận và cho cả folder:

- tổng độ dài
- tổng số đường chuyền
- số đường chuyền trung bình mỗi trận
- độ dài trung bình mọi đường chuyền
- số đường chuyền thành công (`outcome = true`) và độ dài trung bình của nhóm đó

Đường chuyền dài (`isLongBall = true`) bị loại khỏi phép tính này. Độ dài là khoảng cách Euclid trên tọa độ SofaScore (thang 0–100), không phải mét trên sân thật.

## 3. Bản đồ hướng chuyền

Sửa đầu `services/pass-hard.py`:

| Hằng | Ý nghĩa |
|---|---|
| `DATA_DIRS` | Một hoặc nhiều folder trong `output`. Nhiều folder được gộp chung một bản đồ. |
| `MATCH_LIMIT` | Số trận lấy từ mỗi folder. `None` để lấy hết. |
| `MIN_VECTOR_COUNT` | Hướng nào ít hơn ngưỡng này thì không vẽ. |
| `OPPONENT_HALF_MIN_X` | Nửa sân đối phương bắt đầu từ `x > 50`. |
| `REQUIRE_UPWARD` | `True` thì chỉ giữ đường chuyền đi lên phía khung thành đối phương. |

```powershell
.\.venv\Scripts\python.exe services\pass-hard.py
```

Ảnh lưu tại `img/map`. Một folder thì tên file trùng tên folder. Nhiều folder thì tên được ghép, ví dụ `wc + nation-league + international.png`.

Chỉ tính đường chuyền xuất phát ở nửa sân đối phương và đi lên (`x` tăng về phía khung thành). Trong mỗi vùng sân, script giữ hướng xuất hiện nhiều nhất rồi vẽ một mũi tên.

Trên mũi tên, ba số theo thứ tự:

- trắng: số đường chuyền
- vàng: tỉ lệ thành công
- xanh nhạt: độ dài trung bình

Mũi tên xanh lá là chuyền ngắn. Mũi tên xanh dương là chuyền dài (`isLongBall = true`).

Vùng sân:

- chiều sâu: giữa sân đối phương, 1/3 sân cuối, vùng cấm
- chiều ngang: hành lang trái, trung lộ, hành lang phải

Terminal vẫn in đủ số liệu từng loại chuyền và từng zone, kể cả khi ảnh chỉ thể hiện hướng nổi bật.
