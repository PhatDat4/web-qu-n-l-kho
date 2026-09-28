# WMS Web - Hệ thống quản lý kho hàng

Phiên bản web của chương trình WMS, dùng Flask + SQLite. Cùng cấu trúc
dữ liệu với bản CLI trước đó (`warehouse.db`), nên nếu bạn có sẵn file
`warehouse.db` từ bản CLI, chỉ cần copy vào cùng thư mục với `app.py`
là dữ liệu cũ sẽ hiện lên luôn.

## Cài đặt

Yêu cầu: Python 3.9+ (khuyến nghị 3.10+)

```bash
# 1. Tạo môi trường ảo (khuyến nghị, để không ảnh hưởng Python hệ thống)
python3 -m venv venv

# Kích hoạt môi trường ảo
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (cmd):
venv\Scripts\activate.bat
# macOS / Linux:
source venv/bin/activate

# 2. Cài thư viện
pip install -r requirements.txt

## Chạy chương trình

```bash
python3 app.py
```

Mở trình duyệt tại: **http://127.0.0.1:5000**

Nhấn `Ctrl+C` trong terminal để dừng server.

## Cấu trúc thư mục

```
wms_web/
├── app.py               # Flask backend, toàn bộ route
├── requirements.txt
├── warehouse.db          # Tự tạo khi chạy lần đầu (SQLite)
├── templates/             # Giao diện HTML (Jinja2)
│   ├── base.html
│   ├── inventory.html
│   ├── product_form.html
│   ├── stock_form.html
│   ├── low_stock.html
│   └── history.html
└── static/
    └── style.css
```

## Chức năng

- Trang chủ: xem tồn kho, tìm kiếm theo SKU/tên, thống kê nhanh
- Thêm / sửa / xóa sản phẩm
- Nhập kho / xuất kho (tự kiểm tra không cho xuất quá tồn kho)
- Cảnh báo sản phẩm dưới ngưỡng tối thiểu
- Lịch sử giao dịch, lọc theo SKU

## Chạy ổn định / triển khai thật (khi cần)

Chế độ `app.run(debug=True)` chỉ dùng để phát triển/thử nghiệm ở máy cá nhân.
Nếu muốn nhiều người trong công ty cùng truy cập hoặc chạy lâu dài, nên:

1. Tắt `debug=True` trong `app.py`, đặt biến môi trường `WMS_SECRET_KEY`
   riêng thay vì dùng giá trị mặc định.
2. Dùng một WSGI server thật thay vì server phát triển của Flask, ví dụ:

   ```bash
   pip install gunicorn   # Linux/macOS
   gunicorn -w 2 -b 0.0.0.0:5000 app:app
   ```

   Trên Windows có thể dùng `waitress`:

   ```bash
   pip install waitress
   waitress-serve --port=5000 app:app
   ```

3. Nếu cần truy cập từ máy khác trong cùng mạng LAN, chạy với
   `host="0.0.0.0"` và mở port 5000 trên tường lửa.
4. Cân nhắc backup định kỳ file `warehouse.db`.
