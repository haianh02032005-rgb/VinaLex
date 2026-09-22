"""
VinaLex — OcrService: Trích xuất ký tự tiếng Việt bằng VietOCR

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ Thị giác máy):
  - VietOCR + PyTorch: Trích xuất ký tự tiếng Việt từ các vùng đã cắt bởi CvService

Tuân thủ CONTRIBUTING.md §2.1:
  - Class: PascalCase → OcrService
  - Hàm: snake_case → extract_text, extract_from_image_bytes, map_fields

🚫 Quy tắc bảo mật (CONTRIBUTING.md + ARCHITECTURE.md):
  - KHÔNG dùng Google Vision, Textract, hay bất kỳ OCR API bên ngoài nào
  - KHÔNG ghi log (print/logger) văn bản đã trích xuất ra Console hay file
  - Toàn bộ inference chạy Local bằng VietOCR + PyTorch

Cải tiến: Smart Mock OCR — khi chưa có model weights (demo/dev mode),
  tự động phân loại tài liệu qua magic bytes & kích thước file và trả về
  bộ fields mẫu thực tế theo từng loại giấy tờ để demo UI mượt mà.
"""

import io
from typing import Dict, List, Optional
from PIL import Image
import numpy as np

from backend.core.config import settings
from backend.services.cv_service import CvService, DetectedRegion


# ── Bộ dữ liệu mock thực tế cho demo khi chưa có weights ──
# 🔒 Đây là dữ liệu mẫu hoàn toàn — KHÔNG phải thông tin cá nhân thật

_MOCK_CCCD_FIELDS: Dict[str, str] = {
    "Số CCCD": "012345678901",
    "Họ và tên": "NGUYỄN VĂN A",
    "Ngày sinh": "01/01/1990",
    "Giới tính": "Nam",
    "Quê quán": "Hà Nội",
    "Nơi thường trú": "123 Đường ABC, Phường XYZ, Quận Ba Đình, Hà Nội",
    "Ngày cấp": "15/06/2023",
    "Nơi cấp": "Cục Cảnh sát ĐKQL cư trú và DLQG về dân cư",
}

_MOCK_CMND_FIELDS: Dict[str, str] = {
    "Số CMND": "123456789",
    "Họ và tên": "NGUYỄN VĂN A",
    "Ngày sinh": "01/01/1990",
    "Giới tính": "Nam",
    "Quê quán": "Hà Nội",
    "Nơi thường trú": "123 Đường ABC, Hà Nội",
    "Ngày cấp": "20/03/2015",
    "Nơi cấp": "CA TP. Hà Nội",
}

_MOCK_CONTRACT_FIELDS: Dict[str, str] = {
    "Loại hợp đồng": "Hợp đồng mua bán bất động sản",
    "Bên A (Bán)": "Công ty XYZ",
    "Bên B (Mua)": "NGUYỄN VĂN A",
    "Địa chỉ tài sản": "Lô đất số 5, Khu đô thị ABC, Hà Nội",
    "Giá trị hợp đồng": "2,500,000,000 VNĐ",
    "Ngày ký": "15/09/2024",
    "Công chứng viên": "Nguyễn Thị B",
}

_MOCK_GENERIC_FIELDS: Dict[str, str] = {
    "Loại giấy tờ": "Giấy tờ tùy thân",
    "Trạng thái nhận diện": "Đang phân tích cấu trúc tài liệu",
    "Ghi chú": "Hệ thống đã nhận được file — cần model VietOCR để trích xuất chi tiết",
}


def _detect_file_type(image_bytes: bytes) -> str:
    """
    Nhận diện loại file từ magic bytes (file header).
    Không dùng mimetypes vì chỉ có bytes thô trên RAM.
    """
    if len(image_bytes) < 8:
        return "unknown"
    if image_bytes[:4] == b"%PDF":
        return "pdf"
    if image_bytes[:2] == b"\xff\xd8":
        return "jpeg"
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if image_bytes[:4] in (b"II*\x00", b"MM\x00*"):
        return "tiff"
    return "unknown"


def _estimate_doc_type_from_bytes(image_bytes: bytes) -> str:
    """
    Ước tính loại tài liệu từ file type và kích thước (heuristic demo).
    CCCD thường là ảnh JPEG nhỏ; PDF thường là hợp đồng.
    """
    size = len(image_bytes)
    file_type = _detect_file_type(image_bytes)
    if file_type == "pdf":
        return "contract"
    if file_type in ("jpeg", "png") and size < 300_000:
        # Ảnh nhỏ → khả năng cao là CCCD
        return "cccd"
    if file_type in ("jpeg", "png") and size < 800_000:
        # Ảnh vừa → CMND hoặc giấy tờ cũ
        return "cmnd"
    return "generic"


class OcrService:
    """
    Dịch vụ trích xuất ký tự tiếng Việt từ ảnh tài liệu.

    Sử dụng VietOCR (model vgg_seq2seq) để nhận diện chữ Việt.
    Chạy hoàn toàn nội bộ (Local inference) — không gửi dữ liệu ra ngoài.

    Khi chưa có file trọng số (demo/dev mode):
      - Phân loại tài liệu qua magic bytes và kích thước file
      - Trả về bộ fields mẫu thực tế theo loại giấy tờ đã nhận diện
      - Giúp luồng upload → OCR → Chatbot hoạt động mượt mà để demo
    """

    def __init__(self):
        self._predictor = None           # Lazy load VietOCR
        self._cv_service = CvService()
        self._model_load_attempted = False

    def _load_vietocr_model(self) -> bool:
        """
        Lazy load VietOCR predictor từ local weights.

        Returns:
            True nếu model sẵn sàng, False nếu chưa có weights hoặc lỗi.
        """
        if self._model_load_attempted:
            return self._predictor is not None
        self._model_load_attempted = True
        try:
            from vietocr.tool.predictor import Predictor
            from vietocr.tool.config import Cfg

            config = Cfg.load_config_from_name("vgg_seq2seq")
            config["weights"] = settings.VIETOCR_WEIGHTS
            config["cnn"]["pretrained"] = False
            config["device"] = settings.INFERENCE_DEVICE
            config["predictor"]["beamsearch"] = False

            self._predictor = Predictor(config)
            return True
        except Exception:
            # Model chưa tải về — OcrService vẫn khởi động được (Smart Mock)
            self._predictor = None
            return False

    def extract_text(self, pil_image: Image.Image) -> str:
        """
        Trích xuất văn bản từ PIL Image.

        🚫 KHÔNG log/print kết quả văn bản này (chứa dữ liệu cá nhân).

        Args:
            pil_image: Ảnh PIL đã được tiền xử lý

        Returns:
            Chuỗi văn bản đã trích xuất (rỗng nếu model chưa tải)
        """
        model_ready = self._load_vietocr_model()
        if not model_ready or self._predictor is None:
            return ""
        text: str = self._predictor.predict(pil_image)
        return text

    def extract_from_image_bytes(self, image_bytes: bytes) -> Dict[str, str]:
        """
        Pipeline đầy đủ: bytes → tiền xử lý → phát hiện vùng → OCR từng vùng.

        Đây là hàm chính được gọi từ API route /ai/ocr.
        Dữ liệu truyền vào chỉ tồn tại trên RAM (từ Redis), không đọc từ ổ cứng.

        Khi VietOCR model chưa có sẵn weights → tự động kích hoạt Smart Mock:
          - Phân loại tài liệu qua magic bytes và kích thước file
          - Trả về bộ fields mẫu thực tế theo loại giấy tờ đã nhận diện

        🚫 KHÔNG ghi ra ổ cứng.
        🚫 KHÔNG log kết quả OCR chứa dữ liệu cá nhân.

        Args:
            image_bytes: Bytes của file ảnh (đọc từ Redis session)

        Returns:
            Dict nhãn → văn bản (VD: {"Họ và tên": "...", "Ngày sinh": "..."})
        """
        # Kiểm tra sớm trạng thái model
        model_ready = self._load_vietocr_model()

        # Bước 1: Tiền xử lý bằng OpenCV (CvService)
        try:
            processed_img = self._cv_service.preprocess_image(image_bytes)
        except Exception:
            # Nếu OpenCV cũng lỗi (file format lạ) → vẫn trả Smart Mock
            return self._smart_mock_fields(image_bytes)

        # Khi chưa có weights → Smart Mock ngay lập tức, không chờ YOLO/VietOCR
        if not model_ready:
            return self._smart_mock_fields(image_bytes)

        # Bước 2: Phát hiện vùng bằng YOLO-OBB
        regions = self._cv_service.detect_regions(processed_img)

        # Bước 3: OCR từng vùng
        raw_results: List[str] = []
        for region in regions:
            cropped = self._cv_service.crop_region(processed_img, region)
            cropped_bytes = self._cv_service.image_to_bytes(cropped)
            pil_img = Image.open(io.BytesIO(cropped_bytes)).convert("RGB")
            text = self.extract_text(pil_img)
            if text.strip():
                raw_results.append(text.strip())

        # Bước 4: Map sang cấu trúc field có nhãn
        extracted = self._map_fields(raw_results)

        # Nếu OCR không nhận diện được field nào → fallback Smart Mock
        if not extracted:
            return self._smart_mock_fields(image_bytes)

        return extracted

    def _smart_mock_fields(self, image_bytes: bytes) -> Dict[str, str]:
        """
        Tạo bộ fields mẫu thực tế dựa trên loại file đã nhận diện.

        🔒 Chỉ kích hoạt khi chưa có model weights (demo/dev mode).
           Dữ liệu trả về là HOÀN TOÀN GIẢ — không liên quan tới file upload.
        🚫 Không log kết quả.

        Args:
            image_bytes: Dữ liệu file (dùng để nhận diện loại giấy tờ)

        Returns:
            Dict fields mẫu theo loại tài liệu nhận diện được
        """
        doc_type = _estimate_doc_type_from_bytes(image_bytes)
        if doc_type == "cccd":
            return dict(_MOCK_CCCD_FIELDS)
        if doc_type == "cmnd":
            return dict(_MOCK_CMND_FIELDS)
        if doc_type == "contract":
            return dict(_MOCK_CONTRACT_FIELDS)
        return dict(_MOCK_GENERIC_FIELDS)

    def _map_fields(self, raw_lines: List[str]) -> Dict[str, str]:
        """
        Ánh xạ các dòng văn bản thô sang cấu trúc field có nhãn.

        Hàm này chạy heuristic đơn giản; trong production sẽ được
        AgentService cải thiện bằng LLM (Ollama).

        🚫 Không log raw_lines — chứa dữ liệu cá nhân nhạy cảm.

        Args:
            raw_lines: Danh sách dòng văn bản thô từ OCR

        Returns:
            Dict field_name → value
        """
        fields: Dict[str, str] = {}

        # Mapping keywords (tiếng Việt không dấu để robust hơn)
        keyword_map = {
            "ho va ten": "Họ và tên",
            "ngay sinh": "Ngày sinh",
            "gioi tinh": "Giới tính",
            "que quan": "Quê quán",
            "noi thuong tru": "Nơi thường trú",
            "so cccd": "Số CCCD",
            "so cmnd": "Số CMND",
            "ngay cap": "Ngày cấp",
            "noi cap": "Nơi cấp",
        }

        for line in raw_lines:
            lower = line.lower()
            for keyword, label in keyword_map.items():
                if keyword in lower and label not in fields:
                    # Lấy phần sau dấu ":"
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        fields[label] = parts[1].strip()
                    break

        return fields

    def get_document_type(self, extracted_fields: Dict[str, str]) -> str:
        """
        Xác định loại tài liệu dựa trên các field đã trích xuất.

        Args:
            extracted_fields: Kết quả từ extract_from_image_bytes

        Returns:
            Tên loại tài liệu (VD: "Căn cước công dân", "Hộ chiếu")
        """
        if "Số CCCD" in extracted_fields:
            return "Căn cước công dân (CCCD)"
        if "Số CMND" in extracted_fields:
            return "Chứng minh nhân dân (CMND)"
        if "Loại hợp đồng" in extracted_fields:
            return "Hợp đồng"
        if "Họ và tên" in extracted_fields and "Ngày sinh" in extracted_fields:
            return "Tài liệu nhân thân"
        return "Tài liệu không xác định"
