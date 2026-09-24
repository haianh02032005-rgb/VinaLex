"""
VinaLex — Kịch Bản & Chương Trình Kiểm Thử Toàn Diện Hệ Thống (End-to-End System Test Suite)
Đánh giá toàn bộ 8 phân hệ chức năng:
  1. Phân hệ Cơ sở dữ liệu & Tính toàn vẹn (Database & Data Integrity)
  2. Phân hệ Cổng tra cứu Thủ tục Hành chính (Procedures API)
  3. Phân hệ Cổng tra cứu Văn bản Pháp luật (Legal Documents API)
  4. Phân hệ Biểu mẫu Hành chính PDF (PDF Template Service)
  5. Phân hệ Trí tuệ Nhân tạo & RAG (AI Agent & RAG Pipeline)
  6. Phân hệ Thị giác máy & Thẩm định Hồ sơ OCR (CV & Semantic Verification)
  7. Phân hệ Xác thực & Không gian Người dùng (Auth & User Workspace)
  8. Phân hệ Quản trị CMS & Đồng bộ (Admin CMS & Crawler)
"""

import sys
import os
import io
import time
import json
from datetime import datetime
from PIL import Image, ImageDraw

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath("."))

from starlette.testclient import TestClient
from backend.main import app
from backend.core.config import settings

client = TestClient(app)

class TestReport:
    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def add(self, module: str, test_id: str, name: str, passed: bool, detail: str = "", duration_ms: float = 0):
        self.results.append({
            "module": module,
            "id": test_id,
            "name": name,
            "passed": passed,
            "detail": detail,
            "duration_ms": duration_ms
        })
        status_icon = "✓ PASS" if passed else "✗ FAIL"
        print(f"[{status_icon}] [{module}] {test_id} - {name} ({duration_ms:.1f}ms)", flush=True)
        if detail and not passed:
            print(f"       -> Lỗi/Chi tiết: {detail}", flush=True)

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        total_time = time.time() - self.start_time
        print("\n" + "=" * 80)
        print(f"TỔNG KẾT KIỂM THỬ HỆ THỐNG VINALEX: {passed}/{total} VƯỢT QUA ({passed/total*100:.1f}%)")
        print(f"Thời gian thực thi: {total_time:.2f}s | Số lỗi phát hiện: {failed}")
        print("=" * 80)
        return total, passed, failed, self.results

report = TestReport()

# ─────────────────────────────────────────────────────────────────────────────
# 1. KIỂM THỬ CƠ SỞ DỮ LIỆU & TÍNH TOÀN VẸN
# ─────────────────────────────────────────────────────────────────────────────
def test_database_integrity():
    mod = "1. CƠ SỞ DỮ LIỆU"
    t0 = time.time()
    try:
        import sqlite3
        conn = sqlite3.connect("data/vinalex.db")
        c = conn.cursor()
        
        # Check tables
        tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        has_all_tables = all(t in tables for t in ["procedures", "legal_documents", "users", "user_procedures"])
        report.add(mod, "DB-01", "Kiểm tra cấu trúc 4 bảng dữ liệu cốt lõi", has_all_tables, f"Tables: {tables}", (time.time()-t0)*1000)

        # Check procedures data integrity
        t1 = time.time()
        c.execute("SELECT id, slug, title, documents, steps FROM procedures")
        procs = c.fetchall()
        empty_docs = [p[1] for p in procs if not p[3] or p[3] == "[]"]
        empty_steps = [p[1] for p in procs if not p[4] or p[4] == "[]"]
        valid_procs = len(procs) > 0 and len(empty_docs) == 0 and len(empty_steps) == 0
        report.add(mod, "DB-02", f"Tính toàn vẹn {len(procs)} thủ tục hành chính", valid_procs, 
                   f"Empty docs: {len(empty_docs)}, Empty steps: {len(empty_steps)}", (time.time()-t1)*1000)

        # Check legal documents integrity
        t2 = time.time()
        c.execute("SELECT count(*) FROM legal_documents WHERE content_text IS NOT NULL AND length(content_text) > 100")
        valid_legal_count = c.fetchone()[0]
        report.add(mod, "DB-03", f"Kiểm tra {valid_legal_count} văn bản pháp luật có toàn văn", valid_legal_count > 100, 
                   f"Số văn bản đạt chuẩn: {valid_legal_count}", (time.time()-t2)*1000)
        conn.close()
    except Exception as e:
        report.add(mod, "DB-ERR", "Lỗi kết nối cơ sở dữ liệu", False, str(e), (time.time()-t0)*1000)

# ─────────────────────────────────────────────────────────────────────────────
# 2. KIỂM THỬ PHÂN HỆ THỦ TỤC HÀNH CHÍNH (PROCEDURES API)
# ─────────────────────────────────────────────────────────────────────────────
def test_procedures_api():
    mod = "2. THỦ TỤC API"
    
    # PROC-01: Lấy danh sách thủ tục phân trang
    t0 = time.time()
    res = client.get("/api/v1/procedures?page=1&limit=12")
    data = res.json() if res.status_code == 200 else {}
    passed = res.status_code == 200 and len(data.get("items", [])) == 12 and data.get("total", 0) > 100
    report.add(mod, "PROC-01", "Lấy danh sách thủ tục phân trang (limit=12)", passed, f"Total: {data.get('total')}", (time.time()-t0)*1000)

    # PROC-02: Lọc theo danh mục
    t0 = time.time()
    res = client.get("/api/v1/procedures?category=ho-tich&limit=20")
    data = res.json() if res.status_code == 200 else {}
    all_match_cat = all(p.get("category_slug") == "ho-tich" for p in data.get("items", []))
    report.add(mod, "PROC-02", "Lọc thủ tục theo chuyên mục (Hộ tịch)", res.status_code == 200 and all_match_cat and len(data.get("items", [])) > 0, 
               f"Count: {len(data.get('items', []))}", (time.time()-t0)*1000)

    # PROC-03: Tìm kiếm từ khóa chuẩn xác & Hard Pruning
    t0 = time.time()
    res = client.get("/api/v1/procedures?search=khai+sinh&limit=20")
    data = res.json() if res.status_code == 200 else {}
    items = data.get("items", [])
    valid_search = len(items) > 0 and any("khai sinh" in p.get("title", "").lower() for p in items)
    report.add(mod, "PROC-03", "Tìm kiếm từ khóa cụ thể ('khai sinh')", valid_search, f"Found: {len(items)}", (time.time()-t0)*1000)

    # PROC-04: Xử lý từ đồng nghĩa (Synonyms: Sổ đỏ -> Quyền sử dụng đất)
    t0 = time.time()
    res = client.get("/api/v1/procedures?search=so+do&limit=20")
    data = res.json() if res.status_code == 200 else {}
    items = data.get("items", [])
    has_land_proc = len(items) > 0 and any("đất" in p.get("title", "").lower() or "đất" in p.get("category", "").lower() for p in items)
    report.add(mod, "PROC-04", "Tìm kiếm đồng nghĩa ('sổ đỏ' -> Đất đai)", has_land_proc, f"Found: {len(items)}", (time.time()-t0)*1000)

    # PROC-05: Từ khóa vô nghĩa (Hard Pruning -> 0 kết quả)
    t0 = time.time()
    res = client.get("/api/v1/procedures?search=tukhongtontai_xyz_9999")
    data = res.json() if res.status_code == 200 else {}
    passed = res.status_code == 200 and data.get("total") == 0 and len(data.get("items", [])) == 0
    report.add(mod, "PROC-05", "Hard Pruning từ khóa rác -> 0 kết quả", passed, f"Total: {data.get('total')}", (time.time()-t0)*1000)

    # PROC-06: Chi tiết thủ tục theo slug hợp lệ
    t0 = time.time()
    res = client.get("/api/v1/procedures/dang-ky-khai-sinh")
    data = res.json() if res.status_code == 200 else {}
    passed = res.status_code == 200 and data.get("slug") == "dang-ky-khai-sinh" and len(data.get("steps", [])) > 0
    report.add(mod, "PROC-06", "Lấy chi tiết thủ tục theo slug (dang-ky-khai-sinh)", passed, f"Title: {data.get('title')}", (time.time()-t0)*1000)

    # PROC-07: Slug không tồn tại -> Trả 404
    t0 = time.time()
    res = client.get("/api/v1/procedures/thu-tuc-khong-co-that-404")
    report.add(mod, "PROC-07", "Truy vấn slug không tồn tại trả về 404", res.status_code == 404, f"Status: {res.status_code}", (time.time()-t0)*1000)

# ─────────────────────────────────────────────────────────────────────────────
# 3. KIỂM THỬ VĂN BẢN PHÁP LUẬT, THÔNG TƯ & NGHỊ ĐỊNH (LEGAL DOCUMENTS API)
# ─────────────────────────────────────────────────────────────────────────────
def test_legal_documents_api():
    mod = "3. VĂN BẢN PHÁP LUẬT"

    # LEG-01: Lấy danh sách văn bản
    t0 = time.time()
    res = client.get("/api/v1/legal-documents?limit=10")
    data = res.json() if res.status_code == 200 else {}
    passed = res.status_code == 200 and len(data.get("items", [])) == 10 and data.get("total", 0) > 100
    report.add(mod, "LEG-01", "Lấy danh sách văn bản quy phạm pháp luật", passed, f"Total: {data.get('total')}", (time.time()-t0)*1000)

    # LEG-02: Lọc theo loại văn bản (Quyết định)
    t0 = time.time()
    res = client.get("/api/v1/legal-documents?doc_type=Quyết+định&limit=10")
    data = res.json() if res.status_code == 200 else {}
    all_match = all(d.get("doc_type") == "Quyết định" for d in data.get("items", []))
    report.add(mod, "LEG-02", "Lọc văn bản theo loại (Quyết định)", res.status_code == 200 and all_match, f"Count: {len(data.get('items', []))}", (time.time()-t0)*1000)

    # LEG-03: Tìm kiếm từ khóa & Trích xuất Excerpt ngữ cảnh
    t0 = time.time()
    res = client.get("/api/v1/legal-documents?search=lao+dong&limit=5")
    data = res.json() if res.status_code == 200 else {}
    items = data.get("items", [])
    has_excerpt = len(items) > 0 and any(len(d.get("excerpt", "")) > 20 for d in items)
    report.add(mod, "LEG-03", "Tìm kiếm từ khóa kèm trích xuất đoạn trích Excerpt", has_excerpt, f"Found: {len(items)}", (time.time()-t0)*1000)

    # LEG-04: Đọc toàn văn văn bản chi tiết
    t0 = time.time()
    if items:
        test_slug = items[0].get("slug")
        res_detail = client.get(f"/api/v1/legal-documents/{test_slug}")
        detail_data = res_detail.json() if res_detail.status_code == 200 else {}
        has_content = res_detail.status_code == 200 and len(detail_data.get("content_text", "")) > 100
        report.add(mod, "LEG-04", f"Đọc toàn văn văn bản chi tiết ({test_slug[:30]}...)", has_content, 
                   f"Length: {len(detail_data.get('content_text', ''))} chars", (time.time()-t0)*1000)
    else:
        report.add(mod, "LEG-04", "Đọc toàn văn văn bản chi tiết", False, "Không có item để test", (time.time()-t0)*1000)

# ─────────────────────────────────────────────────────────────────────────────
# 4. KIỂM THỬ HỆ THỐNG BIỂU MẪU HÀNH CHÍNH PDF (PDF SERVICE)
# ─────────────────────────────────────────────────────────────────────────────
def test_pdf_templates():
    mod = "4. BIỂU MẪU PDF"

    # PDF-01: Tải biểu mẫu Khai sinh (File đính kèm)
    t0 = time.time()
    res = client.get("/api/v1/procedures/download-template?doc_name=T%E1%BB%9D%20khai%20%C4%91%C4%83ng%20k%C3%BD%20khai%20sinh&title=%C4%90%C4%83ng%20k%C3%BD%20khai%20sinh&slug=dang-ky-khai-sinh")
    passed = res.status_code == 200 and res.headers.get("content-type") == "application/pdf" and len(res.content) > 2000
    is_attachment = "attachment" in res.headers.get("content-disposition", "")
    report.add(mod, "PDF-01", "Tải biểu mẫu Tờ khai khai sinh (PDF attachment)", passed and is_attachment, 
               f"Bytes: {len(res.content)}, Disposition: {res.headers.get('content-disposition')}", (time.time()-t0)*1000)

    # PDF-02: Xem trước biểu mẫu Khai sinh (Preview inline)
    t0 = time.time()
    res = client.get("/api/v1/procedures/download-template?doc_name=T%E1%BB%9D%20khai%20%C4%91%C4%83ng%20k%C3%BD%20khai%20sinh&title=%C4%90%C4%83ng%20k%C3%BD%20khai%20sinh&slug=dang-ky-khai-sinh&preview=true")
    is_inline = "inline" in res.headers.get("content-disposition", "")
    report.add(mod, "PDF-02", "Xem trước biểu mẫu inline trực tiếp trên trình duyệt", res.status_code == 200 and is_inline, 
               f"Disposition: {res.headers.get('content-disposition')}", (time.time()-t0)*1000)

    # PDF-03: Mẫu Kết hôn (Thông tư 04/2020/TT-BTP)
    t0 = time.time()
    res = client.get("/api/v1/procedures/download-template?doc_name=Gi%E1%BA%A5y%20%C4%91%C4%83ng%20k%C3%BD%20k%E1%BA%BFt%20h%C3%B4n")
    report.add(mod, "PDF-03", "Sinh mẫu Tờ khai Đăng ký kết hôn chuẩn TT 04/2020", res.status_code == 200 and len(res.content) > 2000, 
               f"Bytes: {len(res.content)}", (time.time()-t0)*1000)

    # PDF-04: Mẫu Thay đổi cư trú CT01 (Thông tư 56/2021/TT-BCA)
    t0 = time.time()
    res = client.get("/api/v1/procedures/download-template?doc_name=T%E1%BB%9D%20khai%20thay%20%C4%91%E1%BB%95i%20th%C3%B4ng%20tin%20c%C6%B0%20tr%C3%BA%20CT01")
    report.add(mod, "PDF-04", "Sinh mẫu Tờ khai cư trú CT01 chuẩn TT 56/2021", res.status_code == 200 and len(res.content) > 2000, 
               f"Bytes: {len(res.content)}", (time.time()-t0)*1000)

    # PDF-05: Mẫu Đăng ký đất đai Mẫu 04/ĐK
    t0 = time.time()
    res = client.get("/api/v1/procedures/download-template?doc_name=%C4%90%C6%A1n%20%C4%91%C4%83ng%20k%C3%BD%20c%E1%BA%A5p%20GCN%20%C4%91%E1%BA%A5t%20%C4%91ai%20M%E1%BA%ABu%2004%2F%C4%90K")
    report.add(mod, "PDF-05", "Sinh mẫu Đơn cấp GCN đất đai Mẫu 04/ĐK", res.status_code == 200 and len(res.content) > 2000, 
               f"Bytes: {len(res.content)}", (time.time()-t0)*1000)

    # PDF-06: Làm sạch từ rác (Sanitize: loại bỏ '(nếu có)', '(do bệnh viện cấp)')
    from backend.services.pdf_service import sanitize_document_name
    cleaned = sanitize_document_name("Giấy chứng sinh (do bệnh viện/cơ sở y tế cấp) (bản chính)")
    report.add(mod, "PDF-06", "Làm sạch từ rác và chú thích trong tên giấy tờ", cleaned == "Giấy chứng sinh", 
               f"Cleaned: '{cleaned}'", 0.1)

# ─────────────────────────────────────────────────────────────────────────────
# 5. KIỂM THỬ TRÍ TUỆ NHÂN TẠO & RAG (AI & RAG PIPELINE)
# ─────────────────────────────────────────────────────────────────────────────
def test_ai_rag_pipeline():
    mod = "5. AI AGENT & RAG"

    from backend.services.rag_service import RagService
    from backend.services.gemini_service import GeminiService

    # AI-01: Kiểm tra nạp và truy vấn RAG
    t0 = time.time()
    rag = RagService()
    docs = rag.retrieve_relevant_docs("Điều kiện đăng ký kết hôn và thẩm quyền giải quyết", top_k=3)
    context, sources = rag.build_context(docs)
    passed = len(docs) > 0 and len(sources) > 0 and len(context) > 100
    report.add(mod, "AI-01", "Truy xuất ngữ cảnh pháp lý từ hệ thống RAG", passed, 
               f"Docs: {len(docs)}, Sources: {len(sources)}", (time.time()-t0)*1000)

    # AI-02: Bộ công cụ Agent - Tool 1: Tra cứu thủ tục
    t0 = time.time()
    gemini = GeminiService()
    t1 = gemini.tool_tra_cuu_thu_tuc("dang-ky-khai-sinh")
    passed_t1 = "Đăng ký khai sinh" in t1 or "dang-ky-khai-sinh" in t1
    report.add(mod, "AI-02", "Agent Tool 1: Tra cứu chi tiết thủ tục hành chính", passed_t1, 
               f"Length: {len(t1)} chars", (time.time()-t0)*1000)

    # AI-03: Bộ công cụ Agent - Tool 2: Cấp link biểu mẫu PDF
    t0 = time.time()
    t2 = gemini.tool_cung_cap_bieu_mau_pdf("dang-ky-khai-sinh", "Tờ khai đăng ký khai sinh")
    passed_t2 = "/api/v1/procedures/download-template" in t2 and "preview=true" in t2
    report.add(mod, "AI-03", "Agent Tool 2: Cung cấp đường dẫn tải/xem trước biểu mẫu", passed_t2, 
               f"Output preview: {t2[:60]}...", (time.time()-t0)*1000)

    # AI-04: Bộ công cụ Agent - Tool 3: Kích hoạt điều hướng OCR
    t0 = time.time()
    t3 = gemini.tool_kich_hoat_kiem_tra_ocr("dang-ky-ket-hon")
    passed_t3 = "[SYS_TRIGGER_OCR:dang-ky-ket-hon]" in t3
    report.add(mod, "AI-04", "Agent Tool 3: Kích hoạt điều hướng thẩm định OCR", passed_t3, 
               f"Trigger: {t3[:40]}...", (time.time()-t0)*1000)

    # AI-05: Chatbot RAG qua API endpoint (/api/v1/ai/chat)
    t0 = time.time()
    res = client.post("/api/v1/ai/chat", json={
        "message": "Thủ tục làm giấy khai sinh cần giấy tờ gì?",
        "session_id": "test-session-chat-01"
    })
    chat_data = res.json() if res.status_code == 200 else {}
    passed_chat = res.status_code == 200 and len(chat_data.get("answer", "")) > 100 and len(chat_data.get("sources", [])) > 0
    report.add(mod, "AI-05", "Chatbot tư vấn pháp luật viện dẫn căn cứ pháp lý (/api/v1/ai/chat)", passed_chat, 
               f"Answer length: {len(chat_data.get('answer', ''))} chars, Sources: {len(chat_data.get('sources', []))}", (time.time()-t0)*1000)

# ─────────────────────────────────────────────────────────────────────────────
# 6. KIỂM THỬ THỊ GIÁC MÁY & THẨM ĐỊNH HỒ SƠ (CV & VERIFICATION)
# ─────────────────────────────────────────────────────────────────────────────
def test_cv_and_verification():
    mod = "6. CV & OCR THẨM ĐỊNH"

    # CV-01: Tiền xử lý ảnh RAM-only
    t0 = time.time()
    from backend.services.cv_service import CvService
    from backend.services.ocr_service import OcrService
    cv_svc = CvService()
    ocr_svc = OcrService()

    img = Image.new("RGB", (350, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((15, 15), "CAN CUOC CONG DAN", fill=(0, 0, 0))
    d.text((15, 45), "So / No: 001095012345", fill=(0, 0, 0))
    d.text((15, 75), "Ho va ten: NGUYEN VAN AN", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    sample_bytes = buf.getvalue()

    processed = cv_svc.preprocess_image(sample_bytes)
    report.add(mod, "CV-01", "Tiền xử lý ảnh OpenCV trên RAM (không ghi ổ cứng)", processed is not None, 
               f"Shape: {processed.shape if processed is not None else 'None'}", (time.time()-t0)*1000)

    # CV-02: Bóc tách thông tin OCR & nhận diện loại giấy tờ
    t0 = time.time()
    fields = ocr_svc.extract_from_image_bytes(sample_bytes)
    doc_type = ocr_svc.get_document_type(fields)
    report.add(mod, "CV-02", "Bóc tách OCR và phân loại giấy tờ (CCCD)", "Căn cước" in doc_type or "CCCD" in doc_type, 
               f"Doc Type: {doc_type}, Fields: {len(fields)}", (time.time()-t0)*1000)

    # CV-03: Thẩm định hồ sơ hợp lệ qua API (/api/v1/ai/verify-document)
    t0 = time.time()
    buf.seek(0)
    files = {"file": ("cccd_an.jpg", buf.getvalue(), "image/jpeg")}
    form_data = {
        "procedure_slug": "cap-giay-phep-lai-xe-b1",
        "procedure_title": "Cấp giấy phép lái xe hạng B1",
        "expected_document": "CCCD hoặc hộ chiếu còn hạn",
        "session_id": "test-verify-valid-01"
    }
    res = client.post("/api/v1/ai/verify-document", files=files, data=form_data)
    ver_data = res.json() if res.status_code == 200 else {}
    passed_ver = res.status_code == 200 and ver_data.get("is_valid") is True and ver_data.get("status") == "passed"
    report.add(mod, "CV-03", "Thẩm định hồ sơ nộp ĐÚNG loại giấy tờ (Status: passed)", passed_ver, 
               f"Status: {ver_data.get('status')}, Checks: {len(ver_data.get('validation_checks', []))}", (time.time()-t0)*1000)

    # CV-04: Thẩm định hồ sơ nộp SAI loại giấy tờ (Nộp CCCD cho mục Giấy chứng sinh)
    t0 = time.time()
    form_data_wrong = {
        "procedure_slug": "dang-ky-khai-sinh",
        "procedure_title": "Đăng ký khai sinh cho trẻ em",
        "expected_document": "Giấy chứng sinh (do bệnh viện/cơ sở y tế cấp)",
        "session_id": "test-verify-wrong-02"
    }
    res_wrong = client.post("/api/v1/ai/verify-document", files={"file": ("cccd_an.jpg", sample_bytes, "image/jpeg")}, data=form_data_wrong)
    wrong_data = res_wrong.json() if res_wrong.status_code == 200 else {}
    passed_wrong = res_wrong.status_code == 200 and wrong_data.get("is_valid") is False and wrong_data.get("status") == "rejected" and len(wrong_data.get("errors", [])) > 0
    report.add(mod, "CV-04", "Phát hiện sai lệch loại giấy tờ & cảnh báo từ chối (Status: rejected)", passed_wrong, 
               f"Errors: {wrong_data.get('errors')}", (time.time()-t0)*1000)

    # CV-05: Tuân thủ Nghị định 13/2023/NĐ-CP (Cơ chế RAM-Only & Xóa sạch Redis session sau xử lý)
    from backend.db.redis import get_session_data
    import asyncio
    async def check_cleanup():
        data_after = await get_session_data("test-verify-valid-01", "raw_image")
        return data_after is None
    cleanup_passed = asyncio.run(check_cleanup())
    report.add(mod, "CV-05", "Tuân thủ NĐ 13/2023: Xóa sạch dữ liệu ảnh/phiên khỏi Redis/RAM", cleanup_passed, 
               "Redis session data = None sau khi hoàn thành request", 0.5)

# ─────────────────────────────────────────────────────────────────────────────
# 7. KIỂM THỬ XÁC THỰC & KHÔNG GIAN NGƯỜI DÙNG (AUTH & WORKSPACE)
# ─────────────────────────────────────────────────────────────────────────────
def test_auth_and_workspace():
    mod = "7. AUTH & WORKSPACE"

    # AUTH-01: Đăng ký tài khoản mới
    t0 = time.time()
    unique_email = f"test_user_{int(time.time())}@vinalex.vn"
    reg_res = client.post("/api/v1/auth/register", json={
        "name": "Nguyễn Văn Test",
        "email": unique_email,
        "password": "Password123@"
    })
    reg_data = reg_res.json() if reg_res.status_code == 201 else {}
    passed_reg = reg_res.status_code == 201 and reg_data.get("email") == unique_email
    report.add(mod, "AUTH-01", "Đăng ký tài khoản người dùng mới (BCrypt hash)", passed_reg, 
               f"Status: {reg_res.status_code}", (time.time()-t0)*1000)

    # AUTH-02: Đăng ký trùng email -> Trả về lỗi 409 Conflict
    t0 = time.time()
    dup_res = client.post("/api/v1/auth/register", json={
        "name": "Nguyễn Văn Test",
        "email": unique_email,
        "password": "Password123@"
    })
    report.add(mod, "AUTH-02", "Bảo vệ trùng lặp email khi đăng ký (409 Conflict)", dup_res.status_code in (400, 409), 
               f"Status: {dup_res.status_code}", (time.time()-t0)*1000)

    # AUTH-03: Đăng nhập thành công -> Nhận JWT Bearer Token
    t0 = time.time()
    login_res = client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": "Password123@"
    })
    login_data = login_res.json() if login_res.status_code == 200 else {}
    token = login_data.get("access_token")
    report.add(mod, "AUTH-03", "Đăng nhập xác thực và cấp JWT Bearer Token", bool(token), 
               f"Token type: {login_data.get('token_type')}", (time.time()-t0)*1000)

    # AUTH-04: Đăng nhập sai mật khẩu -> Trả 401 Unauthorized
    t0 = time.time()
    wrong_login = client.post("/api/v1/auth/login", json={
        "email": unique_email,
        "password": "WrongPassword999"
    })
    report.add(mod, "AUTH-04", "Từ chối xác thực khi sai mật khẩu (401 Unauthorized)", wrong_login.status_code == 401, 
               f"Status: {wrong_login.status_code}", (time.time()-t0)*1000)

    # AUTH-05: Lấy thông tin cá nhân /api/v1/auth/me
    t0 = time.time()
    auth_headers = {"Authorization": f"Bearer {token}"} if token else {}
    me_res = client.get("/api/v1/auth/me", headers=auth_headers)
    me_data = me_res.json() if me_res.status_code == 200 else {}
    report.add(mod, "AUTH-05", "Truy xuất hồ sơ cá nhân qua JWT (/api/v1/auth/me)", me_res.status_code == 200 and me_data.get("email") == unique_email, 
               f"User: {me_data.get('name')}", (time.time()-t0)*1000)

    # AUTH-06: Lưu thủ tục vào hồ sơ cá nhân
    t0 = time.time()
    save_res = client.post("/api/v1/auth/me/procedures", headers=auth_headers, json={
        "procedure_id": 1,
        "notes": "Hồ sơ chuẩn bị nộp tuần tới"
    })
    saved_data = save_res.json() if save_res.status_code in (200, 201) else {}
    user_proc_id = saved_data.get("id")
    report.add(mod, "AUTH-06", "Lưu thủ tục vào không gian làm việc cá nhân (Workspace)", save_res.status_code in (200, 201), 
               f"User Procedure ID: {user_proc_id}", (time.time()-t0)*1000)

    # AUTH-07: Xóa thủ tục khỏi hồ sơ cá nhân
    t0 = time.time()
    if user_proc_id:
        del_res = client.delete(f"/api/v1/auth/me/procedures/{user_proc_id}", headers=auth_headers)
        report.add(mod, "AUTH-07", "Xóa thủ tục khỏi hồ sơ cá nhân", del_res.status_code == 200, 
                   f"Status: {del_res.status_code}", (time.time()-t0)*1000)
    else:
        report.add(mod, "AUTH-07", "Xóa thủ tục khỏi hồ sơ cá nhân", False, "Không có user_proc_id", (time.time()-t0)*1000)

# ─────────────────────────────────────────────────────────────────────────────
# 8. KIỂM THỬ PHÂN HỆ QUẢN TRỊ CMS & ĐỒNG BỘ (ADMIN CMS)
# ─────────────────────────────────────────────────────────────────────────────
def test_admin_cms():
    mod = "8. ADMIN CMS"

    # ADM-01: Chặn truy cập trái phép không có Admin Key -> 403 Forbidden
    t0 = time.time()
    unauth_res = client.get("/api/v1/admin/procedures")
    report.add(mod, "ADM-01", "Chặn truy cập quản trị khi thiếu header X-Admin-Key (403)", unauth_res.status_code == 403, 
               f"Status: {unauth_res.status_code}", (time.time()-t0)*1000)

    # Header hợp lệ
    admin_headers = {"X-Admin-Key": settings.ADMIN_SECRET_KEY}

    # ADM-02: Lấy danh sách toàn bộ thủ tục (bao gồm bản nháp)
    t0 = time.time()
    procs_res = client.get("/api/v1/admin/procedures?limit=20", headers=admin_headers)
    p_data = procs_res.json() if procs_res.status_code == 200 else {}
    report.add(mod, "ADM-02", "Admin lấy toàn bộ danh sách thủ tục (kể cả bản nháp)", procs_res.status_code == 200 and len(p_data.get("items", [])) > 0, 
               f"Total: {p_data.get('total')}", (time.time()-t0)*1000)

    # ADM-03: Thống kê tổng quan hệ thống (/api/v1/admin/stats)
    t0 = time.time()
    stats_res = client.get("/api/v1/admin/stats", headers=admin_headers)
    s_data = stats_res.json() if stats_res.status_code == 200 else {}
    has_stats = stats_res.status_code == 200 and "procedures" in s_data and "total_views" in s_data
    report.add(mod, "ADM-03", "Báo cáo thống kê lượt xem & thủ tục (/api/v1/admin/stats)", has_stats, 
               f"Total: {s_data.get('procedures', {}).get('total')}, Views: {s_data.get('total_views')}", (time.time()-t0)*1000)

    # ADM-04: Kiểm tra trạng thái Vector DB (/api/v1/admin/sync-status)
    t0 = time.time()
    sync_res = client.get("/api/v1/admin/sync-status", headers=admin_headers)
    sync_data = sync_res.json() if sync_res.status_code == 200 else {}
    report.add(mod, "ADM-04", "Kiểm tra trạng thái Vector DB / Qdrant", sync_res.status_code == 200 and "status" in sync_data, 
               f"Status: {sync_data.get('status')}", (time.time()-t0)*1000)

    # ADM-05: Danh sách văn bản pháp luật trong CMS
    t0 = time.time()
    legal_res = client.get("/api/v1/admin/legal-documents?limit=10", headers=admin_headers)
    l_data = legal_res.json() if legal_res.status_code == 200 else {}
    report.add(mod, "ADM-05", "Admin truy vấn danh sách văn bản pháp luật trong kho CSDL", legal_res.status_code == 200 and len(l_data.get("items", [])) > 0, 
               f"Total: {l_data.get('total')}", (time.time()-t0)*1000)

if __name__ == "__main__":
    print("=" * 80)
    print("KHỞI CHẠY KIỂM THỬ TOÀN BỘ 8 PHÂN HỆ CHỨC NĂNG HỆ THỐNG VINALEX")
    print(f"[*] MÔI TRƯỜNG THỰC THI PYTHON: {sys.version}")
    print(f"[*] ĐƯỜNG DẪN TRÌNH BIÊN DỊCH:  {sys.executable}")
    print(f"[*] PHIÊN BẢN PYTHON XÁC THỰC:  Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (Đạt tiêu chuẩn 3.11.x)")
    assert sys.version_info.major == 3 and sys.version_info.minor == 11, f"Yêu cầu Python 3.11.x! Đang chạy: {sys.version}"
    print("=" * 80)
    
    test_database_integrity()
    test_procedures_api()
    test_legal_documents_api()
    test_pdf_templates()
    test_ai_rag_pipeline()
    test_cv_and_verification()
    test_auth_and_workspace()
    test_admin_cms()
    
    total, passed, failed, results = report.summary()
    if failed > 0:
        sys.exit(1)
