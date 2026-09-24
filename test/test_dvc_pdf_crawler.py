"""
VinaLex — Comprehensive Test Suite for DVC PDF & Document Ingestion Module
Kiểm thử toàn diện:
1. DVCDocumentDatabase (Schema, CRUD, FTS5, SHA256 Deduplication, Statistics)
2. DVCPdfCrawler (Bóc tách profileComponents, sinh vector PDF Nghị định 30, sinh Dossier Guide PDF)
3. Live / Integration Crawl từ Cổng DVC Quốc Gia
4. FastAPI Endpoints (/api/v1/dvc-documents/*)
"""

import os
import sys
import tempfile
import unittest
import fitz

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.db.dvc_document_db import DVCDocumentDatabase
from backend.services.dvc_pdf_crawler import DVCPdfCrawler
from fastapi.testclient import TestClient
from backend.main import app


class TestDVCPdfCrawlerModule(unittest.TestCase):
    def setUp(self):
        # Tạo database tạm thời và thư mục PDF tạm thời cho test
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_dvc.db")
        self.storage_dir = os.path.join(self.temp_dir, "pdf_storage")
        self.db = DVCDocumentDatabase(db_path=self.db_path)
        self.crawler = DVCPdfCrawler(
            db_path=self.db_path,
            storage_dir=self.storage_dir,
            auto_generate_templates=True,
        )
        self.client = TestClient(app)

    def tearDown(self):
        import gc
        import shutil
        gc.collect()
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def test_01_database_initialization_and_crud(self):
        """Kiểm tra khởi tạo CSDL riêng, cấu trúc bảng, FTS5 và thêm/sửa/xóa."""
        # 1. Thêm thủ tục mẫu
        proc_data = {
            "dvc_id": "test-uuid-001",
            "code": "1.999999",
            "title": "Thủ tục đăng ký cấp đổi giấy chứng nhận quyền sử dụng đất",
            "slug": "thu-tuc-dang-ky-cap-doi-giay-chung-nhan",
            "category": "Đất đai - Nhà ở",
            "category_slug": "dat-dai",
            "agency": "Văn phòng Đăng ký đất đai",
            "level": "Cấp Tỉnh/Thành phố",
            "processing_time": "15 ngày làm việc",
            "fee": "100.000 VNĐ",
            "description": "Thủ tục cấp đổi cho người dân khi sổ đỏ bị rách hoặc đổi mẫu",
            "steps": [{"index": 1, "title": "Nộp hồ sơ", "description": "Nộp tại bộ phận một cửa"}],
            "legal_basis": ["Luật Đất đai 2024", "Nghị định 101/2024/NĐ-CP"],
        }
        proc_id = self.db.upsert_procedure(proc_data)
        self.assertIsInstance(proc_id, int)
        self.assertGreater(proc_id, 0)

        # 2. Thêm giấy tờ thành phần
        doc_id = self.db.insert_procedure_document({
            "procedure_id": proc_id,
            "procedure_code": "1.999999",
            "case_name": "Cấp đổi sổ đỏ",
            "doc_name": "Đơn đăng ký biến động đất đai (Mẫu số 11/ĐK)",
            "doc_clean_name": "Đơn đăng ký biến động đất đai Mẫu 11/ĐK",
            "form_code": "MẪU 11/ĐK",
            "is_required": True,
            "original_copy_type": "Bản chính",
            "quantity": 1,
            "note": "Ký ghi rõ họ tên",
        })
        self.assertGreater(doc_id, 0)

        # 3. Thêm tệp PDF
        test_pdf_content = b"%PDF-1.4 test dummy pdf content"
        pdf_id = self.db.insert_pdf_file({
            "procedure_id": proc_id,
            "procedure_code": "1.999999",
            "document_id": doc_id,
            "file_type": "form_template",
            "file_name": "don_dang_ky_bien_dong_mau_11_dk.pdf",
            "file_path": "/fake/path/don_11_dk.pdf",
            "file_size_bytes": len(test_pdf_content),
            "file_hash_sha256": "fakehash1234567890abcdef",
            "source_origin": "vinalex_vector_pdf",
        })
        self.assertGreater(pdf_id, 0)

        # 4. Kiểm tra chống trùng lặp theo SHA-256
        duplicate_pdf_id = self.db.insert_pdf_file({
            "procedure_id": proc_id,
            "procedure_code": "1.999999",
            "document_id": doc_id,
            "file_type": "form_template",
            "file_name": "don_dang_ky_bien_dong_mau_11_dk_copy.pdf",
            "file_path": "/fake/path/copy.pdf",
            "file_size_bytes": len(test_pdf_content),
            "file_hash_sha256": "fakehash1234567890abcdef",
            "source_origin": "vinalex_vector_pdf",
        })
        self.assertEqual(duplicate_pdf_id, pdf_id, "Tệp trùng hash SHA-256 phải trả về ID cũ")

        # 5. Tra cứu lại
        proc = self.db.get_procedure_by_code("1.999999")
        self.assertIsNotNone(proc)
        self.assertEqual(proc["total_documents"], 1)
        self.assertEqual(proc["total_pdfs"], 1)

        # 6. Kiểm tra Full-Text Search FTS5
        search_res = self.db.search_full_text("biến động đất đai")
        self.assertGreaterEqual(len(search_res), 1)
        self.assertEqual(search_res[0]["code"], "1.999999")

        # 7. Thống kê
        stats = self.db.get_database_statistics()
        self.assertEqual(stats["total_procedures"], 1)
        self.assertEqual(stats["total_documents"], 1)
        self.assertEqual(stats["total_pdfs"], 1)

    def test_02_pdf_generation_and_storage(self):
        """Kiểm tra chức năng sinh vector PDF Nghị định 30 và Dossier Summary PDF."""
        proc_data = {
            "code": "1.888888",
            "title": "Đăng ký kết hôn có yếu tố nước ngoài",
            "agency": "UBND Huyện",
            "fee": "1.000.000 VNĐ",
            "processing_time": "15 ngày",
            "level": "Cấp Huyện",
            "steps": [{"index": 1, "title": "Nộp tờ khai", "description": "Nộp tờ khai đăng ký kết hôn"}],
        }
        docs = [
            {"doc_name": "Tờ khai đăng ký kết hôn", "original_copy_type": "Bản chính"},
            {"doc_name": "Giấy xác nhận tình trạng hôn nhân", "original_copy_type": "Bản chính"},
        ]

        # Sinh Dossier Guide PDF
        guide_pdf_bytes = self.crawler._generate_dossier_summary_pdf(proc_data, docs)
        self.assertIsInstance(guide_pdf_bytes, bytes)
        self.assertGreater(len(guide_pdf_bytes), 2000)

        # Mở bằng PyMuPDF để verify chuẩn PDF hợp lệ
        doc_fitz = fitz.open("pdf", guide_pdf_bytes)
        self.assertGreater(len(doc_fitz), 0)
        page_text = doc_fitz[0].get_text().replace("\xa0", " ")
        self.assertIn("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", page_text)
        self.assertIn("BỘ HỒ SƠ HƯỚNG DẪN THỦ TỤC HÀNH CHÍNH", page_text)
        doc_fitz.close()

        # Lưu vào đĩa
        fpath, fhash, fsize = self.crawler._save_pdf_to_disk("1.888888", "guide.pdf", guide_pdf_bytes)
        self.assertTrue(os.path.exists(fpath))
        self.assertEqual(fsize, len(guide_pdf_bytes))
        self.assertEqual(len(fhash), 64)

    def test_03_crawl_and_ingest_live_procedure(self):
        """Kiểm tra cào thực tế 1 mã TTHC có trên dichvucong.gov.vn và kiểm tra lưu CSDL + PDF."""
        # Mã thủ tục cấp đổi GCN đất đai đã kiểm chứng có hồ sơ trên DVC
        test_code = "1.116461"
        res = self.crawler.crawl_by_code(test_code)
        
        self.assertIsNotNone(res, f"Phải cào thành công thủ tục {test_code} từ DVC")
        self.assertEqual(res["code"], test_code)

        # Kiểm tra dữ liệu trong CSDL riêng
        proc_in_db = self.db.get_procedure_by_code(test_code)
        self.assertIsNotNone(proc_in_db)
        self.assertGreater(proc_in_db["total_documents"], 0, "Thủ tục phải có ít nhất 1 thành phần giấy tờ")
        self.assertGreater(proc_in_db["total_pdfs"], 0, "Thủ tục phải sinh/lưu ít nhất 1 file PDF")

        docs = self.db.get_procedure_documents(proc_in_db["id"])
        self.assertGreater(len(docs), 0)
        print(f"\n[Test] TTHC {test_code}: Tìm thấy {len(docs)} giấy tờ thành phần.")
        for d in docs[:3]:
            print(f"       - {d['doc_name'][:60]} ({d['original_copy_type']})")

        pdfs = self.db.get_procedure_pdf_files(proc_in_db["id"])
        self.assertGreater(len(pdfs), 0)
        print(f"[Test] TTHC {test_code}: Đã tạo {len(pdfs)} tệp PDF trong kho:")
        for p in pdfs:
            print(f"       📎 {p['file_name']} -> {p['file_path']} ({round(p['file_size_bytes']/1024, 1)} KB)")
            self.assertTrue(os.path.exists(p["file_path"]), f"File PDF phải tồn tại trên đĩa: {p['file_path']}")

    def test_04_api_endpoints(self):
        """Kiểm tra các endpoints FastAPI /api/v1/dvc-documents/*."""
        # Nạp dữ liệu qua crawl_by_code
        self.crawler.crawl_by_code("1.116461")

        # Gán db tạm thời vào API router để test
        import backend.api.dvc_documents as api_mod
        original_db = api_mod._db
        api_mod._db = self.db

        try:
            # 1. Test /stats
            res = self.client.get("/api/v1/dvc-documents/stats")
            self.assertEqual(res.status_code, 200)
            stats = res.json()
            self.assertGreaterEqual(stats["total_procedures"], 1)

            # 2. Test /procedures
            res = self.client.get("/api/v1/dvc-documents/procedures?page=1&limit=10")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertIn("items", data)
            self.assertGreaterEqual(data["total"], 1)

            # 3. Test /procedures/{code}
            res = self.client.get("/api/v1/dvc-documents/procedures/1.116461")
            self.assertEqual(res.status_code, 200)
            detail = res.json()
            self.assertIn("procedure", detail)
            self.assertIn("documents", detail)
            self.assertIn("pdf_files", detail)

            # 4. Test /pdfs/{id}/download và /preview
            pdf_id = detail["pdf_files"][0]["id"]
            res_down = self.client.get(f"/api/v1/dvc-documents/pdfs/{pdf_id}/download")
            self.assertEqual(res_down.status_code, 200)
            self.assertEqual(res_down.headers["content-type"], "application/pdf")
            self.assertIn("attachment", res_down.headers["content-disposition"])

            res_prev = self.client.get(f"/api/v1/dvc-documents/pdfs/{pdf_id}/preview")
            self.assertEqual(res_prev.status_code, 200)
            self.assertEqual(res_prev.headers["content-type"], "application/pdf")
            self.assertIn("inline", res_prev.headers["content-disposition"])

            # 5. Test /search
            res_search = self.client.get("/api/v1/dvc-documents/search?q=đất")
            self.assertEqual(res_search.status_code, 200)
            self.assertGreaterEqual(res_search.json()["count"], 1)

        finally:
            api_mod._db = original_db


if __name__ == "__main__":
    unittest.main()
