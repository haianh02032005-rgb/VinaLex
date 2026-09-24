"""
VinaLex — DVC Document & PDF Dedicated Database Manager
Quản lý cơ sở dữ liệu riêng biệt lưu trữ dữ liệu giấy tờ, thành phần hồ sơ và các tệp PDF
thu thập từ Cổng Dịch Vụ Công Quốc Gia (dichvucong.gov.vn).

Cơ chế:
- Mặc định lưu trữ tại SQLite độc lập: data/dvc_documents.db
- Bật WAL mode (Write-Ahead Logging) cho hiệu năng đọc/ghi đồng thời cực cao
- Hỗ trợ FTS5 (Full-Text Search) tra cứu siêu tốc tên giấy tờ, biểu mẫu, thủ tục
- Tương thích mở rộng sang PostgreSQL khi cần thiết
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple


DEFAULT_DB_PATH = os.path.join("data", "dvc_documents.db")


class DVCDocumentDatabase:
    """Quản lý CSDL riêng cho hồ sơ, thành phần giấy tờ và tệp PDF từ dichvucong.gov.vn."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối tới SQLite với các cấu hình tối ưu hiệu năng."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        return conn

    def _init_database(self) -> None:
        """Tạo cấu trúc bảng và các chỉ mục nếu chưa tồn tại."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Bảng lưu trữ Thủ tục hành chính (dvc_procedures)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dvc_procedures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dvc_id TEXT UNIQUE,
                    code TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    slug TEXT NOT NULL,
                    category TEXT NOT NULL,
                    category_slug TEXT NOT NULL,
                    agency TEXT,
                    level TEXT,
                    processing_time TEXT,
                    fee TEXT,
                    description TEXT,
                    steps_json TEXT,
                    legal_basis_json TEXT,
                    source_url TEXT,
                    total_documents INTEGER DEFAULT 0,
                    total_pdfs INTEGER DEFAULT 0,
                    crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # 2. Bảng lưu trữ Danh mục Giấy tờ / Thành phần hồ sơ (dvc_procedure_documents)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dvc_procedure_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_id INTEGER NOT NULL,
                    procedure_code TEXT NOT NULL,
                    case_name TEXT,
                    doc_name TEXT NOT NULL,
                    doc_clean_name TEXT NOT NULL,
                    form_code TEXT,
                    is_required INTEGER DEFAULT 1,
                    original_copy_type TEXT DEFAULT 'Bản chính',
                    quantity INTEGER DEFAULT 1,
                    note TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (procedure_id) REFERENCES dvc_procedures(id) ON DELETE CASCADE
                );
            """)

            # 3. Bảng lưu trữ Tệp PDF (dvc_pdf_files)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dvc_pdf_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procedure_id INTEGER NOT NULL,
                    procedure_code TEXT NOT NULL,
                    document_id INTEGER,
                    file_type TEXT NOT NULL, -- 'form_template' | 'dossier_guide' | 'attachment_pdf'
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size_bytes INTEGER NOT NULL,
                    file_hash_sha256 TEXT UNIQUE NOT NULL,
                    mime_type TEXT DEFAULT 'application/pdf',
                    source_origin TEXT NOT NULL, -- 'dvc_download' | 'vinalex_vector_pdf' | 'dossier_summary_pdf'
                    original_file_url TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (procedure_id) REFERENCES dvc_procedures(id) ON DELETE CASCADE,
                    FOREIGN KEY (document_id) REFERENCES dvc_procedure_documents(id) ON DELETE SET NULL
                );
            """)

            # 4. Chỉ mục tối ưu tra cứu
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proc_code ON dvc_procedures(code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proc_category ON dvc_procedures(category_slug);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_proc_id ON dvc_procedure_documents(procedure_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_proc_code ON dvc_procedure_documents(procedure_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pdf_proc_id ON dvc_pdf_files(procedure_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pdf_proc_code ON dvc_pdf_files(procedure_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pdf_hash ON dvc_pdf_files(file_hash_sha256);")

            # 5. Bảng tìm kiếm toàn văn FTS5 (Full-Text Search)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS dvc_search_fts USING fts5(
                    procedure_code,
                    procedure_title,
                    category,
                    doc_name,
                    file_name,
                    tokenize = 'unicode61'
                );
            """)

            conn.commit()

    # ──────────────────────────────────────────
    # Procedures CRUD
    # ──────────────────────────────────────────
    def upsert_procedure(self, proc_data: Dict[str, Any]) -> int:
        """Thêm hoặc cập nhật thông tin thủ tục hành chính."""
        code = proc_data.get("code", "")
        if not code:
            raise ValueError("Procedure code is required")

        steps_json = json.dumps(proc_data.get("steps", []), ensure_ascii=False) if isinstance(proc_data.get("steps"), list) else str(proc_data.get("steps", "[]"))
        legal_basis_json = json.dumps(proc_data.get("legal_basis", []), ensure_ascii=False) if isinstance(proc_data.get("legal_basis"), list) else str(proc_data.get("legal_basis", "[]"))

        now_str = datetime.utcnow().isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dvc_procedures (
                    dvc_id, code, title, slug, category, category_slug, agency,
                    level, processing_time, fee, description, steps_json, legal_basis_json,
                    source_url, crawled_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    title = excluded.title,
                    slug = excluded.slug,
                    category = excluded.category,
                    category_slug = excluded.category_slug,
                    agency = excluded.agency,
                    level = excluded.level,
                    processing_time = excluded.processing_time,
                    fee = excluded.fee,
                    description = excluded.description,
                    steps_json = excluded.steps_json,
                    legal_basis_json = excluded.legal_basis_json,
                    source_url = excluded.source_url,
                    updated_at = excluded.updated_at
                RETURNING id;
            """, (
                proc_data.get("dvc_id") or proc_data.get("id"),
                code,
                proc_data.get("title", ""),
                proc_data.get("slug", ""),
                proc_data.get("category", "Chung"),
                proc_data.get("category_slug", "chung"),
                proc_data.get("agency", ""),
                proc_data.get("level", ""),
                proc_data.get("processing_time", ""),
                proc_data.get("fee", ""),
                proc_data.get("description", ""),
                steps_json,
                legal_basis_json,
                proc_data.get("source_url", f"https://dichvucong.gov.vn/dich-vu-cong-truc-tuyen/{code}"),
                now_str,
                now_str,
            ))
            row = cursor.fetchone()
            proc_id = row["id"] if row else cursor.lastrowid
            conn.commit()
            return proc_id

    # ──────────────────────────────────────────
    # Documents CRUD
    # ──────────────────────────────────────────
    def insert_procedure_document(self, doc_data: Dict[str, Any]) -> int:
        """Thêm giấy tờ / thành phần hồ sơ thuộc thủ tục."""
        procedure_id = doc_data["procedure_id"]
        procedure_code = doc_data["procedure_code"]
        doc_name = doc_data["doc_name"]
        doc_clean_name = doc_data.get("doc_clean_name") or doc_name

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dvc_procedure_documents (
                    procedure_id, procedure_code, case_name, doc_name, doc_clean_name,
                    form_code, is_required, original_copy_type, quantity, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                procedure_id,
                procedure_code,
                doc_data.get("case_name", ""),
                doc_name,
                doc_clean_name,
                doc_data.get("form_code"),
                1 if doc_data.get("is_required", True) else 0,
                doc_data.get("original_copy_type", "Bản chính"),
                doc_data.get("quantity", 1),
                doc_data.get("note", ""),
            ))
            doc_id = cursor.lastrowid

            # Cập nhật số lượng giấy tờ trong bảng procedures
            cursor.execute("""
                UPDATE dvc_procedures
                SET total_documents = (
                    SELECT COUNT(*) FROM dvc_procedure_documents WHERE procedure_id = ?
                )
                WHERE id = ?;
            """, (procedure_id, procedure_id))

            # Đồng bộ FTS index
            cursor.execute("""
                INSERT INTO dvc_search_fts (procedure_code, procedure_title, category, doc_name, file_name)
                SELECT p.code, p.title, p.category, ?, ''
                FROM dvc_procedures p WHERE p.id = ?;
            """, (doc_name, procedure_id))

            conn.commit()
            return doc_id

    # ──────────────────────────────────────────
    # PDF Files CRUD
    # ──────────────────────────────────────────
    def insert_pdf_file(self, pdf_data: Dict[str, Any]) -> Optional[int]:
        """
        Lưu trữ metadata tệp PDF đã tải hoặc sinh ra.
        Nếu sha256 đã tồn tại, bỏ qua hoặc trả về ID cũ để chống trùng lặp.
        """
        sha256 = pdf_data.get("file_hash_sha256", "")
        if not sha256:
            raise ValueError("file_hash_sha256 is required")

        procedure_id = pdf_data["procedure_id"]
        procedure_code = pdf_data["procedure_code"]

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Kiểm tra xem file đã tồn tại theo hash chưa
            cursor.execute("SELECT id FROM dvc_pdf_files WHERE file_hash_sha256 = ?;", (sha256,))
            existing = cursor.fetchone()
            if existing:
                return existing["id"]

            cursor.execute("""
                INSERT INTO dvc_pdf_files (
                    procedure_id, procedure_code, document_id, file_type, file_name,
                    file_path, file_size_bytes, file_hash_sha256, mime_type,
                    source_origin, original_file_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                procedure_id,
                procedure_code,
                pdf_data.get("document_id"),
                pdf_data.get("file_type", "form_template"),
                pdf_data["file_name"],
                pdf_data["file_path"],
                pdf_data.get("file_size_bytes", 0),
                sha256,
                pdf_data.get("mime_type", "application/pdf"),
                pdf_data.get("source_origin", "dvc_download"),
                pdf_data.get("original_file_url"),
            ))
            file_id = cursor.lastrowid

            # Cập nhật số lượng PDF trong bảng procedures
            cursor.execute("""
                UPDATE dvc_procedures
                SET total_pdfs = (
                    SELECT COUNT(*) FROM dvc_pdf_files WHERE procedure_id = ?
                )
                WHERE id = ?;
            """, (procedure_id, procedure_id))

            # Đồng bộ FTS index
            cursor.execute("""
                INSERT INTO dvc_search_fts (procedure_code, procedure_title, category, doc_name, file_name)
                SELECT p.code, p.title, p.category, '', ?
                FROM dvc_procedures p WHERE p.id = ?;
            """, (pdf_data["file_name"], procedure_id))

            conn.commit()
            return file_id

    # ──────────────────────────────────────────
    # Queries & Search
    # ──────────────────────────────────────────
    def get_procedure_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin thủ tục theo mã TTHC."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dvc_procedures WHERE code = ? OR slug = ?;", (code, code))
            row = cursor.fetchone()
            if not row:
                return None
            res = dict(row)
            try:
                res["steps"] = json.loads(res["steps_json"])
            except Exception:
                res["steps"] = []
            try:
                res["legal_basis"] = json.loads(res["legal_basis_json"])
            except Exception:
                res["legal_basis"] = []
            return res

    def get_procedure_documents(self, procedure_id: int) -> List[Dict[str, Any]]:
        """Lấy toàn bộ giấy tờ thuộc một thủ tục kèm tệp PDF liên kết."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT d.*, f.id AS pdf_id, f.file_name AS pdf_file_name,
                       f.file_path AS pdf_file_path, f.file_size_bytes AS pdf_size
                FROM dvc_procedure_documents d
                LEFT JOIN dvc_pdf_files f ON f.document_id = d.id
                WHERE d.procedure_id = ?
                ORDER BY d.id ASC;
            """, (procedure_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_procedure_pdf_files(self, procedure_id: int) -> List[Dict[str, Any]]:
        """Lấy toàn bộ tệp PDF (biểu mẫu + tổng hợp hồ sơ) của thủ tục."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM dvc_pdf_files
                WHERE procedure_id = ?
                ORDER BY id ASC;
            """, (procedure_id,))
            return [dict(r) for r in cursor.fetchall()]

    def get_pdf_by_id(self, pdf_id: int) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một file PDF theo ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM dvc_pdf_files WHERE id = ?;", (pdf_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_procedures(
        self,
        category_slug: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Liệt kê danh sách thủ tục có phân trang và bộ lọc."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM dvc_procedures WHERE 1=1"
            count_query = "SELECT COUNT(*) FROM dvc_procedures WHERE 1=1"
            params: List[Any] = []

            if category_slug:
                query += " AND category_slug = ?"
                count_query += " AND category_slug = ?"
                params.append(category_slug)

            if search:
                query += " AND (title LIKE ? OR code LIKE ?)"
                count_query += " AND (title LIKE ? OR code LIKE ?)"
                kw = f"%{search}%"
                params.extend([kw, kw])

            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            rows = [dict(r) for r in cursor.fetchall()]
            for r in rows:
                try:
                    r["steps"] = json.loads(r["steps_json"])
                except Exception:
                    r["steps"] = []
            return rows, total

    def search_full_text(self, keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Tìm kiếm siêu tốc với FTS5."""
        if not keyword or not keyword.strip():
            return []
        cleaned_kw = keyword.strip().replace('"', '""')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.*, MIN(fts.rank) as search_rank
                FROM dvc_search_fts fts
                JOIN dvc_procedures p ON p.code = fts.procedure_code
                WHERE dvc_search_fts MATCH ?
                GROUP BY p.id
                ORDER BY search_rank ASC
                LIMIT ?;
            """, (f'"{cleaned_kw}"', limit))
            return [dict(r) for r in cursor.fetchall()]

    def get_database_statistics(self) -> Dict[str, Any]:
        """Thống kê tổng quan cơ sở dữ liệu hồ sơ và file PDF."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM dvc_procedures;")
            total_procs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM dvc_procedure_documents;")
            total_docs = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*), COALESCE(SUM(file_size_bytes), 0) FROM dvc_pdf_files;")
            pdf_stats = cursor.fetchone()
            total_pdfs = pdf_stats[0]
            total_pdf_size_bytes = pdf_stats[1]

            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM dvc_procedures
                GROUP BY category
                ORDER BY count DESC;
            """)
            by_category = {r["category"]: r["count"] for r in cursor.fetchall()}

            cursor.execute("""
                SELECT file_type, COUNT(*) as count
                FROM dvc_pdf_files
                GROUP BY file_type;
            """)
            by_file_type = {r["file_type"]: r["count"] for r in cursor.fetchall()}

            return {
                "db_path": os.path.abspath(self.db_path),
                "total_procedures": total_procs,
                "total_documents": total_docs,
                "total_pdfs": total_pdfs,
                "total_pdf_size_mb": round(total_pdf_size_bytes / (1024 * 1024), 2),
                "procedures_by_category": by_category,
                "pdfs_by_type": by_file_type,
            }
