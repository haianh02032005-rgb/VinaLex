"""
VinaLex — CvService: Tiền xử lý ảnh bằng OpenCV + YOLO-OBB

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ Thị giác máy):
  - OpenCV: Tiền xử lý file ảnh tải lên (cắt, xoay, làm nét)
  - YOLO-OBB: Phát hiện và phân vùng bố cục tài liệu (layout detection)

Tuân thủ CONTRIBUTING.md §2.1:
  - Class: PascalCase → CvService
  - Hàm: snake_case → preprocess_image, detect_regions

🚫 Quy tắc bảo mật (ARCHITECTURE.md):
  - Ảnh được xử lý hoàn toàn trên RAM, không ghi ra ổ cứng
  - Không log (print/logger) giá trị pixel hay metadata nhạy cảm
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from backend.core.config import settings


@dataclass
class DetectedRegion:
    """Vùng tài liệu được phát hiện bởi YOLO-OBB."""
    x: int
    y: int
    width: int
    height: int
    label: str        # Nhãn vùng (VD: "text_block", "table", "signature")
    confidence: float


class CvService:
    """
    Dịch vụ tiền xử lý hình ảnh bằng OpenCV và phát hiện bố cục bằng YOLO-OBB.

    Chạy hoàn toàn nội bộ (Local inference) — không gửi ảnh ra bên ngoài.
    Tuân thủ Nghị định 13/2023/NĐ-CP.
    """

    def __init__(self):
        self._yolo_model = None  # Lazy load để tiết kiệm RAM khi không dùng
        self._model_loaded = False

    def _load_yolo_model(self):
        """Lazy load YOLO-OBB model từ local weights."""
        if self._model_loaded:
            return
        try:
            from ultralytics import YOLO
            self._yolo_model = YOLO(settings.YOLO_OBB_WEIGHTS)
            self._model_loaded = True
        except Exception as e:
            # Không raise — CvService vẫn hoạt động ở chế độ basic preprocessing
            pass

    def preprocess_image(self, image_bytes: bytes) -> np.ndarray:
        """
        Tiền xử lý ảnh từ bytes: giải mã, cân chỉnh độ tương phản, khử nhiễu.

        Args:
            image_bytes: Dữ liệu ảnh dạng bytes (đọc từ RAM/Redis, không từ ổ cứng)

        Returns:
            np.ndarray: Ảnh đã xử lý dạng numpy array (BGR)
        """
        # Giải mã từ bytes trực tiếp trong RAM
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Không thể giải mã ảnh — định dạng không hợp lệ")

        # Bước 1: Chuyển sang grayscale để xử lý
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Bước 2: Khử nhiễu (denoising)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Bước 3: Tăng độ tương phản (CLAHE)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # Bước 4: Nhị phân hóa thích nghi (Adaptive Thresholding)
        binary = cv2.adaptiveThreshold(
            enhanced, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2,
        )

        # Trả về ảnh màu đã được cân chỉnh (dùng cho OCR)
        result = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
        return result

    def detect_regions(self, image: np.ndarray) -> List[DetectedRegion]:
        """
        Phát hiện và phân vùng bố cục tài liệu bằng YOLO-OBB.

        Args:
            image: Ảnh đã tiền xử lý (numpy array BGR)

        Returns:
            Danh sách các vùng tài liệu được phát hiện
        """
        self._load_yolo_model()

        regions: List[DetectedRegion] = []

        if self._yolo_model is None:
            # Fallback: trả về toàn bộ ảnh như 1 vùng nếu YOLO chưa tải
            h, w = image.shape[:2]
            regions.append(DetectedRegion(
                x=0, y=0, width=w, height=h,
                label="full_document", confidence=1.0,
            ))
            return regions

        results = self._yolo_model(image, verbose=False)
        for result in results:
            if result.obb is None:
                continue
            for box in result.obb:
                # YOLO trả về tọa độ TÂM (x_center, y_center, w, h)
                # Phải chuyển sang góc trên-trái (x_min, y_min) trước khi lưu
                x_center, y_center, w, h = box.xywh[0].tolist()
                x_min = int(x_center - w / 2)
                y_min = int(y_center - h / 2)
                label_idx = int(box.cls[0].item())
                label = result.names.get(label_idx, "unknown")
                conf = float(box.conf[0].item())
                regions.append(DetectedRegion(
                    x=x_min, y=y_min, width=int(w), height=int(h),
                    label=label, confidence=conf,
                ))

        return regions

    def crop_region(self, image: np.ndarray, region: DetectedRegion) -> np.ndarray:
        """
        Cắt vùng ảnh theo DetectedRegion để đưa vào OCR.

        Args:
            image: Ảnh gốc
            region: Vùng cần cắt

        Returns:
            Ảnh đã cắt
        """
        y1 = max(0, region.y)
        y2 = min(image.shape[0], region.y + region.height)
        x1 = max(0, region.x)
        x2 = min(image.shape[1], region.x + region.width)
        return image[y1:y2, x1:x2]

    def image_to_bytes(self, image: np.ndarray, ext: str = ".jpg") -> bytes:
        """Chuyển numpy array sang bytes để lưu Redis hoặc truyền vào VietOCR."""
        success, buffer = cv2.imencode(ext, image)
        if not success:
            raise ValueError("Không thể encode ảnh sang bytes")
        return buffer.tobytes()
