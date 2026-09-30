"""
VinaLex — CvService: Tiền xử lý ảnh bằng OpenCV + YOLO-OBB

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ Thị giác máy):
  - OpenCV: Tiền xử lý file ảnh tải lên (cắt, xoay, làm nét, chỉnh phối cảnh)
  - YOLO-OBB: Phát hiện và phân vùng bố cục tài liệu (layout detection)

Tuân thủ CONTRIBUTING.md §2.1:
  - Class: PascalCase → CvService
  - Hàm: snake_case → preprocess_image, detect_regions

🚫 Quy tắc bảo mật (ARCHITECTURE.md):
  - Ảnh được xử lý hoàn toàn trên RAM, không ghi ra ổ cứng
  - Không log (print/logger) giá trị pixel hay metadata nhạy cảm

CẢI TIẾN v2.0:
  - Deskew Correction: Tự động xoay ảnh lệch bằng Hough Transform
  - Perspective Correction: Phát hiện 4 góc tài liệu và hiệu chỉnh phối cảnh
  - Smart Binarization: Otsu + Adaptive kết hợp → bảo toàn chi tiết
  - Resolution Enhancement: Bicubic upscale cho ảnh DPI thấp
  - Multi-channel LAB: Xử lý kênh L (LAB color space) cho ảnh nhiều màu
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass

from backend.core.config import settings


# ── Ngưỡng tối thiểu kích thước ảnh cho OCR chất lượng tốt ──
_MIN_OCR_WIDTH = 1200
_MIN_OCR_HEIGHT = 800
_DESKEW_MAX_ANGLE = 15.0  # Giới hạn góc xoay tự động (độ)


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

    Pipeline v2.0:
      1. Giải mã ảnh từ bytes (RAM-only)
      2. Upscale nếu ảnh quá nhỏ (resolution enhancement)
      3. Deskew correction (chỉnh ảnh xoay lệch)
      4. Perspective correction (chỉnh méo phối cảnh)
      5. LAB-based contrast enhancement
      6. Smart binarization (Otsu + Adaptive)
      7. Khử nhiễu (morphological denoising)
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

    # ── BƯỚC 1: Resolution Enhancement ──

    def _enhance_resolution(self, img: np.ndarray) -> np.ndarray:
        """
        Nâng cấp độ phân giải cho ảnh có DPI quá thấp.

        Ảnh chụp điện thoại cũ hoặc scan chất lượng kém thường có kích thước
        nhỏ hơn 1200px chiều rộng → OCR sẽ rất sai. Upscale bicubic 2x.

        Args:
            img: Ảnh đầu vào (BGR)

        Returns:
            Ảnh đã upscale (hoặc giữ nguyên nếu đủ lớn)
        """
        h, w = img.shape[:2]
        if w < _MIN_OCR_WIDTH or h < _MIN_OCR_HEIGHT:
            scale = max(_MIN_OCR_WIDTH / w, _MIN_OCR_HEIGHT / h)
            scale = min(scale, 3.0)  # Tối đa 3x để tránh blur quá mức
            new_w = int(w * scale)
            new_h = int(h * scale)
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        return img

    # ── BƯỚC 2: Deskew Correction ──

    def _compute_skew_angle(self, gray: np.ndarray) -> float:
        """
        Tính góc xoay của tài liệu bằng Hough Line Transform.

        Thuật toán:
          1. Phát hiện cạnh bằng Canny
          2. Dùng HoughLinesP tìm các đoạn thẳng
          3. Tính median angle của các đoạn thẳng ngang (gần 0°)
          4. Trả về góc cần xoay (đơn vị: độ)

        Returns:
            Góc xoay (float), giới hạn trong [-15°, +15°].
            Trả về 0.0 nếu không phát hiện đủ đoạn thẳng.
        """
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=100,
            minLineLength=gray.shape[1] // 8,  # Ít nhất 1/8 chiều rộng
            maxLineGap=10,
        )

        if lines is None or len(lines) < 3:
            return 0.0

        angles = []
        for line in lines:
            x1, y1, x2, y2 = line[0]
            dx = x2 - x1
            dy = y2 - y1
            if abs(dx) < 1:
                continue
            angle = np.degrees(np.arctan2(dy, dx))
            # Chỉ lấy các đoạn gần ngang (trong ±30°)
            if abs(angle) < 30:
                angles.append(angle)

        if not angles:
            return 0.0

        median_angle = float(np.median(angles))
        # Clamp trong giới hạn an toàn
        return max(-_DESKEW_MAX_ANGLE, min(_DESKEW_MAX_ANGLE, median_angle))

    def _deskew(self, img: np.ndarray) -> np.ndarray:
        """
        Tự động xoay ảnh tài liệu nếu phát hiện bị nghiêng.

        Args:
            img: Ảnh đầu vào (BGR hoặc grayscale)

        Returns:
            Ảnh đã chỉnh xoay (cùng số kênh với đầu vào)
        """
        gray = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        angle = self._compute_skew_angle(gray)

        # Không xoay nếu góc quá nhỏ (< 0.3°)
        if abs(angle) < 0.3:
            return img

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        # Tính kích thước canvas mới sau xoay (giữ toàn bộ nội dung)
        cos_val = abs(rotation_matrix[0, 0])
        sin_val = abs(rotation_matrix[0, 1])
        new_w = int(h * sin_val + w * cos_val)
        new_h = int(h * cos_val + w * sin_val)
        rotation_matrix[0, 2] += (new_w - w) / 2
        rotation_matrix[1, 2] += (new_h - h) / 2

        rotated = cv2.warpAffine(
            img, rotation_matrix, (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return rotated

    # ── BƯỚC 3: Perspective Correction ──

    def _find_document_contour(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Phát hiện đường viền tài liệu (4 cạnh) trong ảnh.

        Dùng cho trường hợp chụp CCCD/CMND trên mặt bàn — ảnh bị méo phối cảnh.

        Returns:
            4 điểm góc (np.ndarray shape [4,2]) hoặc None nếu không phát hiện.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)

        # Làm dày cạnh để dễ tìm contour
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        # Sắp xếp theo diện tích giảm dần
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        h, w = img.shape[:2]
        img_area = h * w

        for contour in contours[:5]:  # Chỉ kiểm tra 5 contour lớn nhất
            area = cv2.contourArea(contour)
            # Contour phải chiếm ít nhất 20% ảnh
            if area < img_area * 0.2:
                continue

            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

            if len(approx) == 4:
                return approx.reshape(4, 2).astype(np.float32)

        return None

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """Sắp xếp 4 điểm theo thứ tự: top-left, top-right, bottom-right, bottom-left."""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        d = np.diff(pts, axis=1)

        rect[0] = pts[np.argmin(s)]      # Top-left: tổng x+y nhỏ nhất
        rect[2] = pts[np.argmax(s)]      # Bottom-right: tổng x+y lớn nhất
        rect[1] = pts[np.argmin(d)]      # Top-right: hiệu x-y nhỏ nhất
        rect[3] = pts[np.argmax(d)]      # Bottom-left: hiệu x-y lớn nhất
        return rect

    def _perspective_correct(self, img: np.ndarray) -> np.ndarray:
        """
        Hiệu chỉnh phối cảnh nếu phát hiện được 4 góc tài liệu.

        Args:
            img: Ảnh đầu vào BGR

        Returns:
            Ảnh đã chỉnh phối cảnh (hoặc giữ nguyên nếu không phát hiện được contour)
        """
        pts = self._find_document_contour(img)
        if pts is None:
            return img

        ordered = self._order_points(pts)
        tl, tr, br, bl = ordered

        # Tính kích thước output
        width_top = np.linalg.norm(tr - tl)
        width_bot = np.linalg.norm(br - bl)
        max_width = int(max(width_top, width_bot))

        height_left = np.linalg.norm(bl - tl)
        height_right = np.linalg.norm(br - tr)
        max_height = int(max(height_left, height_right))

        if max_width < 100 or max_height < 100:
            return img  # Quá nhỏ → bỏ qua

        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1],
        ], dtype=np.float32)

        matrix = cv2.getPerspectiveTransform(ordered, dst)
        warped = cv2.warpPerspective(
            img, matrix, (max_width, max_height),
            flags=cv2.INTER_CUBIC,
        )
        return warped

    # ── BƯỚC 4: LAB-based Contrast Enhancement ──

    def _enhance_contrast_lab(self, img: np.ndarray) -> np.ndarray:
        """
        Tăng cường tương phản bằng CLAHE trên kênh L (LAB color space).

        Xử lý trên LAB thay vì grayscale giúp bảo toàn thông tin màu sắc
        (quan trọng cho ảnh CCCD mới có ảnh portrait và watermark).

        Args:
            img: Ảnh BGR

        Returns:
            Ảnh BGR đã tăng tương phản
        """
        if len(img.shape) == 2:
            # Ảnh grayscale → CLAHE trực tiếp
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            return clahe.apply(img)

        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_channel)

        lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
        result = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        return result

    # ── BƯỚC 5: Smart Binarization ──

    def _smart_binarize(self, img: np.ndarray) -> np.ndarray:
        """
        Nhị phân hóa thông minh kết hợp Otsu + Adaptive Threshold.

        Thuật toán:
          1. Chạy Otsu threshold (tốt cho background đồng nhất)
          2. Chạy Adaptive Gaussian threshold (tốt cho background không đều)
          3. Kết hợp bằng bitwise AND → giữ lại vùng text rõ nhất
          4. Morphological closing để lấp khoảng trống trong ký tự

        Args:
            img: Ảnh BGR hoặc grayscale

        Returns:
            Ảnh nhị phân (BGR 3 kênh, sẵn sàng cho OCR)
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        # Khử nhiễu trước binarization
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Phương pháp 1: Otsu
        _, otsu = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Phương pháp 2: Adaptive Gaussian
        adaptive = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 15, 4,
        )

        # Kết hợp: AND để loại bỏ noise từ cả 2 phương pháp
        combined = cv2.bitwise_and(otsu, adaptive)

        # Morphological closing: lấp khoảng trống nhỏ trong ký tự
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        closed = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)

        # Trả về BGR 3 kênh (VietOCR yêu cầu RGB input)
        return cv2.cvtColor(closed, cv2.COLOR_GRAY2BGR)

    # ── PIPELINE CHÍNH ──

    def preprocess_image(self, image_bytes: bytes) -> np.ndarray:
        """
        Pipeline tiền xử lý ảnh v2.0 từ bytes.

        Pipeline:
          1. Giải mã từ bytes (RAM-only)
          2. Resolution enhancement (upscale ảnh nhỏ)
          3. Deskew correction (chỉnh xoay)
          4. Perspective correction (chỉnh méo)
          5. LAB contrast enhancement
          6. Smart binarization

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

        # Bước 1: Nâng cấp độ phân giải nếu ảnh quá nhỏ
        img = self._enhance_resolution(img)

        # Bước 2: Deskew — chỉnh ảnh bị chụp nghiêng
        img = self._deskew(img)

        # Bước 3: Perspective correction — chỉnh méo phối cảnh
        img = self._perspective_correct(img)

        # Bước 4: Tăng tương phản trên LAB color space
        img = self._enhance_contrast_lab(img)

        # Bước 5: Smart binarization (Otsu + Adaptive)
        result = self._smart_binarize(img)

        return result

    def preprocess_for_multipass(self, image_bytes: bytes) -> Tuple[np.ndarray, np.ndarray]:
        """
        Tạo 2 phiên bản ảnh cho Multi-pass OCR:
          - binary_img: Ảnh nhị phân (tốt cho text sắc nét)
          - gray_img: Ảnh grayscale enhanced (tốt cho text mờ/sáng)

        Đây là cải tiến mới — OCR chạy 2 pass trên 2 phiên bản,
        lấy kết quả nào có confidence cao hơn.

        Args:
            image_bytes: Bytes ảnh gốc

        Returns:
            Tuple[binary_img, gray_enhanced_img]
        """
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Không thể giải mã ảnh — định dạng không hợp lệ")

        # Shared preprocessing
        img = self._enhance_resolution(img)
        img = self._deskew(img)
        img = self._perspective_correct(img)

        # Pass 1: Binary (cho text sắc nét trên nền trắng)
        contrast_img = self._enhance_contrast_lab(img)
        binary_img = self._smart_binarize(contrast_img)

        # Pass 2: Gray enhanced (cho text mờ, watermark)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_enhanced = clahe.apply(gray)
        denoised = cv2.fastNlMeansDenoising(gray_enhanced, h=8)
        gray_img = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)

        return binary_img, gray_img

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
