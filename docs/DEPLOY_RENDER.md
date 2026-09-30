# Triển khai VinaLex miễn phí trên Render

Dự án dùng một Render Blueprint gồm:

- `vinalex`: frontend Next.js được static export và phục vụ qua CDN.
- `vinalex-backend`: API FastAPI chạy tại Singapore trên gói Free.

## Triển khai

1. Đẩy nhánh cần triển khai lên GitHub.
2. Mở `https://dashboard.render.com/blueprints` và chọn **New Blueprint Instance**.
3. Kết nối repository VinaLex. Render tự đọc `render.yaml` ở thư mục gốc.
4. Khi được hỏi biến bí mật, nhập:
   - `ADMIN_SECRET_KEY`: một chuỗi bí mật dài, không dùng giá trị mặc định trong mã nguồn.
   - `GEMINI_API_KEY`: khóa Gemini của dự án.
5. Chọn **Deploy Blueprint**. Chờ cả `vinalex-backend` và `vinalex` có trạng thái **Live**.
6. Mở URL frontend hiển thị trong Dashboard và kiểm tra các luồng ở phần dưới.

Không đưa nội dung `.env` vào Git hoặc dán khóa bí mật vào `render.yaml`.

## Kiểm tra sau triển khai

- Trang chủ và danh sách thủ tục mở được.
- `https://<backend>.onrender.com/api/v1/health` trả về `{"status":"ok"}`.
- Tìm kiếm và mở chi tiết một thủ tục.
- Tra cứu địa điểm hành chính.
- Gửi một câu hỏi ở Trợ lý AI.
- Xem trước và tải một biểu mẫu PDF chuẩn.
- Đăng ký, đăng nhập và kiểm tra trang Hồ sơ.

## Giới hạn bắt buộc của gói miễn phí

- Backend ngủ sau 15 phút không có truy cập; yêu cầu đầu tiên sau đó có thể chờ khoảng một phút.
- Filesystem của backend là tạm thời. Dữ liệu tham chiếu SQLite được khôi phục từ Git ở mỗi lần deploy, nhưng tài khoản hoặc thay đổi quản trị tạo trong lúc chạy không được bảo đảm lưu bền sau restart/redeploy.
- Kho PDF cào tự động trong `data/pdf_storage/procedures` có dung lượng khoảng 1,7 GB và không nằm trong Git. Bản miễn phí chỉ phục vụ các biểu mẫu chuẩn đã được theo dõi trong `data/pdf_storage/statutory_forms`.

Muốn lưu bền tài khoản và thay đổi quản trị, cấu hình PostgreSQL bên ngoài có lưu trữ lâu dài rồi đặt `FORCE_POSTGRES=true` và `SQLALCHEMY_DATABASE_URI` trong Render Dashboard.
