# VinaLex - Bản Thiết kế Kiến trúc Hệ thống (Architecture Blueprint)

## Mục đích
Tài liệu này quy định kiến trúc tổng thể, luồng xử lý dữ liệu và danh sách các công nghệ/công cụ (Tech Stack) bắt buộc phải sử dụng trong dự án VinaLex. Mọi thành viên trong đội ngũ phát triển phải đọc hiểu và tuân thủ chặt chẽ tài liệu này trước khi viết code, đặc biệt là các quy tắc về bảo mật thông tin.

---

## 1. Cấu trúc Các lớp Công nghệ (Tech Stack Layers)
Hệ thống được chia thành 4 lớp rõ rệt, kết nối với nhau thông qua API:

### Lớp 1: Giao diện Người dùng (Frontend)
* **Next.js (React):** Quản lý luồng tương tác người dùng, hiển thị nội dung thủ tục hành chính, giao diện tải file và khung chat trợ lý ảo.

### Lớp 2: Giao tiếp & Điều phối (Backend / API Gateway)
* **FastAPI (Python 3.11):** Bắt buộc sử dụng làm Backend lõi. Đảm nhiệm việc tiếp nhận các request từ Frontend, phân luồng tác vụ và xử lý bất đồng bộ (async/await) để không gây nghẽn hệ thống khi các mô hình AI đang chạy.

### Lớp 3: Trí tuệ Nhân tạo & Bóc tách Dữ liệu (AI Services)
Được đóng gói thành các Class (OOP) gọi từ FastAPI, bao gồm 2 phân hệ:
* **Phân hệ Thị giác máy (CV/OCR - Xử lý file ảnh tĩnh):**
  * `OpenCV`: Tiền xử lý file ảnh tải lên (cắt, xoay, làm nét).
  * `YOLO-OBB`: Phân tích bố cục, khoanh vùng chính xác các trường thông tin (tên, ngày sinh, chữ ký).
  * `VietOCR`: Trích xuất ký tự tiếng Việt từ các vùng đã cắt.
* **Phân hệ Xử lý Ngôn ngữ Tự nhiên (RAG):**
  * `LangChain`: Khung sườn liên kết các module NLP.
  * `Qdrant` (ưu tiên) hoặc `ChromaDB`: Cơ sở dữ liệu Vector lưu trữ tài liệu luật.
  * `Ollama`: Môi trường chạy các mô hình ngôn ngữ lớn (Qwen2.5, Llama-3).

### Lớp 4: Lưu trữ & Quản lý Trạng thái (Storage)
* **PostgreSQL:** Lưu trữ dữ liệu hệ thống (Tài khoản, danh sách bài viết thủ tục).
* **Redis:** Bắt buộc sử dụng làm vùng nhớ tạm (In-memory cache) cho các file ảnh tải lên và phiên làm việc (session).

---

## 2. Sơ đồ Luồng Dữ liệu Xử lý Hồ sơ (Data Flow)

Luồng hoạt động dưới đây mô tả quá trình từ lúc người dùng tải file lên đến lúc hệ thống xử lý xong và thực thi cơ chế xóa tự động.

![alt text](image.png)

3. 🚨 QUY TẮC BẢO MẬT & TUÂN THỦ PHÁP LÝ (CRITICAL)
Toàn bộ đội ngũ phát triển phải tuân thủ nghiêm ngặt các quy định sau nhằm đáp ứng Nghị định 13/2023/NĐ-CP về Bảo vệ dữ liệu cá nhân. Vi phạm các quy tắc này là vi phạm kiến trúc hệ thống.

🚫 TUYỆT ĐỐI KHÔNG SỬ DỤNG API LLM/AI CỦA BÊN THỨ 3: Không được phép gọi API của OpenAI, Gemini, Claude, Google Vision hay bất kỳ dịch vụ Cloud nào để xử lý dữ liệu hồ sơ (CMND/CCCD, hợp đồng) của người dùng thật. Mọi suy luận (inference) phải chạy Local 100% bằng Ollama và các mô hình mã nguồn mở.

🚫 KHÔNG LƯU VẾT DỮ LIỆU NHẠY CẢM: Không được phép ghi Log (print/logger) hoặc Hard-code các thông tin cá nhân trích xuất được từ OCR (Họ tên, số ID, địa chỉ, số tiền) vào bất kỳ file .txt, .log hay Console nào trên Server.

✅ CƠ CHẾ RAM-ONLY & TỰ ĐỘNG HỦY: Dữ liệu file tải lên và kết quả OCR thô chỉ được phép tồn tại trên RAM (thông qua Redis). Không lưu file của người dùng vào ổ cứng (Hard Drive/SSD) của máy chủ. Căn cứ theo Sơ đồ Luồng Dữ liệu ở Mục 2, tiến trình tự động dọn dẹp biến và xóa file tạm (Garbage Collection) phải được thực thi ngay lập tức sau khi trả kết quả về Frontend.