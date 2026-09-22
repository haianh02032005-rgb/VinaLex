# VinaLex - Nền tảng Tư vấn Pháp lý & Thủ tục Hành chính

## 1. Mục đích
VinaLex là nền tảng web cung cấp thông tin, hướng dẫn thủ tục hành chính công và tư vấn pháp lý cho người dân, doanh nghiệp. Hệ thống tích hợp phân hệ Trợ lý AI (LegalTech & GovAgent) nhằm bóc tách dữ liệu từ file tài liệu người dùng tải lên, kiểm tra tính hợp lệ của hồ sơ và giải đáp các quy định pháp luật dựa trên dữ liệu thời gian thực.

## 2. Cấu trúc Hệ thống
Hệ thống được chia thành 4 phân hệ chính:
* **Knowledge Hub (Cổng tra cứu):** Nơi lưu trữ và phân loại các thủ tục hành chính, quy trình, điều kiện và biểu mẫu.
* **AI Module (Trợ lý Pháp lý):** Phân hệ lõi xử lý Thị giác máy (OCR tài liệu tải lên) và ngôn ngữ tự nhiên (Chatbot RAG) để tư vấn, đối chiếu hồ sơ.
* **User Workspace:** Không gian để người dùng tải file lên, quản lý tiến độ hồ sơ và tải xuống các biểu mẫu đã được AI điền tự động.
* **Admin CMS:** Giao diện quản trị nội dung bài viết và tự động đồng bộ kiến thức mới vào cơ sở dữ liệu AI (Vector DB).

## 3. Ngăn xếp Công nghệ (Tech Stack)

### 3.1. Web & Backend (Quản lý luồng dữ liệu)
* **Frontend:** `Next.js` (React) - Tối ưu SEO cho các bài viết thủ tục hành chính và quản lý giao diện tương tác.
* **Backend API:** `FastAPI` (Python 3.11) - Xử lý API tốc độ cao, hỗ trợ tốt cho xử lý bất đồng bộ (async) khi gọi các model AI.
* **Database Quan hệ:** `PostgreSQL` - Lưu trữ tài khoản người dùng, danh sách thủ tục, bài viết và lịch sử thao tác.

### 3.2. Trí tuệ Nhân tạo & Xử lý Tài liệu (AI/CV)
* **Thị giác máy & OCR (Xử lý qua File tải lên):** Hệ thống bóc tách dữ liệu từ các file ảnh/scan (JPG, PNG, PDF) do người dùng cung cấp thay vì trích xuất realtime qua camera.
  * `OpenCV`: Tiền xử lý ảnh tĩnh sau khi upload (cắt viền, căn chỉnh, khử nhiễu).
  * `VietOCR` & `PyTorch`: Trích xuất ký tự tiếng Việt từ các vùng đã khoanh.
* **Xử lý Ngôn ngữ Tự nhiên (LLM & RAG):** 
  * `LangChain`: Bộ khung điều phối giữa LLM và cơ sở dữ liệu.
  * `ChromaDB`: Cơ sở dữ liệu Vector lưu trữ văn bản luật để Chatbot tra cứu.
  * `PhoBERT` / `Vietnamese_Embedding_v2`: Mô hình nhúng vector.
  * `Ollama`: Chạy các mô hình LLM (Qwen2.5, Llama-3) tại máy chủ cục bộ.

### 3.3. Bộ nhớ & Bảo mật
* **In-memory Storage:** `Redis` - Lưu trữ session người dùng và dữ liệu file/ảnh tạm thời.

## 4. Quy tắc Tuân thủ Bảo mật (Nghị định 13/2023/NĐ-CP)
1. **Zero Third-Party LLM:** Toàn bộ quá trình đọc OCR và sinh câu trả lời bằng LLM phải được thực thi tại máy chủ nội bộ (Local Inference). Tuyệt đối không gửi dữ liệu hồ sơ qua API bên ngoài.
2. **Cơ chế Hủy dữ liệu:** Dữ liệu cá nhân (file ảnh CMND, hợp đồng) tải lên để kiểm tra/OCR chỉ tồn tại trên RAM thông qua Redis. Hệ thống bắt buộc tự động xóa sau khi API trả kết quả hoặc khi kết thúc phiên.

## 5. Cấu trúc Thư mục Dự án
```text
vinalex/
├── frontend/               # Mã nguồn Next.js (Giao diện web)
├── backend/                # Mã nguồn FastAPI
│   ├── api/                # Các routes (thủ tục, users, ai_chat, upload_ocr)
│   ├── core/               # File cấu hình, bảo mật (.env)
│   ├── db/                 # Kết nối PostgreSQL và Redis
│   ├── models/             # Định nghĩa cấu trúc Database (SQLAlchemy) & Schema (Pydantic)
│   ├── services/           # Lớp logic xử lý chính (Class OOP)
│   │   ├── admin_service.py # Quản lý nội dung CMS
│   │   ├── ocr_service.py  # Trích xuất VietOCR
│   │   ├── rag_service.py  # Truy xuất Vector DB
│   │   └── agent_service.py# Điều phối Chatbot LLM
│   └── main.py             # File khởi chạy server Backend
├── data/                   # (Đã gitignore) Trọng số mô hình AI & Vector DB
├── requirements.txt        # Thư viện Python cho Backend
└── README.md               # Tài liệu dự án

6. Hướng dẫn Khởi chạy (Local Development)
Bước 1: Khởi chạy Backend (FastAPI)

Mở terminal tại thư mục backend/

Tạo và kích hoạt môi trường ảo: python -m venv venv -> source venv/bin/activate (Linux/Mac) hoặc venv\Scripts\activate (Windows)

Cài đặt thư viện: pip install -r requirements.txt

Cấu hình .env (thông số PostgreSQL, Redis, đường dẫn mô hình).

Chạy server: uvicorn main:app --reload (Mặc định chạy ở cổng 8000).

Bước 2: Khởi chạy Frontend (Next.js)

Mở terminal tại thư mục frontend/

Cài đặt Node.js dependencies: npm install

Chạy giao diện: npm run dev (Mặc định chạy ở cổng 3000).
