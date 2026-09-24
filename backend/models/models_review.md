# Đánh Giá Mô Hình Dữ Liệu & Schemas (Models & Schemas Review)

**Module:** `backend/models/`  
**File chính:** `procedure.py` (ORM), `schemas.py` (Pydantic)

---

## 1. SQLAlchemy ORM Models (`backend/models/procedure.py`)
- **Chuẩn hóa 2.0:** Sử dụng `Mapped[...]` và `mapped_column(...)` theo chuẩn SQLAlchemy 2.0 hiện đại và type-safe.
- **Bảng `users` (`UserModel`):**
  - Quản lý tài khoản người dùng, email unique index, mật khẩu mã hóa hash, cờ `is_active`.
  - Quan hệ 1-N với `user_procedures`.
- **Bảng `procedures` (`ProcedureModel`):**
  - Lưu trữ thủ tục hành chính, `slug` unique index, phân loại danh mục, cấp thực hiện.
  - Cột `steps`, `documents`, `tags` sử dụng kiểu dữ liệu `JSON` linh hoạt.
  - Lưu vết số lượt xem `view_count` phục vụ thống kê bài viết nổi bật.
- **Bảng `user_procedures` (`UserProcedureModel`):**
  - Quản lý tiến độ hoàn thành hồ sơ người dùng (progress 0-100%, status, due_date, notes).
- **Bảng `legal_documents` (`LegalDocumentModel`):**
  - Lưu trữ toàn bộ các văn bản quy phạm pháp luật thu thập từ Thư Viện Pháp Luật (số hiệu, cơ quan ban hành, hiệu lực, tóm tắt, toàn văn).

---

## 2. Pydantic Schemas (`backend/models/schemas.py`)
- **Tách bạch Request/Response:**
  - `LoginRequest`, `RegisterRequest`, `TokenResponse`, `UserResponse`.
  - `ProcedureResponse`, `ProcedureListResponse`, `ProcedureCreateRequest`.
  - `ChatRequest`, `ChatResponse`: bắt buộc `session_id` để track phiên và xóa rác RAM.
  - `OcrResponse`: Định dạng trả về có `extracted_fields`, `summary`, `confidence`, `processing_time_ms`.
  - `LegalDocumentResponse`, `LegalDocumentListResponse`, `CrawlRequest`, `CrawlResponse`.
- **Đánh giá bảo mật:** `OcrResponse` chỉ chuyển dữ liệu kết quả qua RAM trả về trực tiếp cho Client, không kèm token nhạy cảm hay thông tin nội bộ server.
