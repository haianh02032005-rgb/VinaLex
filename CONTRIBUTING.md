# Hướng dẫn Đóng góp (Contributing Guidelines) - Dự án VinaLex

Để đảm bảo hệ thống VinaLex hoạt động ổn định và an toàn, mọi thành viên vui lòng đọc kỹ và tuân thủ các quy tắc dưới đây trước khi commit code.

---

## 1. 🚨 Nguyên tắc Bảo mật (Bắt buộc tuân thủ)

Hệ thống VinaLex xử lý dữ liệu cá nhân, do đó việc tuân thủ Nghị định 13/2023/NĐ-CP là yêu cầu bắt buộc. Các Pull Request (PR) vi phạm quy tắc sau sẽ không được merge:

* **Không sử dụng API bên thứ 3:** Không gọi API của OpenAI, Gemini, Claude, hay Google Vision để xử lý dữ liệu hồ sơ thật của người dùng. Mọi tác vụ suy luận (inference) phải chạy Local 100% bằng Ollama và các mô hình mã nguồn mở.
* **Không lưu log dữ liệu nhạy cảm:** Không dùng lệnh `print()` hoặc ghi file log chứa thông tin cá nhân trích xuất từ OCR (họ tên, CCCD, địa chỉ) lên Server.
* **Cơ chế RAM-only & Xóa tự động:** Dữ liệu file tải lên và kết quả OCR thô chỉ được lưu trên RAM qua Redis. Ngay sau khi Backend (FastAPI) trả kết quả về Frontend, hệ thống phải thực thi lệnh xóa toàn bộ dữ liệu của Session ID đó trên Redis. Không lưu file của người dùng vào ổ cứng (Hard Drive/SSD).

---

## 2. Quy chuẩn Thiết kế & Cấu trúc Mã nguồn

Hệ thống chia thành 4 lớp theo kiến trúc đã thống nhất. Bạn cần đặt code đúng thư mục tương ứng.

### 2.1. Backend (FastAPI - Python 3.11)
* **Framework:** Sử dụng FastAPI kết hợp Uvicorn làm Backend lõi.
* **Lập trình Hướng đối tượng (OOP):** Các service xử lý AI và bóc tách dữ liệu phải được viết thành các Class độc lập.
* **Vị trí đặt code:**
  * `backend/api/`: Các endpoint (routes) tiếp nhận request.
  * `backend/services/`: Chứa logic xử lý (VD: `cv_service.py` cho OpenCV/YOLO-OBB, `ocr_service.py` cho VietOCR, `rag_service.py` cho LangChain/Vector DB).
  * `backend/models/`: Cấu trúc Database (SQLAlchemy) và Pydantic schema.
* **Quy tắc đặt tên:** Tên Class viết theo `PascalCase` (VD: `OcrService`), tên biến và hàm viết theo `snake_case` (VD: `extract_text`).

### 2.2. Frontend (Next.js) & Database
* **Frontend:** Phát triển bằng Next.js (React).
* **Database:** Dùng PostgreSQL để lưu dữ liệu hệ thống (tài khoản, thủ tục).

---

## 3. Cài đặt Môi trường (Environment Setup)

1. **Phiên bản Python:** Đảm bảo sử dụng Python 3.11.x.
2. **Cài đặt thư viện:** Dùng lệnh `pip install -r requirements.txt`.
3. **Lưu ý về PyTorch & GPU:** 
   * File `requirements.txt` sử dụng `torch==2.3.0` và `torchvision==0.18.0` (cài qua pip mặc định).
   * Nếu máy bạn có card đồ họa (NVIDIA GPU) và muốn tối ưu tốc độ cho YOLO/VietOCR, hãy bỏ qua bản mặc định này và cài lại `torch` theo lệnh riêng của CUDA.
4. **Thư viện cốt lõi:** Không tự ý thay đổi phiên bản các thư viện lõi như `fastapi==0.111.0`, `redis==5.0.4`, `langchain==0.2.5`, hoặc `opencv-python-headless==4.9.0.80`. Bản `opencv-python-headless` được dùng để tối ưu cho Server vì không yêu cầu giao diện UI.

---

## 4. Quy trình Đẩy code (Git Workflow)

1. **Phân nhánh (Branching):**
   * Không commit trực tiếp vào nhánh `main` hoặc `master`.
   * Tạo nhánh mới theo cú pháp: `type/tên-tính-năng` (VD: `feature/add-ocr`, `bugfix/redis-timeout`).
2. **Tạo Pull Request (PR):**
   * Test kỹ code trên máy cá nhân trước khi tạo PR.
   * Đối chiếu sơ đồ luồng dữ liệu để đảm bảo logic: Người dùng -> Frontend -> FastAPI -> Redis -> AI Services -> Trả JSON -> Xóa Redis.
   * Nhờ ít nhất 1 thành viên khác review (đặc biệt kiểm tra các quy tắc bảo mật) trước khi merge.