"""
VinaLex — PdfTemplateService: Sinh và quản lý file PDF biểu mẫu hành chính chuẩn pháp lý Việt Nam

Tuân thủ nghiêm ngặt:
- Thể thức văn bản hành chính theo Nghị định số 30/2020/NĐ-CP
- Toàn bộ văn bản hiển thị đơn sắc đen trắng chuẩn in ấn công quyền (color=(0, 0, 0))
- Loại bỏ hoàn toàn từ ngữ thô/rác như [HỒ SƠ / BIỂU MẪU], (NẾU CÓ), (DO BỆNH VIỆN CẤP)...
- Thiết kế bám sát các mẫu biểu thực tế ban hành theo thông tư của Bộ Tư pháp, Bộ Công an, Bộ TN&MT
"""

import os
import re
import unicodedata
from typing import Optional, Tuple
import fitz  # PyMuPDF


def _normalize_str(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để phân loại mẫu form bền vững."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def sanitize_admin_procedure_title(raw_title: str) -> str:
    """
    Làm sạch tiêu đề thủ tục hành chính khi đưa vào văn bản pháp lý / biểu mẫu PDF.
    Tuyệt đối loại bỏ câu hỏi 'như thế nào?', 'ra sao?', dấu '?'...
    """
    if not raw_title:
        return ""
    t = raw_title.strip()
    t = re.sub(r"\?+$", "", t).strip()
    question_endings = [
        r"\s+như\s+thế\s+nào\??$",
        r"\s+nhu\s+the\s+nao\??$",
        r"\s+ra\s+sao\??$",
        r"\s+thế\s+nào\??$",
        r"\s+the\s+nao\??$",
        r"\s+là\s+gì\??$",
        r"\s+la\s+gi\??$",
        r"\s+như\s+thế\s+nào\s+ở\s+đâu\??$",
        r"\s+gồm\s+những\s+gì\??$",
    ]
    for pattern in question_endings:
        t = re.sub(pattern, "", t, flags=re.IGNORECASE).strip()
    return t


def sanitize_document_name(raw_name: str) -> str:
    """
    Làm sạch tên giấy tờ: loại bỏ các ghi chú như (nếu có), (do bệnh viện cấp), (bản sao)...
    nhưng giữ nguyên mã hiệu biểu mẫu chính thống (Mẫu số 11/ĐK, Mẫu số 04/ĐK, Phụ lục...).
    """
    if not raw_name:
        return ""
    clean = raw_name.strip()
    # Loại bỏ các ghi chú trong ngoặc đơn (trừ khi là thông tin biểu mẫu / nghị định)
    clean = re.sub(
        r"\s*\([^)]*(nếu có|nếu cần|bản sao|bản chính|do bệnh viện|do cơ sở|tpct|chứng thực|photo)[^)]*\)",
        "",
        clean,
        flags=re.IGNORECASE
    )
    # Loại bỏ các đuôi không cần thiết
    clean = re.sub(r"\s*[-–—:]\s*(bản sao|bản chính|bản photo).*$", "", clean, flags=re.IGNORECASE)
    # Loại bỏ tiền tố thô
    clean = re.sub(
        r"^(mẫu hồ sơ\s*[/:\-]\s*biểu mẫu|mẫu biểu|biểu mẫu|mẫu hồ sơ|thành phần hồ sơ)\s*[:\-]?\s*",
        "",
        clean,
        flags=re.IGNORECASE
    )
    return clean.strip()


class PdfTemplateService:
    """Dịch vụ tạo và cung cấp file PDF biểu mẫu hành chính chuẩn pháp lý."""

    def __init__(self):
        self._font_path = self._detect_vietnamese_font()

    def _detect_vietnamese_font(self) -> Optional[str]:
        """Tìm font hỗ trợ tiếng Việt trên hệ thống."""
        candidates = [
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _setup_page_fonts(self, doc, page) -> Tuple[str, str, str]:
        """Đăng ký font Times New Roman hoặc font hệ thống Unicode."""
        fontname = "vn_font"
        boldfont = "vn_font_bold"
        italicfont = "vn_font_italic"

        if self._font_path:
            page.insert_font(fontname=fontname, fontfile=self._font_path)
            bold_path = self._font_path.lower().replace(".ttf", "bd.ttf")
            if not os.path.exists(bold_path):
                bold_path = self._font_path
            page.insert_font(fontname=boldfont, fontfile=bold_path)

            italic_path = self._font_path.lower().replace(".ttf", "i.ttf")
            if not os.path.exists(italic_path):
                italic_path = self._font_path
            page.insert_font(fontname=italicfont, fontfile=italic_path)
        else:
            fontname = "helv"
            boldfont = "helv-bold"
            italicfont = "helv-oblique"

        return fontname, boldfont, italicfont

    def _draw_national_header(self, page, boldfont, italicfont, legal_code: str = ""):
        """Vẽ Quốc hiệu, Tiêu ngữ và Ký hiệu mẫu chuẩn Nghị định 30/2020/NĐ-CP."""
        # 1. Ký hiệu mẫu góc trên bên phải (nếu có)
        if legal_code:
            page.insert_text(fitz.Point(280, 36), legal_code, fontname=italicfont, fontsize=8, color=(0, 0, 0))

        # 2. Quốc hiệu - Tiêu ngữ
        c1 = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM"
        c2 = "Độc lập - Tự do - Hạnh phúc"
        page.insert_text(fitz.Point(160, 58), c1, fontname=boldfont, fontsize=12, color=(0, 0, 0))
        page.insert_text(fitz.Point(210, 76), c2, fontname=boldfont, fontsize=12, color=(0, 0, 0))
        # Đường kẻ dưới tiêu ngữ
        page.draw_line(fitz.Point(215, 82), fitz.Point(380, 82), color=(0, 0, 0), width=0.8)

    def _draw_footer(self, page, fontname, page_num: str = ""):
        """Vẽ chân trang chuẩn thể thức công quyền."""
        page.draw_line(fitz.Point(50, 805), fitz.Point(545, 805), color=(0.4, 0.4, 0.4), width=0.5)
        text = "Cổng Thông tin Dịch vụ công & Pháp lý Việt Nam — Văn bản in dùng để nộp tại Bộ phận Một cửa"
        if page_num:
            text = f"{text} — {page_num}"
        page.insert_text(
            fitz.Point(50, 818),
            text,
            fontname=fontname,
            fontsize=8,
            color=(0.3, 0.3, 0.3)
        )

    def generate_document_pdf(
        self,
        doc_name: str = "",
        procedure_title: str = "",
        slug: str = "",
        category: str = "",
        agency: str = "",
        document_name: Optional[str] = None,
        **kwargs
    ) -> bytes:
        """
        Truy xuất file PDF biểu mẫu hành chính chuẩn từ CSDL có sẵn (thay thế cho cơ chế tự vẽ cũ).
        """
        actual_name = doc_name or document_name or ""
        
        # ── ƯU TIÊN TRUY XUẤT TRỰC TIẾP TỪ KHO CSDL ĐÃ CÓ SẴN (100% PDF) ──
        if not agency:
            try:
                from backend.services.document_retrieval_service import document_retrieval_service
                pdf_bytes, _, _ = document_retrieval_service.retrieve_document_pdf(
                    doc_name=actual_name,
                    procedure_title=procedure_title,
                    slug=slug,
                    category=category,
                    agency=agency,
                )
                if pdf_bytes and pdf_bytes.startswith(b"%PDF-"):
                    return pdf_bytes
            except Exception:
                pass

        clean_name = sanitize_document_name(actual_name)
        clean_title = sanitize_admin_procedure_title(procedure_title)

        norm_doc = _normalize_str(clean_name)
        norm_title = _normalize_str(clean_title)
        norm_slug = _normalize_str(slug.replace("-", " "))
        norm_cat = _normalize_str(category)

        full_context = f"{norm_doc} {norm_title} {norm_slug} {norm_cat}"

        doc = fitz.open()

        # 1. BIẾN ĐỘNG ĐẤT ĐAI / XÁC ĐỊNH LẠI DIỆN TÍCH ĐẤT Ở (MẪU 11/ĐK - NĐ 101/2024/NĐ-CP)
        if any(k in full_context for k in [
            "11/dk", "11-dk", "xac dinh lai dien tich", "bien dong dat",
            "chuyen nhuong dat", "thua ke dat", "tang cho dat", "tach thua", "hop thua", "cap doi so do"
        ]):
            return self._build_land_change_form_11_dk(doc, clean_name, clean_title, agency)

        # 2. CẤP GCN ĐẤT ĐAI LẦN ĐẦU / ĐĂNG KÝ ĐẤT ĐAI (MẪU 04/ĐK - NĐ 101/2024/NĐ-CP)
        elif any(k in full_context for k in [
            "04/dk", "04-dk", "cap giay chung nhan", "dang ky dat dai", "so do", "so hong", "dat o"
        ]) and any(k in full_context for k in ["dat", "dia chinh", "so do", "nha o"]):
            return self._build_land_form(doc, clean_name, clean_title, agency)

        # 3. DOANH NGHIỆP & HỘ KINH DOANH (NĐ 01/2021 & TT 02/2023/TT-BKHĐT)
        elif any(k in full_context for k in [
            "doanh nghiep", "cong ty", "ho kinh doanh", "bkhdt", "phu luc i-2", "phu luc i-3", "phu luc i-4", "phu luc iii-1"
        ]):
            return self._build_business_reg_form(doc, clean_name, clean_title, agency)

        # 4. GIẤY PHÉP XÂY DỰNG (MẪU SỐ 01 PHỤ LỤC II - NĐ 15/2021/NĐ-CP)
        elif any(k in full_context for k in [
            "xay dung", "gpxd", "giay phep xay dung", "nha o rieng le", "cong trinh xay dung"
        ]):
            return self._build_construction_permit_form(doc, clean_name, clean_title, agency)

        # 5. GIẤY PHÉP LÁI XE (PHỤ LỤC 19 - TT 05/2024/TT-BGTVT)
        elif any(k in full_context for k in [
            "giay phep lai xe", "gplx", "bang lai", "phu luc 19", "doi gplx", "cap lai gplx", "bgtvt"
        ]):
            return self._build_driver_license_form(doc, clean_name, clean_title, agency)

        # 6. Y TẾ & KHÁM CHỮA BỆNH (NĐ 96/2023/NĐ-CP)
        elif any(k in full_context for k in [
            "kham benh", "chua benh", "hanh nghe y", "chung chi hanh nghe y", "phong kham", "co so kham chua benh"
        ]):
            return self._build_healthcare_permit_form(doc, clean_name, clean_title, agency)

        # 7. BẢO HIỂM XÃ HỘI (MẪU 14-HSB - QĐ 166/QĐ-BHXH & QĐ 899)
        elif any(k in full_context for k in [
            "bao hiem xa hoi", "bhxh", "14-hsb", "tk1-ts", "bhxh mot lan", "che do tuat", "tro cap thai san"
        ]):
            return self._build_social_insurance_form(doc, clean_name, clean_title, agency)

        # 8. HỘ TỊCH: KẾT HÔN, KHAI SINH, KHAI TỬ (TT 04/2020/TT-BTP)
        elif "ket hon" in full_context:
            return self._build_marriage_form(doc, clean_name, clean_title)
        elif any(k in norm_doc for k in ["chung sinh", "cam doan", "sinh con"]) or any(k in full_context for k in ["chung sinh", "cam doan"]):
            return self._build_birth_affirmation_form(doc, clean_name, clean_title)
        elif "khai sinh" in full_context:
            return self._build_birth_form(doc, clean_name, clean_title)

        # 9. CƯ TRÚ (CT01, CT07 - TT 56/2021/TT-BCA)
        elif any(k in full_context for k in ["cu tru", "ho khau", "tam tru", "thuong tru", "ct01", "ct07"]):
            return self._build_residence_form(doc, clean_name, clean_title)

        # 10. CĂN CƯỚC (DC01 - TT 17/2024/TT-BCA)
        elif any(k in full_context for k in ["can cuoc", "cccd", "dinh danh", "cmnd", "dc01"]):
            return self._build_identity_form(doc, clean_name, clean_title)

        # 11. THUẾ (MẪU 02/QTT-TNCN & TT 80/2021/TT-BTC)
        elif any(k in full_context for k in ["thue", "qtt", "02/qtt", "tncn", "khau tru thue", "giam tru gia canh"]):
            return self._build_tax_form(doc, clean_name, clean_title)

        # 12. LAO ĐỘNG (GPLĐ MẪU 09/PLI & MẪU 11/PLI - NĐ 152/2020 & NĐ 70/2023)
        elif any(k in full_context for k in ["lao dong", "giay phep lao dong", "gpld", "nguoi nuoc ngoai"]):
            return self._build_work_permit_exemption_form(doc, clean_name, clean_title)

        # 13. MẪU ĐƠN PHỔ QUÁT CHUẨN NGHỊ ĐỊNH 30/2020/NĐ-CP & NGHỊ ĐỊNH 61/2018/NĐ-CP
        else:
            return self._build_general_form(doc, clean_name, clean_title, agency)

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 1: TỜ KHAI ĐĂNG KÝ KẾT HÔN (Thông tư số 04/2020/TT-BTP)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_marriage_form(self, doc, doc_name: str, procedure_title: str) -> bytes:
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Mẫu ban hành kèm theo Thông tư số 04/2020/TT-BTP"
        )

        # Tiêu đề
        page.insert_text(fitz.Point(175, 115), "TỜ KHAI ĐĂNG KÝ KẾT HÔN", fontname=boldfont, fontsize=14, color=(0, 0, 0))
        page.insert_text(fitz.Point(100, 138), "Kính gửi: Ủy ban nhân dân ..........................................................................................", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))

        # Khung phân định 2 bên Nam - Nữ song song theo đúng thực tế
        page.draw_rect(fitz.Rect(50, 155, 545, 575), color=(0, 0, 0), width=0.8)
        # Cột giữa
        page.draw_line(fitz.Point(297, 155), fitz.Point(297, 575), color=(0, 0, 0), width=0.8)
        # Header hàng
        page.draw_line(fitz.Point(50, 180), fitz.Point(545, 180), color=(0, 0, 0), width=0.8)

        page.insert_text(fitz.Point(145, 172), "BÊN NAM", fontname=boldfont, fontsize=11, color=(0, 0, 0))
        page.insert_text(fitz.Point(395, 172), "BÊN NỮ", fontname=boldfont, fontsize=11, color=(0, 0, 0))

        rows_nam = [
            ("Họ, chữ đệm, tên:", ".................................................................."),
            ("Ngày, tháng, năm sinh:", "....... / ....... / ................."),
            ("Dân tộc:", "...........................  Quốc tịch: Việt Nam"),
            ("Nơi cư trú:", ".................................................................."),
            ("", ".................................................................."),
            ("Giấy tờ tùy thân:", "Số CCCD / Hộ chiếu: ..............................."),
            ("Ngày cấp:", "......./......./........... Nơi cấp: .........................."),
            ("Tình trạng hôn nhân:", "Chưa đăng ký kết hôn lần nào"),
            ("Kết hôn lần thứ:", "......."),
        ]

        rows_nu = [
            ("Họ, chữ đệm, tên:", ".................................................................."),
            ("Ngày, tháng, năm sinh:", "....... / ....... / ................."),
            ("Dân tộc:", "...........................  Quốc tịch: Việt Nam"),
            ("Nơi cư trú:", ".................................................................."),
            ("", ".................................................................."),
            ("Giấy tờ tùy thân:", "Số CCCD / Hộ chiếu: ..............................."),
            ("Ngày cấp:", "......./......./........... Nơi cấp: .........................."),
            ("Tình trạng hôn nhân:", "Chưa đăng ký kết hôn lần nào"),
            ("Kết hôn lần thứ:", "......."),
        ]

        y = 202
        for label, line in rows_nam:
            if label:
                page.insert_text(fitz.Point(58, y), label, fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
                y += 18
            page.insert_text(fitz.Point(58, y), line, fontname=fontname, fontsize=9.5, color=(0, 0, 0))
            y += 24

        y = 202
        for label, line in rows_nu:
            if label:
                page.insert_text(fitz.Point(305, y), label, fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
                y += 18
            page.insert_text(fitz.Point(305, y), line, fontname=fontname, fontsize=9.5, color=(0, 0, 0))
            y += 24

        # Cam đoan
        y = 595
        page.insert_text(
            fitz.Point(50, y),
            "Chúng tôi cam đoan việc kết hôn này là hoàn toàn tự nguyện, không bị ép buộc, không vi phạm",
            fontname=fontname, fontsize=9.5, color=(0, 0, 0)
        )
        page.insert_text(
            fitz.Point(50, y + 16),
            "các quy định cấm kết hôn của Luật Hôn nhân và Gia đình. Chúng tôi xin chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=9.5, color=(0, 0, 0)
        )

        # Chữ ký 2 bên
        y += 45
        page.insert_text(fitz.Point(330, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=9.5, color=(0, 0, 0))
        y += 18
        page.insert_text(fitz.Point(120, y), "BÊN NAM", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(380, y), "BÊN NỮ", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(105, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))
        page.insert_text(fitz.Point(365, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 2: TỜ KHAI ĐĂNG KÝ KHAI SINH (Thông tư số 04/2020/TT-BTP)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_birth_form(self, doc, doc_name: str, procedure_title: str) -> bytes:
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Mẫu ban hành kèm theo Thông tư số 04/2020/TT-BTP"
        )

        page.insert_text(fitz.Point(165, 115), "TỜ KHAI ĐĂNG KÝ KHAI SINH", fontname=boldfont, fontsize=14, color=(0, 0, 0))
        page.insert_text(fitz.Point(80, 138), "Kính gửi: Ủy ban nhân dân ..........................................................................................", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))

        y = 165
        page.insert_text(fitz.Point(50, y), "I. THÔNG TIN NGƯỜI YÊU CẦU ĐĂNG KÝ KHAI SINH", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 18
        p_lines = [
            "Họ, chữ đệm, tên người yêu cầu: ............................................................................................................",
            "Nơi cư trú: ................................................................................................................................................",
            "Giấy tờ tùy thân (Số CCCD/Hộ chiếu): ............................................  Quan hệ với người được khai sinh: .........",
        ]
        for line in p_lines:
            page.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=9.5, color=(0, 0, 0))
            y += 19

        y += 8
        page.insert_text(fitz.Point(50, y), "II. THÔNG TIN NGƯỜI ĐƯỢC KHAI SINH", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 18
        c_lines = [
            "Họ, chữ đệm, tên (chữ in hoa): .............................................................................................................",
            "Ngày, tháng, năm sinh: ....... / ....... / ....................  (Ghi bằng chữ: .........................................................)",
            "Giới tính:  [   ] Nam       [   ] Nữ                  Dân tộc: .............................  Quốc tịch: Việt Nam",
            "Nơi sinh (Cơ sở y tế/Bệnh viện): .........................................................................................................",
            "Quê quán: .................................................................................................................................................",
        ]
        for line in c_lines:
            page.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=9.5, color=(0, 0, 0))
            y += 19

        y += 8
        page.insert_text(fitz.Point(50, y), "III. THÔNG TIN CHA, MẸ", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 18
        m_lines = [
            "Họ, chữ đệm, tên người mẹ: ........................................................  Năm sinh: .........................................",
            "Dân tộc: ...........................  Quốc tịch: Việt Nam            Số CCCD/Định danh: .........................................",
            "Nơi cư trú: ................................................................................................................................................",
            "Họ, chữ đệm, tên người cha: ........................................................  Năm sinh: .........................................",
            "Dân tộc: ...........................  Quốc tịch: Việt Nam            Số CCCD/Định danh: .........................................",
            "Nơi cư trú: ................................................................................................................................................",
        ]
        for line in m_lines:
            page.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=9.5, color=(0, 0, 0))
            y += 19

        y += 10
        page.insert_text(
            fitz.Point(50, y),
            "Tôi cam đoan những thông tin đã khai trên đây là đúng sự thật và chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=9.5, color=(0, 0, 0)
        )

        y += 35
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=9.5, color=(0, 0, 0))
        y += 18
        page.insert_text(fitz.Point(365, y), "NGƯỜI YÊU CẦU", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(360, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 3: GIẤY CAM ĐOAN VỀ VIỆC SINH CON (Thay thế Giấy chứng sinh khi nộp hồ sơ)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_birth_affirmation_form(self, doc, doc_name: str, procedure_title: str) -> bytes:
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Áp dụng theo Điều 16 Luật Hộ tịch & TT 04/2020/TT-BTP"
        )

        page.insert_text(fitz.Point(145, 115), "VĂN BẢN CAM ĐOAN VỀ VIỆC SINH CON", fontname=boldfont, fontsize=13.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(110, 134), "(Dùng trong trường hợp trẻ sinh ra ngoài cơ sở y tế hoặc không có Giấy chứng sinh)", fontname=italicfont, fontsize=9, color=(0, 0, 0))
        page.insert_text(fitz.Point(80, 155), "Kính gửi: Ủy ban nhân dân ..........................................................................................", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))

        y = 185
        page.insert_text(fitz.Point(50, y), "1. THÔNG TIN NGƯỜI CAM ĐOAN:", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 20
        fields = [
            "Họ và tên người cam đoan: ................................................................................................................",
            "Ngày, tháng, năm sinh: ....... / ....... / ....................  Số định danh cá nhân / CCCD: ...........................",
            "Nơi thường trú: ...................................................................................................................................",
            "Quan hệ với trẻ được sinh: .................................................................................................................",
        ]
        for f in fields:
            page.insert_text(fitz.Point(60, y), f, fontname=fontname, fontsize=9.5, color=(0, 0, 0))
            y += 20

        y += 10
        page.insert_text(fitz.Point(50, y), "2. NỘI DUNG CAM ĐOAN VỀ SỰ KIỆN SINH:", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 20
        events = [
            "Vào lúc: ...... giờ ...... phút, ngày ....... tháng ....... năm ............",
            "Tại địa chỉ: .........................................................................................................................................",
            "Bà: ................................................................................... đã sinh một người con, cụ thể:",
            "- Họ và tên dự kiến khai sinh cho trẻ: .................................................................................................",
            "- Giới tính:  [   ] Nam       [   ] Nữ",
            "- Cân nặng khi sinh (nếu biết): ................. kg",
            "- Tình trạng sức khỏe hiện tại của mẹ và trẻ: ......................................................................................",
            "Lý do không có Giấy chứng sinh từ cơ sở y tế: .................................................................................",
            "............................................................................................................................................................"
        ]
        for e in events:
            page.insert_text(fitz.Point(60, y), e, fontname=fontname, fontsize=9.5, color=(0, 0, 0))
            y += 20

        y += 10
        page.insert_text(
            fitz.Point(50, y),
            "Tôi xin cam đoan sự việc sinh con nêu trên là hoàn toàn đúng sự thật. Nếu có gian dối, tôi xin chịu",
            fontname=fontname, fontsize=9.5, color=(0, 0, 0)
        )
        page.insert_text(
            fitz.Point(50, y + 16),
            "hoàn toàn trách nhiệm trước pháp luật về hành vi khai báo không trung thực.",
            fontname=fontname, fontsize=9.5, color=(0, 0, 0)
        )

        y += 45
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=9.5, color=(0, 0, 0))
        y += 18
        page.insert_text(fitz.Point(90, y), "NGƯỜI LÀM CHỨNG (NẾU CÓ)", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        page.insert_text(fitz.Point(365, y), "NGƯỜI CAM ĐOAN", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(105, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))
        page.insert_text(fitz.Point(360, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 4: TỜ KHAI THAY ĐỔI THÔNG TIN CƯ TRÚ (MẪU CT01 - Thông tư 56/2021/TT-BCA)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_residence_form(self, doc, doc_name: str, procedure_title: str) -> bytes:
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Mẫu CT01 ban hành kèm theo TT số 56/2021/TT-BCA"
        )

        page.insert_text(fitz.Point(125, 115), "TỜ KHAI THAY ĐỔI THÔNG TIN CƯ TRÚ", fontname=boldfont, fontsize=14, color=(0, 0, 0))
        page.insert_text(fitz.Point(100, 138), "Kính gửi: Công an ........................................................................................................", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))

        y = 168
        page.insert_text(fitz.Point(50, y), "1. Họ, chữ đệm và tên người kê khai: ............................................................................................", fontname=fontname, fontsize=9.5, color=(0, 0, 0))
        y += 20
        page.insert_text(fitz.Point(50, y), "2. Ngày, tháng, năm sinh: ....... / ....... / ....................      3. Giới tính:  [   ] Nam      [   ] Nữ", fontname=fontname, fontsize=9.5, color=(0, 0, 0))
        y += 20
        page.insert_text(fitz.Point(50, y), "4. Số định danh cá nhân / Số CCCD: ..........................................  5. Điện thoại: ................................", fontname=fontname, fontsize=9.5, color=(0, 0, 0))
        y += 20
        page.insert_text(fitz.Point(50, y), "6. Nơi thường trú: ................................................................................................................................", fontname=fontname, fontsize=9.5, color=(0, 0, 0))
        y += 20
        page.insert_text(fitz.Point(50, y), "7. Nơi ở hiện tại: ...................................................................................................................................", fontname=fontname, fontsize=9.5, color=(0, 0, 0))
        y += 20
        page.insert_text(fitz.Point(50, y), "8. Họ tên chủ hộ: ..........................................................  Quan hệ với chủ hộ: ....................................", fontname=fontname, fontsize=9.5, color=(0, 0, 0))
        y += 20
        page.insert_text(fitz.Point(50, y), "9. Nội dung đề nghị: Đăng ký thường trú / Tạm trú / Thay đổi thông tin cư trú vào nơi ở hợp pháp:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 18
        page.insert_text(fitz.Point(60, y), "Địa chỉ: ............................................................................................................................................", fontname=fontname, fontsize=9.5, color=(0, 0, 0))
        y += 20
        page.insert_text(fitz.Point(60, y), "Lý do: ...............................................................................................................................................", fontname=fontname, fontsize=9.5, color=(0, 0, 0))

        y += 25
        page.insert_text(fitz.Point(50, y), "10. Những người cùng thay đổi thông tin cư trú (nếu có):", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        # Kẻ bảng danh sách thành viên
        page.draw_rect(fitz.Rect(50, y, 545, y + 100), color=(0, 0, 0), width=0.7)
        page.draw_line(fitz.Point(50, y + 22), fitz.Point(545, y + 22), color=(0, 0, 0), width=0.7)
        page.draw_line(fitz.Point(85, y), fitz.Point(85, y + 100), color=(0, 0, 0), width=0.7)
        page.draw_line(fitz.Point(240, y), fitz.Point(240, y + 100), color=(0, 0, 0), width=0.7)
        page.draw_line(fitz.Point(340, y), fitz.Point(340, y + 100), color=(0, 0, 0), width=0.7)
        page.draw_line(fitz.Point(440, y), fitz.Point(440, y + 100), color=(0, 0, 0), width=0.7)

        page.insert_text(fitz.Point(55, y + 15), "STT", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(120, y + 15), "Họ và tên", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(260, y + 15), "Ngày sinh", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(355, y + 15), "Số định danh/CCCD", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(455, y + 15), "Quan hệ với người khai", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))

        y += 115
        page.insert_text(
            fitz.Point(50, y),
            "Tôi xin cam đoan những lời khai trên là đúng sự thật và chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=9.5, color=(0, 0, 0)
        )

        y += 35
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=9.5, color=(0, 0, 0))
        y += 18
        page.insert_text(fitz.Point(80, y), "Ý KIẾN CỦA CHỦ HỘ", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        page.insert_text(fitz.Point(365, y), "NGƯỜI KÊ KHAI", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(85, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))
        page.insert_text(fitz.Point(360, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 5: TỜ KHAI CĂN CƯỚC (Theo Luật Căn cước số 26/2023/QH15)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_identity_form(self, doc, doc_name: str, procedure_title: str) -> bytes:
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Áp dụng theo Luật Căn cước số 26/2023/QH15"
        )

        page.insert_text(fitz.Point(180, 115), "TỜ KHAI CĂN CƯỚC", fontname=boldfont, fontsize=14, color=(0, 0, 0))
        page.insert_text(fitz.Point(100, 138), "Kính gửi: Cơ quan quản lý căn cước Công an .............................................................", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))

        y = 170
        fields = [
            "1. Họ, chữ đệm và tên (chữ in hoa): .....................................................................................................",
            "2. Ngày, tháng, năm sinh: ....... / ....... / ....................      3. Giới tính:  [   ] Nam      [   ] Nữ",
            "4. Số định danh cá nhân (nếu đã có): ...................................................................................................",
            "5. Dân tộc: ....................................................   6. Quốc tịch: Việt Nam",
            "7. Quê quán: .........................................................................................................................................",
            "8. Nơi thường trú: ...................................................................................................................................",
            "9. Nơi tạm trú / Nơi ở hiện tại: .................................................................................................................",
            "10. Họ tên cha: ................................................................... Số định danh: ...........................................",
            "11. Họ tên mẹ: ................................................................... Số định danh: ...........................................",
            "12. Yêu cầu:   [   ] Cấp lần đầu         [   ] Cấp đổi         [   ] Cấp lại thẻ căn cước",
            "13. Lý do cấp đổi/cấp lại (nếu có): ........................................................................................................",
        ]
        for f in fields:
            page.insert_text(fitz.Point(50, y), f, fontname=fontname, fontsize=9.5, color=(0, 0, 0))
            y += 22

        y += 15
        page.insert_text(
            fitz.Point(50, y),
            "Tôi xin cam đoan những thông tin kê khai trên là hoàn toàn chính xác và chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=9.5, color=(0, 0, 0)
        )

        y += 45
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=9.5, color=(0, 0, 0))
        y += 18
        page.insert_text(fitz.Point(85, y), "CÁN BỘ TIẾP NHẬN", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        page.insert_text(fitz.Point(365, y), "NGƯỜI KÊ KHAI", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(80, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))
        page.insert_text(fitz.Point(360, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=9, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 6A: ĐƠN ĐĂNG KÝ BIẾN ĐỘNG ĐẤT ĐAI (MẪU SỐ 11/ĐK - NĐ 101/2024/NĐ-CP)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_land_change_form_11_dk(self, doc, doc_name: str, procedure_title: str, agency: str = "") -> bytes:
        """
        MẪU SỐ 11/ĐK: ĐƠN ĐĂNG KÝ BIẾN ĐỘNG ĐẤT ĐAI, TÀI SẢN GẮN LIỀN VỚI ĐẤT
        Ban hành kèm theo Nghị định số 101/2024/NĐ-CP ngày 29/7/2024 của Chính phủ (áp dụng Luật Đất đai 2024).
        Áp dụng chuẩn xác cho:
        - Thủ tục xác định lại diện tích đất ở đã được cấp Sổ đỏ
        - Chuyển quyền, chuyển nhượng, tặng cho, thừa kế, cấp đổi, tách thửa, hợp thửa
        """
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Mẫu số 11/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP"
        )

        clean_p_title = sanitize_admin_procedure_title(procedure_title)

        page.insert_text(fitz.Point(75, 112), "ĐƠN ĐĂNG KÝ BIẾN ĐỘNG ĐẤT ĐAI,", fontname=boldfont, fontsize=13, color=(0, 0, 0))
        page.insert_text(fitz.Point(120, 128), "TÀI SẢN GẮN LIỀN VỚI ĐẤT", fontname=boldfont, fontsize=13, color=(0, 0, 0))

        if clean_p_title:
            page.insert_text(fitz.Point(75, 144), f"(Áp dụng thủ tục: {clean_p_title})", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))

        target_agency = agency if agency else "Chi nhánh Văn phòng Đăng ký đất đai / UBND cấp có thẩm quyền"
        page.insert_text(fitz.Point(60, 162), f"Kính gửi: {target_agency}", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 184
        page.insert_text(fitz.Point(50, y), "I. THÔNG TIN NGƯỜI SỬ DỤNG ĐẤT, CHỦ SỞ HỮU TÀI SẢN:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        fields_1 = [
            "1. Tên người sử dụng đất, chủ sở hữu (cá nhân/hộ gia đình): .........................................................................",
            "2. Số định danh cá nhân / CCCD / MST: ........................................... Ngày cấp: ......./......./........ Nơi cấp: .............",
            "3. Địa chỉ thường trú/trụ sở: .............................................................................................................................",
            "4. Số điện thoại liên hệ: ............................................................. Email: ..........................................................",
        ]
        for f in fields_1:
            page.insert_text(fitz.Point(60, y), f, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "II. THÔNG TIN THỬA ĐẤT VÀ GIẤY CHỨNG NHẬN ĐÃ CẤP:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        fields_2 = [
            "1. Thửa đất số: ..........................................................  Tờ bản đồ số: ....................................................",
            "2. Địa chỉ thửa đất: .............................................................................................................................",
            "3. Giấy chứng nhận đã cấp: Số phát hành (seri): .................................... Số vào sổ cấp GCN: ..........................",
            "   Ngày cấp: ....... / ....... / ....................  Cơ quan cấp: ............................................................................",
        ]
        for f in fields_2:
            page.insert_text(fitz.Point(60, y), f, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "III. NỘI DUNG BIẾN ĐỘNG ĐỀ NGHỊ ĐĂNG KÝ:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 14

        # Kẻ bảng so sánh 3 cột: Nội dung trên GCN đã cấp - Nội dung thay đổi đề nghị - Lý do biến động
        tbl_top = y
        tbl_bot = y + 90
        page.draw_rect(fitz.Rect(50, tbl_top, 545, tbl_bot), color=(0, 0, 0), width=0.8)
        # Header line
        page.draw_line(fitz.Point(50, tbl_top + 22), fitz.Point(545, tbl_top + 22), color=(0, 0, 0), width=0.8)
        # Vertical split lines
        page.draw_line(fitz.Point(215, tbl_top), fitz.Point(215, tbl_bot), color=(0, 0, 0), width=0.5)
        page.draw_line(fitz.Point(380, tbl_top), fitz.Point(380, tbl_bot), color=(0, 0, 0), width=0.5)

        page.insert_text(fitz.Point(65, tbl_top + 15), "Nội dung trên GCN đã cấp", fontname=boldfont, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(230, tbl_top + 15), "Nội dung đề nghị biến động", fontname=boldfont, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(400, tbl_top + 15), "Lý do biến động / Căn cứ", fontname=boldfont, fontsize=8, color=(0, 0, 0))

        # Dòng trong bảng
        r_y = tbl_top + 36
        page.insert_text(fitz.Point(55, r_y), "- Diện tích đất ở: .............. m2", fontname=fontname, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(220, r_y), "- Xác định lại diện tích đất ở", fontname=fontname, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(385, r_y), "- Theo Điều 141 Luật Đất đai", fontname=fontname, fontsize=8, color=(0, 0, 0))

        r_y += 14
        page.insert_text(fitz.Point(55, r_y), "- Đất nông nghiệp: ........... m2", fontname=fontname, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(220, r_y), "  thành: ....................... m2", fontname=fontname, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(385, r_y), "  năm 2024 & NĐ 101/2024/NĐ-CP", fontname=fontname, fontsize=8, color=(0, 0, 0))

        r_y += 14
        page.insert_text(fitz.Point(55, r_y), "- Mục đích: .........................", fontname=fontname, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(220, r_y), "- Đề nghị cấp đổi sang GCN mới", fontname=fontname, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(385, r_y), "- Đã nộp đủ hồ sơ theo quy định", fontname=fontname, fontsize=8, color=(0, 0, 0))

        y = tbl_bot + 12
        page.insert_text(fitz.Point(50, y), "IV. GIẤY TỜ NỘP KÈM THEO:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 15
        att = [
            "[ x ] Bản gốc Giấy chứng nhận quyền sử dụng đất đã cấp",
            "[ x ] Trích đo địa chính thửa đất / Bản đồ hiện trạng vị trí thửa đất",
            "[ x ] Bản sao Căn cước công dân của người sử dụng đất",
            "[ x ] Giấy tờ chứng minh việc hình thành và sử dụng đất trước ngày 15/10/1993 hoặc 01/7/2004",
        ]
        for a in att:
            page.insert_text(fitz.Point(60, y), a, fontname=fontname, fontsize=8, color=(0, 0, 0))
            y += 14

        y += 6
        page.insert_text(
            fitz.Point(50, y),
            "Tôi cam đoan thông tin kê khai trên là trung thực, đúng sự thật và hoàn toàn chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=8, color=(0, 0, 0)
        )

        y += 24
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(70, y), "Ý KIẾN CỦA CHI NHÁNH VP ĐĂNG KÝ ĐẤT ĐAI", fontname=boldfont, fontsize=9, color=(0, 0, 0))
        page.insert_text(fitz.Point(365, y), "NGƯỜI KÊ KHAI ĐƠN", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 12
        page.insert_text(fitz.Point(60, y), "(Đủ điều kiện đăng ký biến động vào hồ sơ địa chính)", fontname=italicfont, fontsize=7.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(360, y), "(Ký, ghi rõ họ và tên)", fontname=italicfont, fontsize=8, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(115, y), "GIÁM ĐỐC / THẨM ĐỊNH", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(105, y + 12), "(Ký tên, đóng dấu xác nhận)", fontname=italicfont, fontsize=7.5, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 6B: ĐƠN ĐĂNG KÝ, CẤP GCN ĐẤT ĐAI (MẪU 04/ĐK - NĐ 101/2024/NĐ-CP CHUẨN 2 TRANG)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_land_form(self, doc, doc_name: str, procedure_title: str, agency: str = "") -> bytes:
        """
        MẪU SỐ 04/ĐK: ĐƠN ĐĂNG KÝ, CẤP GIẤY CHỨNG NHẬN QUYỀN SỬ DỤNG ĐẤT, QUYỀN SỞ HỮU TÀI SẢN GẮN LIỀN VỚI ĐẤT
        Ban hành kèm theo Nghị định số 101/2024/NĐ-CP ngày 29/7/2024 của Chính phủ (áp dụng Luật Đất đai 2024).
        Biểu mẫu hoàn chỉnh chuẩn hóa 02 trang bao gồm đầy đủ ý kiến xác nhận của UBND cấp xã và thẩm tra của VPĐKĐĐ.
        """
        clean_p_title = sanitize_admin_procedure_title(procedure_title)
        target_agency = agency if agency else "Ủy ban nhân dân cấp xã / Chi nhánh Văn phòng Đăng ký đất đai"

        # ── TRANG 1 ──
        page1 = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page1)

        self._draw_national_header(
            page1, boldfont, italicfont,
            legal_code="Mẫu số 04/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP"
        )

        page1.insert_text(fitz.Point(70, 108), "ĐƠN ĐĂNG KÝ, CẤP GIẤY CHỨNG NHẬN QUYỀN SỬ DỤNG ĐẤT,", fontname=boldfont, fontsize=12, color=(0, 0, 0))
        page1.insert_text(fitz.Point(120, 124), "QUYỀN SỞ HỮU TÀI SẢN GẮN LIỀN VỚI ĐẤT", fontname=boldfont, fontsize=12, color=(0, 0, 0))
        if clean_p_title:
            page1.insert_text(fitz.Point(70, 139), f"(Áp dụng hoàn thiện thủ tục: {clean_p_title})", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        page1.insert_text(fitz.Point(60, 156), f"Kính gửi: {target_agency}", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 176
        page1.insert_text(fitz.Point(50, y), "I. THÔNG TIN NGƯỜI SỬ DỤNG ĐẤT, CHỦ SỞ HỮU TÀI SẢN:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        p_lines = [
            "1. Tên người sử dụng đất (cá nhân/vợ chồng/hộ gia đình/tổ chức): .........................................................................",
            "2. Năm sinh: ....................  Số định danh cá nhân / CCCD / MST: .....................................................................",
            "3. Địa chỉ thường trú: ............................................................................................................................................",
            "4. Số điện thoại liên hệ: .............................................................  Email: .........................................................",
        ]
        for line in p_lines:
            page1.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page1.insert_text(fitz.Point(50, y), "II. THỬA ĐẤT ĐĂNG KÝ CẤP GIẤY CHỨNG NHẬN:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        l_lines = [
            "1. Thửa đất số: ..........................................................  Tờ bản đồ số: ....................................................",
            "2. Địa chỉ thửa đất: .............................................................................................................................",
            "3. Diện tích đăng ký: .................... m² (Bằng chữ: .............................................................................................)",
            "4. Mục đích sử dụng đất: [   ] Đất ở nông thôn (ONT)    [   ] Đất ở đô thị (ODT)    [   ] Đất trồng cây lâu năm",
            "5. Thời hạn sử dụng đất: [   ] Ổn định lâu dài          [   ] Đến ngày: ...... / ...... / ....................",
            "6. Nguồn gốc sử dụng đất: [   ] Được Nhà nước giao        [   ] Nhận chuyển nhượng        [   ] Thừa kế / Tặng cho",
            "   [   ] Tự khai hoang, sử dụng ổn định từ ngày: ....... / ....... / ............. (Trước ngày 01/7/2014)",
        ]
        for line in l_lines:
            page1.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page1.insert_text(fitz.Point(50, y), "III. TÀI SẢN GẮN LIỀN VỚI ĐẤT:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        prop_lines = [
            "1. Nhà ở: Loại nhà: [   ] Nhà riêng lẻ    [   ] Biệt thự        Diện tích xây dựng: .................... m²",
            "   Tổng diện tích sàn: .................... m²      Kết cấu: ........................................  Số tầng: ....................",
            "2. Công trình xây dựng khác (nếu có): ..........................................................................................................",
            "3. Rừng sản xuất là rừng trồng / Cây lâu năm: .................................................................................................",
        ]
        for line in prop_lines:
            page1.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page1.insert_text(fitz.Point(50, y), "IV. NGHĨA VỤ TÀI CHÍNH & ĐỀ NGHỊ KHÁC:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        fin_lines = [
            "[   ] Đề nghị được ghi nợ tiền sử dụng đất theo quy định của pháp luật",
            "[   ] Đề nghị được miễn, giảm tiền sử dụng đất (đối tượng chính sách / người có công)",
            "[   ] Nhận Giấy chứng nhận: [   ] Nhận trực tiếp tại Bộ phận Một cửa    [   ] Qua dịch vụ bưu chính công ích",
        ]
        for line in fin_lines:
            page1.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 15

        self._draw_footer(page1, fontname, page_num="Trang 1/2")

        # ── TRANG 2 ──
        page2 = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page2)

        page2.insert_text(fitz.Point(135, 45), "MẪU SỐ 04/ĐK - PHẦN XÁC NHẬN CỦA CƠ QUAN NHÀ NƯỚC", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        page2.draw_line(fitz.Point(135, 52), fitz.Point(460, 52), color=(0, 0, 0), width=0.6)

        y = 75
        page2.insert_text(fitz.Point(50, y), "V. DANH MỤC GIẤY TỜ NỘP KÈM THEO HỒ SƠ:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        docs_lines = [
            "[ x ] Bản sao giấy tờ tùy thân (Căn cước công dân / Hộ chiếu) của người sử dụng đất",
            "[ x ] Một trong các giấy tờ về quyền sử dụng đất quy định tại Điều 137 Luật Đất đai năm 2024 (nếu có)",
            "[ x ] Bản vẽ sơ đồ trích đo địa chính thửa đất / Bản trích lục bản đồ địa chính",
            "[ x ] Chứng từ thực hiện nghĩa vụ tài chính / Giấy tờ miễn giảm nghĩa vụ tài chính (nếu có)",
        ]
        for line in docs_lines:
            page2.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 15

        y += 4
        page2.insert_text(fitz.Point(50, y), "VI. CAM ĐOAN CỦA NGƯỜI KÊ KHAI:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 15
        page2.insert_text(
            fitz.Point(60, y),
            "Tôi cam đoan nội dung kê khai trên là hoàn toàn trung thực, thửa đất không có tranh chấp khiếu nại,",
            fontname=fontname, fontsize=8.5, color=(0, 0, 0)
        )
        y += 14
        page2.insert_text(
            fitz.Point(60, y),
            "nếu có điều gì gian dối tôi xin hoàn toàn chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=8.5, color=(0, 0, 0)
        )

        y += 20
        page2.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        y += 14
        page2.insert_text(fitz.Point(365, y), "NGƯỜI KÊ KHAI ĐƠN", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 12
        page2.insert_text(fitz.Point(355, y), "(Ký, ghi rõ họ và tên)", fontname=italicfont, fontsize=8, color=(0, 0, 0))

        y += 35
        # Kẻ khung xác nhận của UBND cấp xã
        box1_top = y
        box1_bot = y + 155
        page2.draw_rect(fitz.Rect(50, box1_top, 545, box1_bot), color=(0, 0, 0), width=0.8)
        page2.insert_text(fitz.Point(60, box1_top + 16), "VII. KẾT QUẢ KIỂM TRA, XÁC NHẬN CỦA ỦY BAN NHÂN DÂN CẤP XÃ:", fontname=boldfont, fontsize=9, color=(0, 0, 0))
        c_lines = [
            "1. Hiện trạng sử dụng: Thửa đất số: ........... Tờ bản đồ: ........... Diện tích: ........... m2 (Đất ở: ........... m2)",
            "2. Nguồn gốc và thời điểm bắt đầu sử dụng đất: Sử dụng ổn định từ ngày ...... / ...... / ............",
            "3. Tình trạng tranh chấp: [   ] Không có tranh chấp, khiếu nại      [   ] Có tranh chấp",
            "4. Sự phù hợp quy hoạch: [   ] Phù hợp với quy hoạch sử dụng đất cấp huyện đã được phê duyệt",
        ]
        b_y = box1_top + 34
        for cl in c_lines:
            page2.insert_text(fitz.Point(65, b_y), cl, fontname=fontname, fontsize=8, color=(0, 0, 0))
            b_y += 14

        page2.insert_text(fitz.Point(340, box1_top + 98), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8, color=(0, 0, 0))
        page2.insert_text(fitz.Point(350, box1_top + 112), "CHỦ TỊCH ỦY BAN NHÂN DÂN", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page2.insert_text(fitz.Point(365, box1_top + 125), "(Ký tên, đóng dấu xác nhận)", fontname=italicfont, fontsize=7.5, color=(0, 0, 0))

        y = box1_bot + 12
        # Kẻ khung thẩm tra của Chi nhánh VP Đăng ký đất đai
        box2_top = y
        box2_bot = y + 130
        page2.draw_rect(fitz.Rect(50, box2_top, 545, box2_bot), color=(0, 0, 0), width=0.8)
        page2.insert_text(fitz.Point(60, box2_top + 16), "VIII. Ý KIẾN KIỂM TRA CỦA CHI NHÁNH VĂN PHÒNG ĐĂNG KÝ ĐẤT ĐAI:", fontname=boldfont, fontsize=9, color=(0, 0, 0))
        v_lines = [
            "1. Kiểm tra hồ sơ địa chính: [   ] Đầy đủ, hợp lệ theo quy định của pháp luật",
            "2. Trích lục bản đồ / Trích đo địa chính: Đã đối soát ranh giới, không chồng lấn",
            "3. Đủ điều kiện cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất.",
        ]
        vb_y = box2_top + 34
        for vl in v_lines:
            page2.insert_text(fitz.Point(65, vb_y), vl, fontname=fontname, fontsize=8, color=(0, 0, 0))
            vb_y += 14

        page2.insert_text(fitz.Point(340, box2_top + 80), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8, color=(0, 0, 0))
        page2.insert_text(fitz.Point(375, box2_top + 94), "GIÁM ĐỐC", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page2.insert_text(fitz.Point(355, box2_top + 107), "(Ký tên, đóng dấu xác nhận)", fontname=italicfont, fontsize=7.5, color=(0, 0, 0))

        self._draw_footer(page2, fontname, page_num="Trang 2/2")

        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes


    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 7: TỜ KHAI QUYẾT TOÁN THUẾ THU NHẬP CÁ NHÂN (Mẫu 02/QTT-TNCN — TT 80/2021/TT-BTC)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_tax_form(self, doc, doc_name: str, procedure_title: str) -> bytes:
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Mẫu 02/QTT-TNCN (Ban hành kèm TT số 80/2021/TT-BTC)"
        )

        page.insert_text(fitz.Point(125, 115), "TỜ KHAI QUYẾT TOÁN THUẾ THU NHẬP CÁ NHÂN", fontname=boldfont, fontsize=13, color=(0, 0, 0))
        page.insert_text(fitz.Point(115, 132), "(Áp dụng cho cá nhân có thu nhập từ tiền lương, tiền công trực tiếp quyết toán với cơ quan thuế)", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(155, 148), "Kỳ tính thuế: Năm 202...      [   ] Chính thức      [   ] Bổ sung lần: ...", fontname=fontname, fontsize=9.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(60, 168), "Kính gửi: Cơ quan Thuế ..........................................................................................................................", fontname=boldfont, fontsize=10, color=(0, 0, 0))

        y = 194
        page.insert_text(fitz.Point(50, y), "I. THÔNG TIN NGƯỜI NỘP THUẾ:", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 18
        p_lines = [
            "[01] Họ và tên: ..................................................................... [02] Mã số thuế: .............................................",
            "[03] Số CCCD/Hộ chiếu: ....................................................... [04] Ngày cấp: ....../....../......... Nơi cấp: .............",
            "[05] Địa chỉ cư trú: ..........................................................................................................................................",
            "[06] Điện thoại: .................................................................... [07] Email: .....................................................",
        ]
        for line in p_lines:
            page.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=9, color=(0, 0, 0))
            y += 18

        y += 6
        page.insert_text(fitz.Point(50, y), "II. BẢNG KÊ KHAI NGHĨA VỤ THUẾ:", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 16

        # Kẻ bảng chỉ tiêu kê khai thuế
        table_top = y
        table_bottom = y + 170
        page.draw_rect(fitz.Rect(50, table_top, 545, table_bottom), color=(0, 0, 0), width=0.8)
        # Header row
        page.draw_line(fitz.Point(50, table_top + 20), fitz.Point(545, table_top + 20), color=(0, 0, 0), width=0.8)
        page.draw_line(fitz.Point(90, table_top), fitz.Point(90, table_bottom), color=(0, 0, 0), width=0.5)
        page.draw_line(fitz.Point(390, table_top), fitz.Point(390, table_bottom), color=(0, 0, 0), width=0.5)

        page.insert_text(fitz.Point(55, table_top + 14), "Mã CT", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(180, table_top + 14), "Chỉ tiêu kê khai", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(425, table_top + 14), "Số tiền (VNĐ)", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))

        tax_rows = [
            ("[20]", "Tổng thu nhập chịu thuế phát sinh trong kỳ", "............................................."),
            ("[21]", "Trong đó: Thu nhập chịu thuế được miễn giảm theo Hiệp định/Luật", "............................................."),
            ("[22]", "Tổng các khoản giảm trừ (Bản thân, người phụ thuộc, BHXH)", "............................................."),
            ("[23]", "Tổng thu nhập tính thuế ([23] = [20] - [21] - [22])", "............................................."),
            ("[24]", "Tổng số thuế thu nhập cá nhân phát sinh trong kỳ", "............................................."),
            ("[25]", "Tổng số thuế đã khấu trừ, tạm nộp trong năm", "............................................."),
            ("[26]", "Số thuế nộp thừa đề nghị hoàn trả vào tài khoản", "............................................."),
        ]

        row_y = table_top + 36
        for ct, label, dots in tax_rows:
            page.insert_text(fitz.Point(58, row_y), ct, fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
            page.insert_text(fitz.Point(96, row_y), label, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            page.insert_text(fitz.Point(398, row_y), dots, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            page.draw_line(fitz.Point(50, row_y + 6), fitz.Point(545, row_y + 6), color=(0, 0, 0), width=0.3)
            row_y += 21

        y = table_bottom + 14
        page.insert_text(fitz.Point(50, y), "III. THÔNG TIN TÀI KHOẢN NHẬN HOÀN THUẾ (NẾU CÓ SỐ THUẾ NỘP THỪA):", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 18
        page.insert_text(fitz.Point(60, y), "Số tài khoản ngân hàng: ............................................  Tên chủ tài khoản: ............................................................", fontname=fontname, fontsize=9, color=(0, 0, 0))
        y += 18
        page.insert_text(fitz.Point(60, y), "Mở tại Ngân hàng: ....................................................  Chi nhánh: .....................................................................", fontname=fontname, fontsize=9, color=(0, 0, 0))

        y += 16
        page.insert_text(
            fitz.Point(50, y),
            "Tôi cam đoan số liệu kê khai trên đây là hoàn toàn đúng sự thật và chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=9, color=(0, 0, 0)
        )

        y += 30
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=9, color=(0, 0, 0))
        y += 16
        page.insert_text(fitz.Point(355, y), "NGƯỜI NỘP THUẾ", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(340, y), "(Ký, ghi rõ họ tên và đóng dấu nếu có)", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 7B: VĂN BẢN ĐỀ NGHỊ XÁC NHẬN KHÔNG THUỘC DIỆN CẤP GPLĐ (MẪU SỐ 09/PLI)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_work_permit_exemption_form(self, doc, doc_name: str, procedure_title: str) -> bytes:
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Mẫu số 09/PLI ban hành kèm theo Nghị định 152/2020/NĐ-CP & NĐ 70/2023/NĐ-CP"
        )

        page.insert_text(fitz.Point(75, 112), "VĂN BẢN ĐỀ NGHỊ XÁC NHẬN NGƯỜI LAO ĐỘNG NƯỚC NGOÀI", fontname=boldfont, fontsize=11.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(125, 128), "KHÔNG THUỘC DIỆN CẤP GIẤY PHÉP LAO ĐỘNG", fontname=boldfont, fontsize=11.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(60, 148), "Kính gửi: Sở Lao động - Thương binh và Xã hội / Ban Quản lý các Khu công nghiệp & Chế xuất", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 172
        page.insert_text(fitz.Point(50, y), "I. THÔNG TIN DOANH NGHIỆP / TỔ CHỨC BẢO LÃNH:", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 18
        corp_fields = [
            "1. Tên doanh nghiệp/tổ chức: .....................................................................................................................",
            "2. Mã số doanh nghiệp/Mã số thuế: .........................................  Ngày cấp: ....... / ....... / ....................",
            "3. Địa chỉ trụ sở chính: ..................................................................................................................................",
            "4. Điện thoại: .................................................................  Email: ................................................................",
            "5. Người đại diện theo pháp luật: .......................................................  Chức vụ: .....................................",
        ]
        for line in corp_fields:
            page.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=9, color=(0, 0, 0))
            y += 17

        y += 6
        page.insert_text(fitz.Point(50, y), "II. THÔNG TIN NGƯỜI LAO ĐỘNG NƯỚC NGOÀI ĐỀ NGHỊ XÁC NHẬN:", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 18
        worker_fields = [
            "1. Họ và tên (chữ in hoa): .............................................................  Giới tính: [  ] Nam    [  ] Nữ",
            "2. Ngày, tháng, năm sinh: ....... / ....... / ....................      Quốc tịch: .....................................................",
            "3. Số hộ chiếu: .................................................  Ngày cấp: ....... / ....... / ............ Có giá trị đến: .................",
            "4. Vị trí công việc: [  ] Nhà quản lý    [  ] Giám đốc điều hành    [  ] Chuyên gia    [  ] Lao động kỹ thuật",
            "5. Thời hạn làm việc: Từ ngày ....... / ....... / ............ đến ngày ....... / ....... / ............",
        ]
        for line in worker_fields:
            page.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=9, color=(0, 0, 0))
            y += 17

        y += 6
        page.insert_text(fitz.Point(50, y), "III. CĂN CỨ KHÔNG THUỘC DIỆN CẤP GIẤY PHÉP LAO ĐỘNG:", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 17
        reasons = [
            "[  ] Là chủ sở hữu hoặc thành viên góp vốn của công ty TNHH có giá trị góp vốn theo quy định.",
            "[  ] Là Chủ tịch hoặc thành viên Hội đồng quản trị của công ty cổ phần có giá trị góp vốn theo quy định.",
            "[  ] Vào Việt Nam làm việc tại vị trí chuyên gia, nhà quản lý, giám đốc điều hành dưới 30 ngày và không quá 03 lần/năm.",
            "[  ] Di chuyển trong nội bộ doanh nghiệp thuộc phạm vi 11 ngành dịch vụ theo cam kết WTO của Việt Nam.",
            "[  ] Trường hợp khác theo quy định tại Điều 154 Bộ luật Lao động và Điều 7 Nghị định 152/2020/NĐ-CP.",
        ]
        for line in reasons:
            page.insert_text(fitz.Point(60, y), line, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 8
        page.insert_text(
            fitz.Point(50, y),
            "Doanh nghiệp cam đoan các thông tin kê khai trên là hoàn toàn chính xác và chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=8.5, color=(0, 0, 0)
        )

        y += 28
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=9, color=(0, 0, 0))
        y += 16
        page.insert_text(fitz.Point(70, y), "NGƯỜI LAO ĐỘNG NƯỚC NGOÀI", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(340, y), "NGƯỜI SỬ DỤNG LAO ĐỘNG", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(95, y), "(Ký, ghi rõ họ tên)", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(335, y), "(Ký, đóng dấu, ghi rõ họ tên & chức vụ)", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 8: GIẤY ĐỀ NGHỊ ĐĂNG KÝ DOANH NGHIỆP / HỘ KINH DOANH (NĐ 01/2021 & TT 02/2023)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_business_reg_form(self, doc, doc_name: str, procedure_title: str, agency: str = "") -> bytes:
        """
        GIẤY ĐỀ NGHỊ ĐĂNG KÝ DOANH NGHIỆP / HỘ KINH DOANH
        Ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT và Nghị định số 01/2021/NĐ-CP.
        """
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Ban hành kèm theo TT 02/2023/TT-BKHĐT & NĐ 01/2021/NĐ-CP"
        )

        clean_p_title = sanitize_admin_procedure_title(procedure_title)
        page.insert_text(fitz.Point(110, 112), "GIẤY ĐỀ NGHỊ ĐĂNG KÝ DOANH NGHIỆP", fontname=boldfont, fontsize=13, color=(0, 0, 0))
        page.insert_text(fitz.Point(135, 128), "(HOẶC ĐĂNG KÝ HỘ KINH DOANH CÁ THỂ)", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        if clean_p_title:
            page.insert_text(fitz.Point(75, 144), f"(Áp dụng thủ tục: {clean_p_title})", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))

        target_agency = agency if agency else "Phòng Đăng ký kinh doanh - Sở Kế hoạch và Đầu tư / Phòng TC-KH cấp huyện"
        page.insert_text(fitz.Point(60, 162), f"Kính gửi: {target_agency}", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 184
        page.insert_text(fitz.Point(50, y), "I. TÊN DOANH NGHIỆP / HỘ KINH DOANH DỰ KIẾN:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        n_lines = [
            "1. Tên tiếng Việt (viết in hoa): .................................................................................................................",
            "2. Tên bằng tiếng nước ngoài (nếu có): .......................................................................................................",
            "3. Tên viết tắt (nếu có): .................................................................................................................................",
        ]
        for l in n_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "II. ĐỊA CHỈ TRỤ SỞ CHÍNH:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        a_lines = [
            "Số nhà, ngách, hẻm, ngõ, đường phố: .........................................................................................................",
            "Xã/Phường/Thị trấn: ........................................... Quận/Huyện/Thị xã: ....................................................",
            "Tỉnh/Thành phố trực thuộc TW: .....................................................................................................................",
            "Điện thoại: ............................................................. Email: ............................................................................",
        ]
        for l in a_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "III. NGÀNH, NGHỀ KINH DOANH CHÍNH & VỐN ĐIỀU LỆ:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        b_lines = [
            "1. Ngành nghề kinh doanh chính: ............................................................................. Mã ngành: ..................",
            "2. Vốn điều lệ / Vốn kinh doanh: .................................................... VNĐ",
            "   (Bằng chữ: ............................................................................................................................................)",
        ]
        for l in b_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "IV. THÔNG TIN NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT / CHỦ HỘ:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        rep_lines = [
            "1. Họ và tên (chữ in hoa): ................................................................................. Giới tính: [  ] Nam  [  ] Nữ",
            "2. Chức danh: [   ] Giám đốc / Tổng giám đốc    [   ] Chủ tịch HĐTV / Chủ tịch HĐQT    [   ] Chủ hộ KD",
            "3. Sinh ngày: ...... / ...... / .........  Dân tộc: .......................  Quốc tịch: ....................................................",
            "4. Số định danh cá nhân / CCCD / Hộ chiếu: ..................................... Ngày cấp: ....../....../...... Nơi cấp: ..............",
            "5. Địa chỉ thường trú: ....................................................................................................................................",
        ]
        for l in rep_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 6
        page.insert_text(
            fitz.Point(50, y),
            "Tôi cam đoan trụ sở chính đúng quy định, hồ sơ hợp pháp, trung thực và hoàn toàn chịu trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=8, color=(0, 0, 0)
        )

        y += 24
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(310, y), "NGƯỜI ĐẠI DIỆN THEO PHÁP LUẬT", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 12
        page.insert_text(fitz.Point(335, y), "(Ký, đóng dấu nếu có và ghi rõ họ tên)", fontname=italicfont, fontsize=8, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 9: ĐƠN ĐỀ NGHỊ CẤP GIẤY PHÉP XÂY DỰNG (MẪU SỐ 01 - NĐ 15/2021/NĐ-CP)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_construction_permit_form(self, doc, doc_name: str, procedure_title: str, agency: str = "") -> bytes:
        """
        MẪU SỐ 01 PHỤ LỤC II: ĐƠN ĐỀ NGHỊ CẤP GIẤY PHÉP XÂY DỰNG
        Ban hành kèm theo Nghị định số 15/2021/NĐ-CP ngày 03/3/2021 của Chính phủ.
        Áp dụng cho công trình xây dựng, nhà ở riêng lẻ đô thị và nông thôn.
        """
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Mẫu số 01 Phụ lục II ban hành kèm theo Nghị định số 15/2021/NĐ-CP"
        )

        clean_p_title = sanitize_admin_procedure_title(procedure_title)
        page.insert_text(fitz.Point(125, 112), "ĐƠN ĐỀ NGHỊ CẤP GIẤY PHÉP XÂY DỰNG", fontname=boldfont, fontsize=13, color=(0, 0, 0))
        page.insert_text(fitz.Point(155, 128), "(SỬ DỤNG CHO CÔNG TRÌNH / NHÀ Ở RIÊNG LẺ)", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        if clean_p_title:
            page.insert_text(fitz.Point(75, 144), f"(Áp dụng thủ tục: {clean_p_title})", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))

        target_agency = agency if agency else "Ủy ban nhân dân cấp huyện / Sở Xây dựng"
        page.insert_text(fitz.Point(60, 162), f"Kính gửi: {target_agency}", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 184
        page.insert_text(fitz.Point(50, y), "I. THÔNG TIN CHỦ ĐẦU TƯ / CHỦ HỘ:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        c_lines = [
            "1. Tên chủ đầu tư (cá nhân/tổ chức): ..........................................................................................................",
            "2. Số định danh cá nhân / CCCD / MST: ........................................... Ngày cấp: ......./......./........ Nơi cấp: .............",
            "3. Địa chỉ liên hệ: ...........................................................................................................................................",
            "4. Số điện thoại: ..................................................................... Email: .........................................................",
        ]
        for l in c_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "II. ĐỊA ĐIỂM XÂY DỰNG & QUY MÔ CÔNG TRÌNH:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        site_lines = [
            "1. Lô đất số: ................................. Thửa đất số: ................................. Tờ bản đồ số: .................................",
            "2. Địa chỉ công trình: ........................................................................................................................................",
            "3. Cấp công trình: [   ] Cấp III      [   ] Cấp IV      [   ] Nhà ở riêng lẻ đô thị/nông thôn",
            "4. Diện tích xây dựng tầng 1 (tầng trệt): .................... m²     Tổng diện tích sàn: .................... m²",
            "5. Chiều cao toàn bộ công trình: .................... m               Số tầng (gồm tầng hầm/lửng/tum): ............ tầng",
        ]
        for l in site_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "III. TỔ CHỨC / CÁ NHÂN LẬP THIẾT KẾ:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        des_lines = [
            "1. Tên đơn vị thiết kế: ....................................................................................................................................",
            "2. Chứng chỉ năng lực hoạt động xây dựng số: ................................... Do: .................................... cấp",
            "3. Dự kiến thời gian hoàn thành công trình: ............ tháng kể từ ngày được cấp phép.",
        ]
        for l in des_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "IV. HỒ SƠ ĐÍNH KÈM:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 15
        att_lines = [
            "[ x ] Bản sao giấy tờ hợp pháp về đất đai (Giấy chứng nhận QSDĐ)",
            "[ x ] 02 bộ bản vẽ thiết kế xây dựng kèm theo phương án móng",
            "[ x ] Bản cam kết bảo đảm an toàn đối với công trình liền kề (đối với nhà ở)",
        ]
        for l in att_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8, color=(0, 0, 0))
            y += 14

        y += 6
        page.insert_text(
            fitz.Point(50, y),
            "Tôi cam đoan thi công đúng giấy phép được cấp, chịu hoàn toàn trách nhiệm trước pháp luật về an toàn công trình.",
            fontname=fontname, fontsize=8, color=(0, 0, 0)
        )

        y += 24
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(365, y), "CHỦ ĐẦU TƯ / CHỦ HỘ", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 12
        page.insert_text(fitz.Point(360, y), "(Ký, ghi rõ họ và tên)", fontname=italicfont, fontsize=8, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 10: ĐƠN ĐỀ NGHỊ ĐỔI, CẤP LẠI GPLX (PHỤ LỤC 19 - TT 05/2024/TT-BGTVT)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_driver_license_form(self, doc, doc_name: str, procedure_title: str, agency: str = "") -> bytes:
        """
        PHỤ LỤC 19: ĐƠN ĐỀ NGHỊ ĐỔI (CẤP LẠI) GIẤY PHÉP LÁI XE
        Ban hành kèm theo Thông tư số 05/2024/TT-BGTVT ngày 31/3/2024 của Bộ GTVT.
        """
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Phụ lục 19 ban hành kèm theo Thông tư số 05/2024/TT-BGTVT"
        )

        # Ô dán ảnh 3x4 góc trên bên phải
        page.draw_rect(fitz.Rect(450, 40, 535, 145), color=(0, 0, 0), width=0.8)
        page.insert_text(fitz.Point(465, 85), "ẢNH 3x4", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(455, 100), "(Dán ảnh màu,", fontname=italicfont, fontsize=7.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(458, 112), "nền trắng)", fontname=italicfont, fontsize=7.5, color=(0, 0, 0))

        clean_p_title = sanitize_admin_procedure_title(procedure_title)
        page.insert_text(fitz.Point(90, 112), "ĐƠN ĐỀ NGHỊ ĐỔI (CẤP LẠI) GIẤY PHÉP LÁI XE", fontname=boldfont, fontsize=12.5, color=(0, 0, 0))
        if clean_p_title:
            page.insert_text(fitz.Point(75, 130), f"(Áp dụng thủ tục: {clean_p_title})", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))

        target_agency = agency if agency else "Cục Đường bộ Việt Nam / Sở Giao thông vận tải"
        page.insert_text(fitz.Point(60, 155), f"Kính gửi: {target_agency}", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 180
        page.insert_text(fitz.Point(50, y), "I. THÔNG TIN NGƯỜI LÀM ĐƠN:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        p_lines = [
            "1. Họ và tên (chữ in hoa): .................................................................................................................",
            "2. Quốc tịch: .......................................  Giới tính: [   ] Nam      [   ] Nữ",
            "3. Ngày, tháng, năm sinh: ....... / ....... / ....................  Nơi sinh: .............................................................",
            "4. Số định danh cá nhân / CCCD / Hộ chiếu: ..............................................................................................",
            "   Ngày cấp: ....... / ....... / ....................  Nơi cấp: ............................................................................",
            "5. Nơi cư trú (thường trú/tạm trú): .................................................................................................................",
            "6. Số điện thoại liên hệ: .............................................................  Email: .........................................................",
        ]
        for l in p_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "II. THÔNG TIN GIẤY PHÉP LÁI XE ĐÃ ĐƯỢC CẤP:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        g_lines = [
            "1. Đã có Giấy phép lái xe hạng: ......................... Số GPLX: .........................................................................",
            "2. Nơi cấp GPLX: .................................................................... Ngày cấp: ....... / ....... / ....................",
            "3. Có giá trị đến ngày: ....... / ....... / .................... (Không thời hạn đối với hạng A1, A2, A3)",
        ]
        for l in g_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "III. LÝ DO XIN ĐỔI / CẤP LẠI GIẤY PHÉP LÁI XE:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        r_lines = [
            "[   ] Giấy phép lái xe hết thời hạn sử dụng theo quy định",
            "[   ] Giấy phép lái xe bị mất (Lý do mất: ............................................................................................)",
            "[   ] Giấy phép lái xe bị rách, hư hỏng không còn nhận dạng được",
            "[   ] Thay đổi thông tin cá nhân ghi trên Giấy phép lái xe (Số CCCD, Họ tên, Nơi cư trú)",
            "[   ] Đổi Giấy phép lái xe bằng giấy bìa sang Giấy phép lái xe bằng vật liệu PET",
        ]
        for l in r_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 6
        page.insert_text(
            fitz.Point(50, y),
            "Tôi cam đoan không bị cơ quan thu giữ hoặc tước GPLX, chịu hoàn toàn trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=8, color=(0, 0, 0)
        )

        y += 24
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(85, y), "CÁN BỘ TIẾP NHẬN", fontname=boldfont, fontsize=9, color=(0, 0, 0))
        page.insert_text(fitz.Point(365, y), "NGƯỜI LÀM ĐƠN", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 12
        page.insert_text(fitz.Point(75, y), "(Ký, đóng dấu tiếp nhận)", fontname=italicfont, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(355, y), "(Ký, ghi rõ họ và tên)", fontname=italicfont, fontsize=8, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 11: ĐƠN ĐỀ NGHỊ CẤP GIẤY PHÉP HÀNH NGHỀ Y TẾ (NĐ 96/2023/NĐ-CP)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_healthcare_permit_form(self, doc, doc_name: str, procedure_title: str, agency: str = "") -> bytes:
        """
        ĐƠN ĐỀ NGHỊ CẤP GIẤY PHÉP HÀNH NGHỀ / HOẠT ĐỘNG KHÁM BỆNH, CHỮA BỆNH
        Ban hành kèm theo Nghị định số 96/2023/NĐ-CP ngày 30/12/2023 của Chính phủ.
        """
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Ban hành kèm theo Nghị định số 96/2023/NĐ-CP (Luật Khám bệnh, chữa bệnh 2023)"
        )

        clean_p_title = sanitize_admin_procedure_title(procedure_title)
        page.insert_text(fitz.Point(70, 112), "ĐƠN ĐỀ NGHỊ CẤP / ĐIỀU CHỈNH GIẤY PHÉP HÀNH NGHỀ", fontname=boldfont, fontsize=12, color=(0, 0, 0))
        page.insert_text(fitz.Point(145, 128), "HOẶC GIẤY PHÉP HOẠT ĐỘNG KHÁM CHỮA BỆNH", fontname=boldfont, fontsize=10.5, color=(0, 0, 0))
        if clean_p_title:
            page.insert_text(fitz.Point(75, 144), f"(Áp dụng thủ tục: {clean_p_title})", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))

        target_agency = agency if agency else "Bộ Y tế / Sở Y tế tỉnh/thành phố"
        page.insert_text(fitz.Point(60, 162), f"Kính gửi: {target_agency}", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 184
        page.insert_text(fitz.Point(50, y), "I. THÔNG TIN NGƯỜI ĐỀ NGHỊ / CƠ SỞ KHÁM BỆNH, CHỮA BỆNH:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        m_lines = [
            "1. Họ và tên cá nhân / Tên cơ sở: .............................................................................................................",
            "2. Số định danh cá nhân / CCCD / Mã số doanh nghiệp: ..................................................................................",
            "3. Địa chỉ thường trú / Trụ sở cơ sở y tế: .........................................................................................................",
            "4. Điện thoại liên hệ: .............................................................  Email: .........................................................",
        ]
        for l in m_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "II. VĂN BẰNG CHUYÊN MÔN & PHẠM VI HÀNH NGHỀ:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        q_lines = [
            "1. Văn bằng chuyên môn: [   ] Bác sĩ y khoa    [   ] Bác sĩ chuyên khoa    [   ] Y sĩ    [   ] Điều dưỡng    [   ] Dược sĩ",
            "2. Cơ sở đào tạo cấp văn bằng: ...................................................................................................................",
            "3. Năm tốt nghiệp: ....................  Số văn bằng: .............................................................................................",
            "4. Chức danh chuyên môn đề nghị cấp phép: ..............................................................................................",
            "5. Phạm vi hành nghề chuyên môn đăng ký: ................................................................................................",
        ]
        for l in q_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "III. HỒ SƠ KÈM THEO:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 15
        att_lines = [
            "[ x ] Bản sao hợp lệ văn bằng chuyên môn y tế",
            "[ x ] Văn bản xác nhận quá trình thực hành khám bệnh, chữa bệnh",
            "[ x ] Giấy khám sức khỏe do cơ sở y tế có thẩm quyền cấp",
            "[ x ] Phiếu lý lịch tư pháp (đối với cá nhân đề nghị cấp lần đầu)",
        ]
        for l in att_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8, color=(0, 0, 0))
            y += 14

        y += 6
        page.insert_text(
            fitz.Point(50, y),
            "Tôi cam đoan nội dung kê khai là chính xác, chấp hành nghiêm quy định pháp luật và quy chế chuyên môn ngành y.",
            fontname=fontname, fontsize=8, color=(0, 0, 0)
        )

        y += 24
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(345, y), "NGƯỜI ĐỀ NGHỊ / ĐẠI DIỆN", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 12
        page.insert_text(fitz.Point(355, y), "(Ký, ghi rõ họ và tên)", fontname=italicfont, fontsize=8, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 12: ĐƠN ĐỀ NGHỊ GIẢI QUYẾT CHẾ ĐỘ BHXH (MẪU 14-HSB - QĐ 166/QĐ-BHXH)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_social_insurance_form(self, doc, doc_name: str, procedure_title: str, agency: str = "") -> bytes:
        """
        MẪU SỐ 14-HSB: ĐƠN ĐỀ NGHỊ GIẢI QUYẾT HƯỞNG CHẾ ĐỘ BẢO HIỂM XÃ HỘI
        Ban hành kèm theo Quyết định số 166/QĐ-BHXH của Bảo hiểm xã hội Việt Nam.
        Áp dụng cho: Hưởng BHXH một lần, Chế độ thai sản, Hưu trí, Chế độ tử tuất.
        """
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Mẫu số 14-HSB ban hành kèm theo Quyết định số 166/QĐ-BHXH"
        )

        clean_p_title = sanitize_admin_procedure_title(procedure_title)
        page.insert_text(fitz.Point(100, 112), "ĐƠN ĐỀ NGHỊ GIẢI QUYẾT HƯỞNG CHẾ ĐỘ BHXH", fontname=boldfont, fontsize=12.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(125, 128), "(HOẶC BẢO HIỂM THẤT NGHIỆP / TỬ TUẤT / THAI SẢN)", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        if clean_p_title:
            page.insert_text(fitz.Point(75, 144), f"(Áp dụng thủ tục: {clean_p_title})", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))

        target_agency = agency if agency else "Cơ quan Bảo hiểm xã hội quận/huyện/tỉnh"
        page.insert_text(fitz.Point(60, 162), f"Kính gửi: {target_agency}", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 184
        page.insert_text(fitz.Point(50, y), "I. THÔNG TIN NGƯỜI ĐỀ NGHỊ / NGƯỜI LAO ĐỘNG:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        s_lines = [
            "1. Họ và tên: ................................................................................. Giới tính: [  ] Nam    [  ] Nữ",
            "2. Ngày, tháng, năm sinh: ....... / ....... / ....................  Số định danh cá nhân / CCCD: ....................................",
            "3. Mã số BHXH: ................................................................. Sổ BHXH số: ........................................................",
            "4. Nơi cư trú hiện nay: .....................................................................................................................................",
            "5. Điện thoại liên hệ: .............................................................  Email: .........................................................",
        ]
        for l in s_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "II. CHẾ ĐỘ ĐỀ NGHỊ GIẢI QUYẾT:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        types = [
            "[   ] Trợ cấp Bảo hiểm xã hội một lần (Do nghỉ việc đủ 12 tháng không tiếp tục đóng / Định cư)",
            "[   ] Chế độ thai sản (Khám thai, sinh con, nhận nuôi con nuôi)",
            "[   ] Chế độ hưu trí hàng tháng",
            "[   ] Chế độ tai nạn lao động, bệnh nghề nghiệp",
            "[   ] Chế độ tử tuất (Mai táng phí, trợ cấp tuất một lần hoặc hàng tháng)",
        ]
        for l in types:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 4
        page.insert_text(fitz.Point(50, y), "III. HÌNH THỨC NHẬN TIỀN TRỢ CẤP:", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 16
        pay_lines = [
            "[   ] Nhận trực tiếp bằng tiền mặt tại cơ quan Bảo hiểm xã hội hoặc Bưu cục chi trả",
            "[   ] Nhận qua tài khoản cá nhân (ATM):",
            "     - Tên chủ tài khoản: ...........................................................................................................................",
            "     - Số tài khoản: .................................................  Ngân hàng: ................................................................",
        ]
        for l in pay_lines:
            page.insert_text(fitz.Point(60, y), l, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 15

        y += 6
        page.insert_text(
            fitz.Point(50, y),
            "Tôi cam đoan thông tin kê khai trên là đúng sự thật và chịu hoàn toàn trách nhiệm trước pháp luật.",
            fontname=fontname, fontsize=8, color=(0, 0, 0)
        )

        y += 24
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(85, y), "CƠ QUAN TIẾP NHẬN", fontname=boldfont, fontsize=9, color=(0, 0, 0))
        page.insert_text(fitz.Point(355, y), "NGƯỜI KÊ KHAI ĐƠN", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 12
        page.insert_text(fitz.Point(75, y), "(Ký, đóng dấu tiếp nhận)", fontname=italicfont, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(350, y), "(Ký, ghi rõ họ và tên)", fontname=italicfont, fontsize=8, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────────────────────────────────────
    # MẪU 13: ĐƠN ĐỀ NGHỊ GIẢI QUYẾT TTHC CHUẨN (Nghị định 30/2020 & 61/2018/NĐ-CP)
    # ──────────────────────────────────────────────────────────────────────────
    def _build_general_form(self, doc, doc_name: str, procedure_title: str, agency: str = "") -> bytes:
        """
        MẪU ĐƠN PHỔ QUÁT CHUẨN NGHỊ ĐỊNH 30/2020/NĐ-CP & NGHỊ ĐỊNH 61/2018/NĐ-CP
        Tích hợp thông tin cơ quan tiếp nhận thực tế và Phiếu tiếp nhận Một cửa.
        """
        page = doc.new_page(width=595, height=842)
        fontname, boldfont, italicfont = self._setup_page_fonts(doc, page)

        self._draw_national_header(
            page, boldfont, italicfont,
            legal_code="Ban hành theo chuẩn Nghị định 30/2020/NĐ-CP & NĐ 61/2018/NĐ-CP"
        )

        clean_p_title = sanitize_admin_procedure_title(procedure_title)

        is_already_don = any(kw in doc_name.lower() for kw in ["đơn", "tờ khai", "bản khai", "giấy đề nghị"])
        if is_already_don:
            main_title = doc_name.upper()
        else:
            main_title = f"ĐƠN ĐỀ NGHỊ: {doc_name.upper()}"

        page.insert_text(fitz.Point(60, 116), main_title[:80], fontname=boldfont, fontsize=12, color=(0, 0, 0))
        if clean_p_title:
            page.insert_text(fitz.Point(60, 134), f"(Áp dụng hoàn thiện thủ tục: {clean_p_title})", fontname=italicfont, fontsize=9, color=(0, 0, 0))
        page.draw_line(fitz.Point(60, 142), fitz.Point(535, 142), color=(0, 0, 0), width=0.8)

        target_agency = agency if agency else "Bộ phận Tiếp nhận và Trả kết quả / Cơ quan có thẩm quyền giải quyết"
        page.insert_text(fitz.Point(60, 162), f"Kính gửi: {target_agency}", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))

        y = 186
        page.insert_text(fitz.Point(60, y), "I. THÔNG TIN NGƯỜI LÀM ĐƠN / NGƯỜI YÊU CẦU", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 18
        fields = [
            "1. Họ và tên (chữ in hoa): .................................................................................................................",
            "2. Ngày, tháng, năm sinh: ....... / ....... / ....................            Giới tính: [   ] Nam      [   ] Nữ",
            "3. Số định danh cá nhân / Số CCCD: ......................................    Ngày cấp: ....... / ....... / ............ Nơi cấp: .............",
            "4. Nơi thường trú: .............................................................................................................................",
            "5. Nơi ở hiện tại: ................................................................................................................................",
            "6. Số điện thoại liên hệ: ................................................    Email: .......................................................",
        ]
        for f in fields:
            page.insert_text(fitz.Point(70, y), f, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 17

        y += 6
        page.insert_text(fitz.Point(60, y), "II. NỘI DUNG ĐỀ NGHỊ GIẢI QUYẾT", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 18
        requests_lines = [
            f"1. Đề nghị cơ quan có thẩm quyền tiếp nhận và giải quyết thủ tục: {clean_p_title}",
            f"2. Thành phần hồ sơ cung cấp: {doc_name}",
            "3. Nội dung kê khai chi tiết:",
            "   .....................................................................................................................................................",
            "   .....................................................................................................................................................",
        ]
        for line in requests_lines:
            page.insert_text(fitz.Point(70, y), line, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 17

        y += 6
        page.insert_text(fitz.Point(60, y), "III. TÀI LIỆU KÈM THEO & LỜI CAM ĐOAN", fontname=boldfont, fontsize=10, color=(0, 0, 0))
        y += 18
        att_lines = [
            f"[ x ] {doc_name} (Bản chính hoặc bản chứng thực hợp lệ)",
            "[ x ] Bản sao Căn cước công dân / Hộ chiếu của người làm đơn",
            "Tôi xin cam đoan toàn bộ các thông tin đã kê khai trên đây là hoàn toàn đúng sự thật và chịu trách nhiệm pháp luật.",
        ]
        for line in att_lines:
            page.insert_text(fitz.Point(70, y), line, fontname=fontname, fontsize=8.5, color=(0, 0, 0))
            y += 16

        y += 20
        page.insert_text(fitz.Point(340, y), "......, ngày ...... tháng ...... năm 202...", fontname=italicfont, fontsize=8.5, color=(0, 0, 0))
        y += 14
        page.insert_text(fitz.Point(80, y), "CƠ QUAN TIẾP NHẬN", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(365, y), "NGƯỜI LÀM ĐƠN", fontname=boldfont, fontsize=9.5, color=(0, 0, 0))
        y += 12
        page.insert_text(fitz.Point(85, y), "(Ký, đóng dấu tiếp nhận)", fontname=italicfont, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(360, y), "(Ký và ghi rõ họ tên)", fontname=italicfont, fontsize=8, color=(0, 0, 0))

        # Khung kiểm soát một cửa theo Nghị định 61/2018/NĐ-CP ở cuối trang
        y += 45
        box_top = y
        box_bot = y + 78
        page.draw_rect(fitz.Rect(50, box_top, 545, box_bot), color=(0, 0, 0), width=0.8)
        page.insert_text(fitz.Point(60, box_top + 14), "PHIẾU TIẾP NHẬN HỒ SƠ VÀ HẸN TRẢ KẾT QUẢ (Theo Nghị định số 61/2018/NĐ-CP):", fontname=boldfont, fontsize=8.5, color=(0, 0, 0))
        page.insert_text(fitz.Point(65, box_top + 28), "- Mã số hồ sơ TTHC: ..................................................................... Ngày tiếp nhận: ....../....../.........", fontname=fontname, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(65, box_top + 42), "- Cán bộ tiếp nhận: ..................................................................... Thời hạn giải quyết: ........... ngày làm việc", fontname=fontname, fontsize=8, color=(0, 0, 0))
        page.insert_text(fitz.Point(65, box_top + 56), "- Ngày hẹn trả kết quả: ....../....../......... Tại: Bộ phận Một cửa .....................................................................", fontname=fontname, fontsize=8, color=(0, 0, 0))

        self._draw_footer(page, fontname)
        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes



# Singleton instance để các module khác có thể import trực tiếp
pdf_service = PdfTemplateService()

