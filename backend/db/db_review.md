# Đánh Giá Tầng Lưu Trữ & Bộ Nhớ (Database & Memory Review)

**Module:** `backend/db/`  
**File chính:** `postgres.py`, `redis.py`

---

## 1. Kết Nối PostgreSQL (`backend/db/postgres.py`)
- **Công nghệ:** SQLAlchemy 2.0 Async + `asyncpg`.
- **Cấu hình Connection Pool:**
  - `pool_size = 10`, `max_overflow = 20`, `pool_pre_ping = True`.
  - Hỗ trợ tốt cho các tác vụ async không gây block event loop của FastAPI.
- **Dependency Injection:**
  - Hàm `get_db()` yield session với `commit()` tự động khi thành công và `rollback()` khi gặp ngoại lệ.

---

## 2. Quản Lý Session & Bộ Nhớ Tạm (`backend/db/redis.py`)
- **Công nghệ:** `redis.asyncio`.
- **Cơ chế RAM-Only (Tuân thủ Nghị định 13/2023/NĐ-CP):**
  - Dữ liệu file ảnh được lưu dưới dạng binary (`decode_responses=False`).
  - Gắn TTL tự động qua `setex(key, FILE_SESSION_TTL, data)`.
  - Hàm `delete_session(session_id)` hỗ trợ dọn dẹp triệt để mọi key theo pattern `session:{session_id}:*`.
- **Cơ chế Dự Phòng (In-Memory Fallback):**
  - Tích hợp sẵn `_memory_store = {}` chạy hoàn toàn trên RAM Python khi Redis server chưa được khởi động trên máy phát triển.
  - Khi `delete_session()` được gọi, cả Redis lẫn `_memory_store` đều được dọn dẹp sạch sẽ.
