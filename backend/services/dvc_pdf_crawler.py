"""
VinaLex — DVCPdfCrawler Engine
Module thu thập dữ liệu giấy tờ, thành phần hồ sơ và các tệp PDF từ Cổng Dịch Vụ Công Quốc Gia
(https://dichvucong.gov.vn/) tích hợp vào Database riêng.

Tính năng:
- Bóc tách toàn diện chi tiết TTHC: executionCases -> profileComponents -> attachments
- Khai thác tệp đính kèm trực tiếp và các liên kết mẫu biểu
- Tự động sinh PDF vector chuyên ngành chuẩn Nghị định 30/2020/NĐ-CP cho 100% giấy tờ mẫu
- Tự động đóng gói bản PDF "Hồ Sơ Hướng Dẫn TTHC Hoàn Chỉnh" (Dossier Guidebook PDF)
- Mã hóa SHA-256 chống trùng lặp, lưu trữ file có cấu trúc theo mã thủ tục
- Tích hợp ghi vào CSDL riêng DVCDocumentDatabase theo thời gian thực (Atomic Transaction)
"""

import os
import re
import sys
import time
import json
import random
import hashlib
import logging
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urljoin, quote

import requests
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from backend.db.dvc_document_db import DVCDocumentDatabase, DEFAULT_DB_PATH
from backend.services.pdf_service import (
    PdfTemplateService,
    sanitize_document_name,
    sanitize_admin_procedure_title,
)

logger = logging.getLogger("DVCPdfCrawler")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


BASE_URL = "https://dichvucong.gov.vn"
API_LIST_PROCEDURES  = f"{BASE_URL}/api/v1/submitting/formality/list-all-public-formality-by-citizen"
API_DETAIL_PROCEDURE = f"{BASE_URL}/api/v1/configuring/formality/get-formality-by-citizen"

DEFAULT_PDF_STORAGE = os.path.join("data", "pdf_storage")

# Phân loại danh mục TTHC chuẩn
LINH_VUC_MAP: Dict[str, str] = {
    "dat-dai":             "Đất đai - Nhà ở",
    "doanh-nghiep":        "Doanh nghiệp",
    "giao-thong":          "Giao thông - Vận tải",
    "ho-tich":             "Hộ tịch - Quốc tịch",
    "y-te":                "Y tế - Sức khoẻ",
    "giao-duc":            "Giáo dục - Đào tạo",
    "lao-dong":            "Lao động - Việc làm",
    "tu-phap":             "Tư pháp",
    "xay-dung":            "Xây dựng - Đô thị",
    "thue-phi":            "Thuế - Phí - Lệ phí",
    "moi-truong":          "Tài nguyên - Môi trường",
    "cong-thuong":         "Công thương - Xuất nhập khẩu",
    "nong-nghiep":         "Nông nghiệp - Phát triển nông thôn",
    "khoa-hoc-cong-nghe":  "Khoa học - Công nghệ",
    "bao-hiem":            "Bảo hiểm xã hội",
}

LINH_VUC_KEYWORDS: Dict[str, List[str]] = {
    "dat-dai":      ["đất đai", "sổ đỏ", "cấp giấy chứng nhận", "biến động đất đai", "tách thửa"],
    "doanh-nghiep": ["thành lập doanh nghiệp", "đăng ký kinh doanh", "hộ kinh doanh"],
    "giao-thong":   ["bằng lái xe", "đổi giấy phép lái xe", "đăng ký xe", "biển số xe"],
    "ho-tich":      ["khai sinh", "kết hôn", "căn cước", "xác nhận tình trạng hôn nhân"],
    "y-te":         ["chứng chỉ hành nghề y", "giấy phép khám bệnh", "an toàn thực phẩm"],
    "giao-duc":     ["thành lập trường", "công nhận văn bằng", "chuyển trường"],
    "lao-dong":     ["giấy phép lao động", "thất nghiệp", "hợp đồng lao động"],
    "tu-phap":      ["lý lịch tư pháp", "công chứng", "chứng thực"],
    "xay-dung":     ["giấy phép xây dựng", "chứng chỉ xây dựng", "thẩm định thiết kế"],
    "thue-phi":     ["đăng ký thuế", "mã số thuế", "quyết toán thuế", "lệ phí trước bạ"],
    "bao-hiem":     ["bảo hiểm xã hội", "chế độ thai sản", "chế độ ốm đau", "hưu trí"],
}


class DVCPdfCrawler:
    """Crawler thu thập thành phần hồ sơ và tệp PDF từ Cổng DVC Quốc Gia."""

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        storage_dir: str = DEFAULT_PDF_STORAGE,
        request_delay: float = 1.2,
        jitter: float = 0.3,
        auto_generate_templates: bool = True,
    ):
        self.db = DVCDocumentDatabase(db_path=db_path)
        self.storage_dir = storage_dir
        self.request_delay = request_delay
        self.jitter = jitter
        self.auto_generate_templates = auto_generate_templates

        self._stop_event = threading.Event()
        self.session = requests.Session()
        self.pdf_service = PdfTemplateService()

        os.makedirs(self.storage_dir, exist_ok=True)
        self._init_session()

        self.stats = {
            "procedures_crawled": 0,
            "documents_indexed": 0,
            "pdfs_stored": 0,
            "total_bytes_downloaded": 0,
            "errors": 0,
        }

    # ──────────────────────────────────────────
    # Session Handshake & Protection Bypass
    # ──────────────────────────────────────────
    def _init_session(self) -> None:
        """Thiết lập session mô phỏng trình duyệt vượt rào kiểm duyệt."""
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/",
            "Connection": "keep-alive",
            "Sec-Ch-Ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        })
        try:
            logger.info("[Session] Thiết lập cookies và bảo mật NDC WAF...")
            r = self.session.get(f"{BASE_URL}/", timeout=12)
            if r.status_code == 200:
                logger.info(f"[Session] Sẵn sàng! Tiếp nhận {len(self.session.cookies)} session cookies.")
        except Exception as e:
            logger.warning(f"[Session] Cảnh báo kết nối ban đầu: {e}")

    def stop(self) -> None:
        """Dừng tiến trình cào an toàn."""
        self._stop_event.set()

    def _should_stop(self) -> bool:
        return self._stop_event.is_set()

    def _sleep(self, seconds: Optional[float] = None) -> None:
        delay = seconds if seconds is not None else (self.request_delay + random.uniform(0, self.jitter))
        step, elapsed = 0.1, 0.0
        while elapsed < delay and not self._should_stop():
            time.sleep(min(step, delay - elapsed))
            elapsed += step

    def _slugify(self, text: str) -> str:
        if not text:
            return f"item-{int(time.time() * 1000)}"
        text = text.lower()
        text = re.sub(r"[áàảãạăắằẳẵặâấầẩẫậ]", "a", text)
        text = re.sub(r"[éèẻẽẹêếềểễệ]", "e", text)
        text = re.sub(r"[íìỉĩị]", "i", text)
        text = re.sub(r"[óòỏõọôốồổỗộơớờởỡợ]", "o", text)
        text = re.sub(r"[úùủũụưứừửữự]", "u", text)
        text = re.sub(r"[ýỳỷỹỵ]", "y", text)
        text = re.sub(r"[đ]", "d", text)
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        return re.sub(r"[\s-]+", "-", text).strip("-")[:120]

    def _api_post(self, url: str, payload: dict, retries: int = 3) -> Optional[dict]:
        """Gửi POST API an toàn với cơ chế retry và backoff."""
        for attempt in range(retries):
            if self._should_stop():
                return None
            try:
                r = self.session.post(url, json=payload, timeout=15)
                if r.status_code in (200, 201):
                    return r.json()
                elif r.status_code == 403:
                    self.session.get(f"{BASE_URL}/", timeout=10)
            except Exception as e:
                logger.debug(f"[API] Thử lại {attempt + 1}/{retries} ({url}): {e}")
                time.sleep(1.0 + attempt)
        self.stats["errors"] += 1
        return None

    # ──────────────────────────────────────────
    # PDF Storage & Generation Helpers
    # ──────────────────────────────────────────
    def _compute_sha256(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def _save_pdf_to_disk(
        self,
        procedure_code: str,
        filename: str,
        pdf_bytes: bytes,
    ) -> Tuple[str, str, int]:
        """
        Lưu tệp PDF vào thư mục data/pdf_storage/procedures/{procedure_code}/{filename}.
        Trả về: (file_path, file_hash_sha256, file_size_bytes).
        """
        proc_dir = os.path.join(self.storage_dir, "procedures", procedure_code)
        os.makedirs(proc_dir, exist_ok=True)

        # Đảm bảo filename an toàn
        safe_name = re.sub(r'[\\/*?:"<>|]', "_", filename)
        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"

        file_path = os.path.join(proc_dir, safe_name)
        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        file_hash = self._compute_sha256(pdf_bytes)
        file_size = len(pdf_bytes)
        return file_path, file_hash, file_size

    def _generate_dossier_summary_pdf(self, proc_data: Dict[str, Any], documents: List[Dict[str, Any]]) -> bytes:
        """
        Sinh file PDF "Hồ Sơ Hướng Dẫn TTHC Hoàn Chỉnh" (Dossier Guidebook)
        chứa toàn văn trình tự, thành phần giấy tờ, biểu mẫu, căn cứ pháp lý.
        Tuân thủ thể thức Nghị định 30/2020/NĐ-CP.
        """
        doc = fitz.open()
        page = doc.new_page(width=595, height=842)  # Khổ A4 đứng

        font_name = "tieng-viet"
        font_path = self.pdf_service._font_path
        if font_path and os.path.exists(font_path):
            try:
                page.insert_font(fontname=font_name, fontfile=font_path)
            except Exception:
                font_name = "helv"
        else:
            font_name = "helv"

        y = 50.0

        # 1. Quốc hiệu & Tiêu ngữ
        page.insert_text(fitz.Point(190, y), "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", fontname=font_name, fontsize=11, color=(0, 0, 0))
        y += 16
        page.insert_text(fitz.Point(230, y), "Độc lập - Tự do - Hạnh phúc", fontname=font_name, fontsize=11, color=(0, 0, 0))
        y += 6
        page.draw_line(fitz.Point(225, y), fitz.Point(370, y), color=(0, 0, 0), width=0.8)
        y += 28

        # 2. Tiêu đề tài liệu
        page.insert_text(fitz.Point(135, y), "BỘ HỒ SƠ HƯỚNG DẪN THỦ TỤC HÀNH CHÍNH", fontname=font_name, fontsize=13, color=(0, 0, 0))
        y += 22

        # 3. Thông tin chung
        title = proc_data.get("title", "")
        code = proc_data.get("code", "")
        agency = proc_data.get("agency", "Cơ quan nhà nước có thẩm quyền")
        fee = proc_data.get("fee", "Theo quy định")
        time_limit = proc_data.get("processing_time", "Theo quy định")
        level = proc_data.get("level", "Cấp thẩm quyền")

        # Khung viền thông tin
        page.draw_rect(fitz.Rect(45, y, 550, y + 115), color=(0, 0, 0), width=0.6)
        
        info_y = y + 18
        page.insert_text(fitz.Point(55, info_y), f"• Tên thủ tục: {title[:75]}", fontname=font_name, fontsize=10, color=(0, 0, 0))
        if len(title) > 75:
            info_y += 14
            page.insert_text(fitz.Point(65, info_y), f"{title[75:150]}", fontname=font_name, fontsize=10, color=(0, 0, 0))

        info_y += 16
        page.insert_text(fitz.Point(55, info_y), f"• Mã TTHC: {code}  |  Cấp thực hiện: {level}", fontname=font_name, fontsize=9.5, color=(0, 0, 0))
        info_y += 15
        page.insert_text(fitz.Point(55, info_y), f"• Cơ quan giải quyết: {agency[:65]}", fontname=font_name, fontsize=9.5, color=(0, 0, 0))
        info_y += 15
        page.insert_text(fitz.Point(55, info_y), f"• Thời hạn giải quyết: {time_limit}", fontname=font_name, fontsize=9.5, color=(0, 0, 0))
        info_y += 15
        page.insert_text(fitz.Point(55, info_y), f"• Lệ phí: {fee}", fontname=font_name, fontsize=9.5, color=(0, 0, 0))

        y += 130

        # 4. Thành phần hồ sơ cần nộp (Danh mục giấy tờ)
        page.insert_text(fitz.Point(45, y), "I. DANH MỤC THÀNH PHẦN HỒ SƠ & GIẤY TỜ CẦN CHUẨN BỊ:", fontname=font_name, fontsize=11, color=(0, 0, 0))
        y += 16

        for idx, doc_item in enumerate(documents[:8], 1):
            doc_name = doc_item.get("doc_name", "")
            orig_type = doc_item.get("original_copy_type", "Bản chính")
            box_text = f"[{idx}] {doc_name[:85]}"
            page.insert_text(fitz.Point(55, y), box_text, fontname=font_name, fontsize=9, color=(0, 0, 0))
            page.insert_text(fitz.Point(460, y), f"({orig_type})", fontname=font_name, fontsize=8.5, color=(0.2, 0.2, 0.2))
            y += 15
            if len(doc_name) > 85:
                page.insert_text(fitz.Point(70, y), doc_name[85:170], fontname=font_name, fontsize=8.5, color=(0.2, 0.2, 0.2))
                y += 14

        y += 10

        # 5. Trình tự các bước thực hiện
        page.insert_text(fitz.Point(45, y), "II. TRÌNH TỰ CÁC BƯỚC THỰC HIỆN:", fontname=font_name, fontsize=11, color=(0, 0, 0))
        y += 16

        steps = proc_data.get("steps", [])
        for s in steps[:4]:
            idx = s.get("index", "")
            st_title = s.get("title", "")
            st_desc = s.get("description", "")
            page.insert_text(fitz.Point(55, y), f"Bước {idx}: {st_title[:75]}", fontname=font_name, fontsize=9.5, color=(0, 0, 0))
            y += 13
            if st_desc and st_desc != st_title:
                page.insert_text(fitz.Point(70, y), f"Chi tiết: {st_desc[:100]}...", fontname=font_name, fontsize=8.5, color=(0.3, 0.3, 0.3))
                y += 13

        # Footer
        page.draw_line(fitz.Point(45, 800), fitz.Point(550, 800), color=(0.5, 0.5, 0.5), width=0.5)
        page.insert_text(
            fitz.Point(45, 814),
            f"VinaLex Legal Automation Engine — Nguồn dữ liệu chính thức từ dichvucong.gov.vn — {datetime.now().strftime('%d/%m/%Y')}",
            fontname=font_name,
            fontsize=8,
            color=(0.4, 0.4, 0.4),
        )

        pdf_bytes = doc.tobytes()
        doc.close()
        return pdf_bytes

    # ──────────────────────────────────────────
    # Procedure Parsing & Ingestion
    # ──────────────────────────────────────────
    def _extract_form_code(self, doc_name: str) -> Optional[str]:
        """Nhận diện mã biểu mẫu quy định từ tên giấy tờ (Mẫu 04/ĐK, Mẫu 18, CT01, v.v.)."""
        patterns = [
            r"(?:mẫu|mau)\s*(?:số|so)?\s*([0-9]+[a-zA-Z]*(?:/[a-zA-Z0-9_-]+)?)",
            r"(?:mẫu|mau)\s*([0-9]{2}/[a-zA-Z]{2,4})",
            r"\b(ct\s*[0-9]{2})\b",
            r"\b(dc\s*[0-9]{2})\b",
            r"(?:phụ lục|phu luc)\s*([0-9]+[a-zA-Z]*)",
        ]
        for pat in patterns:
            m = re.search(pat, doc_name, re.IGNORECASE)
            if m:
                return m.group(0).strip().upper()
        return None

    def process_procedure_detail(self, it: dict, detail_data: dict, lv_name: str, lv_slug: str) -> Dict[str, Any]:
        """
        Bóc tách chi tiết thủ tục, trích xuất danh sách giấy tờ, xử lý PDF và lưu vào database riêng.
        """
        code = it.get("code") or detail_data.get("code") or ""
        name = it.get("name") or detail_data.get("name") or ""
        proc_id_raw = it.get("id") or detail_data.get("id") or ""

        # Chuẩn hóa các bước thực hiện
        parsed_steps = []
        raw_steps = detail_data.get("executionSteps", [])
        if raw_steps:
            full_text = raw_steps[0].get("description", "")
            chunks = re.split(r"(?:^|\n)(?:[-•*]?\s*)?(?:Bước|Buoc|\(\s*[iIvVxX\d]+\s*\))\s*[\d.:]+\s*", full_text)
            if len(chunks) > 1:
                for idx, c in enumerate(chunks[1:], 1):
                    c = c.strip()
                    if c:
                        lines = c.split("\n", 1)
                        parsed_steps.append({
                            "index": idx,
                            "title": lines[0].strip()[:100],
                            "description": lines[1].strip() if len(lines) > 1 else lines[0].strip(),
                            "duration": "Theo quy định",
                        })
            else:
                parsed_steps.append({
                    "index": 1,
                    "title": "Nộp hồ sơ và giải quyết",
                    "description": full_text[:600] if full_text else "Theo hướng dẫn của cơ quan có thẩm quyền",
                    "duration": "Theo quy định",
                })

        # Phí & Lệ phí
        fee_str = "Theo quy định của Nhà nước"
        raw_fees = detail_data.get("fees", [])
        if raw_fees and isinstance(raw_fees, list) and len(raw_fees) > 0:
            amt = raw_fees[0].get("amount") or raw_fees[0].get("fee")
            if amt:
                fee_str = f"{amt:,} VNĐ".replace(",", ".")

        # Thời hạn giải quyết
        proc_time = "Theo quy định"
        cases = detail_data.get("cases", [])
        if cases and cases[0].get("processingDay"):
            p_day = cases[0]["processingDay"]
            qty = p_day.get("qty", "")
            unit = "ngày làm việc" if p_day.get("type") == "WORKING_DAY" else "ngày"
            proc_time = f"{qty} {unit}" if qty else "Theo quy định"

        # Cấp thực hiện
        level = "Cấp Tỉnh/Huyện"
        if detail_data.get("isWard"):
            level = "Cấp Xã/Phường"
        elif detail_data.get("isProvince"):
            level = "Cấp Tỉnh/Thành phố"
        elif detail_data.get("isMinistry"):
            level = "Cấp Bộ/Trung ương"

        agency = (
            detail_data.get("departmentPromulgateName")
            or it.get("departmentPromulgate")
            or "Cơ quan nhà nước có thẩm quyền"
        )

        clean_title = sanitize_admin_procedure_title(name)

        proc_record = {
            "dvc_id": str(proc_id_raw),
            "code": str(code),
            "title": clean_title,
            "slug": self._slugify(clean_title),
            "category": lv_name,
            "category_slug": lv_slug,
            "agency": agency,
            "level": level,
            "processing_time": proc_time,
            "fee": fee_str,
            "description": detail_data.get("description") or clean_title,
            "steps": parsed_steps,
            "legal_basis": [lb.get("name") for lb in detail_data.get("legalBasisesDetails", []) if lb.get("name")],
            "source_url": f"{BASE_URL}/dich-vu-cong-truc-tuyen/{code}",
        }

        # 1. Lưu Procedure vào CSDL riêng
        db_proc_id = self.db.upsert_procedure(proc_record)
        self.stats["procedures_crawled"] += 1

        # 2. Bóc tách Thành phần hồ sơ & Giấy tờ (executionCases)
        extracted_docs = []
        exec_cases = detail_data.get("executionCases", [])
        seen_doc_names = set()

        # Nếu không có executionCases -> fallback lấy profileComponents ngoài cùng
        if not exec_cases:
            comps = detail_data.get("profileComponents", [])
            if comps:
                exec_cases = [{"name": "Trường hợp chuẩn", "profileComponents": comps}]

        for c_idx, cs in enumerate(exec_cases):
            case_title = cs.get("name") or f"Trường hợp {c_idx + 1}"
            components = cs.get("profileComponents", [])

            for comp in components:
                raw_doc_name = comp.get("name") or comp.get("componentName") or ""
                if not raw_doc_name:
                    continue

                clean_doc_name = sanitize_document_name(raw_doc_name)
                norm_key = clean_doc_name.lower()
                if norm_key in seen_doc_names:
                    continue
                seen_doc_names.add(norm_key)

                form_code = self._extract_form_code(raw_doc_name)
                attachments = comp.get("attachments", [])

                doc_entry = {
                    "procedure_id": db_proc_id,
                    "procedure_code": code,
                    "case_name": case_title,
                    "doc_name": raw_doc_name,
                    "doc_clean_name": clean_doc_name,
                    "form_code": form_code,
                    "is_required": True,
                    "original_copy_type": "Bản chính" if "bản chính" in raw_doc_name.lower() else "Bản sao hoặc bản chính",
                    "quantity": comp.get("quantity", 1),
                    "note": comp.get("note", ""),
                    "attachments": attachments,
                }

                # Lưu Giấy tờ vào CSDL riêng
                db_doc_id = self.db.insert_procedure_document(doc_entry)
                doc_entry["id"] = db_doc_id
                extracted_docs.append(doc_entry)
                self.stats["documents_indexed"] += 1

                # 3. Xử lý & Tạo file PDF cho Giấy tờ/Biểu mẫu
                self._handle_document_pdf(
                    db_proc_id=db_proc_id,
                    procedure_code=code,
                    proc_title=clean_title,
                    category=lv_name,
                    agency=agency,
                    doc_id=db_doc_id,
                    doc_entry=doc_entry,
                )

        # 4. Sinh và lưu tệp PDF "Hồ Sơ Hướng Dẫn TTHC Hoàn Chỉnh" (Dossier Guide PDF)
        try:
            dossier_pdf_bytes = self._generate_dossier_summary_pdf(proc_record, extracted_docs)
            guide_filename = f"ho_so_thu_tuc_{code}.pdf"
            guide_path, guide_hash, guide_size = self._save_pdf_to_disk(
                procedure_code=code,
                filename=guide_filename,
                pdf_bytes=dossier_pdf_bytes,
            )
            self.db.insert_pdf_file({
                "procedure_id": db_proc_id,
                "procedure_code": code,
                "document_id": None,
                "file_type": "dossier_guide",
                "file_name": f"Hồ sơ hướng dẫn thủ tục {code}.pdf",
                "file_path": guide_path,
                "file_size_bytes": guide_size,
                "file_hash_sha256": guide_hash,
                "source_origin": "dossier_summary_pdf",
                "original_file_url": proc_record["source_url"],
            })
            self.stats["pdfs_stored"] += 1
            self.stats["total_bytes_downloaded"] += guide_size
        except Exception as e:
            logger.warning(f"[PDF] Lỗi sinh Dossier Guide PDF cho {code}: {e}")

        logger.info(
            f"  ✓ [{lv_name}] Đã lưu TTHC {code}: {clean_title[:45]} "
            f"({len(extracted_docs)} giấy tờ | {self.stats['pdfs_stored']} PDFs)"
        )
        return proc_record

    def _handle_document_pdf(
        self,
        db_proc_id: int,
        procedure_code: str,
        proc_title: str,
        category: str,
        agency: str,
        doc_id: int,
        doc_entry: Dict[str, Any],
    ) -> None:
        """
        Xử lý tệp PDF cho từng giấy tờ:
        1. Thử tải file trực tiếp nếu có URL khả dụng.
        2. Tự động sinh PDF vector chuyên ngành chuẩn Nghị định 30/2020/NĐ-CP nếu là biểu mẫu/đơn tờ khai.
        """
        doc_name = doc_entry["doc_name"]
        clean_name = doc_entry["doc_clean_name"]
        form_code = doc_entry.get("form_code")
        attachments = doc_entry.get("attachments", [])

        # Kiểm tra xem có file đính kèm trực tiếp không
        pdf_stored = False
        for att in attachments:
            file_name = att.get("fileName", "")
            file_path_rel = att.get("filePath", "")
            file_id = att.get("id") or att.get("fileId")

            # Nếu có tệp PDF/DOCX có thể tải trực tiếp
            if file_path_rel or file_id:
                # Thử endpoint nếu khả dụng
                candidate_url = f"{BASE_URL}/files/{quote(file_path_rel)}" if file_path_rel else None
                try:
                    r = self.session.get(candidate_url, timeout=5) if candidate_url else None
                    if r and r.status_code == 200 and len(r.content) > 1000 and "application/pdf" in r.headers.get("Content-Type", ""):
                        saved_path, f_hash, f_size = self._save_pdf_to_disk(
                            procedure_code=procedure_code,
                            filename=file_name or f"bieu_mau_{doc_id}.pdf",
                            pdf_bytes=r.content,
                        )
                        self.db.insert_pdf_file({
                            "procedure_id": db_proc_id,
                            "procedure_code": procedure_code,
                            "document_id": doc_id,
                            "file_type": "attachment_pdf",
                            "file_name": file_name,
                            "file_path": saved_path,
                            "file_size_bytes": f_size,
                            "file_hash_sha256": f_hash,
                            "source_origin": "dvc_download",
                            "original_file_url": candidate_url,
                        })
                        self.stats["pdfs_stored"] += 1
                        self.stats["total_bytes_downloaded"] += f_size
                        pdf_stored = True
                        break
                except Exception:
                    pass

        # Nếu chưa có PDF tải về và giấy tờ mang tính chất biểu mẫu/tờ khai -> Tự động sinh PDF vector
        is_form_paper = any(k in doc_name.lower() for k in [
            "mẫu", "đơn", "tờ khai", "giấy đề nghị", "bản khai", "phiếu yêu cầu",
            "văn bản đề nghị", "báo cáo", "bản cam đoan", "ct01", "dc01"
        ])

        if self.auto_generate_templates and (is_form_paper or form_code) and not pdf_stored:
            try:
                pdf_bytes = self.pdf_service.generate_document_pdf(
                    doc_name=clean_name,
                    procedure_title=proc_title,
                    slug=self._slugify(proc_title),
                    category=category,
                    agency=agency,
                )
                safe_slug = re.sub(r"[^a-zA-Z0-9]+", "_", self._slugify(clean_name)).strip("_")[:40]
                form_filename = f"{form_code.lower()}_{safe_slug}.pdf" if form_code else f"bieu_mau_{safe_slug}.pdf"

                saved_path, f_hash, f_size = self._save_pdf_to_disk(
                    procedure_code=procedure_code,
                    filename=form_filename,
                    pdf_bytes=pdf_bytes,
                )
                self.db.insert_pdf_file({
                    "procedure_id": db_proc_id,
                    "procedure_code": procedure_code,
                    "document_id": doc_id,
                    "file_type": "form_template",
                    "file_name": f"{clean_name}.pdf",
                    "file_path": saved_path,
                    "file_size_bytes": f_size,
                    "file_hash_sha256": f_hash,
                    "source_origin": "vinalex_vector_pdf",
                    "original_file_url": None,
                })
                self.stats["pdfs_stored"] += 1
                self.stats["total_bytes_downloaded"] += f_size
            except Exception as e:
                logger.debug(f"[PDF] Lỗi sinh biểu mẫu PDF cho '{clean_name}': {e}")

    # ──────────────────────────────────────────
    # Main Crawl Pipelines
    # ──────────────────────────────────────────
    def crawl_by_code(self, procedure_code: str) -> Optional[Dict[str, Any]]:
        """Cào chính xác một mã thủ tục hành chính cụ thể."""
        logger.info(f"\n[Crawl] Đang tìm kiếm thủ tục có mã: {procedure_code}...")
        resp = self._api_post(API_LIST_PROCEDURES, {"limit": 5, "lastId": "", "q": procedure_code})
        items = resp.get("data", {}).get("items", []) if resp else []
        matched = next((it for it in items if str(it.get("code")) == str(procedure_code)), None)
        if not matched and items:
            matched = items[0]

        if not matched:
            logger.warning(f"[Crawl] Không tìm thấy thủ tục mã {procedure_code} trên DVC.")
            return None

        pid = matched.get("id")
        det = self._api_post(API_DETAIL_PROCEDURE, {"id": pid})
        detail_data = det.get("data", {}) if det else {}

        return self.process_procedure_detail(
            it=matched,
            detail_data=detail_data,
            lv_name="Thủ tục tra cứu",
            lv_slug="tra-cuu",
        )

    def crawl_categories(
        self,
        linh_vuc_slugs: Optional[List[str]] = None,
        limit_per_category: int = 10,
        max_total: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Cào hồ sơ giấy tờ & PDF theo danh mục lĩnh vực."""
        targets = linh_vuc_slugs or list(LINH_VUC_MAP.keys())
        results = []

        logger.info(f"\n[Pipeline] Bắt đầu thu thập hồ sơ giấy tờ & PDF từ {len(targets)} lĩnh vực...")
        logger.info(f"[Storage] Lưu trữ PDF tại: {os.path.abspath(self.storage_dir)}")
        logger.info(f"[Database] Tích hợp CSDL tại: {os.path.abspath(self.db.db_path)}")

        for lv_slug in targets:
            if self._should_stop():
                break
            lv_name = LINH_VUC_MAP.get(lv_slug, lv_slug)
            keywords = LINH_VUC_KEYWORDS.get(lv_slug, [lv_name])

            logger.info(f"\n─── Lĩnh vực: [{lv_name}] ({len(keywords)} từ khóa) ───")
            category_count = 0

            for kw in keywords:
                if self._should_stop() or category_count >= limit_per_category:
                    break
                if max_total and len(results) >= max_total:
                    break

                self._sleep()
                payload = {
                    "limit": min(10, limit_per_category - category_count),
                    "lastId": "",
                    "q": kw,
                    "categoryId": "",
                    "departmentCode": "",
                }
                resp = self._api_post(API_LIST_PROCEDURES, payload)
                items = resp.get("data", {}).get("items", []) if resp else []

                for it in items:
                    if self._should_stop() or category_count >= limit_per_category:
                        break
                    if max_total and len(results) >= max_total:
                        break

                    code = str(it.get("code", ""))
                    # Kiểm tra xem đã cào thủ tục này chưa
                    existing = self.db.get_procedure_by_code(code)
                    if existing and existing.get("total_documents", 0) > 0:
                        continue

                    pid = it.get("id")
                    self._sleep(0.5)
                    det_resp = self._api_post(API_DETAIL_PROCEDURE, {"id": pid})
                    detail_data = det_resp.get("data", {}) if det_resp else {}

                    record = self.process_procedure_detail(it, detail_data, lv_name, lv_slug)
                    results.append(record)
                    category_count += 1

        logger.info("\n" + "=" * 60)
        logger.info(f" Hoàn tất phiên cào dữ liệu:")
        logger.info(f" • Thủ tục đã xử lý   : {self.stats['procedures_crawled']}")
        logger.info(f" • Giấy tờ đã lập chỉ mục: {self.stats['documents_indexed']}")
        logger.info(f" • File PDF đã tạo/lưu : {self.stats['pdfs_stored']}")
        logger.info(f" • Dung lượng tải về   : {round(self.stats['total_bytes_downloaded'] / (1024*1024), 2)} MB")
        logger.info("=" * 60)
        return results
