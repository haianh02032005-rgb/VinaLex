"""
VinaLex — Administrative Agency & Location Dedicated Database Manager
Quản lý cơ sở dữ liệu riêng biệt lưu trữ thông tin địa giới hành chính, danh mục sáp nhập (2023-2025)
và danh bạ trụ sở cơ quan giải quyết dịch vụ hành chính công trên toàn quốc.

Tuân thủ ARCHITECTURE.md:
- Cơ chế CSDL độc lập: data/administrative_locations.db
- Không làm ảnh hưởng hay xung đột dữ liệu với vinalex.db hay dvc_documents.db
- WAL mode (Write-Ahead Logging) cho hiệu năng đọc đồng thời cực cao
- Hỗ trợ FTS5 (Full-Text Search) tra cứu siêu tốc tên cơ quan, địa chỉ, phường/xã sáp nhập
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

DEFAULT_LOCATION_DB_PATH = os.path.join("data", "administrative_locations.db")


class AgencyLocationDatabase:
    """Quản lý CSDL riêng cho địa giới hành chính, sáp nhập và trụ sở cơ quan hành chính."""

    def __init__(self, db_path: str = DEFAULT_LOCATION_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối tới SQLite với WAL mode và các tối ưu hiệu năng."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        return conn

    def _init_database(self) -> None:
        """Tạo cấu trúc bảng, chỉ mục và virtual table FTS5 nếu chưa tồn tại."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 1. Bảng Đơn vị hành chính chuẩn hóa (administrative_units)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS administrative_units (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    level TEXT NOT NULL, -- province | district | ward
                    parent_code TEXT,
                    full_name TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (parent_code) REFERENCES administrative_units(code) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_units_level ON administrative_units(level);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_units_parent ON administrative_units(parent_code);")

            # 2. Bảng Biến động sáp nhập đơn vị hành chính 2023 - 2025 (administrative_mergers)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS administrative_mergers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    old_unit_name TEXT NOT NULL,
                    old_district TEXT NOT NULL,
                    old_province TEXT NOT NULL,
                    new_unit_code TEXT NOT NULL,
                    new_unit_name TEXT NOT NULL,
                    resolution_code TEXT NOT NULL, -- Ví dụ: 1199/NQ-UBTVQH15
                    effective_date TEXT NOT NULL,  -- Ví dụ: 2025-01-01
                    headquarters_address TEXT,     -- Trụ sở mới tiếp nhận hồ sơ
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (new_unit_code) REFERENCES administrative_units(code) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mergers_old_lookup ON administrative_mergers(old_province, old_district, old_unit_name);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_mergers_new_code ON administrative_mergers(new_unit_code);")

            # 3. Bảng Cơ quan giải quyết thủ tục hành chính (agencies)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agencies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    short_name TEXT,
                    agency_type TEXT NOT NULL, -- one_stop_ward, one_stop_district, one_stop_province, land_registry, police, tax, social_insurance, other
                    level TEXT NOT NULL,       -- ward | district | province | central
                    province_code TEXT NOT NULL,
                    district_code TEXT,
                    ward_code TEXT,
                    province_name TEXT NOT NULL,
                    district_name TEXT,
                    ward_name TEXT,
                    address TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    phone TEXT,
                    email TEXT,
                    working_hours TEXT DEFAULT '08:00 - 11:30 | 13:30 - 17:00 (Thứ 2 - Thứ 6)',
                    google_place_id TEXT,
                    google_maps_url TEXT,
                    is_main_headquarter INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    verification_status TEXT DEFAULT 'verified',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_geo ON agencies(latitude, longitude);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_admin ON agencies(province_code, district_code, ward_code);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agencies_type ON agencies(agency_type, level);")

            # 4. Bảng Ánh xạ Lĩnh vực / Thủ tục phục vụ của cơ quan (agency_services)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agency_services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agency_id INTEGER NOT NULL,
                    category_slug TEXT NOT NULL, -- dat-dai, ho-tich, doanh-nghiep, giao-thong, etc.
                    procedure_code TEXT,
                    service_name TEXT,
                    FOREIGN KEY (agency_id) REFERENCES agencies(id) ON DELETE CASCADE
                );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agency_services_slug ON agency_services(category_slug);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agency_services_proc ON agency_services(procedure_code);")

            # 5. Virtual Table FTS5 tìm kiếm toàn văn siêu tốc (agencies_fts)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS agencies_fts USING fts5(
                    name,
                    agency_type,
                    address,
                    province_name,
                    district_name,
                    ward_name,
                    search_keywords
                );
            """)

            # 6. Triggers tự động đồng bộ sang bảng FTS5
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS agencies_ai AFTER INSERT ON agencies BEGIN
                    INSERT INTO agencies_fts(rowid, name, agency_type, address, province_name, district_name, ward_name, search_keywords)
                    VALUES (
                        new.id,
                        new.name,
                        new.agency_type,
                        new.address,
                        new.province_name,
                        coalesce(new.district_name, ''),
                        coalesce(new.ward_name, ''),
                        coalesce(new.short_name, '') || ' ' || coalesce(new.name, '') || ' ' || coalesce(new.address, '')
                    );
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS agencies_ad AFTER DELETE ON agencies BEGIN
                    DELETE FROM agencies_fts WHERE rowid = old.id;
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS agencies_au AFTER UPDATE ON agencies BEGIN
                    DELETE FROM agencies_fts WHERE rowid = old.id;
                    INSERT INTO agencies_fts(rowid, name, agency_type, address, province_name, district_name, ward_name, search_keywords)
                    VALUES (
                        new.id,
                        new.name,
                        new.agency_type,
                        new.address,
                        new.province_name,
                        coalesce(new.district_name, ''),
                        coalesce(new.ward_name, ''),
                        coalesce(new.short_name, '') || ' ' || coalesce(new.name, '') || ' ' || coalesce(new.address, '')
                    );
                END;
            """)
            conn.commit()

    # ──────────────────────────────────────────────────────────────────────────
    # CÁC PHƯƠNG THỨC THAO TÁC ĐƠN VỊ HÀNH CHÍNH & SÁP NHẬP
    # ──────────────────────────────────────────────────────────────────────────

    def upsert_administrative_unit(self, code: str, name: str, level: str, parent_code: Optional[str], full_name: str, is_active: int = 1) -> None:
        """Thêm mới hoặc cập nhật một đơn vị hành chính."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO administrative_units (code, name, level, parent_code, full_name, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    level = excluded.level,
                    parent_code = excluded.parent_code,
                    full_name = excluded.full_name,
                    is_active = excluded.is_active;
            """, (code, name, level, parent_code, full_name, is_active))
            conn.commit()

    def get_administrative_units(self, level: Optional[str] = None, parent_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy danh sách các đơn vị hành chính theo cấp hoặc mã cha."""
        query = "SELECT code, name, level, parent_code, full_name, is_active FROM administrative_units WHERE is_active = 1"
        params = []
        if level:
            query += " AND level = ?"
            params.append(level)
        if parent_code:
            query += " AND parent_code = ?"
            params.append(parent_code)
        query += " ORDER BY name ASC"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def add_administrative_merger(
        self,
        old_unit_name: str,
        old_district: str,
        old_province: str,
        new_unit_code: str,
        new_unit_name: str,
        resolution_code: str,
        effective_date: str,
        headquarters_address: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Ghi nhận dữ liệu biến động sáp nhập đơn vị hành chính."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO administrative_mergers (
                    old_unit_name, old_district, old_province, new_unit_code, new_unit_name,
                    resolution_code, effective_date, headquarters_address, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                old_unit_name, old_district, old_province, new_unit_code, new_unit_name,
                resolution_code, effective_date, headquarters_address, notes
            ))
            conn.commit()
            return cursor.lastrowid

    def resolve_merger(self, query_name: str, province_name: Optional[str] = None, district_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Tìm kiếm thông tin sáp nhập nếu tên người dùng tra cứu là tên cũ của xã/phường/huyện.
        Hỗ trợ giải quyết thắc mắc khi người dân cầm CCCD cũ hoặc địa chỉ cũ.
        """
        query_pattern = f"%{query_name.strip()}%"
        sql = """
            SELECT m.*, u.full_name as new_unit_full_name, u.level as unit_level
            FROM administrative_mergers m
            LEFT JOIN administrative_units u ON m.new_unit_code = u.code
            WHERE (m.old_unit_name LIKE ? OR m.new_unit_name LIKE ?)
        """
        params = [query_pattern, query_pattern]

        if province_name:
            sql += " AND m.old_province LIKE ?"
            params.append(f"%{province_name.strip()}%")
        if district_name:
            sql += " AND m.old_district LIKE ?"
            params.append(f"%{district_name.strip()}%")

        sql += " LIMIT 1"

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    # ──────────────────────────────────────────────────────────────────────────
    # CÁC PHƯƠNG THỨC THAO TÁC CƠ QUAN HÀNH CHÍNH (AGENCIES)
    # ──────────────────────────────────────────────────────────────────────────

    def upsert_agency(self, agency_data: Dict[str, Any]) -> int:
        """Thêm mới hoặc cập nhật thông tin cơ quan hành chính."""
        full_data = {
            "short_name": None,
            "district_code": None,
            "ward_code": None,
            "district_name": None,
            "ward_name": None,
            "phone": None,
            "email": None,
            "working_hours": "08:00 - 11:30 | 13:30 - 17:00 (Thứ 2 - Thứ 6)",
            "google_place_id": None,
            "google_maps_url": None,
            "is_main_headquarter": 1,
            "is_active": 1,
            "verification_status": "verified",
            **agency_data
        }
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Kiểm tra xem đã tồn tại cơ quan cùng tên và địa chỉ chưa
            cursor.execute("SELECT id FROM agencies WHERE name = ? AND address = ?", (full_data["name"], full_data["address"]))
            existing = cursor.fetchone()

            if existing:
                agency_id = existing["id"]
                cursor.execute("""
                    UPDATE agencies SET
                        short_name = :short_name,
                        agency_type = :agency_type,
                        level = :level,
                        province_code = :province_code,
                        district_code = :district_code,
                        ward_code = :ward_code,
                        province_name = :province_name,
                        district_name = :district_name,
                        ward_name = :ward_name,
                        address = :address,
                        latitude = :latitude,
                        longitude = :longitude,
                        phone = :phone,
                        email = :email,
                        working_hours = :working_hours,
                        google_place_id = :google_place_id,
                        google_maps_url = :google_maps_url,
                        is_main_headquarter = :is_main_headquarter,
                        is_active = :is_active,
                        verification_status = :verification_status,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """, {**full_data, "id": agency_id})
            else:
                cursor.execute("""
                    INSERT INTO agencies (
                        name, short_name, agency_type, level,
                        province_code, district_code, ward_code,
                        province_name, district_name, ward_name,
                        address, latitude, longitude, phone, email,
                        working_hours, google_place_id, google_maps_url,
                        is_main_headquarter, is_active, verification_status
                    ) VALUES (
                        :name, :short_name, :agency_type, :level,
                        :province_code, :district_code, :ward_code,
                        :province_name, :district_name, :ward_name,
                        :address, :latitude, :longitude, :phone, :email,
                        :working_hours, :google_place_id, :google_maps_url,
                        :is_main_headquarter, :is_active, :verification_status
                    )
                """, full_data)
                agency_id = cursor.lastrowid

            conn.commit()
            return agency_id

    def link_agency_service(self, agency_id: int, category_slug: str, procedure_code: Optional[str] = None, service_name: Optional[str] = None) -> None:
        """Gắn thủ tục/lĩnh vực dịch vụ cho cơ quan."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO agency_services (agency_id, category_slug, procedure_code, service_name)
                VALUES (?, ?, ?, ?)
            """, (agency_id, category_slug, procedure_code, service_name))
            conn.commit()

    def get_agency_by_id(self, agency_id: int) -> Optional[Dict[str, Any]]:
        """Lấy thông tin chi tiết một cơ quan bao gồm cả danh sách dịch vụ tiếp nhận."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agencies WHERE id = ? AND is_active = 1", (agency_id,))
            row = cursor.fetchone()
            if not row:
                return None
            agency = dict(row)

            # Lấy danh sách dịch vụ
            cursor.execute("SELECT category_slug, procedure_code, service_name FROM agency_services WHERE agency_id = ?", (agency_id,))
            agency["services"] = [dict(r) for r in cursor.fetchall()]
            return agency

    def query_agencies(
        self,
        province_code: Optional[str] = None,
        district_code: Optional[str] = None,
        ward_code: Optional[str] = None,
        agency_type: Optional[str] = None,
        level: Optional[str] = None,
        keyword: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Tra cứu danh sách cơ quan theo phân cấp hành chính hoặc FTS5."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            where_clauses = ["a.is_active = 1"]
            params: List[Any] = []

            if keyword and keyword.strip():
                # Tìm kiếm FTS5
                clean_kw = keyword.replace('"', '""').strip()
                sql = f"""
                    SELECT a.* FROM agencies a
                    JOIN agencies_fts f ON a.id = f.rowid
                    WHERE agencies_fts MATCH ? AND a.is_active = 1
                """
                params.append(f'"{clean_kw}"*')
                if province_code:
                    sql += " AND a.province_code = ?"
                    params.append(province_code)
                if district_code:
                    sql += " AND a.district_code = ?"
                    params.append(district_code)
                if ward_code:
                    sql += " AND a.ward_code = ?"
                    params.append(ward_code)
                if agency_type:
                    sql += " AND a.agency_type = ?"
                    params.append(agency_type)
                if level:
                    sql += " AND a.level = ?"
                    params.append(level)

                # Count query
                count_sql = f"SELECT COUNT(*) FROM ({sql})"
                cursor.execute(count_sql, params)
                total = cursor.fetchone()[0]

                sql += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                return [dict(r) for r in rows], total

            # Truy vấn lọc thông thường
            if province_code:
                where_clauses.append("a.province_code = ?")
                params.append(province_code)
            if district_code:
                where_clauses.append("a.district_code = ?")
                params.append(district_code)
            if ward_code:
                where_clauses.append("a.ward_code = ?")
                params.append(ward_code)
            if agency_type:
                where_clauses.append("a.agency_type = ?")
                params.append(agency_type)
            if level:
                where_clauses.append("a.level = ?")
                params.append(level)

            where_str = " AND ".join(where_clauses)
            count_sql = f"SELECT COUNT(*) FROM agencies a WHERE {where_str}"
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            sql = f"""
                SELECT a.* FROM agencies a
                WHERE {where_str}
                ORDER BY a.level DESC, a.name ASC
                LIMIT ? OFFSET ?
            """
            params.extend([limit, offset])
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows], total

    def get_all_agencies_for_geo(self, province_code: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lấy tất cả các cơ quan kèm toạ độ để tính khoảng cách cự ly."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if province_code:
                cursor.execute("""
                    SELECT id, name, short_name, agency_type, level, province_code, district_code, ward_code,
                           province_name, district_name, ward_name, address, latitude, longitude, phone,
                           working_hours, google_maps_url, is_main_headquarter
                    FROM agencies
                    WHERE is_active = 1 AND province_code = ?
                """, (province_code,))
            else:
                cursor.execute("""
                    SELECT id, name, short_name, agency_type, level, province_code, district_code, ward_code,
                           province_name, district_name, ward_name, address, latitude, longitude, phone,
                           working_hours, google_maps_url, is_main_headquarter
                    FROM agencies
                    WHERE is_active = 1
                """)
            return [dict(r) for r in cursor.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """Báo cáo thống kê CSDL địa điểm hành chính."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM administrative_units WHERE level = 'province';")
            provinces = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM administrative_units WHERE level = 'district';")
            districts = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM administrative_units WHERE level = 'ward';")
            wards = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM administrative_mergers;")
            mergers = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM agencies WHERE is_active = 1;")
            agencies = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM agency_services;")
            services = cursor.fetchone()[0]

            return {
                "db_path": self.db_path,
                "db_size_bytes": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
                "total_provinces": provinces,
                "total_districts": districts,
                "total_wards": wards,
                "total_mergers_recorded": mergers,
                "total_active_agencies": agencies,
                "total_linked_services": services,
            }


# Singleton instance mặc định
agency_location_db = AgencyLocationDatabase()
