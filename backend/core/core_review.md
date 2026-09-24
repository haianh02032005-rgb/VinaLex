# Đánh Giá Hệ Thống Lõi & Cấu Hình (Core & Config Review)

**Module:** `backend/core/`  
**File chính:** `config.py`, `.env`

---

## 1. Kiến Trúc & Thiết Kế
- Sử dụng `pydantic-settings` (`BaseSettings`) để nạp biến môi trường từ `.env`.
- Tách biệt rõ ràng các phân vùng cấu hình:
  1. **Server API:** `APP_ENV`, `API_V1_STR`, `SECRET_KEY`, `ADMIN_SECRET_KEY`, `BACKEND_CORS_ORIGINS`.
  2. **PostgreSQL:** Server, user, password, port, db name và tạo connection string chuẩn `postgresql+asyncpg://`.
  3. **Redis & Session:** Host, port, db, `FILE_SESSION_TTL` (300 giây).
  4. **AI Models (Local Inference):** Đường dẫn weights `YOLO_OBB_WEIGHTS`, `VIETOCR_WEIGHTS`, `INFERENCE_DEVICE`.
  5. **Ollama & Vector DB:** URL Ollama local, tên model `qwen2.5:latest`, Qdrant host/port, embedding model `keepitreal/vietnamese-sbert`.

---

## 2. Đánh Giá Bảo Mật & Tuân Thủ
- ✅ **Tuân thủ Zero Cloud AI:** Cấu hình trỏ hoàn toàn về `localhost:11434` (Ollama) và weights cục bộ, không có bất kỳ API key nào của OpenAI/Google Gemini/Anthropic trong code.
- ✅ **Cơ chế TTL:** `FILE_SESSION_TTL = 300` đảm bảo session file ảnh tải lên không tồn tại quá 5 phút.
- ⚠️ **Lưu ý triển khai Production:**
  - `SECRET_KEY` và `ADMIN_SECRET_KEY` hiện có giá trị mặc định cho môi trường dev. Cần tạo script tự động cảnh báo hoặc sinh chuỗi ngẫu nhiên khi `APP_ENV=production`.
  - CORS đang mở cho `http://localhost:3000` và `http://127.0.0.1:3000`, phù hợp với môi trường phát triển Next.js.
