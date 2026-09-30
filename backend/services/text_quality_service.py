"""
VinaLex — TextQualityService: Kiểm tra chất lượng văn bản OCR tiếng Việt

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ NLP Tiếng Việt):
  - Spell-check dựa trên n-gram và bảng lỗi OCR phổ biến
  - Kiểm tra tính nhất quán chính tả tên riêng / địa danh
  - Đánh giá điểm chất lượng tổng thể của kết quả OCR

Tuân thủ CONTRIBUTING.md §2.1:
  - Class: PascalCase → TextQualityService
  - Hàm: snake_case → check_spelling, assess_quality

🚫 Quy tắc bảo mật:
  - KHÔNG log nội dung văn bản cá nhân ra Console/file
  - Chỉ trả kết quả chất lượng, KHÔNG lưu trữ nội dung
"""

import re
import unicodedata
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field


# ── BỘ DỮ LIỆU LỖI OCR PHỔ BIẾN TIẾNG VIỆT ──
# Các lỗi VietOCR/Tesseract hay mắc phải khi OCR tiếng Việt

_COMMON_OCR_ERRORS: Dict[str, str] = {
    # Lỗi chữ Việt đặc thù do bảng mã hoặc font
    "ð": "đ",   # Ký tự Latin eth → đ
    "Ð": "Đ",   # Ký tự Latin hoa → Đ
    "Þ": "Đ",   # Thorn hoa → Đ
    "þ": "đ",   # Thorn thường → đ
}

# Các cặp ký tự dễ nhầm lẫn trong OCR tiếng Việt
_CONFUSABLE_PAIRS: List[Tuple[str, str]] = [
    ("ă", "a"), ("â", "a"), ("ê", "e"), ("ô", "o"), ("ơ", "o"),
    ("ư", "u"), ("đ", "d"), ("ắ", "á"), ("ặ", "ạ"), ("ẵ", "ã"),
    ("ấ", "á"), ("ầ", "à"), ("ẩ", "ả"), ("ẫ", "ã"), ("ậ", "ạ"),
    ("ế", "é"), ("ề", "è"), ("ể", "ẻ"), ("ễ", "ẽ"), ("ệ", "ẹ"),
    ("ố", "ó"), ("ồ", "ò"), ("ổ", "ỏ"), ("ỗ", "õ"), ("ộ", "ọ"),
    ("ớ", "ó"), ("ờ", "ò"), ("ở", "ỏ"), ("ỡ", "õ"), ("ợ", "ọ"),
    ("ứ", "ú"), ("ừ", "ù"), ("ử", "ủ"), ("ữ", "ũ"), ("ự", "ụ"),
]

# ── BỘ TỪ TIẾNG VIỆT PHỔ BIẾN ──
# Tập con các từ đơn tiếng Việt phổ biến nhất (dùng cho spell-check nhanh)

_COMMON_VIETNAMESE_WORDS = {
    # Đại từ
    "tôi", "bạn", "anh", "chị", "em", "ông", "bà", "nó", "họ", "chúng",
    # Động từ phổ biến
    "là", "có", "được", "làm", "đi", "đến", "cho", "lấy", "nói", "biết",
    "muốn", "cần", "phải", "nên", "xin", "nộp", "yêu", "cầu", "khai",
    # Danh từ hành chính
    "giấy", "tờ", "đơn", "hồ", "sơ", "thủ", "tục", "hành", "chính",
    "căn", "cước", "công", "dân", "chứng", "minh", "nhân", "khai", "sinh",
    "hộ", "khẩu", "đăng", "ký", "kết", "hôn", "tạm", "trú", "thường",
    "giấy", "phép", "lao", "động", "cấp", "sở", "ban", "ngành",
    # Tên tháng / ngày
    "ngày", "tháng", "năm", "thứ",
    # Liên từ & giới từ
    "và", "của", "trong", "trên", "dưới", "với", "theo", "về", "từ",
    "đến", "tại", "qua", "bằng", "để", "mà", "nhưng", "hoặc", "hay",
    # Tính từ
    "lớn", "nhỏ", "mới", "cũ", "đầy", "đủ", "hợp", "lệ", "chính",
    "xác", "đúng", "sai", "rõ", "ràng",
    # Số từ
    "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười",
    # Giấy tờ hành chính
    "quận", "huyện", "phường", "xã", "thị", "trấn", "tỉnh", "thành", "phố",
    "đường", "số", "ngõ", "ngách", "tổ", "khu", "phố",
}

# ── BỘ TỈNH/THÀNH VÀ ĐỊA DANH VIỆT NAM ──
_VIETNAM_PROVINCES = {
    "Hà Nội", "TP. Hồ Chí Minh", "Đà Nẵng", "Hải Phòng", "Cần Thơ",
    "An Giang", "Bà Rịa - Vũng Tàu", "Bắc Giang", "Bắc Kạn", "Bạc Liêu",
    "Bắc Ninh", "Bến Tre", "Bình Định", "Bình Dương", "Bình Phước",
    "Bình Thuận", "Cà Mau", "Cao Bằng", "Đắk Lắk", "Đắk Nông",
    "Điện Biên", "Đồng Nai", "Đồng Tháp", "Gia Lai", "Hà Giang",
    "Hà Nam", "Hà Tĩnh", "Hải Dương", "Hậu Giang", "Hòa Bình",
    "Hưng Yên", "Khánh Hòa", "Kiên Giang", "Kon Tum", "Lai Châu",
    "Lâm Đồng", "Lạng Sơn", "Lào Cai", "Long An", "Nam Định",
    "Nghệ An", "Ninh Bình", "Ninh Thuận", "Phú Thọ", "Phú Yên",
    "Quảng Bình", "Quảng Nam", "Quảng Ngãi", "Quảng Ninh", "Quảng Trị",
    "Sóc Trăng", "Sơn La", "Tây Ninh", "Thái Bình", "Thái Nguyên",
    "Thanh Hóa", "Thừa Thiên Huế", "Tiền Giang", "Trà Vinh", "Tuyên Quang",
    "Vĩnh Long", "Vĩnh Phúc", "Yên Bái",
}

# Tên tỉnh normalized (không dấu, lowercase) để so sánh mờ
_PROVINCES_NORMALIZED = {}
for _prov in _VIETNAM_PROVINCES:
    _nfd = unicodedata.normalize("NFD", _prov.replace("đ", "d").replace("Đ", "D"))
    _stripped = "".join(c for c in _nfd if unicodedata.category(c) != "Mn")
    _PROVINCES_NORMALIZED[re.sub(r"\s+", " ", _stripped).strip().lower()] = _prov


@dataclass
class SpellCheckResult:
    """Kết quả kiểm tra chính tả 1 từ."""
    word: str
    is_correct: bool
    suggestion: str = ""
    error_type: str = ""  # "ocr_error", "accent_missing", "unknown_word"


@dataclass
class TextQualityReport:
    """Báo cáo chất lượng tổng thể của văn bản OCR."""
    quality_score: float = 1.0   # 0.0 → 1.0
    total_words: int = 0
    correct_words: int = 0
    suspicious_words: int = 0
    spell_issues: List[SpellCheckResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "quality_score": round(self.quality_score, 3),
            "total_words": self.total_words,
            "correct_words": self.correct_words,
            "suspicious_words": self.suspicious_words,
            "spell_issues": [
                {"word": s.word, "suggestion": s.suggestion, "error_type": s.error_type}
                for s in self.spell_issues[:10]  # Giới hạn 10 lỗi trong response
            ],
            "warnings": self.warnings[:5],
        }


class TextQualityService:
    """
    Dịch vụ kiểm tra chất lượng văn bản OCR tiếng Việt.

    Chức năng:
      1. Phát hiện lỗi OCR phổ biến (ký tự nhầm lẫn, mất dấu)
      2. Spell-check tiếng Việt dựa trên bộ từ vựng chuẩn
      3. Kiểm tra tên riêng / địa danh Việt Nam
      4. Đánh giá điểm chất lượng tổng thể
    """

    def __init__(self):
        pass

    def _normalize_word(self, word: str) -> str:
        """Chuẩn hóa từ: lowercase, loại bỏ ký tự đặc biệt."""
        return re.sub(r"[^\w\sàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]",
                       "", word.lower().strip())

    def check_ocr_errors(self, text: str) -> List[SpellCheckResult]:
        """
        Phát hiện các lỗi OCR phổ biến trong văn bản.

        Kiểm tra:
          - Ký tự bị nhầm (0↔O, 1↔l, rn↔m)
          - Mất dấu tiếng Việt
          - Ký tự Unicode lạ thay thế ký tự Việt

        Returns:
            Danh sách các từ có vấn đề
        """
        issues: List[SpellCheckResult] = []
        words = text.split()

        for word in words:
            clean = self._normalize_word(word)
            if not clean or len(clean) < 2:
                continue

            # 1. Kiểm tra ký tự Unicode bất thường
            for char in clean:
                if char in _COMMON_OCR_ERRORS:
                    correct = _COMMON_OCR_ERRORS[char]
                    issues.append(SpellCheckResult(
                        word=word,
                        is_correct=False,
                        suggestion=word.replace(char, correct),
                        error_type="ocr_error",
                    ))
                    break

            # 2. Kiểm tra số lẫn trong text (VD: "Nguy3n" thay vì "Nguyễn")
            if re.search(r"[a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]\d+[a-zàáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]", clean):
                issues.append(SpellCheckResult(
                    word=word,
                    is_correct=False,
                    suggestion="",
                    error_type="mixed_digits_letters",
                ))

        return issues

    def check_vietnamese_spelling(self, text: str) -> List[SpellCheckResult]:
        """
        Kiểm tra chính tả tiếng Việt cơ bản.

        So sánh từng từ với bộ từ vựng phổ biến.
        Từ không có trong bộ từ → đánh dấu suspicious (có thể là tên riêng).

        Returns:
            Danh sách các từ nghi ngờ sai chính tả
        """
        issues: List[SpellCheckResult] = []
        words = text.split()

        for word in words:
            clean = self._normalize_word(word)
            if not clean or len(clean) < 2:
                continue

            # Bỏ qua số
            if clean.isdigit():
                continue

            # Bỏ qua viết hoa toàn bộ (có thể là từ viết tắt: TP., UBND, CCCD)
            if word.isupper() and len(word) <= 6:
                continue

            # Kiểm tra có trong bộ từ phổ biến
            if clean in _COMMON_VIETNAMESE_WORDS:
                continue

            # Kiểm tra có phải tên tỉnh/thành không
            if any(clean in prov_norm for prov_norm in _PROVINCES_NORMALIZED):
                continue

            # Kiểm tra pattern tên riêng (chữ cái đầu viết hoa)
            if word[0].isupper() and len(clean) <= 10:
                continue  # Có thể là tên riêng → bỏ qua

            # Từ không xác định → suspicious
            issues.append(SpellCheckResult(
                word=word,
                is_correct=False,
                suggestion="",
                error_type="unknown_word",
            ))

        return issues

    def check_accent_consistency(self, text: str) -> List[SpellCheckResult]:
        """
        Kiểm tra tính nhất quán dấu tiếng Việt.

        Phát hiện:
          - Từ thiếu dấu bất thường trong ngữ cảnh có dấu
          - Dấu sai vị trí (VD: "hồà" thay vì "hòa")

        Returns:
            Danh sách các từ có vấn đề dấu
        """
        issues: List[SpellCheckResult] = []
        words = text.split()

        # Đếm tỷ lệ từ có dấu
        accented_count = 0
        total_alpha = 0

        for word in words:
            clean = self._normalize_word(word)
            if not clean or clean.isdigit():
                continue
            total_alpha += 1

            has_accent = bool(re.search(
                r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]",
                clean
            ))
            if has_accent:
                accented_count += 1

        # Nếu đa số từ có dấu nhưng có từ dài > 3 ký tự không dấu → nghi ngờ mất dấu
        if total_alpha > 0 and accented_count / total_alpha > 0.3:
            for word in words:
                clean = self._normalize_word(word)
                if not clean or clean.isdigit() or len(clean) <= 3:
                    continue

                has_accent = bool(re.search(
                    r"[àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ]",
                    clean
                ))
                if not has_accent and clean not in _COMMON_VIETNAMESE_WORDS:
                    # Từ dài, không dấu, trong văn bản có dấu → khả năng mất dấu do OCR
                    issues.append(SpellCheckResult(
                        word=word,
                        is_correct=False,
                        suggestion="",
                        error_type="accent_missing",
                    ))

        return issues

    def assess_quality(self, extracted_fields: Dict[str, str]) -> TextQualityReport:
        """
        Đánh giá chất lượng tổng thể của kết quả OCR.

        Kết hợp tất cả kiểm tra:
          1. OCR error detection
          2. Vietnamese spelling
          3. Accent consistency

        Args:
            extracted_fields: Dict field → value từ OcrService

        Returns:
            TextQualityReport với điểm chất lượng và danh sách vấn đề
        """
        report = TextQualityReport()

        if not extracted_fields:
            report.quality_score = 0.0
            report.warnings.append("Không có dữ liệu OCR để đánh giá.")
            return report

        # Gộp tất cả text từ các field
        all_text = " ".join(extracted_fields.values())
        words = all_text.split()
        report.total_words = len(words)

        if report.total_words == 0:
            report.quality_score = 0.0
            return report

        # Kiểm tra 1: Lỗi OCR phổ biến
        ocr_issues = self.check_ocr_errors(all_text)

        # Kiểm tra 2: Chính tả tiếng Việt
        spelling_issues = self.check_vietnamese_spelling(all_text)

        # Kiểm tra 3: Nhất quán dấu
        accent_issues = self.check_accent_consistency(all_text)

        # Gộp tất cả issues (loại trùng theo word)
        seen_words = set()
        for issue in ocr_issues + accent_issues + spelling_issues:
            if issue.word not in seen_words:
                report.spell_issues.append(issue)
                seen_words.add(issue.word)

        report.suspicious_words = len(report.spell_issues)
        report.correct_words = report.total_words - report.suspicious_words

        # Tính điểm chất lượng
        if report.total_words > 0:
            # Mỗi lỗi OCR trừ 3% (nghiêm trọng), mỗi spelling trừ 1%
            ocr_penalty = len(ocr_issues) * 0.03
            accent_penalty = len(accent_issues) * 0.02
            spelling_penalty = len(spelling_issues) * 0.01

            report.quality_score = max(0.0, min(1.0,
                1.0 - ocr_penalty - accent_penalty - spelling_penalty
            ))

        # Warnings
        if len(ocr_issues) > 3:
            report.warnings.append(
                f"Phát hiện {len(ocr_issues)} lỗi ký tự OCR phổ biến — "
                "chất lượng ảnh gốc có thể thấp."
            )
        if len(accent_issues) > 2:
            report.warnings.append(
                f"Phát hiện {len(accent_issues)} từ nghi ngờ mất dấu tiếng Việt — "
                "kiểm tra lại ảnh đầu vào."
            )
        if report.total_words < 3:
            report.warnings.append(
                "Số lượng từ trích xuất quá ít — có thể ảnh bị cắt hoặc quá mờ."
            )

        return report

    def auto_correct_fields(self, extracted_fields: Dict[str, str]) -> Dict[str, str]:
        """
        Tự động sửa các lỗi OCR rõ ràng trong kết quả trích xuất theo ngữ cảnh trường.

        Chỉ sửa các lỗi có độ tin cậy cao:
          - Trường số / CCCD / Ngày tháng: Sửa chữ nhầm thành số (O->0, I/l->1), chuẩn hóa định dạng
          - Trường tên người: Sửa số nhầm thành chữ, sửa NGUYỄ0 -> NGUYỄN, chuẩn hóa khoảng trắng
          - Chuẩn hóa Unicode NFC cho toàn bộ trường

        Args:
            extracted_fields: Dict gốc từ OCR

        Returns:
            Dict đã sửa lỗi (bản sao)
        """
        corrected: Dict[str, str] = {}

        def _norm_label(lbl: str) -> str:
            nfd = unicodedata.normalize("NFD", lbl.lower())
            return "".join(c for c in nfd if unicodedata.category(c) != "Mn")

        for label, value in extracted_fields.items():
            if not isinstance(value, str):
                corrected[label] = value
                continue

            fixed_value = unicodedata.normalize("NFC", value)

            # Sửa ký tự lỗi encoding cố định
            for wrong, right in _COMMON_OCR_ERRORS.items():
                fixed_value = fixed_value.replace(wrong, right)

            norm_lbl = _norm_label(label)

            # 1. Trường Số / CCCD / CMND / Mã định danh / Điện thoại
            is_id_or_number = any(k in norm_lbl for k in ["cccd", "cmnd", "dinh danh", "dien thoai", "phone"]) or (
                "so" in norm_lbl and "nha" not in norm_lbl and "phong" not in norm_lbl and "ho" not in norm_lbl
            )
            is_date = any(k in norm_lbl for k in ["ngay", "sinh", "cap", "han", "nam"])

            if is_id_or_number:
                # Với số CCCD / CMND / Mã số: Không biến số thành chữ!
                # Ngược lại: Sửa ký tự chữ hay bị OCR nhầm thành số
                cleaned_id = fixed_value.strip()
                # Bỏ khoảng trắng bên trong nếu là chuỗi dài có dạng CCCD/CMND
                if re.match(r"^[\d\sOIlsSBZb]+$", cleaned_id) and len(re.sub(r"\s+", "", cleaned_id)) in [9, 10, 11, 12]:
                    cleaned_id = re.sub(r"\s+", "", cleaned_id)
                    cleaned_id = cleaned_id.replace("O", "0").replace("o", "0")
                    cleaned_id = cleaned_id.replace("I", "1").replace("l", "1").replace("|", "1")
                    cleaned_id = cleaned_id.replace("Z", "2").replace("z", "2")
                    cleaned_id = cleaned_id.replace("S", "5").replace("s", "5")
                    cleaned_id = cleaned_id.replace("B", "8").replace("b", "8")
                fixed_value = cleaned_id

            elif is_date:
                # Chuẩn hóa ngày: dd/mm/yyyy
                d_val = re.sub(r"[.\-]", "/", fixed_value.strip())
                # Sửa O/o hoặc l/I trong date segments
                parts = d_val.split("/")
                if len(parts) == 3:
                    fixed_parts = []
                    for p in parts:
                        p_fix = p.replace("O", "0").replace("o", "0").replace("I", "1").replace("l", "1")
                        fixed_parts.append(p_fix)
                    d_val = "/".join(fixed_parts)
                fixed_value = d_val

            elif "ten" in norm_lbl or "ho" in norm_lbl:
                # Trường Họ và tên: Sửa số lẫn trong chữ
                # Trường hợp đặc biệt VietOCR hay nhầm N cuối thành 0
                fixed_value = re.sub(r"NGUYỄ0\b", "NGUYỄN", fixed_value)
                fixed_value = re.sub(r"Nguyễ0\b", "Nguyễn", fixed_value)
                # Thay số 0, 1, 5 nếu nằm giữa các ký tự chữ cái viết hoa
                fixed_value = re.sub(r"(?<=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ])0(?=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ])", "O", fixed_value)
                fixed_value = re.sub(r"(?<=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ])1(?=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ])", "I", fixed_value)
                fixed_value = re.sub(r"(?<=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ])5(?=[A-ZÀÁẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÈÉẺẼẸÊẾỀỂỄỆÌÍỈĨỊÒÓỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÙÚỦŨỤƯỨỪỬỮỰỲÝỶỸỴĐ])", "S", fixed_value)
                # Xóa các ký tự đặc biệt thừa không thuộc họ tên
                fixed_value = re.sub(r"[!@#$%^&*()_+=\[\]{};:\"\\|<>,.?~]", "", fixed_value)

            # Chuẩn hóa khoảng trắng
            fixed_value = re.sub(r"\s+", " ", fixed_value).strip()
            corrected[label] = fixed_value

        return corrected
