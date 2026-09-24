# 🏛️ VinaLex — Nền Tảng Tư Vấn Pháp Lý & Thủ Tục Hành Chính Công Thông Minh

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI_0.111-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js_14-black?style=flat-square&logo=next.js&logoColor=white)](https://nextjs.org)
[![Python](https://img.shields.io/badge/Python-3.11.x-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Database](https://img.shields.io/badge/Database-SQLite_%7C_PostgreSQL-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://sqlite.org)
[![AI RAG](https://img.shields.io/badge/AI_RAG-Vector_Database_%7C_Retrieval-4285F4?style=flat-square&logo=google&logoColor=white)](https://ai.google.dev/)
[![Compliance](https://img.shields.io/badge/Compliance-NĐ_30/2020_%7C_NĐ_13/2023-critical?style=flat-square)](#)

> **VinaLex** là giải pháp GovTech & LegalTech tiên tiến, hỗ trợ người dân và doanh nghiệp Việt Nam tra cứu quy trình hành chính công, đọc toàn văn thông tư - nghị định, tư vấn pháp lý với Trợ lý AI và tự động sinh biểu mẫu PDF chuẩn thể thức in ấn hành chính nhà nước.

---

## 🌟 Tính Năng Nổi Bật

### 1. 🔍 Tra Cứu Kép (Dual Search Engine)
* **Thủ tục hành chính (556 thủ tục):** Phân loại theo 8 nhóm lĩnh vực nghiệp vụ trọng điểm (Đất đai, Hộ tịch, Doanh nghiệp, Giao thông, Giáo dục, Y tế, Thuế, Lao động - BHXH).
* **Văn bản quy phạm pháp luật (204 văn bản):** Tra cứu nhanh số hiệu, trích yếu, ngày ban hành và xem toàn văn Thông tư, Nghị định, Luật với trình đọc trực quan (`Legal Documents Reader`).
* **Thuật toán tìm kiếm thông minh:** Hỗ trợ tiếng Việt không dấu, tìm kiếm mờ (fuzzy) và từ khóa pháp lý đồng nghĩa (ví dụ: *"sổ đỏ"* ↔ *"giấy chứng nhận quyền sử dụng đất"*, *"cccd"* ↔ *"căn cước"*).

### 2. 🤖 Trợ Lý AI Pháp Lý Đột Phá (Hệ Thống RAG Tri Thức Pháp Luật)
* **Truy xuất tri thức pháp luật thời gian thực (RAG):** Đào sâu trong kho 8.301 điều khoản pháp lý số hóa để trả lời chính xác, trích dẫn rõ ràng điều/khoản/luật ban hành.
* **Cung cấp Biểu mẫu PDF Trực tiếp trong Khung Chat:** Khi người dùng hỏi hoặc yêu cầu mẫu đơn, Trợ lý AI tự động nhận diện ý định và trả về thẻ tải file PDF chuẩn trực tiếp trên giao diện chat.
* **Thẩm định Hồ sơ Cá nhân (Document Verification):** Tự động đối chiếu các giấy tờ người dùng hiện có với quy định pháp luật để chỉ ra những giấy tờ còn thiếu hoặc cần bổ sung.

### 3. 📄 Sinh Biểu Mẫu PDF Chuẩn Pháp Lý (Statutory Form Generator)
* **Tuân thủ Nghị định số 30/2020/NĐ-CP:** Quốc hiệu, Tiêu ngữ, Tên mẫu chuẩn, khoảng cách lề và khung ký duyệt theo thể thức hành chính nhà nước.
* **100% Đơn sắc đen trắng:** Thiết kế vector chuẩn in ấn công quyền, không màu mè, không watermark, làm sạch hoàn toàn các từ ngữ thô/rác.
* **Hỗ trợ đầy đủ các biểu mẫu chuẩn:**
  * Đất đai: *Mẫu 11/ĐK (Đăng ký biến động)*, *Mẫu 04/ĐK (Cấp GCN lần đầu)*, *Mẫu 01/ĐK-GCN*.
  * Hộ tịch: *Tờ khai đăng ký khai sinh*, *Tờ khai đăng ký kết hôn*.
  * Doanh nghiệp: *Giấy đề nghị đăng ký doanh nghiệp (Phụ lục I-2)*.
  * Xây dựng: *Đơn đề nghị cấp giấy phép xây dựng*.
  * Giao thông: *Đơn đề nghị đổi/cấp lại Giấy phép lái xe*.
  * Thuế & BHXH: *Mẫu TK1-TS (BHXH)*, *Mẫu 05-ĐK-TCT (Đăng ký thuế)*.

---

## 📊 Số Liệu Thống Kê Thực Tế Của Hệ Thống

| Nhóm Dữ Liệu | Số Lượng Thực Tế | Nguồn / Trạng Thái |
| :--- | :---: | :--- |
| **Thủ tục hành chính** | **556** | Chuẩn hóa trong `data/vinalex.db` |
| **Văn bản pháp luật** | **204** | Thông tư, Nghị định, Quyết định toàn văn |
| **Điều khoản quy phạm RAG** | **8.301** | `data/parsed_rag_chunks.json` |
| **Mẫu biểu luật định** | **10 Nhóm** | PyMuPDF Vector Engine chuẩn in ấn |
| **Chuẩn hóa thể thức** | **100%** | Nghị định 30/2020/NĐ-CP & Nghị định 13/2023/NĐ-CP |

---

## 🚀 Hướng Dẫn Khởi Chạy Nhanh Cho Đồng Đội (3 Bước)

Hệ thống đã được đóng gói sẵn cơ sở dữ liệu SQLite cục bộ `data/vinalex.db`, bạn **không cần cài đặt PostgreSQL hay Redis** mà vẫn có thể khởi chạy và phát triển bình thường.

### Yêu cầu tiên quyết:
- **Python:** 3.11.x
- **Node.js:** 18.x hoặc 20.x
- **Git**

---

### Bước 1: Clone Kho Mã Nguồn & Thiết Lập Biến Môi Trường

```bash
# 1. Clone dự án về máy
git clone <URL_REPO_GITHUB>
cd Hackthon

# 2. Cấu hình biến môi trường Backend
copy .env.example .env

# 3. Cấu hình biến môi trường Frontend
cd frontend
copy .env.local.example .env.local
cd ..
```

> [!TIP]
> Bạn có thể mở `.env` và điền `GEMINI_API_KEY` từ [Google AI Studio](https://aistudio.google.com/) nếu muốn sử dụng tính năng Chatbot AI nâng cao với Gemini Flash.

---

### Bước 2: Cài Đặt & Khởi Chạy Backend (FastAPI)

```bash
# 1. Tạo môi trường ảo Python 3.11
python -m venv venv

# 2. Kích hoạt môi trường ảo:
# Windows (PowerShell/CMD):
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Cài đặt các thư viện cần thiết
pip install -r requirements.txt

# 4. Khởi chạy Backend Server
python main.py
```

* Backend API sẽ khởi động tại: `http://localhost:8000`
* Tài liệu Swagger UI tương tác: `http://localhost:8000/api/docs`
* Kiểm tra trạng thái hệ thống: `http://localhost:8000/api/v1/health`

---

### Bước 3: Cài Đặt & Khởi Chạy Frontend (Next.js)

Mở một cửa sổ Terminal mới:

```bash
# Di chuyển vào thư mục frontend
cd frontend

# Cài đặt các gói phụ thuộc Node.js
npm install

# Khởi chạy giao diện nhà phát triển
npm run dev
```

* Ứng dụng Web sẽ sẵn sàng tại: `http://localhost:3000`

---

## 🧪 Kiểm Thử Tự Động Hóa Hệ Thống (Automated Test Suites)

Dự án cung cấp bộ kiểm thử tự động hóa toàn diện 100%:

```bash
# 1. Kiểm tra tính toàn vẹn CSDL và số liệu danh mục:
python test/test_stats_and_categories.py

# 2. Kiểm tra sinh 10 biểu mẫu PDF luật định:
python test/test_all_statutory_form_templates.py

# 3. Chạy 42 ca kiểm thử toàn diện hồi quy hệ thống:
python test/comprehensive_system_test.py

# 4. Kiểm tra biên dịch production của Frontend:
cd frontend && npm run build
```

---

## 📁 Cấu Trúc Bố Cục Thư Mục Dự Án

```text
Hackthon/
├── docs/                             # Tài liệu kiến trúc & tài sản hình ảnh
│   └── assets/
│       └── architecture_flow.png     # Sơ đồ luồng xử lý dữ liệu và bảo mật
├── backend/                          # Mã nguồn Backend FastAPI
│   ├── api/                          # Các Router: procedures, ai, auth, admin, legal_documents
│   ├── core/                         # Config, cấu hình bảo mật JWT & CORS
│   ├── db/                           # Quản lý kết nối SQLite và PostgreSQL
│   ├── models/                       # Schema Pydantic và SQLAlchemy Models
│   ├── services/                     # Business Logic: Gemini, PDF Engine, RAG, Verification
│   ├── init_db.py                    # Script khởi tạo CSDL
│   └── main.py                       # App FastAPI chính
├── frontend/                         # Mã nguồn Frontend Next.js 14 App Router
│   ├── app/                          # Giao diện các trang: /, /thu-tuc, /tro-ly-ai, /admin
│   ├── components/                   # Modal xem PDF, Modal thẩm định hồ sơ, Navbar, Footer
│   ├── lib/                          # API client, hằng số thống kê và danh mục chuẩn
│   └── types/                        # Định nghĩa TypeScript toàn dự án
├── data/                             # Dữ liệu hệ thống đã chuẩn hóa
│   ├── vinalex.db                    # CSDL SQLite 556 TTHC + 204 Văn bản (Đã kèm trong Git)
│   ├── crawled_procedures.json       # Dữ liệu thô thủ tục hành chính
│   ├── dvc_procedures.json           # Dữ liệu dịch vụ công quốc gia
│   ├── crawled_legal_docs.json       # Dữ liệu văn bản pháp luật
│   └── parsed_rag_chunks.json        # 8,301 Chunks tri thức RAG số hóa
├── scripts/                          # Script chuẩn hóa dữ liệu
│   └── normalize_procedure_database.py # Chuẩn hóa tên thủ tục và mã mẫu biểu
├── test/                             # 15 kịch bản kiểm thử tự động hóa
├── .env.example                      # Mẫu biến môi trường Backend
├── .gitignore                        # Cấu hình Gitignore tối ưu cho đồng đội
├── ARCHITECTURE.md                   # Bản thiết kế kiến trúc hệ thống
├── CONTRIBUTING.md                   # Hướng dẫn quy trình đóng góp code
├── main.py                           # Root runner khởi chạy server Backend
├── README.md                         # Tài liệu hướng dẫn sử dụng & triển khai
└── requirements.txt                  # Danh sách thư viện Python
```

---

## 🔒 Quy Định Bảo Mật (Nghị định 13/2023/NĐ-CP)

1. **Cơ chế RAM-Only:** Mọi tài liệu cá nhân người dùng tải lên để kiểm tra/OCR chỉ tồn tại trong bộ nhớ RAM tạm thời và **tự động bị xóa sạch** sau phiên làm việc.
2. **Không lưu vết dữ liệu:** Máy chủ tuyệt đối không ghi log bất kỳ thông tin nhận dạng cá nhân nào (Họ tên, CCCD, địa chỉ...).
3. **Phân quyền chặt chẽ:** Các thao tác quản trị dữ liệu yêu cầu khóa bí mật `X-Admin-Key`.

---

## 👥 Đóng Góp & Phát Triển
Vui lòng đọc kỹ [CONTRIBUTING.md](CONTRIBUTING.md) và [ARCHITECTURE.md](ARCHITECTURE.md) trước khi tạo pull request. Mọi đóng góp đều cần vượt qua 100% các bài kiểm thử tự động.
