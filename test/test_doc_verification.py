import sys
import os
import io

sys.path.insert(0, os.path.abspath("."))

from starlette.testclient import TestClient
from backend.main import app

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

client = TestClient(app)

def test_download_pdf_template():
    print("=== TEST 1: Tải biểu mẫu PDF hành chính ===")
    url = "/api/v1/procedures/download-template"
    params = {
        "doc_name": "Tờ khai đăng ký khai sinh",
        "title": "Đăng ký khai sinh cho trẻ em",
        "slug": "dang-ky-khai-sinh",
    }
    res = client.get(url, params=params)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert res.headers.get("content-type") == "application/pdf", f"Invalid content-type: {res.headers.get('content-type')}"
    assert len(res.content) > 1000, f"PDF file too small: {len(res.content)} bytes"
    print(f"PASSED! Nhận được {len(res.content)} bytes PDF, content-disposition: {res.headers.get('content-disposition')}")

def test_preview_pdf_template():
    print("\n=== TEST 1B: Xem trước biểu mẫu PDF (preview=true) ===")
    url = "/api/v1/procedures/download-template"
    params = {
        "doc_name": "Tờ khai đăng ký khai sinh",
        "title": "Đăng ký khai sinh cho trẻ em",
        "slug": "dang-ky-khai-sinh",
        "preview": "true",
    }
    res = client.get(url, params=params)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    assert "inline" in res.headers.get("content-disposition", ""), f"Expected inline in content-disposition, got {res.headers.get('content-disposition')}"
    print(f"PASSED! Nhận được header xem trước inline: {res.headers.get('content-disposition')}")

def test_verify_document_success():
    print("\n=== TEST 2: Thẩm định hồ sơ hợp lệ (CCCD khớp với yêu cầu CCCD) ===")
    url = "/api/v1/ai/verify-document"
    
    # Tạo một file ảnh JPEG giả lập
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 200), color=(240, 240, 240))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "CAN CUOC CONG DAN", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    files = {"file": ("cccd_mat_truoc.jpg", buf, "image/jpeg")}
    data = {
        "procedure_slug": "dang-ky-khai-sinh",
        "procedure_title": "Đăng ký khai sinh cho trẻ em",
        "expected_document": "CCCD hoặc hộ chiếu của bố/mẹ",
        "session_id": "test-session-verify-123",
    }
    res = client.post(url, files=files, data=data)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    json_data = res.json()
    print("Response status:", json_data.get("status"))
    print("Is valid:", json_data.get("is_valid"))
    print("Document type:", json_data.get("document_type"))
    print("Checks:", len(json_data.get("validation_checks", [])))
    assert json_data.get("is_valid") is True, f"Expected valid=True, got {json_data}"
    assert json_data.get("status") == "passed"
    print("PASSED! Thẩm định thành công hồ sơ hợp lệ.")

def test_verify_document_mismatch():
    print("\n=== TEST 3: Thẩm định hồ sơ nộp sai (Nộp CCCD cho mục Giấy chứng sinh) ===")
    url = "/api/v1/ai/verify-document"
    
    from PIL import Image
    img = Image.new("RGB", (300, 200), color=(240, 240, 240))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    # Đặt tên file gợi ý CCCD
    files = {"file": ("cccd_bo.jpg", buf, "image/jpeg")}
    data = {
        "procedure_slug": "dang-ky-khai-sinh",
        "procedure_title": "Đăng ký khai sinh cho trẻ em",
        "expected_document": "Giấy chứng sinh (do bệnh viện/cơ sở y tế cấp)",
        "session_id": "test-session-verify-456",
    }
    res = client.post(url, files=files, data=data)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    json_data = res.json()
    print("Response status:", json_data.get("status"))
    print("Is valid:", json_data.get("is_valid"))
    print("Errors:", json_data.get("errors"))
    assert json_data.get("is_valid") is False, "Expected valid=False when doc type mismatched"
    assert json_data.get("status") == "rejected"
    assert len(json_data.get("errors", [])) > 0, "Expected at least 1 error message"
    print("PASSED! Hệ thống đã phát hiện chính xác lỗi nộp sai loại giấy tờ.")

if __name__ == "__main__":
    try:
        test_download_pdf_template()
        test_preview_pdf_template()
        test_verify_document_success()
        test_verify_document_mismatch()
        print("\nALL BACKEND TESTS PASSED!")
    except Exception as e:
        print("\nTEST FAILED:", e)
        sys.exit(1)
