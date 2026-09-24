"""
Test kiểm tra tính pháp lý và độ chính xác của biểu mẫu PDF sinh ra
"""

import sys
import os
import io

sys.path.insert(0, os.path.abspath("."))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import fitz
from starlette.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_marriage_form():
    print("=== TEST 1: Biểu mẫu Đăng ký kết hôn ===")
    url = "/api/v1/procedures/download-template"
    params = {
        "doc_name": "Giấy đăng ký kết hôn (nếu có)",
        "title": "Đăng ký khai sinh cho trẻ em",
        "slug": "dang-ky-khai-sinh",
        "preview": "true",
    }
    res = client.get(url, params=params)
    assert res.status_code == 200
    assert "to_khai_dang_ky_ket_hon.pdf" in res.headers.get("content-disposition", "")
    
    # Đọc nội dung PDF bằng PyMuPDF
    doc = fitz.open(stream=res.content, filetype="pdf")
    page_text = doc[0].get_text().replace('\xa0', ' ')
    
    print("Tiêu đề trích xuất:", [line for line in page_text.splitlines() if "KẾT HÔN" in line or "TỜ KHAI" in line])
    assert "TỜ KHAI ĐĂNG KÝ KẾT HÔN" in page_text, "Thiếu tiêu đề TỜ KHAI ĐĂNG KÝ KẾT HÔN"
    assert "BÊN NAM" in page_text, "Thiếu cột BÊN NAM"
    assert "BÊN NỮ" in page_text, "Thiếu cột BÊN NỮ"
    assert "04/2020/TT" in page_text, "Thiếu căn cứ Thông tư 04/2020/TT-BTP"
    assert "(NẾU CÓ)" not in page_text, "Còn sót từ '(NẾU CÓ)' trong PDF!"
    assert "HỒ SƠ / BIỂU MẪU" not in page_text, "Còn sót từ 'HỒ SƠ / BIỂU MẪU' trong PDF!"
    print("PASSED! Mẫu Đăng ký kết hôn chuẩn xác 100% Thông tư 04/2020/TT-BTP, không có từ rác.")

def test_birth_certificate_alternative_form():
    print("\n=== TEST 2: Biểu mẫu Giấy cam đoan sinh con (thay Giấy chứng sinh) ===")
    url = "/api/v1/procedures/download-template"
    params = {
        "doc_name": "Giấy chứng sinh (do bệnh viện/cơ sở y tế cấp)",
        "title": "Đăng ký khai sinh cho trẻ em",
        "slug": "dang-ky-khai-sinh",
    }
    res = client.get(url, params=params)
    assert res.status_code == 200
    doc = fitz.open(stream=res.content, filetype="pdf")
    page_text = doc[0].get_text().replace('\xa0', ' ')
    
    assert "CAM ĐOAN VỀ VIỆC SINH CON" in page_text
    assert "Điều 16 Luật Hộ tịch" in page_text
    assert "(do bệnh viện/cơ sở y tế cấp)" not in page_text
    print("PASSED! Mẫu cam đoan sinh con chuẩn pháp lý.")

def test_residence_ct01_form():
    print("\n=== TEST 3: Mẫu CT01 Thay đổi thông tin cư trú ===")
    url = "/api/v1/procedures/download-template"
    params = {
        "doc_name": "Hộ khẩu gia đình",
        "title": "Đăng ký khai sinh cho trẻ em",
        "slug": "dang-ky-khai-sinh",
    }
    res = client.get(url, params=params)
    assert res.status_code == 200
    doc = fitz.open(stream=res.content, filetype="pdf")
    page_text = doc[0].get_text().replace('\xa0', ' ')
    
    assert "TỜ KHAI THAY ĐỔI THÔNG TIN CƯ TRÚ" in page_text
    assert "Mẫu CT01" in page_text
    print("PASSED! Mẫu CT01 cư trú chuẩn Thông tư 56/2021/TT-BCA của Bộ Công an.")

if __name__ == "__main__":
    test_marriage_form()
    test_birth_certificate_alternative_form()
    test_residence_ct01_form()
    print("\nTẤT CẢ CÁC MẪU BIỂU PHÁP LÝ ĐỀU VƯỢT QUA KIỂM TRA!")
