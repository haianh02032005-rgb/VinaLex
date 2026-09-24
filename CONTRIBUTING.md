# Hướng Dẫn Đóng Góp (Contributing Guidelines) — Dự Án VinaLex

Chào mừng bạn tham gia phát triển dự án **VinaLex**! Để đảm bảo chất lượng mã nguồn, tính toàn vẹn của dữ liệu pháp lý và tuân thủ các quy định bảo mật, vui lòng đọc kỹ hướng dẫn dưới đây trước khi commit hoặc tạo Pull Request (PR).

---

## 1. 🚨 Nguyên Tắc Bảo Mật Bắt Buộc (Nghị định 13/2023/NĐ-CP)

1. **Không ghi log thông tin nhạy cảm:** Tuyệt đối không dùng `print()` hoặc ghi file log chứa thông tin cá nhân trích xuất từ tài liệu (Họ tên, số CCCD, địa chỉ, số tiền, tài sản).
2. **Cơ chế RAM-Only & Tự hủy:** Dữ liệu file tải lên từ người dùng chỉ được giữ trên RAM (qua Redis với TTL 300s) và phải được giải phóng ngay sau khi xử lý xong.
3. **Bảo mật khóa API:** Tuyệt đối không commit file `.env` chứa `GEMINI_API_KEY`, `SECRET_KEY`, hoặc mật khẩu cơ sở dữ liệu thật lên Git. Hãy sử dụng `.env.example` làm mẫu.

---

## 2. Quy Chuẩn Mã Nguồn & Cấu Trúc Dự Án

* **Backend (Python 3.11):**
  * Tuân thủ chuẩn PEP 8.
  * Tên Class theo `PascalCase` (ví dụ: `PdfTemplateService`, `GeminiService`).
  * Tên biến và hàm theo `snake_case` (ví dụ: `get_statutory_form_pdf`, `search_procedures`).
  * Tất cả các file Python phải hỗ trợ encoding UTF-8 tiếng Việt.
* **Frontend (Next.js 14 / TypeScript):**
  * Tên component theo `PascalCase` (ví dụ: `DocumentVerificationModal.tsx`).
  * Luôn kiểm tra tính tương thích TypeScript, không dùng `any` bừa bãi.
  * Đảm bảo giao diện đồng bộ chính xác với số liệu từ CSDL (dùng dynamic count, không hardcode mock data).

---

## 3. Quy Trình Kiểm Thử Bắt Buộc Trước Khi Tạo Pull Request

Trước khi push code lên nhánh hoặc tạo PR, bạn **BẮT BUỘC** phải chạy và vượt qua 100% các bộ kiểm thử sau trên máy local:

```bash
# 1. Kiểm tra tính toàn vẹn CSDL và phân loại danh mục:
python test/test_stats_and_categories.py

# 2. Kiểm tra sinh 10 mẫu biểu PDF hành chính luật định:
python test/test_all_statutory_form_templates.py

# 3. Chạy bộ kiểm thử hồi quy toàn diện hệ thống (42 ca kiểm thử):
python test/comprehensive_system_test.py

# 4. Kiểm tra biên dịch Frontend (Next.js Build):
cd frontend && npm run build
```

> [!IMPORTANT]
> Toàn bộ các bài kiểm thử trên phải đạt **100% PASS** thì PR mới được xem xét hợp nhất.

---

## 4. Quy Trình Git & Phân Nhánh (Git Workflow)

1. **Tạo nhánh mới:**
   * Cú pháp đặt tên: `feature/ten-tinh-nang`, `fix/loi-can-sua`, hoặc `docs/cap-nhat-tai-lieu`.
   * Ví dụ: `feature/pdf-form-export`, `fix/category-count-badge`.
2. **Commit message chuẩn mực:**
   * Cú pháp: `feat: mô tả ngắn`, `fix: mô tả ngắn`, `docs: mô tả ngắn`.
   * Ví dụ: `feat: add statutory form template 11-DK for land registration`.
3. **Tạo Pull Request:**
   * Mô tả rõ những thay đổi đã thực hiện.
   * Đính kèm kết quả chạy các bài kiểm thử tự động.
   * Yêu cầu ít nhất 1 thành viên review và phê duyệt trước khi merge vào `main`.