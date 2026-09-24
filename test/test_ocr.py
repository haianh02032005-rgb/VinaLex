"""
VinaLex — Test Pipeline Thị Giác Máy & OCR (Local)
Kiểm tra CvService tiền xử lý và OcrService trích xuất (hỗ trợ Smart Mock).
"""

import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import unittest
from PIL import Image, ImageDraw
import io

from backend.services.cv_service import CvService
from backend.services.ocr_service import OcrService


class TestOcrPipeline(unittest.TestCase):

    def setUp(self):
        self.cv = CvService()
        self.ocr = OcrService()

        # Tạo một ảnh mẫu trên RAM (không lưu ổ cứng)
        img = Image.new("RGB", (400, 250), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 30), "CAN CUOC CONG DAN", fill=(0, 0, 0))
        draw.text((20, 70), "So: 012345678901", fill=(0, 0, 0))
        draw.text((20, 110), "Ho va ten: NGUYEN VAN A", fill=(0, 0, 0))

        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        self.sample_bytes = buf.getvalue()

    def test_cv_preprocessing(self):
        """Kiểm tra tiền xử lý ảnh bằng OpenCV trên RAM."""
        processed = self.cv.preprocess_image(self.sample_bytes)
        self.assertIsNotNone(processed)
        self.assertEqual(len(processed.shape), 3)

    def test_ocr_extraction_ram_only(self):
        """Kiểm tra trích xuất OCR (kể cả khi chưa nạp weights VietOCR)."""
        fields = self.ocr.extract_from_image_bytes(self.sample_bytes)
        self.assertIsInstance(fields, dict)
        self.assertTrue(len(fields) > 0)

        doc_type = self.ocr.get_document_type(fields)
        self.assertIsInstance(doc_type, str)
        print(f"\n[Test OK] Loại giấy tờ nhận diện: {doc_type}")
        print(f"[Test OK] Số trường thông tin trích xuất: {len(fields)}")


if __name__ == "__main__":
    unittest.main()
