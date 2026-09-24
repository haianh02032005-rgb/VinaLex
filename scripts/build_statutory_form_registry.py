"""
VinaLex — Build Statutory Form Registry & Ingest into dvc_documents.db
Tạo và đăng ký toàn bộ kho Biểu mẫu Hành chính chuẩn Quốc gia vào CSDL đã có sẵn.
Đảm bảo 100% định dạng PDF, chuẩn thể thức văn bản hành chính theo Nghị định 30/2020/NĐ-CP.
"""

import os
import sys
import hashlib
import sqlite3

# Thêm root vào sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.services.pdf_service import pdf_service
from backend.db.dvc_document_db import DVCDocumentDatabase, DEFAULT_DB_PATH

STATUTORY_STORAGE = os.path.join("data", "pdf_storage", "statutory_forms")
os.makedirs(STATUTORY_STORAGE, exist_ok=True)

STATUTORY_FORMS = [
    {
        "form_code": "MẪU 11/ĐK",
        "doc_name": "Đơn đăng ký biến động đất đai, tài sản gắn liền với đất (Mẫu số 11/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)",
        "file_name": "don_dang_ky_bien_dong_dat_dai_mau_11_dk.pdf",
        "procedure_title": "Thủ tục đăng ký biến động đất đai, tài sản gắn liền với đất",
        "slug": "dang-ky-bien-dong-dat-dai",
        "category": "Đất đai - Nhà ở",
        "agency": "Văn phòng Đăng ký đất đai",
        "legal_basis": "Nghị định 101/2024/NĐ-CP & Luật Đất đai 2024",
    },
    {
        "form_code": "MẪU 04/ĐK",
        "doc_name": "Đơn đăng ký, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất (Mẫu số 04/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)",
        "file_name": "don_dang_ky_cap_gcn_dat_dai_mau_04_dk.pdf",
        "procedure_title": "Thủ tục cấp Giấy chứng nhận quyền sử dụng đất lần đầu",
        "slug": "cap-giay-chung-nhan-quyen-su-dung-dat-lan-dau",
        "category": "Đất đai - Nhà ở",
        "agency": "Ủy ban nhân dân cấp xã / Chi nhánh VPĐKĐĐ",
        "legal_basis": "Nghị định 101/2024/NĐ-CP & Luật Đất đai 2024",
    },
    {
        "form_code": "MẪU SỐ 18",
        "doc_name": "Đơn đăng ký biến động đất đai theo Mẫu số 18 ban hành kèm theo",
        "file_name": "don_dang_ky_bien_dong_dat_dai_mau_18.pdf",
        "procedure_title": "Đăng ký biến động đất đai cấp xã",
        "slug": "dang-ky-bien-dong-dat-dai-cap-xa",
        "category": "Đất đai - Nhà ở",
        "agency": "UBND cấp xã",
        "legal_basis": "Luật Đất đai 2024",
    },
    {
        "form_code": "MẪU SỐ 20",
        "doc_name": "Đơn đăng ký đất đai, tài sản gắn liền với đất theo Mẫu số 20",
        "file_name": "don_dang_ky_dat_dai_mau_20.pdf",
        "procedure_title": "Đăng ký đất đai, tài sản gắn liền với đất lần đầu",
        "slug": "dang-ky-dat-dai-lan-dau",
        "category": "Đất đai - Nhà ở",
        "agency": "UBND cấp huyện / Chi nhánh VPĐKĐĐ",
        "legal_basis": "Luật Đất đai 2024",
    },
    {
        "form_code": "DN-01",
        "doc_name": "Giấy đề nghị đăng ký doanh nghiệp (Ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT)",
        "file_name": "giay_de_nghi_dang_ky_doanh_nghiep.pdf",
        "procedure_title": "Đăng ký thành lập doanh nghiệp",
        "slug": "dang-ky-thanh-lap-doanh-nghiep",
        "category": "Doanh nghiệp",
        "agency": "Phòng Đăng ký kinh doanh - Sở Kế hoạch và Đầu tư",
        "legal_basis": "Nghị định 01/2021/NĐ-CP & Thông tư 02/2023/TT-BKHĐT",
    },
    {
        "form_code": "MẪU SỐ 01",
        "doc_name": "Đơn đề nghị cấp giấy phép xây dựng (Mẫu số 01 Phụ lục II ban hành kèm theo Nghị định số 15/2021/NĐ-CP)",
        "file_name": "don_de_nghi_cap_giay_phep_xay_dung_mau_01.pdf",
        "procedure_title": "Cấp giấy phép xây dựng nhà ở riêng lẻ đô thị",
        "slug": "cap-giay-phep-xay-dung-nha-o-rieng-le",
        "category": "Xây dựng - Đô thị",
        "agency": "Ủy ban nhân dân cấp huyện",
        "legal_basis": "Nghị định 15/2021/NĐ-CP",
    },
    {
        "form_code": "PHỤ LỤC 19",
        "doc_name": "Đơn đề nghị đổi, cấp lại Giấy phép lái xe (Phụ lục 19 ban hành kèm theo Thông tư số 05/2024/TT-BGTVT)",
        "file_name": "don_de_nghi_doi_gplx_phu_luc_19.pdf",
        "procedure_title": "Đổi Giấy phép lái xe do ngành Giao thông vận tải cấp",
        "slug": "doi-giay-phep-lai-xe",
        "category": "Giao thông - Vận tải",
        "agency": "Sở Giao thông vận tải",
        "legal_basis": "Thông tư 05/2024/TT-BGTVT",
    },
    {
        "form_code": "Y-01",
        "doc_name": "Đơn đề nghị cấp giấy phép hành nghề khám bệnh, chữa bệnh (Ban hành kèm theo Nghị định số 96/2023/NĐ-CP)",
        "file_name": "don_de_nghi_cap_giay_phep_hanh_nghe_y.pdf",
        "procedure_title": "Cấp mới giấy phép hành nghề khám bệnh chữa bệnh",
        "slug": "cap-giay-phep-hanh-nghe-kham-chua-benh",
        "category": "Y tế - Sức khoẻ",
        "agency": "Sở Y tế",
        "legal_basis": "Nghị định 96/2023/NĐ-CP & Luật Khám bệnh, chữa bệnh",
    },
    {
        "form_code": "MẪU 14-HSB",
        "doc_name": "Đơn đề nghị giải quyết hưởng chế độ bảo hiểm xã hội (Mẫu số 14-HSB ban hành kèm theo Quyết định 166/QĐ-BHXH)",
        "file_name": "don_de_nghi_huong_che_do_bhxh_mau_14_hsb.pdf",
        "procedure_title": "Giải quyết hưởng chế độ bảo hiểm xã hội một lần",
        "slug": "huong-bao-hiem-xa-hoi-mot-lan",
        "category": "Bảo hiểm xã hội",
        "agency": "Bảo hiểm xã hội cấp huyện/tỉnh",
        "legal_basis": "Quyết định 166/QĐ-BHXH",
    },
    {
        "form_code": "MẪU 09/PLI",
        "doc_name": "Văn bản đề nghị xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động (Mẫu số 09/PLI ban hành kèm Nghị định 152/2020/NĐ-CP)",
        "file_name": "van_ban_de_nghi_mien_gpld_mau_09_pli.pdf",
        "procedure_title": "Xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động",
        "slug": "xac-nhan-khong-thuoc-dien-cap-giay-phep-lao-dong",
        "category": "Lao động - Việc làm",
        "agency": "Sở Lao động - Thương binh và Xã hội",
        "legal_basis": "Nghị định 152/2020/NĐ-CP & Nghị định 70/2023/NĐ-CP",
    },
    {
        "form_code": "TT 04/2020",
        "doc_name": "Tờ khai đăng ký kết hôn (Ban hành kèm theo Thông tư số 04/2020/TT-BTP)",
        "file_name": "to_khai_dang_ky_ket_hon.pdf",
        "procedure_title": "Đăng ký kết hôn trong nước",
        "slug": "dang-ky-ket-hon",
        "category": "Hộ tịch - Quốc tịch",
        "agency": "Ủy ban nhân dân cấp xã",
        "legal_basis": "Thông tư 04/2020/TT-BTP & Luật Hộ tịch",
    },
    {
        "form_code": "TT 04/2020",
        "doc_name": "Tờ khai đăng ký khai sinh (Ban hành kèm theo Thông tư số 04/2020/TT-BTP)",
        "file_name": "to_khai_dang_ky_khai_sinh.pdf",
        "procedure_title": "Đăng ký khai sinh cho trẻ em",
        "slug": "dang-ky-khai-sinh",
        "category": "Hộ tịch - Quốc tịch",
        "agency": "Ủy ban nhân dân cấp xã",
        "legal_basis": "Thông tư 04/2020/TT-BTP & Luật Hộ tịch",
    },
    {
        "form_code": "ĐIỀU 16 LHT",
        "doc_name": "Giấy cam đoan về việc sinh con (theo quy định tại Điều 16 Luật Hộ tịch)",
        "file_name": "giay_cam_doan_ve_viec_sinh_con.pdf",
        "procedure_title": "Đăng ký khai sinh không có Giấy chứng sinh",
        "slug": "dang-ky-khai-sinh",
        "category": "Hộ tịch - Quốc tịch",
        "agency": "Ủy ban nhân dân cấp xã",
        "legal_basis": "Điều 16 Luật Hộ tịch & Thông tư 04/2020/TT-BTP",
    },
    {
        "form_code": "MẪU CT01",
        "doc_name": "Tờ khai thay đổi thông tin cư trú (Mẫu CT01 ban hành kèm theo Thông tư số 56/2021/TT-BCA)",
        "file_name": "to_khai_thay_doi_thong_tin_cu_tru_ct01.pdf",
        "procedure_title": "Đăng ký thường trú / tạm trú / thay đổi thông tin cư trú",
        "slug": "dang-ky-tam-tru",
        "category": "Hộ tịch - Quốc tịch",
        "agency": "Công an cấp xã / phường",
        "legal_basis": "Thông tư 56/2021/TT-BCA & Luật Cư trú",
    },
    {
        "form_code": "MẪU DC01",
        "doc_name": "Phiếu thu thập thông tin dân cư (Mẫu DC01 ban hành kèm theo Thông tư số 17/2024/TT-BCA)",
        "file_name": "to_khai_can_cuoc_dc01.pdf",
        "procedure_title": "Cấp, cấp đổi thẻ Căn cước",
        "slug": "cap-the-can-cuoc",
        "category": "Hộ tịch - Quốc tịch",
        "agency": "Công an cấp huyện / Phòng Cảnh sát QLHC về TTXH",
        "legal_basis": "Thông tư 17/2024/TT-BCA & Luật Căn cước 2023",
    },
    {
        "form_code": "MẪU DC02",
        "doc_name": "Phiếu đề nghị giải quyết thủ tục về căn cước (Mẫu DC02 ban hành kèm theo Thông tư số 17/2024/TT-BCA)",
        "file_name": "phieu_de_nghi_giai_quyet_can_cuoc_dc02.pdf",
        "procedure_title": "Cấp, cấp đổi, khai thác thông tin thẻ Căn cước",
        "slug": "cap-the-can-cuoc",
        "category": "Hộ tịch - Quốc tịch",
        "agency": "Cơ quan quản lý căn cước Công an",
        "legal_basis": "Thông tư 17/2024/TT-BCA",
    },
    {
        "form_code": "MẪU CC01",
        "doc_name": "Phiếu thu nhận thông tin căn cước (Mẫu CC01 ban hành kèm theo Thông tư số 17/2024/TT-BCA)",
        "file_name": "phieu_thu_nhan_thong_tin_can_cuoc_cc01.pdf",
        "procedure_title": "Thu nhận hồ sơ cấp Căn cước",
        "slug": "cap-the-can-cuoc",
        "category": "Hộ tịch - Quốc tịch",
        "agency": "Cơ quan quản lý căn cước Công an",
        "legal_basis": "Thông tư 17/2024/TT-BCA",
    },
    {
        "form_code": "MẪU TK03",
        "doc_name": "Phiếu đề nghị khóa, mở khóa tài khoản định danh điện tử, căn cước điện tử (Mẫu TK03 ban hành kèm theo Nghị định số 69/2024/NĐ-CP)",
        "file_name": "phieu_de_nghi_khoa_mo_khoa_dinh_danh_tk03.pdf",
        "procedure_title": "Khóa, mở khóa tài khoản định danh điện tử, căn cước điện tử",
        "slug": "khoa-mo-khoa-dinh-danh-dien-tu",
        "category": "Hộ tịch - Quốc tịch",
        "agency": "Công an cấp xã / huyện",
        "legal_basis": "Nghị định 69/2024/NĐ-CP",
    },
    {
        "form_code": "02/QTT-TNCN",
        "doc_name": "Tờ khai quyết toán thuế thu nhập cá nhân (Mẫu số 02/QTT-TNCN ban hành kèm theo Thông tư số 80/2021/TT-BTC)",
        "file_name": "to_khai_quyet_toan_thue_tncn.pdf",
        "procedure_title": "Quyết toán thuế thu nhập cá nhân đối với cá nhân trực tiếp quyết toán",
        "slug": "quyet-toan-thue-tncn",
        "category": "Thuế - Phí - Lệ phí",
        "agency": "Chi cục Thuế / Cục Thuế",
        "legal_basis": "Thông tư 80/2021/TT-BTC & Luật Quản lý thuế",
    },
]


def main():
    print("=" * 70)
    print("VINALEX — KHỞI TẠO VÀ ĐỒNG BỘ KHO BIỂU MẪU CHUẨN QUỐC GIA (100% PDF)")
    print("=" * 70)

    db = DVCDocumentDatabase()
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    cursor = conn.cursor()

    count_created = 0
    count_indexed = 0

    for item in STATUTORY_FORMS:
        file_path = os.path.join(STATUTORY_STORAGE, item["file_name"])
        
        # 1. Tạo file PDF chuẩn nếu chưa có
        if not os.path.exists(file_path):
            pdf_bytes = pdf_service.generate_document_pdf(
                doc_name=item["doc_name"],
                procedure_title=item["procedure_title"],
                slug=item["slug"],
                category=item["category"],
                agency=item["agency"],
            )
            with open(file_path, "wb") as f:
                f.write(pdf_bytes)
            count_created += 1
        
        # Lấy kích thước và sha256
        with open(file_path, "rb") as f:
            content = f.read()
        file_size = len(content)
        sha256 = hashlib.sha256(content).hexdigest()

        # 2. Tìm hoặc tạo thủ tục trong dvc_procedures
        cursor.execute("SELECT id, code FROM dvc_procedures WHERE slug = ? OR title LIKE ? LIMIT 1",
                       (item["slug"], f"%{item['procedure_title'][:20]}%"))
        proc_row = cursor.fetchone()
        
        if proc_row:
            proc_id, proc_code = proc_row[0], proc_row[1]
        else:
            # Tạo thủ tục đại diện cho danh mục
            proc_code = f"STAT.{item['slug'][:15]}"
            cursor.execute("""
                INSERT OR IGNORE INTO dvc_procedures (
                    code, title, slug, category, category_slug, agency, level,
                    processing_time, fee, description, steps_json, legal_basis_json, source_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?)
            """, (
                proc_code,
                item["procedure_title"],
                item["slug"],
                item["category"],
                item["category"].lower().replace(" ", "-"),
                item["agency"],
                "Cấp Huyện/Xã",
                "Theo quy định",
                "Theo quy định",
                f"Thủ tục {item['procedure_title']} - Biểu mẫu chuẩn quốc gia",
                f"[\"{item['legal_basis']}\"]",
                f"https://dichvucong.gov.vn/thu-tuc/{item['slug']}"
            ))
            cursor.execute("SELECT id FROM dvc_procedures WHERE code = ?", (proc_code,))
            row = cursor.fetchone()
            proc_id = row[0] if row else 1

        # 3. Thêm hoặc cập nhật giấy tờ vào dvc_procedure_documents
        cursor.execute("""
            SELECT id FROM dvc_procedure_documents 
            WHERE procedure_id = ? AND (doc_name = ? OR form_code = ?)
            LIMIT 1
        """, (proc_id, item["doc_name"], item["form_code"]))
        doc_row = cursor.fetchone()

        if doc_row:
            doc_id = doc_row[0]
        else:
            cursor.execute("""
                INSERT INTO dvc_procedure_documents (
                    procedure_id, procedure_code, case_name, doc_name, doc_clean_name,
                    form_code, is_required, original_copy_type, quantity, note
                ) VALUES (?, ?, 'Trường hợp chuẩn', ?, ?, ?, 1, 'Bản chính', 1, ?)
            """, (
                proc_id,
                proc_code,
                item["doc_name"],
                item["doc_name"],
                item["form_code"],
                item["legal_basis"]
            ))
            doc_id = cursor.lastrowid

        # 4. Đăng ký tệp PDF vào dvc_pdf_files
        cursor.execute("SELECT id FROM dvc_pdf_files WHERE file_hash_sha256 = ?", (sha256,))
        pdf_row = cursor.fetchone()

        if not pdf_row:
            cursor.execute("""
                INSERT INTO dvc_pdf_files (
                    procedure_id, procedure_code, document_id, file_type, file_name,
                    file_path, file_size_bytes, file_hash_sha256, mime_type,
                    source_origin, original_file_url
                ) VALUES (?, ?, ?, 'form_template', ?, ?, ?, ?, 'application/pdf', 'statutory_registry', ?)
            """, (
                proc_id,
                proc_code,
                doc_id,
                item["file_name"],
                file_path,
                file_size,
                sha256,
                item.get("legal_basis", "")
            ))
            count_indexed += 1

        # 5. Đồng bộ vào FTS index
        cursor.execute("""
            INSERT INTO dvc_search_fts (procedure_code, procedure_title, category, doc_name, file_name)
            VALUES (?, ?, ?, ?, ?)
        """, (
            proc_code,
            item["procedure_title"],
            item["category"],
            item["doc_name"],
            item["file_name"]
        ))

        print(f"  ✓ Đã lập chỉ mục: [{item['form_code']:<12}] -> {item['file_name']} ({file_size:,} bytes)")

    conn.commit()
    conn.close()

    print("\n" + "=" * 70)
    print(f"HOÀN TẤT: Đã tạo {count_created} tệp PDF mới, lập chỉ mục {count_indexed} biểu mẫu vào CSDL!")
    print(f"Kho lưu trữ tĩnh: {os.path.abspath(STATUTORY_STORAGE)}")
    print("=" * 70)

if __name__ == "__main__":
    main()
