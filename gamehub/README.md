# GameHub

Trang chủ game: ai cũng vào chơi được, chỉ admin mới đăng nhập để thêm/sửa/xóa game.

## Chạy

```bash
pip install -r requirements.txt
python app.py
```

Mở http://localhost:5000

## Tài khoản admin có sẵn

- Tên đăng nhập: `admin`
- Mật khẩu: `Admin@123`

Hãy đổi mật khẩu ngay trong trang Quản trị (mục "Đổi tài khoản admin") trước khi đưa lên mạng.
Muốn đặt mật khẩu ban đầu khác khi chạy lần đầu: `ADMIN_PASSWORD="mat-khau-cua-ban" python app.py`
(chỉ có tác dụng khi chưa có file `data/gamehub.db`).

## Thêm game

Đăng nhập → Quản trị → điền tên, chọn ảnh, rồi tải file `.html` lên hoặc dán code HTML → Thêm game.

## Sao lưu

- Tự động: mỗi lần thêm/sửa/xóa game, lưu vào `data/backups/` (giữ 20 bản mới nhất).
- Thủ công: nút "Tải bản sao lưu (.zip)" và "Khôi phục" trong trang Quản trị.
- Toàn bộ dữ liệu nằm trong thư mục `data/`, chỉ cần copy thư mục này là chuyển được sang máy khác.

## Ghi chú bảo mật

- Game chạy trong iframe sandbox nên không đọc được phiên đăng nhập admin.
  Vì vậy game dùng `localStorage` để lưu điểm sẽ không lưu được (đây là đánh đổi để an toàn).
- Nếu đưa lên internet, nên chạy sau HTTPS (nginx/Caddy) và dùng `gunicorn app:app` thay cho `python app.py`.
