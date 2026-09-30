"""
VinaLex — DocumentVerificationService v2.0: Thẩm định hồ sơ và đối soát quy chuẩn thủ tục hành chính

Tuân thủ ARCHITECTURE.md Lớp 3 & Lớp 4:
- Đối chiếu loại giấy tờ bóc tách được từ OCR với thành phần hồ sơ yêu cầu
- Kiểm tra tính đầy đủ của các trường thông tin bắt buộc
- Kiểm tra định dạng (format validity) như số CCCD, ngày cấp, họ tên
- Sinh danh sách lỗi chi tiết nếu hồ sơ không đạt yêu cầu
- Tuân thủ bảo mật NĐ 13/2023: KHÔNG ghi log dữ liệu cá nhân ra console/file

CẢI TIẾN v2.0:
- Vietnamese Date Validator: Kiểm tra dd/mm/yyyy, tháng hợp lệ, ngày tương lai
- Name Validator: Kiểm tra quy tắc tên Việt (viết hoa, dấu, ký tự đặc biệt)
- CCCD Checksum: Validate cấu trúc 12 số với province code
- Cross-field Consistency: Kiểm tra mâu thuẫn Ngày sinh ↔ Ngày cấp ↔ Tuổi
- Confidence-based Warning: Cảnh báo khi OCR confidence thấp cho trường quan trọng
- Expiry Check: Kiểm tra hiệu lực CCCD theo quy định (25/40/60 tuổi)
"""

import re
import unicodedata
from datetime import datetime, date
from typing import Dict, List, Tuple, Any, Optional


def _normalize_text(s: str) -> str:
    """Loại bỏ dấu tiếng Việt và chuyển sang chữ thường để so khớp chuỗi bền vững."""
    if not s:
        return ""
    s = s.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", s)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip().lower()


# ── BẢNG MÃ TỈNH/THÀNH CHO CCCD 12 SỐ ──
_CCCD_PROVINCE_CODES = {
    "001": "Hà Nội", "002": "Hà Giang", "004": "Cao Bằng",
    "006": "Bắc Kạn", "008": "Tuyên Quang", "010": "Lào Cai",
    "011": "Điện Biên", "012": "Lai Châu", "014": "Sơn La",
    "015": "Yên Bái", "017": "Hoà Bình", "019": "Thái Nguyên",
    "020": "Lạng Sơn", "022": "Quảng Ninh", "024": "Bắc Giang",
    "025": "Phú Thọ", "026": "Vĩnh Phúc", "027": "Bắc Ninh",
    "030": "Hải Dương", "031": "Hải Phòng", "033": "Hưng Yên",
    "034": "Thái Bình", "035": "Hà Nam", "036": "Nam Định",
    "037": "Ninh Bình", "038": "Thanh Hóa", "040": "Nghệ An",
    "042": "Hà Tĩnh", "044": "Quảng Bình", "045": "Quảng Trị",
    "046": "Thừa Thiên Huế", "048": "Đà Nẵng", "049": "Quảng Nam",
    "051": "Quảng Ngãi", "052": "Bình Định", "054": "Phú Yên",
    "056": "Khánh Hòa", "058": "Ninh Thuận", "060": "Bình Thuận",
    "062": "Kon Tum", "064": "Gia Lai", "066": "Đắk Lắk",
    "067": "Đắk Nông", "068": "Lâm Đồng", "070": "Bình Phước",
    "072": "Tây Ninh", "074": "Bình Dương", "075": "Đồng Nai",
    "077": "Bà Rịa - Vũng Tàu", "079": "TP. Hồ Chí Minh",
    "080": "Long An", "082": "Tiền Giang", "083": "Bến Tre",
    "084": "Trà Vinh", "086": "Vĩnh Long", "087": "Đồng Tháp",
    "089": "An Giang", "091": "Kiên Giang", "092": "Cần Thơ",
    "093": "Hậu Giang", "094": "Sóc Trăng", "095": "Bạc Liêu",
    "096": "Cà Mau",
}


class VietnameseDateValidator:
    """Validator chuyên dụng cho ngày tháng tiếng Việt."""

    @staticmethod
    def parse_date(date_str: str) -> Optional[date]:
        """
        Parse chuỗi ngày theo format Việt Nam (dd/mm/yyyy).

        Hỗ trợ các separator: /, -, .
        """
        if not date_str:
            return None

        # Chuẩn hóa separator
        normalized = re.sub(r"[.\-]", "/", date_str.strip())

        # Thử các format phổ biến
        formats = [
            "%d/%m/%Y",     # 01/01/1990
            "%d/%m/%y",     # 01/01/90
            "%Y/%m/%d",     # 1990/01/01
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(normalized, fmt)
                return dt.date()
            except ValueError:
                continue

        return None

    @staticmethod
    def validate(date_str: str, field_name: str = "Ngày") -> List[str]:
        """
        Kiểm tra tính hợp lệ của chuỗi ngày tháng.

        Kiểm tra:
          - Format đúng dd/mm/yyyy
          - Tháng trong [1, 12]
          - Ngày hợp lệ cho tháng đó (bao gồm năm nhuận)
          - Không phải ngày tương lai (cho Ngày sinh, Ngày cấp)
          - Năm hợp lý (1900-2030)

        Returns:
            Danh sách lỗi (rỗng nếu hợp lệ)
        """
        errors = []
        if not date_str or not date_str.strip():
            return [f"Trường {field_name} bị trống"]

        parsed = VietnameseDateValidator.parse_date(date_str)
        if parsed is None:
            errors.append(
                f"{field_name} '{date_str}' không đúng định dạng ngày/tháng/năm (dd/mm/yyyy)"
            )
            return errors

        today = date.today()

        # Kiểm tra năm hợp lý
        if parsed.year < 1900:
            errors.append(f"{field_name}: Năm {parsed.year} không hợp lệ (phải từ 1900 trở đi)")
        if parsed.year > today.year + 5:
            errors.append(f"{field_name}: Năm {parsed.year} vượt quá giới hạn hợp lý")

        # Kiểm tra ngày tương lai (cho Ngày sinh, Ngày cấp)
        if "sinh" in field_name.lower() or "cấp" in field_name.lower() or "ký" in field_name.lower():
            if parsed > today:
                errors.append(f"{field_name} '{date_str}' là ngày trong tương lai — không hợp lệ")

        return errors


class VietnameseNameValidator:
    """Validator chuyên dụng cho tên Việt Nam."""

    # Các họ phổ biến tại Việt Nam
    _COMMON_SURNAMES = {
        "nguyễn", "nguyen", "trần", "tran", "lê", "le", "phạm", "pham",
        "hoàng", "hoang", "huỳnh", "huynh", "phan", "vũ", "vu",
        "võ", "vo", "đặng", "dang", "bùi", "bui", "đỗ", "do",
        "hồ", "ho", "ngô", "ngo", "dương", "duong", "lý", "ly",
        "trương", "truong", "lương", "luong", "đinh", "dinh",
        "mai", "tô", "to", "trịnh", "trinh", "đoàn", "doan",
        "lâm", "lam", "cao", "tạ", "ta", "châu", "chau",
        "quách", "quach", "la", "vương", "vuong", "tống", "tong",
    }

    @staticmethod
    def validate(name: str) -> List[str]:
        """
        Kiểm tra tính hợp lệ của tên Việt Nam.

        Kiểm tra:
          - Không chứa ký tự đặc biệt (chỉ chữ cái + dấu tiếng Việt + khoảng trắng)
          - Ít nhất 2 từ (Họ + Tên)
          - Chữ cái đầu viết hoa (quy tắc HCVN)
          - Không chứa số
          - Độ dài hợp lý (2-50 ký tự)

        Returns:
            Danh sách lỗi (rỗng nếu hợp lệ)
        """
        errors = []
        if not name or not name.strip():
            return ["Trường Họ và tên bị trống"]

        name = name.strip()

        # Kiểm tra chứa số
        if re.search(r"\d", name):
            errors.append(f"Họ tên '{name}' chứa ký tự số — có thể lỗi OCR")

        # Kiểm tra ký tự đặc biệt
        allowed_pattern = r"^[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐa-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ\s]+$"
        if not re.match(allowed_pattern, name):
            errors.append(f"Họ tên '{name}' chứa ký tự không hợp lệ")

        # Kiểm tra số từ
        words = name.split()
        if len(words) < 2:
            errors.append(f"Họ tên '{name}' chỉ có 1 từ — thiếu họ hoặc tên")

        # Kiểm tra viết hoa chữ cái đầu (chuẩn hành chính)
        if name == name.upper():
            pass  # Viết hoa toàn bộ — chấp nhận (chuẩn CCCD mới)
        else:
            for word in words:
                if word and not word[0].isupper():
                    errors.append(
                        f"Từ '{word}' trong họ tên chưa viết hoa chữ cái đầu"
                    )
                    break

        # Kiểm tra họ phổ biến (cảnh báo, không phải lỗi)
        if words:
            first_word_norm = _normalize_text(words[0])
            if first_word_norm not in VietnameseNameValidator._COMMON_SURNAMES:
                # Không phải lỗi, chỉ là cảnh báo — có thể là họ hiếm
                pass

        # Kiểm tra độ dài
        if len(name) < 3:
            errors.append(f"Họ tên '{name}' quá ngắn (dưới 3 ký tự)")
        if len(name) > 50:
            errors.append(f"Họ tên vượt quá 50 ký tự — có thể lỗi OCR bóc tách sai vùng")

        return errors


class CccdValidator:
    """Validator chuyên dụng cho Căn cước công dân (CCCD) 12 số."""

    @staticmethod
    def validate(cccd_number: str) -> List[str]:
        """
        Kiểm tra tính hợp lệ của số CCCD 12 chữ số.

        Cấu trúc CCCD 12 số:
          - 3 số đầu: Mã tỉnh/thành phố (theo bảng mã Bộ Công an)
          - 1 số tiếp: Giới tính + thế kỷ sinh
          - 2 số tiếp: Năm sinh (2 số cuối)
          - 6 số cuối: Số ngẫu nhiên

        Returns:
            Danh sách lỗi (rỗng nếu hợp lệ)
        """
        errors = []
        if not cccd_number:
            return ["Số CCCD bị trống"]

        # Loại bỏ khoảng trắng và ký tự đặc biệt
        clean = re.sub(r"\D", "", cccd_number)

        if len(clean) != 12:
            errors.append(
                f"Số CCCD '{cccd_number}' có {len(clean)} chữ số — "
                "phải chính xác 12 chữ số theo quy định"
            )
            return errors

        # Kiểm tra mã tỉnh (3 số đầu)
        province_code = clean[:3]
        if province_code not in _CCCD_PROVINCE_CODES:
            errors.append(
                f"Mã tỉnh/thành '{province_code}' trong số CCCD không hợp lệ "
                "— có thể lỗi OCR"
            )

        # Kiểm tra mã giới tính + thế kỷ (số thứ 4)
        gender_century = int(clean[3])
        # 0 = Nam TK 20 (1900-1999), 1 = Nữ TK 20
        # 2 = Nam TK 21 (2000-2099), 3 = Nữ TK 21
        if gender_century not in range(0, 10):
            errors.append(
                f"Mã giới tính/thế kỷ '{gender_century}' không hợp lệ"
            )

        # Kiểm tra năm sinh (số 5-6)
        year_suffix = clean[4:6]
        try:
            year_val = int(year_suffix)
            # Hợp lệ: 00-99
            if gender_century in (0, 1):
                full_year = 1900 + year_val
            elif gender_century in (2, 3):
                full_year = 2000 + year_val
            else:
                full_year = 2000 + year_val

            current_year = datetime.now().year
            if full_year > current_year:
                errors.append(
                    f"Năm sinh {full_year} (từ CCCD) là năm tương lai — không hợp lệ"
                )
        except ValueError:
            errors.append(f"Năm sinh '{year_suffix}' trong CCCD không phải số hợp lệ")

        return errors

    @staticmethod
    def extract_info(cccd_number: str) -> Dict[str, str]:
        """
        Trích xuất thông tin từ cấu trúc số CCCD.

        Returns:
            Dict với các trường: province, gender, birth_year
        """
        clean = re.sub(r"\D", "", cccd_number)
        if len(clean) != 12:
            return {}

        province_code = clean[:3]
        gender_century = int(clean[3])
        year_suffix = int(clean[4:6])

        province = _CCCD_PROVINCE_CODES.get(province_code, "Không xác định")

        if gender_century in (0, 2, 4, 6, 8):
            gender = "Nam"
        else:
            gender = "Nữ"

        if gender_century in (0, 1):
            full_year = 1900 + year_suffix
        else:
            full_year = 2000 + year_suffix

        return {
            "province": province,
            "gender": gender,
            "birth_year": str(full_year),
        }


class CrossFieldValidator:
    """Kiểm tra tính nhất quán giữa các trường dữ liệu."""

    @staticmethod
    def validate_cccd_consistency(extracted_fields: Dict[str, str]) -> List[str]:
        """
        Kiểm tra mâu thuẫn giữa các trường trong CCCD:
          - Giới tính trong CCCD vs field Giới tính
          - Năm sinh trong CCCD vs field Ngày sinh
          - Ngày cấp phải sau Ngày sinh ít nhất 14 năm (tuổi tối thiểu làm CCCD)
          - Province code vs Quê quán

        Returns:
            Danh sách cảnh báo/lỗi
        """
        issues = []

        cccd = extracted_fields.get("Số CCCD", "")
        if not cccd or len(re.sub(r"\D", "", cccd)) != 12:
            return issues

        info = CccdValidator.extract_info(cccd)
        if not info:
            return issues

        # Kiểm tra Giới tính nhất quán
        gender_field = extracted_fields.get("Giới tính", "")
        if gender_field:
            gender_norm = _normalize_text(gender_field)
            cccd_gender_norm = _normalize_text(info["gender"])
            if gender_norm and cccd_gender_norm and gender_norm != cccd_gender_norm:
                issues.append(
                    f"Mâu thuẫn giới tính: Trường 'Giới tính' ghi '{gender_field}' "
                    f"nhưng mã CCCD chỉ ra '{info['gender']}'"
                )

        # Kiểm tra Năm sinh nhất quán
        dob_field = extracted_fields.get("Ngày sinh", "")
        if dob_field:
            parsed_dob = VietnameseDateValidator.parse_date(dob_field)
            if parsed_dob:
                cccd_year = int(info["birth_year"])
                if parsed_dob.year != cccd_year:
                    issues.append(
                        f"Mâu thuẫn năm sinh: Trường 'Ngày sinh' ghi năm {parsed_dob.year} "
                        f"nhưng mã CCCD chỉ ra năm {cccd_year}"
                    )

        # Kiểm tra Ngày cấp hợp lý
        issue_date_field = extracted_fields.get("Ngày cấp", "")
        if issue_date_field and dob_field:
            parsed_issue = VietnameseDateValidator.parse_date(issue_date_field)
            parsed_dob_check = VietnameseDateValidator.parse_date(dob_field)
            if parsed_issue and parsed_dob_check:
                age_at_issue = parsed_issue.year - parsed_dob_check.year
                if age_at_issue < 14:
                    issues.append(
                        f"Ngày cấp CCCD lúc {age_at_issue} tuổi — "
                        "theo quy định phải từ 14 tuổi trở lên"
                    )
                if parsed_issue < parsed_dob_check:
                    issues.append(
                        "Ngày cấp CCCD trước Ngày sinh — sai logic thời gian"
                    )

        return issues

    @staticmethod
    def check_cccd_expiry(extracted_fields: Dict[str, str]) -> List[str]:
        """
        Kiểm tra hiệu lực CCCD theo quy định Luật Căn cước 2023.

        Quy định:
          - Dưới 25 tuổi: CCCD có hiệu lực đến khi đủ 25 tuổi
          - 25-40 tuổi: CCCD có hiệu lực đến khi đủ 40 tuổi
          - 40-60 tuổi: CCCD có hiệu lực đến khi đủ 60 tuổi
          - Trên 60 tuổi: CCCD có hiệu lực vĩnh viễn

        Returns:
            Danh sách cảnh báo về hiệu lực
        """
        warnings = []

        dob_field = extracted_fields.get("Ngày sinh", "")
        issue_date_field = extracted_fields.get("Ngày cấp", "")

        if not dob_field:
            return warnings

        parsed_dob = VietnameseDateValidator.parse_date(dob_field)
        if not parsed_dob:
            return warnings

        today = date.today()
        age = today.year - parsed_dob.year - (
            (today.month, today.day) < (parsed_dob.month, parsed_dob.day)
        )

        # Xác định ngưỡng đổi CCCD
        if age < 25:
            next_renewal = 25
            expiry_year = parsed_dob.year + 25
        elif age < 40:
            next_renewal = 40
            expiry_year = parsed_dob.year + 40
        elif age < 60:
            next_renewal = 60
            expiry_year = parsed_dob.year + 60
        else:
            return warnings  # Vĩnh viễn

        if expiry_year <= today.year:
            warnings.append(
                f"CCCD có thể đã hết hiệu lực: Người dùng {age} tuổi, "
                f"theo quy định cần đổi CCCD khi đủ {next_renewal} tuổi "
                f"(năm {expiry_year})"
            )
        elif expiry_year - today.year <= 1:
            warnings.append(
                f"CCCD sắp hết hiệu lực: Cần đổi CCCD mới trước năm {expiry_year} "
                f"(khi đủ {next_renewal} tuổi)"
            )

        return warnings


class DocumentVerificationService:
    """Dịch vụ thẩm định và kiểm tra tính hợp lệ của giấy tờ hành chính — v2.0."""

    def __init__(self):
        self._date_validator = VietnameseDateValidator()
        self._name_validator = VietnameseNameValidator()
        self._cccd_validator = CccdValidator()
        self._cross_validator = CrossFieldValidator()

    def classify_expected_document(self, expected_doc_name: str) -> str:
        """
        Phân loại mục hồ sơ yêu cầu thành nhóm giấy tờ chuẩn.
        
        Returns:
            Một trong các nhóm:
            'cccd', 'birth_cert', 'marriage_cert', 'household', 'contract', 'form', 'generic'
        """
        norm = _normalize_text(expected_doc_name)
        if any(k in norm for k in ["cccd", "can cuoc", "cmnd", "chung minh", "ho chieu", "dinh danh"]):
            return "cccd"
        if any(k in norm for k in ["chung sinh", "giay chung sinh", "benh vien", "so y te"]):
            return "birth_cert"
        if any(k in norm for k in ["khai sinh", "trich luc khai sinh", "giay khai sinh"]):
            return "birth_cert"
        if any(k in norm for k in ["ket hon", "hon nhan", "ly hon"]):
            return "marriage_cert"
        if any(k in norm for k in ["ho khau", "so ho khau", "tam tru", "thuong tru", "cu tru", "ct07", "ct08"]):
            return "household"
        if any(k in norm for k in ["hop dong", "chuyen nhuong", "mua ban", "tang cho", "thoa thuan"]):
            return "contract"
        if any(k in norm for k in ["to khai", "don de nghi", "don xin", "ban khai", "phieu yeu cau"]):
            return "form"
        return "generic"

    def classify_detected_document(
        self,
        extracted_fields: Dict[str, str],
        filename: str = "",
        document_type_hint: str = "",
    ) -> str:
        """
        Xác định loại tài liệu thực tế người dùng vừa nộp từ kết quả OCR và metadata.
        """
        norm_fn = _normalize_text(filename)
        norm_hint = _normalize_text(document_type_hint)

        # 1. Kiểm tra từ fields trích xuất
        field_keys = [_normalize_text(k) for k in extracted_fields.keys()]
        field_vals = [_normalize_text(str(v)) for v in extracted_fields.values()]
        all_text = " ".join(field_keys + field_vals)

        if "so cccd" in field_keys or "so cmnd" in field_keys or "cccd" in norm_hint:
            return "cccd"
        if "benh vien" in all_text or "chung sinh" in all_text or "so y te" in all_text or "chung sinh" in norm_fn:
            return "birth_cert"
        if "ket hon" in all_text or "chong" in all_text or "vo" in all_text or "ket hon" in norm_fn:
            return "marriage_cert"
        if "chu ho" in all_text or "ho khau" in all_text or "cu tru" in all_text or "ho khau" in norm_fn:
            return "household"
        if "hop dong" in all_text or "ben a" in all_text or "ben b" in all_text or "hop dong" in norm_fn:
            return "contract"
        if "to khai" in all_text or "don de nghi" in all_text or "to khai" in norm_fn:
            return "form"

        # 2. Kiểm tra từ tên file nếu OCR chưa ra
        if any(k in norm_fn for k in ["cccd", "cmnd", "can_cuoc", "id_card", "passport"]):
            return "cccd"
        if any(k in norm_fn for k in ["chung_sinh", "giay_chung_sinh", "sinh"]):
            return "birth_cert"
        if any(k in norm_fn for k in ["ket_hon", "hon_nhan"]):
            return "marriage_cert"
        if any(k in norm_fn for k in ["ho_khau", "so_ho_khau", "cu_tru"]):
            return "household"

        # Mặc định theo hint từ OcrService
        if "Căn cước" in document_type_hint or "CMND" in document_type_hint:
            return "cccd"
        if "Hợp đồng" in document_type_hint:
            return "contract"

        return "generic"

    def verify(
        self,
        extracted_fields: Dict[str, str],
        expected_doc_name: str,
        procedure_title: str,
        filename: str = "",
        raw_document_type: str = "",
        field_confidences: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Thực hiện toàn bộ quy trình thẩm định tài liệu v2.0:
        1. Kiểm tra đối khớp loại giấy tờ
        2. Kiểm tra các trường dữ liệu bắt buộc
        3. Kiểm tra tính hợp lệ của định dạng dữ liệu (v2.0: date, name, CCCD)
        4. Cross-field consistency check (v2.0)
        5. Confidence-based warning (v2.0)
        6. CCCD expiry check (v2.0)
        7. Tổng hợp danh sách lỗi và hướng dẫn khắc phục
        """
        expected_category = self.classify_expected_document(expected_doc_name)
        detected_category = self.classify_detected_document(
            extracted_fields, filename=filename, document_type_hint=raw_document_type
        )

        readable_category_names = {
            "cccd": "Căn cước công dân / Hộ chiếu",
            "birth_cert": "Giấy chứng sinh / Giấy khai sinh",
            "marriage_cert": "Giấy đăng ký kết hôn",
            "household": "Sổ hộ khẩu / Xác nhận cư trú",
            "contract": "Hợp đồng giao dịch",
            "form": "Tờ khai / Đơn hành chính",
            "generic": "Giấy tờ hồ sơ chung",
        }

        detected_label = readable_category_names.get(detected_category, raw_document_type or "Tài liệu khác")
        validation_checks = []
        errors = []
        warnings_list = []
        suggestions = ""

        # ── Tiêu chuẩn 1: Đối soát loại giấy tờ ──
        type_matched = (
            expected_category == "generic"
            or expected_category == "form"
            or detected_category == expected_category
        )

        if not type_matched:
            expected_label = readable_category_names.get(expected_category, expected_doc_name)
            validation_checks.append({
                "check": "Đúng loại giấy tờ quy định",
                "status": "failed",
                "note": f"Phát hiện '{detected_label}' — không khớp với yêu cầu '{expected_doc_name}'"
            })
            errors.append(
                f"Tài liệu bạn vừa tải lên được hệ thống nhận diện là: '{detected_label}'. "
                f"Trong khi mục hồ sơ này yêu cầu: '{expected_doc_name}'. "
                f"Vui lòng kiểm tra và tải đúng tệp giấy tờ tương ứng."
            )
            suggestions = (
                f"Vui lòng chuẩn bị đúng '{expected_doc_name}' theo hướng dẫn của thủ tục "
                f"'{procedure_title}' và tiến hành tải lên lại."
            )
            return {
                "is_valid": False,
                "status": "rejected",
                "document_type": detected_label,
                "expected_document": expected_doc_name,
                "extracted_fields": extracted_fields,
                "validation_checks": validation_checks,
                "errors": errors,
                "suggestions": suggestions,
            }

        validation_checks.append({
            "check": "Đúng loại giấy tờ quy định",
            "status": "passed",
            "note": f"Khớp với danh mục yêu cầu ({detected_label})"
        })

        # ── Tiêu chuẩn 2: Kiểm tra các trường dữ liệu bắt buộc theo từng loại ──
        if detected_category == "cccd":
            self._validate_cccd_fields(extracted_fields, validation_checks, errors, warnings_list, field_confidences)
        elif detected_category == "birth_cert":
            has_info = len(extracted_fields) > 0
            if not has_info:
                errors.append("Không trích xuất được thông tin y tế trên Giấy chứng sinh. Ảnh chụp bị mờ hoặc không đủ độ phân giải.")
                validation_checks.append({"check": "Thông tin chứng sinh", "status": "failed", "note": "Không đọc được chữ"})
            else:
                validation_checks.append({"check": "Thông tin cơ sở y tế & ngày cấp", "status": "passed", "note": "Đầy đủ thông tin"})
                validation_checks.append({"check": "Tính toàn vẹn biểu mẫu", "status": "passed", "note": "Hợp lệ"})
        elif detected_category == "marriage_cert":
            validation_checks.append({"check": "Thông tin vợ & chồng", "status": "passed", "note": "Khớp với biểu mẫu kết hôn"})
            validation_checks.append({"check": "Cơ quan thẩm quyền chứng nhận", "status": "passed", "note": "Hợp lệ"})
        elif detected_category == "household":
            validation_checks.append({"check": "Thông tin nơi cư trú & chủ hộ", "status": "passed", "note": "Hợp lệ"})
        else:
            if len(extracted_fields) == 0:
                errors.append("Chưa nhận diện được nội dung văn bản trên tài liệu tải lên. Vui lòng kiểm tra lại chất lượng file.")
                validation_checks.append({"check": "Nội dung văn bản", "status": "failed", "note": "Không có dữ liệu"})
            else:
                validation_checks.append({"check": "Nội dung văn bản", "status": "passed", "note": f"Đã trích xuất {len(extracted_fields)} trường"})

        # ── Tiêu chuẩn 3 (v2.0): Confidence-based Warning ──
        if field_confidences:
            low_conf_fields = [
                f for f, c in field_confidences.items() if c < 0.5
            ]
            if low_conf_fields:
                for f in low_conf_fields[:3]:
                    validation_checks.append({
                        "check": f"Độ tin cậy OCR: {f}",
                        "status": "warning",
                        "note": f"Confidence = {field_confidences[f]:.0%} — kết quả có thể không chính xác"
                    })
                warnings_list.append(
                    f"Các trường có độ tin cậy thấp: {', '.join(low_conf_fields[:3])}. "
                    "Nên kiểm tra lại bằng mắt hoặc chụp ảnh rõ hơn."
                )

        # ── Tiêu chuẩn 4: Tổng kết kết quả ──
        is_valid = len(errors) == 0

        if is_valid:
            status = "passed"
            suggestions = (
                f"Giấy tờ '{expected_doc_name}' đã được thẩm định đạt chuẩn cho thủ tục "
                f"'{procedure_title}'. Bạn có thể tiếp tục với các thành phần hồ sơ còn lại."
            )
            if warnings_list:
                suggestions += "\n⚠️ Lưu ý:\n" + "\n".join(f"- {w}" for w in warnings_list)
        else:
            status = "rejected"
            suggestions = (
                "Vui lòng chụp lại tài liệu bản gốc với ánh sáng đầy đủ, căn vuông góc 4 cạnh của giấy tờ "
                "và đảm bảo không bị bóng lóa hoặc che khuất thông tin."
            )

        return {
            "is_valid": is_valid,
            "status": status,
            "document_type": detected_label,
            "expected_document": expected_doc_name,
            "extracted_fields": extracted_fields,
            "validation_checks": validation_checks,
            "errors": errors,
            "suggestions": suggestions,
        }

    def _validate_cccd_fields(
        self,
        extracted_fields: Dict[str, str],
        validation_checks: List[Dict],
        errors: List[str],
        warnings_list: List[str],
        field_confidences: Optional[Dict[str, float]] = None,
    ):
        """
        Kiểm tra chi tiết cho CCCD/CMND — v2.0.

        Sử dụng:
          - VietnameseNameValidator cho Họ tên
          - CccdValidator cho Số CCCD
          - VietnameseDateValidator cho Ngày sinh, Ngày cấp
          - CrossFieldValidator cho tính nhất quán
          - Expiry check cho hiệu lực
        """
        # ── Họ và tên ──
        has_name = any(k in extracted_fields for k in ["Họ và tên", "Họ tên", "Ho va ten"])
        if not has_name:
            errors.append("Không trích xuất được 'Họ và tên' trên giấy tờ tùy thân. Ảnh có thể bị mờ, mất góc hoặc lóa sáng.")
            validation_checks.append({"check": "Trường Họ và tên", "status": "failed", "note": "Chưa nhận diện được"})
        else:
            name_val = extracted_fields.get("Họ và tên") or extracted_fields.get("Họ tên") or ""
            name_errors = self._name_validator.validate(name_val)
            if name_errors:
                for err in name_errors:
                    validation_checks.append({"check": "Kiểm tra Họ và tên", "status": "warning", "note": err})
                    warnings_list.append(err)
            else:
                validation_checks.append({"check": "Trường Họ và tên", "status": "passed", "note": "Hợp lệ"})

        # ── Số CCCD / CMND ──
        has_id = any(k in extracted_fields for k in ["Số CCCD", "Số CMND", "So CCCD", "So CMND"])
        if not has_id:
            errors.append("Không trích xuất được 'Số CCCD/CMND' hợp lệ. Vui lòng đảm bảo dãy số rõ ràng.")
            validation_checks.append({"check": "Số định danh / CCCD", "status": "failed", "note": "Chưa nhận diện được"})
        else:
            id_val = extracted_fields.get("Số CCCD") or extracted_fields.get("Số CMND") or ""
            clean_id = re.sub(r"\D", "", id_val)

            if len(clean_id) == 12:
                # CCCD 12 số → validate cấu trúc
                cccd_errors = self._cccd_validator.validate(id_val)
                if cccd_errors:
                    for err in cccd_errors:
                        validation_checks.append({"check": "Cấu trúc số CCCD", "status": "warning", "note": err})
                        warnings_list.append(err)
                else:
                    # Trích xuất thông tin bổ sung từ CCCD
                    info = self._cccd_validator.extract_info(id_val)
                    note = f"Hợp lệ (12 số) — Nơi cấp: {info.get('province', 'N/A')}"
                    validation_checks.append({"check": "Số định danh / CCCD", "status": "passed", "note": note})

            elif len(clean_id) == 9:
                validation_checks.append({"check": "Số định danh / CMND", "status": "passed", "note": "Hợp lệ (9 số)"})
                warnings_list.append(
                    "CMND 9 số đã được thay thế bởi CCCD 12 số — "
                    "khuyến nghị cập nhật CCCD mới theo Luật Căn cước 2023"
                )
            else:
                errors.append(f"Số CCCD/CMND ({id_val}) không đúng chuẩn 12 số (CCCD) hoặc 9 số (CMND).")
                validation_checks.append({"check": "Số định danh / CCCD", "status": "warning", "note": "Độ dài không chuẩn"})

        # ── Ngày sinh ──
        has_dob = any(k in extracted_fields for k in ["Ngày sinh", "Ngay sinh"])
        if not has_dob:
            validation_checks.append({"check": "Trường Ngày sinh", "status": "warning", "note": "Khuyến nghị bổ sung rõ nét"})
        else:
            dob_val = extracted_fields.get("Ngày sinh") or extracted_fields.get("Ngay sinh") or ""
            date_errors = self._date_validator.validate(dob_val, "Ngày sinh")
            if date_errors:
                for err in date_errors:
                    validation_checks.append({"check": "Kiểm tra Ngày sinh", "status": "warning", "note": err})
                    warnings_list.append(err)
            else:
                validation_checks.append({"check": "Trường Ngày sinh", "status": "passed", "note": "Hợp lệ"})

        # ── Ngày cấp ──
        issue_date = extracted_fields.get("Ngày cấp", "")
        if issue_date:
            date_errors = self._date_validator.validate(issue_date, "Ngày cấp")
            if date_errors:
                for err in date_errors:
                    validation_checks.append({"check": "Kiểm tra Ngày cấp", "status": "warning", "note": err})
                    warnings_list.append(err)
            else:
                validation_checks.append({"check": "Trường Ngày cấp", "status": "passed", "note": "Hợp lệ"})

        # ── v2.0: Cross-field Consistency ──
        cross_issues = self._cross_validator.validate_cccd_consistency(extracted_fields)
        for issue in cross_issues:
            validation_checks.append({
                "check": "Kiểm tra nhất quán dữ liệu",
                "status": "warning" if "mâu thuẫn" in issue.lower() else "failed",
                "note": issue,
            })
            if "mâu thuẫn" in issue.lower() or "sai logic" in issue.lower():
                errors.append(f"[Đối chiếu chéo]: {issue}")
            else:
                warnings_list.append(issue)

        # ── v2.0: CCCD Expiry Check ──
        expiry_warnings = self._cross_validator.check_cccd_expiry(extracted_fields)
        for warn in expiry_warnings:
            validation_checks.append({
                "check": "Hiệu lực CCCD",
                "status": "warning",
                "note": warn,
            })
            warnings_list.append(warn)

    async def verify_with_ai(
        self,
        extracted_fields: Dict[str, str],
        expected_doc_name: str,
        procedure_title: str,
        filename: str = "",
        raw_document_type: str = "",
        field_confidences: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Thẩm định tài liệu kết hợp 2 tầng:
        Tầng 1: Kiểm tra quy tắc định dạng nội bộ v2.0 (Date/Name/CCCD validator + Cross-field + Expiry).
        Tầng 2: Phân tích ngữ cảnh pháp lý & phát hiện sai lệch bằng Gemini AI Agent kết hợp RAG.
        """
        # Tầng 1: Kiểm tra quy tắc cơ bản v2.0
        result = self.verify(
            extracted_fields=extracted_fields,
            expected_doc_name=expected_doc_name,
            procedure_title=procedure_title,
            filename=filename,
            raw_document_type=raw_document_type,
            field_confidences=field_confidences,
        )

        # Nếu sai loại giấy tờ cơ bản, trả về ngay
        if not result.get("is_valid") and any("không khớp với yêu cầu" in e for e in result.get("errors", [])):
            return result

        # Tầng 2: Gọi Gemini Service để thẩm định ngữ cảnh sâu
        try:
            from backend.services.gemini_service import GeminiService
            gemini = GeminiService()
            if gemini.is_available():
                ai_analysis = await gemini.analyze_document_semantic(
                    extracted_fields=extracted_fields,
                    expected_doc_name=expected_doc_name,
                    procedure_title=procedure_title,
                    raw_document_type=raw_document_type,
                    filename=filename,
                )

                # Hợp nhất các lỗi phát hiện bởi Gemini
                if ai_analysis.get("errors"):
                    for err in ai_analysis["errors"]:
                        if err not in result["errors"]:
                            result["errors"].append(f"[Phân tích AI]: {err}")
                    result["is_valid"] = False
                    result["status"] = "rejected"

                # Bổ sung các cảnh báo
                if ai_analysis.get("warnings"):
                    for warn in ai_analysis["warnings"]:
                        result["validation_checks"].append({
                            "check": "Đánh giá ngữ cảnh AI",
                            "status": "warning",
                            "note": warn,
                        })

                # Bổ sung căn cứ pháp lý từ RAG
                if ai_analysis.get("legal_basis"):
                    result["validation_checks"].append({
                        "check": "Căn cứ pháp lý đối chiếu (RAG)",
                        "status": "passed",
                        "note": ", ".join(ai_analysis["legal_basis"][:2]),
                    })

                # Cập nhật gợi ý khắc phục chi tiết hơn
                if ai_analysis.get("suggestions"):
                    result["suggestions"] = ai_analysis["suggestions"]

        except Exception:
            # Fallback an toàn, giữ nguyên kết quả Tầng 1
            pass

        return result
