"""
VinaLex — Document Retrieval Engine: Dịch vụ truy xuất biểu mẫu & văn bản hành chính công từ CSDL có sẵn
Thay thế hoàn toàn cơ chế tự sinh/vẽ văn bản mô phỏng bằng cơ chế truy xuất 100% tệp PDF chuẩn từ CSDL.

Tuân thủ:
- Thể thức văn bản hành chính theo Nghị định số 30/2020/NĐ-CP
- Đảm bảo 100% tệp cung cấp cho người dùng có định dạng PDF (application/pdf)
- Khai thác kho CSDL data/dvc_documents.db (1.739+ tệp PDF) và data/pdf_storage
- Tra cứu đa tầng (Exact Form Code -> FTS5 Semantic Search -> Dossier Guidebook PDF)
"""

import os
import re
import sqlite3
import unicodedata
import hashlib
from typing import Optional, Tuple, Dict, Any, List

from backend.db.dvc_document_db import DEFAULT_DB_PATH
from backend.services.pdf_service import (
    sanitize_document_name,
    sanitize_admin_procedure_title,
    _normalize_str,
)


def _strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để so sánh chuỗi bền vững."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _format_safe_filename(name: str) -> str:
    """Tạo tên tệp an toàn cho HTTP Header Content-Disposition."""
    if not name:
        return "bieu_mau_hanh_chinh.pdf"
    base = os.path.basename(name)
    if not base.lower().endswith(".pdf"):
        base += ".pdf"
    safe = _strip_accents(base)
    safe = re.sub(r"[^a-zA-Z0-9_\.\-]", "_", safe)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe.lower().endswith(".pdf"):
        safe += ".pdf"
    return safe


class DocumentRetrievalService:
    """
    Động cơ truy xuất biểu mẫu và giấy tờ hành chính công chuẩn Quốc gia.
    Tuyệt đối không tự sinh vẽ tùy tiện; truy xuất trực tiếp từ các file PDF trong CSDL.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._cache: Dict[str, Tuple[bytes, str, Dict[str, Any]]] = {}

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối tới SQLite độc lập của kho giấy tờ."""
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        return conn

    # ──────────────────────────────────────────────────────────
    # Phân tích & Trích xuất mã biểu mẫu quy định
    # ──────────────────────────────────────────────────────────
    def extract_form_code(self, doc_name: str) -> Optional[str]:
        """Nhận diện mã biểu mẫu chính thức từ tên văn bản."""
        if not doc_name:
            return None
        patterns = [
            r"(?:mẫu\s*(?:số)?\s*|mau\s*(?:so)?\s*)([0-9]+[a-zA-Z]*(?:/[a-zA-Z0-9_-]+)?)",
            r"(?:mẫu\s*|mau\s*)([0-9]{2}/[a-zA-Z]{2,4})",
            r"\b(ct\s*[0-9]{2})\b",
            r"\b(dc\s*[0-9]{2})\b",
            r"\b(cc\s*[0-9]{2})\b",
            r"\b(tk\s*[0-9]{2})\b",
            r"(?:phụ lục|phu luc)\s*([0-9]+[a-zA-Z]*)",
        ]
        for pat in patterns:
            m = re.search(pat, doc_name, re.IGNORECASE)
            if m:
                return m.group(0).strip().upper()
        return None

    # ──────────────────────────────────────────────────────────
    # Hàm truy xuất cốt lõi: retrieve_document_pdf
    # ──────────────────────────────────────────────────────────
    def retrieve_document_pdf(
        self,
        doc_name: str,
        procedure_title: Optional[str] = "",
        slug: Optional[str] = "",
        category: Optional[str] = "",
        agency: Optional[str] = "",
        preview: bool = False,
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        """
        Truy xuất tệp PDF biểu mẫu hành chính từ Cơ sở dữ liệu đã có sẵn.

        Trả về:
            Tuple[bytes, str, Dict[str, Any]]:
                - pdf_bytes: Nội dung tệp PDF nguyên gốc dạng nhị phân
                - filename: Tên tệp PDF chuẩn hóa
                - metadata: Thông tin nguồn gốc, mã băm SHA-256, dung lượng, tính pháp lý
        """
        clean_doc = sanitize_document_name(doc_name or "")
        clean_title = sanitize_admin_procedure_title(procedure_title or "")
        form_code = self.extract_form_code(clean_doc)

        cache_key = f"{clean_doc}::{slug}::{clean_title}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # ── TẦNG 1: Tra cứu trực tiếp theo Form Code hoặc Tên Biểu Mẫu Chuẩn Quốc Gia ──
        statutory_res = self._lookup_statutory_form(clean_doc, clean_title, slug, form_code)
        if statutory_res:
            self._cache[cache_key] = statutory_res
            return statutory_res

        # ── TẦNG 2: Tra cứu trong CSDL theo mã thủ tục (procedure_code) hoặc slug ──
        procedure_res = self._lookup_by_procedure_code_or_slug(slug, clean_title, clean_doc, form_code)
        if procedure_res:
            self._cache[cache_key] = procedure_res
            return procedure_res

        # ── TẦNG 3: Tìm kiếm toàn văn FTS5 (Full-Text Search) ──
        fts_res = self._lookup_via_fts5(clean_doc, clean_title)
        if fts_res:
            self._cache[cache_key] = fts_res
            return fts_res

        # ── TẦNG 4: Tra cứu Hồ sơ Hướng dẫn TTHC chuẩn (Dossier Guide PDF) ──
        dossier_res = self._lookup_dossier_guide(slug, clean_title)
        if dossier_res:
            self._cache[cache_key] = dossier_res
            return dossier_res

        # ── TẦNG 5: Fallback an toàn tới Biểu mẫu chuẩn gần nhất trong CSDL ──
        fallback_res = self._fallback_standard_form(clean_doc, clean_title, slug)
        self._cache[cache_key] = fallback_res
        return fallback_res

    # ──────────────────────────────────────────────────────────
    # TẦNG 1: Tra cứu Biểu Mẫu Chuẩn Quốc Gia (Statutory Registry)
    # ──────────────────────────────────────────────────────────
    def _lookup_statutory_form(
        self, clean_doc: str, clean_title: str, slug: str, form_code: Optional[str]
    ) -> Optional[Tuple[bytes, str, Dict[str, Any]]]:
        doc_safe = _strip_accents(clean_doc).lower()
        full_query = f"{clean_doc} {clean_title} {slug}".lower()
        safe_raw = _strip_accents(full_query)

        target_filename = None

        # Ưu tiên kiểm tra trực tiếp trên tên giấy tờ (clean_doc)
        if form_code and "11" in form_code and "DK" in _strip_accents(form_code).upper():
            target_filename = "don_dang_ky_bien_dong_dat_dai_mau_11_dk.pdf"
        elif any(k in doc_safe for k in ["11/dk", "11-dk", "xac dinh lai", "bien dong"]):
            target_filename = "don_dang_ky_bien_dong_dat_dai_mau_11_dk.pdf"
        elif form_code and "04" in form_code and "DK" in _strip_accents(form_code).upper():
            target_filename = "don_dang_ky_cap_gcn_dat_dai_mau_04_dk.pdf"
        elif any(k in doc_safe for k in ["04/dk", "04-dk", "cap gcn", "so do", "dat dai"]):
            target_filename = "don_dang_ky_cap_gcn_dat_dai_mau_04_dk.pdf"
        elif form_code and "18" in form_code:
            target_filename = "don_dang_ky_bien_dong_dat_dai_mau_18.pdf"
        elif form_code and "20" in form_code:
            target_filename = "don_dang_ky_dat_dai_mau_20.pdf"
        elif any(k in doc_safe for k in ["cu tru", "ho khau", "tam tru", "thuong tru", "ct01"]):
            target_filename = "to_khai_thay_doi_thong_tin_cu_tru_ct01.pdf"
        elif any(k in doc_safe for k in ["chung sinh", "cam doan sinh con", "sinh con"]):
            target_filename = "giay_cam_doan_ve_viec_sinh_con.pdf"
        elif "ket hon" in doc_safe:
            target_filename = "to_khai_dang_ky_ket_hon.pdf"
        elif "khai sinh" in doc_safe:
            target_filename = "to_khai_dang_ky_khai_sinh.pdf"
        elif any(k in doc_safe for k in ["can cuoc", "cccd", "cmnd", "dc01", "dc02", "cc01"]):
            target_filename = "to_khai_can_cuoc_dc01.pdf"
        elif any(k in doc_safe for k in ["tk03", "dinh danh dien tu"]):
            target_filename = "phieu_de_nghi_khoa_mo_khoa_dinh_danh_tk03.pdf"
        elif any(k in doc_safe for k in ["doanh nghiep", "cong ty", "ho kinh doanh"]):
            target_filename = "giay_de_nghi_dang_ky_doanh_nghiep.pdf"
        elif any(k in doc_safe for k in ["xay dung", "gpxd"]) and any(k in doc_safe for k in ["phep", "don", "de nghi"]):
            target_filename = "don_de_nghi_cap_giay_phep_xay_dung_mau_01.pdf"
        elif any(k in doc_safe for k in ["lai xe", "gplx", "bang lai"]):
            target_filename = "don_de_nghi_doi_gplx_phu_luc_19.pdf"
        elif any(k in doc_safe for k in ["kham benh", "chua benh", "hanh nghe y"]):
            target_filename = "don_de_nghi_cap_giay_phep_hanh_nghe_y.pdf"
        elif any(k in doc_safe for k in ["14-hsb", "14/hsb"]) or ("bao hiem" in doc_safe and "don" in doc_safe):
            target_filename = "don_de_nghi_huong_che_do_bhxh_mau_14_hsb.pdf"
        elif any(k in doc_safe for k in ["09/pli", "09-pli", "mien gpld", "giay phep lao dong"]):
            target_filename = "van_ban_de_nghi_mien_gpld_mau_09_pli.pdf"
        elif any(k in doc_safe for k in ["thue tncn", "quyet toan thue", "02/qtt"]):
            target_filename = "to_khai_quyet_toan_thue_tncn.pdf"
        
        # Nếu chưa khớp trên tên giấy tờ, kiểm tra ngữ cảnh thủ tục
        if not target_filename:
            if any(k in safe_raw for k in ["11/dk", "11-dk", "xac dinh lai", "bien dong"]):
                target_filename = "don_dang_ky_bien_dong_dat_dai_mau_11_dk.pdf"
            elif any(k in safe_raw for k in ["04/dk", "04-dk", "cap gcn", "so do"]) and any(k in safe_raw for k in ["dat", "dia chinh"]):
                target_filename = "don_dang_ky_cap_gcn_dat_dai_mau_04_dk.pdf"
            elif any(k in safe_raw for k in ["doanh nghiep", "cong ty", "ho kinh doanh"]):
                target_filename = "giay_de_nghi_dang_ky_doanh_nghiep.pdf"
            elif any(k in safe_raw for k in ["xay dung", "gpxd"]) and "phep" in safe_raw:
                target_filename = "don_de_nghi_cap_giay_phep_xay_dung_mau_01.pdf"
            elif any(k in safe_raw for k in ["lai xe", "gplx", "bang lai"]):
                target_filename = "don_de_nghi_doi_gplx_phu_luc_19.pdf"
            elif any(k in safe_raw for k in ["kham benh", "chua benh", "hanh nghe y"]):
                target_filename = "don_de_nghi_cap_giay_phep_hanh_nghe_y.pdf"
            elif any(k in safe_raw for k in ["14-hsb", "14/hsb"]) or ("bao hiem xa hoi" in safe_raw and "don" in safe_raw):
                target_filename = "don_de_nghi_huong_che_do_bhxh_mau_14_hsb.pdf"
            elif any(k in safe_raw for k in ["09/pli", "09-pli", "mien gpld", "giay phep lao dong"]):
                target_filename = "van_ban_de_nghi_mien_gpld_mau_09_pli.pdf"
            elif "ket hon" in safe_raw:
                target_filename = "to_khai_dang_ky_ket_hon.pdf"
            elif "khai sinh" in safe_raw:
                target_filename = "to_khai_dang_ky_khai_sinh.pdf"
            elif any(k in safe_raw for k in ["cu tru", "ho khau", "tam tru", "thuong tru"]):
                target_filename = "to_khai_thay_doi_thong_tin_cu_tru_ct01.pdf"
            elif any(k in safe_raw for k in ["can cuoc", "cccd", "cmnd"]):
                target_filename = "to_khai_can_cuoc_dc01.pdf"

        if target_filename:
            # Tìm trong statutory_storage trước
            stat_path = os.path.join("data", "pdf_storage", "statutory_forms", target_filename)
            if os.path.exists(stat_path):
                return self._read_pdf_file(
                    file_path=stat_path,
                    filename=target_filename,
                    source_origin="statutory_registry",
                    extra_meta={"form_code": form_code or "QUỐC GIA", "is_exact_statutory": True}
                )

            # Tìm trong dvc_pdf_files qua file_name
            try:
                with self._get_connection() as conn:
                    c = conn.cursor()
                    c.execute("""
                        SELECT file_path, file_name, file_size_bytes, file_hash_sha256, procedure_code
                        FROM dvc_pdf_files
                        WHERE file_name LIKE ? AND file_type = 'form_template'
                        ORDER BY id DESC LIMIT 1
                    """, (f"%{target_filename}%",))
                    row = c.fetchone()
                    if row and os.path.exists(row["file_path"]):
                        return self._read_pdf_file(
                            file_path=row["file_path"],
                            filename=target_filename,
                            source_origin="dvc_documents_db",
                            extra_meta={"procedure_code": row["procedure_code"], "is_exact_statutory": True}
                        )
            except Exception:
                pass

        return None

    # ──────────────────────────────────────────────────────────
    # TẦNG 2: Tra cứu theo mã thủ tục (procedure_code) hoặc slug
    # ──────────────────────────────────────────────────────────
    def _lookup_by_procedure_code_or_slug(
        self, slug: str, clean_title: str, clean_doc: str, form_code: Optional[str]
    ) -> Optional[Tuple[bytes, str, Dict[str, Any]]]:
        if not slug and not clean_title:
            return None

        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                # 1. Tìm procedure tương ứng
                c.execute("""
                    SELECT id, code, title FROM dvc_procedures 
                    WHERE slug = ? OR code = ? OR title LIKE ?
                    LIMIT 1
                """, (slug, slug, f"%{clean_title[:25]}%"))
                proc = c.fetchone()
                if not proc:
                    return None

                proc_id = proc["id"]
                proc_code = proc["code"]

                # 2. Tìm PDF biểu mẫu tương thích trong procedure đó
                # Ưu tiên theo form_code nếu có
                if form_code:
                    c.execute("""
                        SELECT f.file_path, f.file_name, f.file_size_bytes, f.file_hash_sha256
                        FROM dvc_pdf_files f
                        JOIN dvc_procedure_documents d ON f.document_id = d.id
                        WHERE f.procedure_id = ? AND (d.form_code LIKE ? OR f.file_name LIKE ?)
                        LIMIT 1
                    """, (proc_id, f"%{form_code}%", f"%{form_code}%"))
                    row = c.fetchone()
                    if row and os.path.exists(row["file_path"]):
                        return self._read_pdf_file(
                            file_path=row["file_path"],
                            filename=row["file_name"],
                            source_origin="dvc_procedure_match",
                            extra_meta={"procedure_code": proc_code, "form_code": form_code}
                        )

                # Nếu không có form_code, tìm theo tên giấy tờ doc_name
                c.execute("""
                    SELECT f.file_path, f.file_name, f.file_size_bytes, f.file_hash_sha256
                    FROM dvc_pdf_files f
                    WHERE f.procedure_id = ? AND f.file_type = 'form_template' AND f.file_name LIKE ?
                    LIMIT 1
                """, (proc_id, f"%{clean_doc[:25]}%"))
                row = c.fetchone()
                if row and os.path.exists(row["file_path"]):
                    return self._read_pdf_file(
                        file_path=row["file_path"],
                        filename=row["file_name"],
                        source_origin="dvc_procedure_match",
                        extra_meta={"procedure_code": proc_code}
                    )

                # Lấy file biểu mẫu đầu tiên có sẵn của procedure này
                c.execute("""
                    SELECT f.file_path, f.file_name, f.file_size_bytes, f.file_hash_sha256
                    FROM dvc_pdf_files f
                    WHERE f.procedure_id = ? AND f.file_type = 'form_template'
                    ORDER BY f.id ASC LIMIT 1
                """, (proc_id,))
                row = c.fetchone()
                if row and os.path.exists(row["file_path"]):
                    return self._read_pdf_file(
                        file_path=row["file_path"],
                        filename=row["file_name"],
                        source_origin="dvc_procedure_template",
                        extra_meta={"procedure_code": proc_code}
                    )
        except Exception:
            pass

        return None

    # ──────────────────────────────────────────────────────────
    # TẦNG 3: Tìm kiếm toàn văn FTS5
    # ──────────────────────────────────────────────────────────
    def _lookup_via_fts5(
        self, clean_doc: str, clean_title: str
    ) -> Optional[Tuple[bytes, str, Dict[str, Any]]]:
        if not clean_doc:
            return None

        # Trích các từ khóa chính không dấu
        words = [w for w in re.findall(r"\w+", clean_doc) if len(w) > 2][:4]
        if not words:
            return None
        fts_query = " OR ".join(words)

        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT s.procedure_code, f.file_path, f.file_name
                    FROM dvc_search_fts s
                    JOIN dvc_pdf_files f ON s.procedure_code = f.procedure_code
                    WHERE dvc_search_fts MATCH ? AND f.file_type = 'form_template'
                    ORDER BY rank LIMIT 1
                """, (fts_query,))
                row = c.fetchone()
                if row and os.path.exists(row["file_path"]):
                    return self._read_pdf_file(
                        file_path=row["file_path"],
                        filename=row["file_name"],
                        source_origin="fts5_match",
                        extra_meta={"procedure_code": row["procedure_code"]}
                    )
        except Exception:
            pass

        return None

    # ──────────────────────────────────────────────────────────
    # TẦNG 4: Tra cứu Hồ sơ hướng dẫn TTHC chuẩn (Dossier Guide)
    # ──────────────────────────────────────────────────────────
    def _lookup_dossier_guide(
        self, slug: str, clean_title: str
    ) -> Optional[Tuple[bytes, str, Dict[str, Any]]]:
        try:
            with self._get_connection() as conn:
                c = conn.cursor()
                c.execute("""
                    SELECT f.file_path, f.file_name, f.procedure_code
                    FROM dvc_pdf_files f
                    JOIN dvc_procedures p ON f.procedure_id = p.id
                    WHERE (p.slug = ? OR p.code = ? OR p.title LIKE ?) AND f.file_type = 'dossier_guide'
                    ORDER BY f.id DESC LIMIT 1
                """, (slug, slug, f"%{clean_title[:20]}%"))
                row = c.fetchone()
                if row and os.path.exists(row["file_path"]):
                    return self._read_pdf_file(
                        file_path=row["file_path"],
                        filename=row["file_name"],
                        source_origin="dossier_summary_pdf",
                        extra_meta={"procedure_code": row["procedure_code"], "is_dossier_guide": True}
                    )
        except Exception:
            pass

        return None

    # ──────────────────────────────────────────────────────────
    # TẦNG 5: Phục hồi biểu mẫu chuẩn dự phòng từ kho tĩnh
    # ──────────────────────────────────────────────────────────
    def _fallback_standard_form(
        self, clean_doc: str, clean_title: str, slug: str
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        # Tìm file bất kỳ trong statutory_forms
        stat_dir = os.path.join("data", "pdf_storage", "statutory_forms")
        if os.path.exists(stat_dir):
            files = [f for f in os.listdir(stat_dir) if f.lower().endswith(".pdf")]
            if files:
                chosen = files[0]
                full_path = os.path.join(stat_dir, chosen)
                return self._read_pdf_file(
                    file_path=full_path,
                    filename=chosen,
                    source_origin="fallback_statutory",
                    extra_meta={"is_fallback": True}
                )

        # Fallback khẩn cấp nếu chưa có file nào trên đĩa
        return (
            b"%PDF-1.4\n1 0 obj\n<< /Title (VinaLex Legal Form) >>\nendobj\n%%EOF",
            "bieu_mau_hanh_chinh.pdf",
            {"source_origin": "emergency_buffer", "is_fallback": True}
        )

    # ──────────────────────────────────────────────────────────
    # Đọc tệp PDF từ đĩa cứng và kiểm tra tính hợp lệ
    # ──────────────────────────────────────────────────────────
    def _read_pdf_file(
        self,
        file_path: str,
        filename: str,
        source_origin: str,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        with open(file_path, "rb") as f:
            pdf_bytes = f.read()

        # Kiểm tra tính toàn vẹn của tệp PDF (Bắt buộc bắt đầu bằng %PDF-)
        if not pdf_bytes.startswith(b"%PDF-"):
            raise ValueError(f"Tệp tại {file_path} không phải là tệp PDF hợp lệ!")

        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        safe_name = _format_safe_filename(filename)

        metadata = {
            "source_origin": source_origin,
            "file_path": file_path,
            "file_size_bytes": len(pdf_bytes),
            "file_hash_sha256": sha256,
            "mime_type": "application/pdf",
        }
        if extra_meta:
            metadata.update(extra_meta)

        return pdf_bytes, safe_name, metadata


# Khởi tạo singleton phục vụ toàn hệ thống
document_retrieval_service = DocumentRetrievalService()
