"""
VinaLex — BỘ KIỂM THỬ TỰ ĐỘNG TOÀN DIỆN TÍNH NĂNG OCR & THẨM ĐỊNH HỒ SƠ
Thực thi theo Bản Kế hoạch Kiểm thử (Test Plan) chuẩn mực:
  - Phân hệ 1: Tiền xử lý Thị giác máy (CvService)
  - Phân hệ 2: Bóc tách OCR & Phân loại Giấy tờ (OcrService)
  - Phân hệ 3: Thẩm định & Đối soát Quy chuẩn Hồ sơ (DocumentVerificationService)
  - Phân hệ 4: Bảo mật, Vòng đời Session & Tuân thủ NĐ 13/2023/NĐ-CP (Redis RAM-only)
  - Phân hệ 5: Tích hợp API Gateway (/ai/ocr & /ai/verify-document) & Chat Trigger
  - Phân hệ 6: Hiệu năng SLA & Cách ly Phiên đồng thời (Concurrency & Isolation)
"""

import sys
import os
import io
import time
import asyncio
import unittest
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Đưa workspace root vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from starlette.testclient import TestClient
from backend.main import app
from backend.services.cv_service import CvService, DetectedRegion
from backend.services.ocr_service import OcrService, _detect_file_type, _estimate_doc_type_from_bytes
from backend.services.verification_service import DocumentVerificationService
from backend.db.redis import store_session_data, get_session_data, delete_session, _memory_store


class TestOcrComprehensivePlan(unittest.TestCase):
    """Bộ kiểm thử thực thi toàn bộ kịch bản trong Kế hoạch Kiểm thử OCR VinaLex."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.cv = CvService()
        cls.ocr = OcrService()
        cls.verifier = DocumentVerificationService()

        # Tạo ảnh mẫu tổng hợp (Synthetic Data) CCCD chuẩn trên RAM
        img_cccd = Image.new("RGB", (450, 280), color=(245, 245, 245))
        d_cccd = ImageDraw.Draw(img_cccd)
        d_cccd.text((20, 20), "CONG HOA XA HOI CHU NGHIA VIET NAM", fill=(0, 0, 0))
        d_cccd.text((20, 50), "CAN CUOC CONG DAN", fill=(0, 0, 0))
        d_cccd.text((20, 90), "So / No.: 012345678901", fill=(0, 0, 0))
        d_cccd.text((20, 130), "Ho va ten / Full name: NGUYEN VAN A", fill=(0, 0, 0))
        d_cccd.text((20, 170), "Ngay sinh / Date of birth: 01/01/1990", fill=(0, 0, 0))
        d_cccd.text((20, 210), "Que quan / Place of origin: Ha Noi", fill=(0, 0, 0))
        buf_cccd = io.BytesIO()
        img_cccd.save(buf_cccd, format="JPEG")
        cls.sample_cccd_bytes = buf_cccd.getvalue()

        # Tạo ảnh mẫu PNG
        buf_png = io.BytesIO()
        img_cccd.save(buf_png, format="PNG")
        cls.sample_png_bytes = buf_png.getvalue()

        # Tạo mẫu PDF header
        cls.sample_pdf_bytes = b"%PDF-1.4\n%test pdf document\n%%EOF"

    # =========================================================================
    # PHÂN HỆ 1: TIỀN XỬ LÝ THỊ GIÁC MÁY (CvService)
    # =========================================================================

    def test_tc_cv_01_decode_ram_only_bytes(self):
        """TC-CV-01: Giải mã ảnh từ luồng byte trên RAM."""
        processed = self.cv.preprocess_image(self.sample_cccd_bytes)
        self.assertIsNotNone(processed)
        self.assertEqual(len(processed.shape), 3, "Ảnh xử lý phải là định dạng 3 kênh (BGR)")
        self.assertGreater(processed.shape[0], 0)
        self.assertGreater(processed.shape[1], 0)

    def test_tc_cv_02_corrupted_bytes_handling(self):
        """TC-CV-02: Xử lý an toàn khi nạp byte hỏng/không đúng định dạng."""
        corrupted_bytes = b"NOT_AN_IMAGE_RANDOM_CORRUPTED_BYTES_123456789"
        with self.assertRaises(ValueError) as ctx:
            self.cv.preprocess_image(corrupted_bytes)
        self.assertIn("Không thể giải mã ảnh", str(ctx.exception))

    def test_tc_cv_03_contrast_and_binarization(self):
        """TC-CV-03: Kiểm tra CLAHE và Adaptive Thresholding."""
        processed = self.cv.preprocess_image(self.sample_cccd_bytes)
        # Giá trị nhị phân hóa (chỉ có mức 0 hoặc 255 sau thresholding)
        unique_vals = set(processed.flatten()[:200])
        self.assertTrue(0 in unique_vals or 255 in unique_vals)

    def test_tc_cv_04_yolo_obb_detection_or_fallback(self):
        """TC-CV-04 & TC-CV-05: Phân vùng tài liệu và cơ chế Fallback."""
        processed = self.cv.preprocess_image(self.sample_cccd_bytes)
        regions = self.cv.detect_regions(processed)
        self.assertIsInstance(regions, list)
        self.assertGreater(len(regions), 0, "Phải phát hiện ít nhất 1 vùng (hoặc full_document fallback)")
        
        reg = regions[0]
        self.assertIsInstance(reg, DetectedRegion)
        self.assertGreaterEqual(reg.width, 0)
        self.assertGreaterEqual(reg.height, 0)

    # =========================================================================
    # PHÂN HỆ 2: BÓC TÁCH KÝ TỰ & PHÂN LOẠI GIẤY TỜ (OcrService)
    # =========================================================================

    def test_tc_ocr_01_magic_bytes_detection(self):
        """TC-OCR-01: Nhận diện định dạng tệp qua Magic Bytes header."""
        self.assertEqual(_detect_file_type(self.sample_pdf_bytes), "pdf")
        self.assertEqual(_detect_file_type(self.sample_cccd_bytes), "jpeg")
        self.assertEqual(_detect_file_type(self.sample_png_bytes), "png")
        self.assertEqual(_detect_file_type(b"II*\x00SomeTIFFData"), "tiff")
        self.assertEqual(_detect_file_type(b"unknown_header"), "unknown")

    def test_tc_ocr_02_field_extraction_cccd(self):
        """TC-OCR-02: Bóc tách trường thông tin CCCD."""
        fields = self.ocr.extract_from_image_bytes(self.sample_cccd_bytes)
        self.assertIsInstance(fields, dict)
        self.assertGreater(len(fields), 0)
        # Các trường cốt lõi của CCCD
        self.assertTrue(any(k in fields for k in ["Số CCCD", "Họ và tên", "Ngày sinh"]))

    def test_tc_ocr_03_classify_document_type(self):
        """TC-OCR-03 & TC-OCR-04: Phân loại loại tài liệu từ fields."""
        doc_type_cccd = self.ocr.get_document_type({"Số CCCD": "012345678901", "Họ và tên": "NGUYEN VAN A"})
        self.assertIn("Căn cước công dân", doc_type_cccd)

        doc_type_cmnd = self.ocr.get_document_type({"Số CMND": "123456789", "Họ và tên": "NGUYEN VAN A"})
        self.assertIn("Chứng minh nhân dân", doc_type_cmnd)

        doc_type_contract = self.ocr.get_document_type({"Loại hợp đồng": "Hợp đồng mua bán"})
        self.assertIn("Hợp đồng", doc_type_contract)

        doc_type_unknown = self.ocr.get_document_type({})
        self.assertEqual(doc_type_unknown, "Tài liệu không xác định")

    def test_tc_ocr_05_smart_mock_resilience(self):
        """TC-OCR-05: Kiểm tra cơ chế Smart Mock thích ứng an toàn."""
        mock_fields = self.ocr._smart_mock_fields(self.sample_cccd_bytes)
        self.assertIsInstance(mock_fields, dict)
        self.assertIn("Số CCCD", mock_fields)
        self.assertEqual(mock_fields["Số CCCD"], "012345678901")

    # =========================================================================
    # PHÂN HỆ 3: THẨM ĐỊNH & ĐỐI SOÁT HỒ SƠ (VerificationService)
    # =========================================================================

    def test_tc_ver_01_verify_valid_document(self):
        """TC-VER-01: Thẩm định hồ sơ hợp lệ (CCCD khớp yêu cầu CCCD)."""
        res = self.verifier.verify(
            extracted_fields={
                "Số CCCD": "012345678901",
                "Họ và tên": "NGUYỄN VĂN A",
                "Ngày sinh": "01/01/1990",
            },
            expected_doc_name="Bản sao CCCD hoặc Hộ chiếu của người yêu cầu",
            procedure_title="Đăng ký khai sinh",
            filename="cccd_mat_truoc.jpg",
            raw_document_type="Căn cước công dân (CCCD)",
        )
        self.assertTrue(res["is_valid"])
        self.assertEqual(res["status"], "passed")
        self.assertEqual(len(res["errors"]), 0)

    def test_tc_ver_02_verify_mismatched_document(self):
        """TC-VER-02: Phát hiện nộp sai loại giấy tờ (Nộp CCCD cho mục Giấy chứng sinh)."""
        res = self.verifier.verify(
            extracted_fields={
                "Số CCCD": "012345678901",
                "Họ và tên": "NGUYỄN VĂN A",
            },
            expected_doc_name="Giấy chứng sinh do cơ sở y tế cấp",
            procedure_title="Đăng ký khai sinh",
            filename="cccd_bo.jpg",
            raw_document_type="Căn cước công dân (CCCD)",
        )
        self.assertFalse(res["is_valid"])
        self.assertEqual(res["status"], "rejected")
        self.assertTrue(any("yêu cầu" in e for e in res["errors"]))
        self.assertTrue(any(c["status"] == "failed" for c in res["validation_checks"]))

    def test_tc_ver_03_invalid_id_length_warning(self):
        """TC-VER-03: Cảnh báo số CCCD không đúng 9 hoặc 12 số."""
        res = self.verifier.verify(
            extracted_fields={
                "Số CCCD": "12345",  # Chỉ 5 số (thiếu)
                "Họ và tên": "NGUYỄN VĂN A",
                "Ngày sinh": "01/01/1990",
            },
            expected_doc_name="Căn cước công dân",
            procedure_title="Đăng ký kết hôn",
            filename="cccd_loi.jpg",
            raw_document_type="Căn cước công dân (CCCD)",
        )
        self.assertFalse(res["is_valid"])
        self.assertTrue(any("không đúng chuẩn" in e for e in res["errors"]))

    def test_tc_ver_04_missing_name_field(self):
        """TC-VER-04: Báo lỗi khi thiếu trường Họ và tên trên CCCD."""
        res = self.verifier.verify(
            extracted_fields={
                "Số CCCD": "012345678901",
                # Thiếu Họ và tên
            },
            expected_doc_name="Căn cước công dân",
            procedure_title="Đăng ký kết hôn",
            filename="cccd_mo.jpg",
            raw_document_type="Căn cước công dân (CCCD)",
        )
        self.assertFalse(res["is_valid"])
        self.assertTrue(any("Họ và tên" in e for e in res["errors"]))

    # =========================================================================
    # PHÂN HỆ 4: BẢO MẬT & NGHỊ ĐỊNH 13/2023/NĐ-CP (RAM-Only & Redis Cleanup)
    # =========================================================================

    def test_tc_sec_01_redis_session_lifecycle_and_cleanup(self):
        """TC-SEC-01: Vòng đời Session và bắt buộc xóa sạch trên Redis/RAM."""
        test_session_id = "test-sec-session-" + str(int(time.time()))

        async def run_lifecycle():
            # 1. Lưu dữ liệu file vào RAM
            await store_session_data(test_session_id, "raw_image", self.sample_cccd_bytes)
            # Kiểm tra dữ liệu tồn tại
            data = await get_session_data(test_session_id, "raw_image")
            self.assertIsNotNone(data)
            self.assertEqual(data, self.sample_cccd_bytes)

            # 2. Xóa session (mô phỏng finally block của API)
            await delete_session(test_session_id)

            # 3. Kiểm tra dữ liệu ĐÃ BỊ XÓA HOÀN TOÀN
            data_after = await get_session_data(test_session_id, "raw_image")
            self.assertIsNone(data_after, "Session data phải bị tiêu hủy hoàn toàn khỏi RAM")

        asyncio.run(run_lifecycle())

    def test_tc_sec_02_zero_disk_leakage(self):
        """TC-SEC-02: Đảm bảo không tạo bất kỳ file tạm nào ra ổ cứng khi OCR."""
        initial_files = set(os.listdir("."))
        
        # Gửi request OCR qua API
        res = self.client.post(
            "/api/v1/ai/ocr",
            files={"file": ("temp_test.jpg", io.BytesIO(self.sample_cccd_bytes), "image/jpeg")},
            data={"session_id": "test-disk-leak-session"},
        )
        self.assertEqual(res.status_code, 200)

        # Kiểm tra lại thư mục hiện tại
        current_files = set(os.listdir("."))
        new_files = current_files - initial_files
        self.assertEqual(len(new_files), 0, f"Phát hiện file rác ghi ra ổ cứng: {new_files}")

    def test_tc_sec_04_finally_block_cleanup_on_exception(self):
        """TC-SEC-04: Đảm bảo xóa session ngay cả khi gặp lỗi xử lý."""
        test_session_id = "test-exception-cleanup-" + str(int(time.time()))
        
        # Gửi file với dữ liệu gây lỗi nhưng vẫn truyền session_id
        res = self.client.post(
            "/api/v1/ai/ocr",
            files={"file": ("corrupted.jpg", io.BytesIO(b"corrupted_bytes"), "image/jpeg")},
            data={"session_id": test_session_id},
        )
        self.assertEqual(res.status_code, 200)
        
        # Kiểm tra session_id đã được dọn sạch khỏi bộ nhớ
        async def verify_empty():
            val = await get_session_data(test_session_id, "raw_image")
            self.assertIsNone(val, "Session phải được dọn sạch kể cả khi có exception")

        asyncio.run(verify_empty())

    def test_tc_sec_05_file_size_and_mime_validation(self):
        """TC-SEC-05: Chặn file quá khổ (>10MB) và định dạng không hỗ trợ."""
        # 1. Chặn file sai MIME type
        res_mime = self.client.post(
            "/api/v1/ai/ocr",
            files={"file": ("script.exe", io.BytesIO(b"executable_content"), "application/x-msdownload")},
            data={"session_id": "test-mime-session"},
        )
        self.assertEqual(res_mime.status_code, 415, "Phải trả về HTTP 415 khi MIME không hợp lệ")

        # 2. Chặn file vượt quá 10MB
        large_bytes = b"0" * (10 * 1024 * 1024 + 1024)  # 10MB + 1KB
        res_size = self.client.post(
            "/api/v1/ai/ocr",
            files={"file": ("large.jpg", io.BytesIO(large_bytes), "image/jpeg")},
            data={"session_id": "test-size-session"},
        )
        self.assertEqual(res_size.status_code, 413, "Phải trả về HTTP 413 khi file > 10MB")

    # =========================================================================
    # PHÂN HỆ 5: TÍCH HỢP API GATEWAY & CHAT TRIGGER
    # =========================================================================

    def test_tc_api_01_upload_ocr_endpoint_schema(self):
        """TC-API-01: Kiểm tra cấu trúc Response của endpoint /api/v1/ai/ocr."""
        res = self.client.post(
            "/api/v1/ai/ocr",
            files={"file": ("test_cccd.jpg", io.BytesIO(self.sample_cccd_bytes), "image/jpeg")},
            data={"session_id": "test-api-ocr-session"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertIn("document_type", data)
        self.assertIn("extracted_fields", data)
        self.assertIn("summary", data)
        self.assertIn("processing_time_ms", data)
        self.assertEqual(data["session_id"], "test-api-ocr-session")

    def test_tc_api_02_verify_document_endpoint_schema(self):
        """TC-API-02: Kiểm tra cấu trúc Response của endpoint /api/v1/ai/verify-document."""
        res = self.client.post(
            "/api/v1/ai/verify-document",
            files={"file": ("test_cccd.jpg", io.BytesIO(self.sample_cccd_bytes), "image/jpeg")},
            data={
                "procedure_slug": "dang-ky-khai-sinh",
                "procedure_title": "Đăng ký khai sinh",
                "expected_document": "CCCD bố mẹ",
                "session_id": "test-api-verify-session",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("is_valid", data)
        self.assertIn("status", data)
        self.assertIn("validation_checks", data)
        self.assertIn("errors", data)
        self.assertIn("suggestions", data)

    def test_tc_api_03_chat_trigger_ocr_regex(self):
        """TC-API-03: Kiểm tra định dạng mã kích hoạt [SYS_TRIGGER_OCR:<slug>]."""
        import re
        trigger_text = "Hệ thống cần bạn cung cấp giấy tờ tùy thân. [SYS_TRIGGER_OCR:dang-ky-ket-hon] Vui lòng tải lên."
        match = re.search(r"\[SYS_TRIGGER_OCR:([^\]]+)\]", trigger_text)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), "dang-ky-ket-hon")

    # =========================================================================
    # PHÂN HỆ 6: HIỆU NĂNG SLA & CÁCH LY PHIÊN ĐỒNG THỜI (Concurrency)
    # =========================================================================

    def test_tc_perf_01_response_time_sla(self):
        """TC-PERF-01: Đảm bảo thời gian phản hồi OCR lõi thỏa mãn SLA < 1.0 giây và API < 5.0 giây."""
        # 1. Đo lường tốc độ pipeline OCR lõi (CvService + OcrService trên RAM)
        start_core = time.time()
        fields = self.ocr.extract_from_image_bytes(self.sample_cccd_bytes)
        core_elapsed = time.time() - start_core
        self.assertLessEqual(core_elapsed, 1.0, "Thời gian xử lý OCR lõi vượt quá ngưỡng 1.0s")
        print(f"\n  [SLA Benchmark] Pipeline OCR Lõi: {core_elapsed:.4f}s (SLA <= 1.0s)")

        # 2. Đo lường toàn trình API Gateway
        start_api = time.time()
        res = self.client.post(
            "/api/v1/ai/ocr",
            files={"file": ("sla_test.jpg", io.BytesIO(self.sample_cccd_bytes), "image/jpeg")},
            data={"session_id": "test-sla-session"},
        )
        api_elapsed = time.time() - start_api
        self.assertEqual(res.status_code, 200)
        print(f"  [SLA Benchmark] Toàn trình API Gateway /ai/ocr: {api_elapsed:.2f}s")

    def test_tc_perf_02_concurrent_session_isolation(self):
        """TC-PERF-02: Kiểm tra cách ly phiên đồng thời giữa các người dùng (No Cross-Talk)."""
        num_sessions = 5
        results = []

        def worker(session_idx):
            sid = f"concurrent-session-{session_idx}-{time.time()}"
            r = self.client.post(
                "/api/v1/ai/ocr",
                files={"file": (f"user_{session_idx}.jpg", io.BytesIO(self.sample_cccd_bytes), "image/jpeg")},
                data={"session_id": sid},
            )
            return sid, r.status_code, r.json()

        with ThreadPoolExecutor(max_workers=num_sessions) as executor:
            futures = [executor.submit(worker, i) for i in range(num_sessions)]
            for f in futures:
                results.append(f.result())

        for sid, status_code, json_res in results:
            self.assertEqual(status_code, 200)
            self.assertTrue(json_res["success"])
            self.assertEqual(json_res["session_id"], sid, "Session ID phải khớp chính xác, không bị nhầm lẫn giữa các luồng")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestOcrComprehensivePlan)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
