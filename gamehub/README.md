# GameHub – Hướng dẫn thêm game

GameHub gồm **2 phần**:

| Phần | Chạy ở đâu | Dùng để làm gì |
|---|---|---|
| **Trang quản lý** (`app.py`) | Trên máy của bạn (`localhost:5000`) | Đăng nhập, thêm / sửa / xóa game, sao lưu |
| **Web công khai** (thư mục `site`) | Netlify (`2cc.netlify.app`, tên miền riêng nếu đã gắn) | Người chơi vào chọn game và chơi |

Netlify chỉ chứa web tĩnh nên **không có đăng nhập và không thêm game trên web được**.
Mỗi lần thêm game, bạn làm trên máy rồi *xuất* ra thư mục `site` và đưa lên.

---

## 1. Thêm game mới (tóm tắt)

1. Chạy trang quản lý → đăng nhập → thêm game.
2. Chạy `python export_static.py` để tạo lại thư mục `site`.
3. Tải thư mục `site` mới lên GitHub (vào trong thư mục `gamehub`).
4. Netlify tự đăng lại sau vài chục giây → mở web, nhấn **Ctrl+F5**.

Chi tiết từng bước ở dưới.

---

## 2. Thêm game ở trang quản lý

### Chuẩn bị
- **File game**: một file `.html` chạy được độc lập (hoặc copy toàn bộ code HTML).
- **Logo**: ảnh **vuông 1:1**, khuyên dùng 512×512.
- **Ảnh intro**: ảnh **ngang 16:9**, khuyên dùng 1280×720 (ảnh sai tỉ lệ sẽ được tự cắt giữa).
- Định dạng ảnh: png, jpg, gif hoặc webp.

### Các bước
1. Mở terminal trong thư mục `gamehub`, chạy:
   ```
   python app.py
   ```
2. Mở trình duyệt vào **http://localhost:5000/login** và đăng nhập.
3. Ở trang **Quản trị**, mục **Thêm game mới**:
   - **Tên game** (bắt buộc), **Mô tả ngắn**.
   - **Hướng chơi**: *Tự do* / *Chỉ ngang* (khung 16:9) / *Chỉ dọc* (khung 9:16).
   - **Logo** và **Ảnh intro**.
   - **File game (.html)** *hoặc* dán code HTML vào ô bên cạnh (nếu chọn file thì file được ưu tiên).
   - **Thể loại**: chọn **tối đa 3**.
   - **🔥 Đánh dấu game HOT**: tích ô này để thẻ game có huy hiệu HOT và hiện trong bộ lọc "🔥 Hot".
   - **Vị trí trong "🏆 Top game được yêu thích"**: nhập số 1–5 để game vào mục Top ở đầu trang chủ (1 = hạng nhất).
     Để trống thì game không vào Top. Web chạy trên Netlify không đếm được lượt thích của người xem,
     nên thứ hạng Top do bạn tự xếp.
4. Bấm **Thêm game**, rồi bấm **Chơi** ở danh sách để thử ngay trên `localhost`.

### Mẹo để game chạy tốt
- Thêm `<meta charset="utf-8">` vào phần `<head>` của game, nếu không chữ tiếng Việt có thể bị vỡ.
- Cho game co giãn theo khung: dùng `width:100%; height:100%` hoặc đơn vị `vw / vh`, và thẻ
  `<meta name="viewport" content="width=device-width, initial-scale=1">`.
- Game chạy trong khung cách ly (sandbox) để an toàn, nên **`localStorage` / cookie có thể không dùng được**.
  Game lưu điểm bằng `localStorage` nên bọc trong `try { ... } catch (e) {}` để không bị lỗi.
- Game chỉ dùng file `.html` đơn lẻ. Ảnh / âm thanh nên nhúng thẳng vào file (base64) hoặc dùng đường dẫn tuyệt đối trên mạng.

---

## 3. Sửa hoặc xóa game

- **Sửa**: ở danh sách game bấm **Sửa**, đổi thông tin rồi **Lưu thay đổi**.
  Để trống ô logo / ảnh / file game thì giữ nguyên bản cũ.
- **Xóa**: bấm **Xóa**. Hệ thống tự sao lưu trước khi xóa.

---

## 4. Đưa lên web (Netlify)

### Bước 1 – Xuất web tĩnh
Dừng `app.py` (Ctrl+C) hoặc mở terminal khác, trong thư mục `gamehub` chạy:
```
python export_static.py
```
Lệnh này tạo lại thư mục **`site`** (có `index.html` ở gốc).

### Bước 2 – Tải lên GitHub
1. Mở repo trên GitHub, bấm vào thư mục **`gamehub`**.
2. Bấm **Add file → Upload files**.
3. Kéo **cả thư mục `site`** từ máy vào (kéo thư mục, không kéo từng file) → **Commit changes**.

> Repo cần có file `netlify.toml` ở thư mục gốc với nội dung:
> ```
> [build]
>   publish = "gamehub/site"
> ```
> File này làm Netlify chỉ đăng thư mục `gamehub/site`.

### Bước 3 – Kiểm tra
Netlify tự đăng lại sau vài chục giây. Mở web và nhấn **Ctrl+F5**.
Vào **Deploys** trên Netlify để xem trạng thái (Published là thành công).

### Khi xóa game
Trang chủ sẽ không còn hiện game đó. Muốn xóa hẳn file trên GitHub, vào `gamehub/site/play/<mã game>` và `gamehub/site/raw/<mã game>.html` để xóa.

---

## 5. Sao lưu

- Trang quản lý tự sao lưu mỗi lần thêm / sửa / xóa, lưu trong `data/backups` (giữ 20 bản gần nhất).
- Mục **Sao lưu** có nút **Tải bản sao lưu (.zip)** để lưu về chỗ khác và **Khôi phục** từ file `.zip`.
- Toàn bộ dữ liệu của bạn nằm trong thư mục **`data`**. Hãy copy thư mục này đi nơi khác thỉnh thoảng.

---

## 6. Gặp lỗi?

| Hiện tượng | Nguyên nhân / cách xử lý |
|---|---|
| Web báo **Page not found** | Netlify không thấy `index.html` ở gốc. Kiểm tra repo có `netlify.toml` và có `gamehub/site/index.html`. |
| Game mới không hiện | Chưa chạy `export_static.py`, chưa tải `site` lên, hoặc cần nhấn Ctrl+F5. |
| Chữ tiếng Việt trong game bị vỡ | Thêm `<meta charset="utf-8">` vào game rồi xuất lại. |
| PowerShell báo lỗi với dấu `<` | PowerShell không hỗ trợ `lệnh < file`. Dùng cách khác hoặc sửa file bằng tay trong VS Code. |
| `python app.py` báo cổng bận | Đang có một `app.py` khác chạy. Tắt nó (Ctrl+C) rồi chạy lại. |
| Quên mật khẩu admin | Liên hệ người hỗ trợ code để đặt lại. Đừng xóa `data/gamehub.db` vì sẽ mất danh sách game. |

---

## 7. Bảo mật

- **Đổi mật khẩu admin** trong trang Quản trị, mục *Đổi tài khoản admin*.
- **Không đưa thư mục `data` lên GitHub hay Netlify** (có database và khóa phiên đăng nhập).
  Chỉ đăng thư mục `site`.
- Nên để repo GitHub ở chế độ **Private**.

---

## 8. Gắn tên miền riêng (tham khảo)

Trong Netlify: **Domain management → thêm tên miền**. Rồi ở nơi quản lý DNS của tên miền thêm:

| Loại | Tên | Giá trị |
|---|---|---|
| CNAME | `www` | địa chỉ `ten-site.netlify.app` mà Netlify hiển thị |
| A | `@` | `75.2.60.5` (theo tài liệu Netlify) |

Netlify khuyên dùng `www.tenmien` làm địa chỉ chính khi dùng DNS bên ngoài. Bản ghi có thể mất đến một ngày để có hiệu lực.
