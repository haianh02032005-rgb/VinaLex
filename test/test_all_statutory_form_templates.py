"""
Kiểm thử toàn diện Hệ thống Biểu mẫu Hành chính Chuẩn hóa VinaLex (10+ Domain Templates)
Tuân thủ nghiêm ngặt Nghị định 30/2020/NĐ-CP, Nghị định 101/2024/NĐ-CP, Nghị định 61/2018/NĐ-CP.
"""

import os
import sys
import sqlite3
import json
import fitz  # PyMuPDF

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.pdf_service import pdf_service, sanitize_admin_procedure_title, sanitize_document_name


def test_sanitize_admin_procedure_title():
    print("\n--- TEST 1: Sanitize Admin Procedure Title ---")
    test_cases = [
        ("Thủ tục xác định lại diện tích đất ở đã được cấp Số đỏ trước 01/7/2024 tỉnh Tây Ninh như thế nào?",
         "Thủ tục xác định lại diện tích đất ở đã được cấp Số đỏ trước 01/7/2024 tỉnh Tây Ninh"),
        ("Đăng ký thành lập công ty TNHH ra sao?", "Đăng ký thành lập công ty TNHH"),
        ("Cấp đổi giấy phép lái xe hết hạn như thế nào?", "Cấp đổi giấy phép lái xe hết hạn"),
        ("Hồ sơ hưởng bảo hiểm xã hội một lần là gì?", "Hồ sơ hưởng bảo hiểm xã hội một lần"),
        ("Đăng ký kết hôn có yếu tố nước ngoài?", "Đăng ký kết hôn có yếu tố nước ngoài"),
    ]
    for inp, expected in test_cases:
        res = sanitize_admin_procedure_title(inp)
        assert res == expected, f"Failed for '{inp}': got '{res}', expected '{expected}'"
        assert "?" not in res, f"Question mark still in '{res}'"
        assert "như thế nào" not in res.lower(), f"'như thế nào' still in '{res}'"
    print("PASS: Sanitize procedure title successfully eliminated all question phrases.")


def test_database_zero_defect():
    print("\n--- TEST 2: Database Zero-Defect Check (556 Procedures) ---")
    db_path = "data/vinalex.db"
    assert os.path.exists(db_path), f"{db_path} does not exist"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    c.execute("SELECT count(*) FROM procedures WHERE title LIKE '%?' OR title LIKE '%như thế nào%' OR title LIKE '%ra sao%'")
    question_count = c.fetchone()[0]
    assert question_count == 0, f"Found {question_count} question titles remaining in DB"

    c.execute("SELECT count(*) FROM procedures WHERE documents LIKE '%quy định của cơ quan%'")
    generic_count = c.fetchone()[0]
    assert generic_count == 0, f"Found {generic_count} generic doc strings remaining in DB"

    c.execute("SELECT count(*) FROM procedures")
    total_count = c.fetchone()[0]
    assert total_count == 556, f"Expected 556 procedures, got {total_count}"

    conn.close()
    print(f"PASS: 556 procedures verified: 0 question titles, 0 generic dummy strings.")


def test_all_10_statutory_form_templates():
    print("\n--- TEST 3: Generate and Inspect 10 Domain Statutory Form Templates ---")

    test_domains = [
        {
            "name": "1. Biến động đất đai / Xác định lại diện tích (Mẫu 11/ĐK)",
            "doc_name": "Đơn đăng ký biến động đất đai, tài sản gắn liền với đất (Mẫu số 11/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)",
            "title": "Thủ tục xác định lại diện tích đất ở đã được cấp Sổ đỏ trước 01/7/2024 tỉnh Tây Ninh",
            "slug": "thu-tuc-xac-dinh-lai-dien-tich-dat-o",
            "category": "Đất đai - Bất động sản",
            "agency": "Chi nhánh Văn phòng Đăng ký đất đai thị xã Trảng Bàng",
            "expect_keyword": "Mẫu số 11/ĐK",
            "expect_agency": "Chi nhánh Văn phòng Đăng ký đất đai thị xã Trảng Bàng",
            "min_pages": 1,
        },
        {
            "name": "2. Cấp Sổ đỏ lần đầu (Mẫu 04/ĐK 2 trang)",
            "doc_name": "Đơn đăng ký, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất (Mẫu số 04/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)",
            "title": "Thủ tục đăng ký đất đai và cấp Giấy chứng nhận quyền sử dụng đất lần đầu",
            "slug": "cap-giay-chung-nhan-quyen-su-dung-dat-lan-dau",
            "category": "Đất đai - Bất động sản",
            "agency": "Ủy ban nhân dân cấp xã và Chi nhánh VPĐKĐĐ",
            "expect_keyword": "Mẫu số 04/ĐK",
            "expect_agency": "Ủy ban nhân dân cấp xã",
            "min_pages": 2,
        },
        {
            "name": "3. Doanh nghiệp / Hộ kinh doanh (NĐ 01/2021 & TT 02/2023)",
            "doc_name": "Giấy đề nghị đăng ký doanh nghiệp (Ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT)",
            "title": "Đăng ký thành lập công ty TNHH một thành viên",
            "slug": "dang-ky-thanh-lap-cong-ty-tnhh-mot-thanh-vien",
            "category": "Doanh nghiệp",
            "agency": "Phòng Đăng ký kinh doanh - Sở Kế hoạch và Đầu tư",
            "expect_keyword": "GIẤY ĐỀ NGHỊ ĐĂNG KÝ DOANH NGHIỆP",
            "expect_agency": "Sở Kế hoạch và Đầu tư",
            "min_pages": 1,
        },
        {
            "name": "4. Xây dựng (Mẫu 01 Phụ lục II NĐ 15/2021/NĐ-CP)",
            "doc_name": "Đơn đề nghị cấp giấy phép xây dựng nhà ở riêng lẻ (Mẫu số 01 Phụ lục II Nghị định số 15/2021/NĐ-CP)",
            "title": "Cấp giấy phép xây dựng nhà ở riêng lẻ đô thị",
            "slug": "cap-giay-phep-xay-dung-nha-o-rieng-le",
            "category": "Xây dựng",
            "agency": "Ủy ban nhân dân quận/huyện",
            "expect_keyword": "Mẫu số 01 Phụ lục II",
            "expect_agency": "Ủy ban nhân dân quận/huyện",
            "min_pages": 1,
        },
        {
            "name": "5. Giấy phép lái xe (Phụ lục 19 TT 05/2024/TT-BGTVT)",
            "doc_name": "Đơn đề nghị đổi, cấp lại Giấy phép lái xe (Phụ lục 19 ban hành kèm theo Thông tư số 05/2024/TT-BGTVT)",
            "title": "Thủ tục đổi Giấy phép lái xe do ngành Giao thông vận tải cấp",
            "slug": "doi-giay-phep-lai-xe-gplx",
            "category": "Giao thông vận tải",
            "agency": "Sở Giao thông vận tải TP. Hồ Chí Minh",
            "expect_keyword": "Phụ lục 19",
            "expect_agency": "Sở Giao thông vận tải",
            "min_pages": 1,
        },
        {
            "name": "6. Y tế (Nghị định 96/2023/NĐ-CP)",
            "doc_name": "Đơn đề nghị cấp giấy phép hành nghề khám bệnh, chữa bệnh (Ban hành kèm Nghị định số 96/2023/NĐ-CP)",
            "title": "Cấp mới giấy phép hành nghề khám bệnh chữa bệnh đối với bác sĩ",
            "slug": "cap-moi-giay-phep-hanh-nghe-kham-chua-benh",
            "category": "Y tế",
            "agency": "Sở Y tế",
            "expect_keyword": "Nghị định số 96/2023/NĐ-CP",
            "expect_agency": "Sở Y tế",
            "min_pages": 1,
        },
        {
            "name": "7. Bảo hiểm xã hội (Mẫu 14-HSB QĐ 166/QĐ-BHXH)",
            "doc_name": "Đơn đề nghị giải quyết hưởng chế độ bảo hiểm xã hội (Mẫu số 14-HSB ban hành kèm Quyết định 166/QĐ-BHXH)",
            "title": "Thủ tục giải quyết hưởng bảo hiểm xã hội một lần",
            "slug": "giai-quyet-huong-bao-hiem-xa-hoi-mot-lan",
            "category": "Bảo hiểm xã hội",
            "agency": "Bảo hiểm xã hội quận Cầu Giấy",
            "expect_keyword": "Mẫu số 14-HSB",
            "expect_agency": "Bảo hiểm xã hội quận Cầu Giấy",
            "min_pages": 1,
        },
        {
            "name": "8. Thuế (Mẫu 02/QTT-TNCN TT 80/2021/TT-BTC)",
            "doc_name": "Tờ khai quyết toán thuế thu nhập cá nhân (Mẫu số 02/QTT-TNCN ban hành kèm Thông tư số 80/2021/TT-BTC)",
            "title": "Quyết toán thuế thu nhập cá nhân trực tiếp với cơ quan thuế",
            "slug": "quyet-toan-thue-tncn-truc-tiep",
            "category": "Tài chính - Thuế",
            "agency": "Chi cục Thuế khu vực",
            "expect_keyword": "02/QTT-TNCN",
            "expect_agency": "Cơ quan Thuế",
            "min_pages": 1,
        },
        {
            "name": "9. Lao động nước ngoài (Mẫu 09/PLI NĐ 152/2020 & NĐ 70/2023)",
            "doc_name": "Văn bản đề nghị xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động (Mẫu số 09/PLI ban hành kèm Nghị định 152/2020/NĐ-CP và NĐ 70/2023/NĐ-CP)",
            "title": "Xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động",
            "slug": "xac-nhan-khong-thuoc-dien-cap-giay-phep-lao-dong",
            "category": "Lao động - Việc làm",
            "agency": "Sở Lao động - Thương binh và Xã hội",
            "expect_keyword": "Mẫu số 09/PLI",
            "expect_agency": "Sở Lao động",
            "min_pages": 1,
        },
        {
            "name": "10. Phổ quát One-Stop (Nghị định 30/2020/NĐ-CP & NĐ 61/2018/NĐ-CP)",
            "doc_name": "Đơn đề nghị cấp bản sao bằng tốt nghiệp trung học phổ thông",
            "title": "Cấp bản sao văn bằng chứng chỉ từ sổ gốc",
            "slug": "cap-ban-sao-van-bang-chung-chi-tu-so-goc",
            "category": "Giáo dục và Đào tạo",
            "agency": "Sở Giáo dục và Đào tạo tỉnh Tây Ninh",
            "expect_keyword": "Nghị định 30/2020/NĐ-CP",
            "expect_agency": "Sở Giáo dục và Đào tạo tỉnh Tây Ninh",
            "min_pages": 1,
        },
    ]

    for item in test_domains:
        print(f"Testing {item['name']}...")
        pdf_bytes = pdf_service.generate_document_pdf(
            doc_name=item["doc_name"],
            procedure_title=item["title"],
            slug=item["slug"],
            category=item["category"],
            agency=item["agency"],
        )
        assert pdf_bytes and len(pdf_bytes) > 2000, f"PDF byte size too small: {len(pdf_bytes) if pdf_bytes else 0}"

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert doc.page_count >= item["min_pages"], f"Expected >= {item['min_pages']} pages, got {doc.page_count}"

        all_text = ""
        for page_idx in range(doc.page_count):
            all_text += doc[page_idx].get_text()
        all_text = all_text.replace('\xa0', ' ').replace('\xad', '-').replace('\u2013', '-').replace('\u2014', '-')

        # Kiểm tra không còn câu hỏi rác
        assert "?" not in all_text, f"Question mark found in generated PDF for {item['name']}"
        assert "như thế nào" not in all_text.lower(), f"'như thế nào' found in generated PDF for {item['name']}"

        # Kiểm tra từ khóa biểu mẫu chính thức
        assert item["expect_keyword"].lower() in all_text.lower(), f"Keyword '{item['expect_keyword']}' not in text of {item['name']}"

        # Kiểm tra thẩm quyền cơ quan
        if item.get("expect_agency"):
            assert item["expect_agency"].lower() in all_text.lower(), f"Agency '{item['expect_agency']}' not found in {item['name']}"

        p_count = doc.page_count
        doc.close()
        print(f"  -> OK: {p_count} page(s), valid legal references, clean administrative tone.")

    print("\nALL 10 STATUTORY DOMAIN FORMS PASSED WITH FLYING COLORS!")


if __name__ == "__main__":
    test_sanitize_admin_procedure_title()
    test_database_zero_defect()
    test_all_10_statutory_form_templates()
    print("\n[SUCCESS] ALL VERIFICATION CHECKS COMPLETED PERFECTLY.")
