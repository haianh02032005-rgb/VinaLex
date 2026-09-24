# Đánh Giá Tầng Giao Tiếp API (API Layer Review)

**Module:** `backend/api/`  
**File chính:** `procedures.py`, `ai.py`, `auth.py`, `admin.py`, `main.py`

---

## 1. Phân Hệ Thủ Tục Hành Chính (`procedures.py`)
- **GET `/api/v1/procedures`:**
  - Hỗ trợ lọc theo `category`, tìm kiếm từ khóa `search`, phân trang `page`, `limit`.
  - **Khả năng dự phòng cao (High Resilience):** Tự động chuyển sang `_load_fallback_procedures()` đọc từ `data/crawled_procedures.json` nếu PostgreSQL chưa khởi động.
  - Tích hợp thuật toán tính điểm xếp hạng tìm kiếm tiếng Việt không dấu (`_score_proc`) với từ khóa đồng nghĩa (synonyms: "sổ đỏ" <-> "quyền sử dụng đất", "cccd" <-> "căn cước").
- **GET `/api/v1/procedures/{slug}`:** Lấy chi tiết thủ tục, tự động tăng `view_count` khi có kết nối DB, fallback JSON mượt mà.
- **Admin CRUD:** Đầy đủ POST, PUT, DELETE được bảo vệ bằng dependency `_verify_admin_key`.

---

## 2. Phân Hệ Trí Tuệ Nhân Tạo & OCR (`ai.py`)
- **POST `/api/v1/ai/chat`:**
  - Tiếp nhận câu hỏi pháp lý và `session_id`.
  - Điều phối qua `AgentService` và `RagService` (Qdrant similarity search -> Fallback CSDL văn bản luật -> Ollama generation).
- **POST `/api/v1/ai/ocr`:**
  - 🔒 **Tuân thủ quy chuẩn bảo mật Nghị định 13/2023/NĐ-CP:**
    1. Đọc file tải lên dưới dạng `bytes` trực tiếp vào RAM.
    2. Lưu tạm vào Redis với session TTL (không ghi ra ổ cứng).
    3. Chạy `run_in_threadpool` cho các tác vụ nặng CPU (`CvService`, `OcrService`).
    4. Gửi kết quả cho `AgentService` đánh giá tính hợp lệ hồ sơ.
    5. **Khối `finally` đảm bảo gọi `await delete_session(session_id)` để xóa sạch dữ liệu khỏi Redis/RAM trong mọi tình huống.**

---

## 3. Phân Hệ Xác Thực & Người Dùng (`auth.py`)
- **POST `/api/v1/auth/register` & `/api/v1/auth/login`:**
  - Xác thực bằng mật khẩu băm (`passlib[bcrypt]`), sinh JWT Bearer token (`python-jose`).
  - Quản lý hồ sơ người dùng lưu trữ (`/api/v1/auth/me/procedures`).
- **Chế độ Offline:** Hỗ trợ demo người dùng mẫu khi database chưa kết nối.

---

## 4. Phân Hệ Quản Trị CMS & Đồng Bộ RAG (`admin.py`)
- **Xác thực:** Yêu cầu header `X-Admin-Key` khớp với cấu hình hệ thống.
- **Tính năng:**
  - Lấy danh sách toàn bộ thủ tục (bao gồm bản nháp chưa publish).
  - POST `/api/v1/admin/sync-legal-doc`: Nhúng văn bản vào Qdrant Vector DB.
  - GET `/api/v1/admin/sync-status`: Báo cáo trạng thái kết nối Qdrant.
  - POST `/api/v1/admin/crawler/run`: Kích hoạt cào dữ liệu từ CMS Admin.
