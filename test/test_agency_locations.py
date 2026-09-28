"""
VinaLex — Kịch Bản Kiểm Thử Chuyên Sâu: Tra Cứu Địa Điểm & Đường Đi Đến Cơ Quan Dịch Vụ Công
(Comprehensive Test Suite for Administrative Agency Locations & Google Maps Directions)

Đánh giá 6 phân mục:
  1. Kiểm thử CSDL riêng biệt & Toàn vẹn Schema (Database & FTS5 Integrity)
  2. Kiểm thử Độ chính xác Sáp nhập Đơn vị Hành chính 2023 - 2025 (Merger Resolution Accuracy)
  3. Kiểm thử Tính cự ly Haversine & Geofencing (Distance & Boundary Checks)
  4. Kiểm thử Tích hợp API FastAPI & Đường dẫn Google Maps (API & Google Maps Universal URL)
  5. Kiểm thử Tích hợp Trí tuệ Nhân tạo Gemini (AI Agent Location Tooling)
  6. Kiểm thử Bảo mật & Tuân thủ Nghị định 13/2023/NĐ-CP (Privacy & Non-persistence)
"""

import os
import sys
import time
import json
import sqlite3
from typing import Dict, Any

# Cấu hình UTF-8 an toàn cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.abspath("."))

from starlette.testclient import TestClient
from backend.main import app
from backend.db.agency_location_db import agency_location_db, DEFAULT_LOCATION_DB_PATH
from backend.services.agency_crawler import (
    agency_crawler,
    calculate_haversine_distance,
    build_google_maps_directions_url,
    build_google_maps_search_url,
    BOUNDING_BOXES,
)
from backend.services.agency_location_service import agency_location_service
from backend.services.gemini_service import GeminiService

client = TestClient(app)


class LocationTestReport:
    def __init__(self):
        self.results = []
        self.start_time = time.time()

    def add(self, category: str, test_id: str, name: str, passed: bool, detail: str = "", duration_ms: float = 0):
        self.results.append({
            "category": category,
            "id": test_id,
            "name": name,
            "passed": passed,
            "detail": detail,
            "duration_ms": duration_ms
        })
        status_icon = "✓ PASS" if passed else "✗ FAIL"
        print(f"[{status_icon}] [{category}] {test_id}: {name} ({duration_ms:.1f}ms)", flush=True)
        if not passed and detail:
            print(f"       -> Lỗi: {detail}", flush=True)

    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed
        total_time = time.time() - self.start_time
        print("\n" + "=" * 80)
        print(f"TỔNG KẾT KIỂM THỬ TÍNH NĂNG ĐỊA ĐIỂM & CHỈ ĐƯỜNG: {passed}/{total} VƯỢT QUA ({passed/total*100:.1f}%)")
        print(f"Thời gian thực thi: {total_time:.2f}s | Số lỗi phát hiện: {failed}")
        print("=" * 80)
        return total, passed, failed


report = LocationTestReport()


# ─────────────────────────────────────────────────────────────────────────────
# 1. KIỂM THỬ CƠ SỞ DỮ LIỆU RIÊNG BIỆT & TOÀN VẸN SCHEMA
# ─────────────────────────────────────────────────────────────────────────────
def test_database_integrity():
    cat = "1. CSDL RIÊNG"
    t0 = time.time()

    # DB-01: File DB tồn tại và độc lập
    db_exists = os.path.exists(DEFAULT_LOCATION_DB_PATH)
    report.add(cat, "LOC-DB-01", "Tệp CSDL data/administrative_locations.db tồn tại độc lập", db_exists, duration_ms=(time.time()-t0)*1000)

    # DB-02: Kiểm tra WAL Mode và bảng dữ liệu
    t0 = time.time()
    try:
        conn = sqlite3.connect(DEFAULT_LOCATION_DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode;")
        journal_mode = cur.fetchone()[0].lower()
        is_wal = journal_mode in ["wal", "memory"]

        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cur.fetchall()]
        required_tables = ["administrative_units", "administrative_mergers", "agencies", "agency_services", "agencies_fts"]
        has_all_tables = all(t in tables for t in required_tables)
        conn.close()

        report.add(cat, "LOC-DB-02", "CSDL hỗ trợ WAL mode và có đầy đủ các bảng bắt buộc", is_wal and has_all_tables, f"WAL: {is_wal}, Tables: {tables}", duration_ms=(time.time()-t0)*1000)
    except Exception as e:
        report.add(cat, "LOC-DB-02", "Kiểm tra cấu trúc CSDL", False, str(e))

    # DB-03: Kiểm tra FTS5 Full-Text Search
    t0 = time.time()
    try:
        conn = sqlite3.connect(DEFAULT_LOCATION_DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT rowid, name FROM agencies_fts WHERE agencies_fts MATCH '\"kham thien\"*' LIMIT 1;")
        fts_res = cur.fetchone()
        conn.close()
        report.add(cat, "LOC-DB-03", "Bảng ảo FTS5 hoạt động chính xác với tìm kiếm tiếng Việt", fts_res is not None, duration_ms=(time.time()-t0)*1000)
    except Exception as e:
        report.add(cat, "LOC-DB-03", "Kiểm tra FTS5", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 2. KIỂM THỬ ĐỘ CHÍNH XÁC SÁP NHẬP ĐƠN VỊ HÀNH CHÍNH 2023 - 2025
# ─────────────────────────────────────────────────────────────────────────────
def test_merger_accuracy():
    cat = "2. CHÍNH XÁC SÁP NHẬP"

    # MERGE-01: Phường Trung Phụng -> Khâm Thiên (NQ 1199/NQ-UBTVQH15)
    t0 = time.time()
    m1 = agency_location_service.resolve_merger("Trung Phụng")
    valid_m1 = (
        m1 is not None and
        "Khâm Thiên" in m1.get("new_unit_name", "") and
        "1199/NQ-UBTVQH15" in m1.get("resolution_code", "") and
        "18 Ngõ Thổ Quan" in m1.get("headquarters_address", "")
    )
    report.add(cat, "LOC-MERGE-01", "Sáp nhập Phường Trung Phụng -> Phường Khâm Thiên (NQ 1199)", valid_m1, f"Kết quả: {m1}", duration_ms=(time.time()-t0)*1000)

    # MERGE-02: Phường Cầu Dền -> Bách Khoa & Thanh Nhàn (NQ 1199/NQ-UBTVQH15)
    t0 = time.time()
    m2 = agency_location_service.resolve_merger("Cầu Dền")
    valid_m2 = (
        m2 is not None and
        "Bách Khoa" in m2.get("new_unit_name", "") and
        "1199/NQ-UBTVQH15" in m2.get("resolution_code", "")
    )
    report.add(cat, "LOC-MERGE-02", "Sáp nhập Phường Cầu Dền -> Phường Bách Khoa (NQ 1199)", valid_m2, f"Kết quả: {m2}", duration_ms=(time.time()-t0)*1000)

    # MERGE-03: Sáp nhập các phường Quận 3 TP.HCM -> Phường Võ Thị Sáu
    t0 = time.time()
    m3 = agency_location_service.resolve_merger("Phường 6", province_name="Hồ Chí Minh")
    valid_m3 = (
        m3 is not None and
        "Võ Thị Sáu" in m3.get("new_unit_name", "") and
        "Bà Huyện Thanh Quan" in m3.get("headquarters_address", "")
    )
    report.add(cat, "LOC-MERGE-03", "Sáp nhập Phường 6,7,8 Quận 3 -> Phường Võ Thị Sáu (TP.HCM)", valid_m3, f"Kết quả: {m3}", duration_ms=(time.time()-t0)*1000)

    # MERGE-04: Đơn vị không sáp nhập trả về None một cách an toàn
    t0 = time.time()
    m4 = agency_location_service.resolve_merger("Địa danh không tồn tại 999")
    report.add(cat, "LOC-MERGE-04", "Không có biến động sáp nhập trả về None an toàn", m4 is None, duration_ms=(time.time()-t0)*1000)


# ─────────────────────────────────────────────────────────────────────────────
# 3. KIỂM THỬ TÍNH CỰ LY HAVERSINE & GEOFENCING
# ─────────────────────────────────────────────────────────────────────────────
def test_haversine_and_geofence():
    cat = "3. CỰ LY & TOẠ ĐỘ"

    # GEO-01: Độ chính xác tính cự ly Haversine
    t0 = time.time()
    # Toạ độ Hồ Gươm (21.028511, 105.854444) đến UBND Phường Khâm Thiên (21.018942, 105.834125)
    # Khoảng cách thực tế xấp xỉ 2.3 - 2.4 km
    dist = calculate_haversine_distance(21.028511, 105.854444, 21.018942, 105.834125)
    valid_dist = 2.2 <= dist <= 2.5
    report.add(cat, "LOC-GEO-01", f"Tính cự ly Haversine chuẩn xác ({dist} km ~ 2.34 km)", valid_dist, f"Khoảng cách tính được: {dist} km", duration_ms=(time.time()-t0)*1000)

    # GEO-02: Bounding Box Geofencing
    t0 = time.time()
    all_agencies = agency_location_db.get_all_agencies_for_geo()
    all_in_bounds = True
    violator = ""
    for ag in all_agencies:
        p_code = ag["province_code"]
        lat = ag["latitude"]
        lng = ag["longitude"]
        if p_code == "01": # Hà Nội
            box = BOUNDING_BOXES["hanoi"]
            if not (box["min_lat"] <= lat <= box["max_lat"] and box["min_lng"] <= lng <= box["max_lng"]):
                all_in_bounds = False
                violator = f"{ag['name']} ({lat}, {lng})"
                break
        elif p_code == "79": # TP.HCM
            box = BOUNDING_BOXES["hcm"]
            if not (box["min_lat"] <= lat <= box["max_lat"] and box["min_lng"] <= lng <= box["max_lng"]):
                all_in_bounds = False
                violator = f"{ag['name']} ({lat}, {lng})"
                break

    report.add(cat, "LOC-GEO-02", "Toàn bộ toạ độ cơ quan nằm chính xác trong Bounding Box địa giới", all_in_bounds, violator, duration_ms=(time.time()-t0)*1000)


# ─────────────────────────────────────────────────────────────────────────────
# 4. KIỂM THỬ TÍCH HỢP API FASTAPI & GOOGLE MAPS UNIVERSAL URL
# ─────────────────────────────────────────────────────────────────────────────
def test_api_endpoints_and_google_maps():
    cat = "4. API & GOOGLE MAPS"

    # API-01: GET /api/v1/locations/divisions
    t0 = time.time()
    r1 = client.get("/api/v1/locations/divisions?level=province")
    p_data = r1.json()
    valid_p = r1.status_code == 200 and p_data.get("total", 0) >= 63
    report.add(cat, "LOC-API-01", "API /api/v1/locations/divisions trả về 63 tỉnh thành", valid_p, duration_ms=(time.time()-t0)*1000)

    # API-02: GET /api/v1/locations/mergers/resolve
    t0 = time.time()
    r2 = client.get("/api/v1/locations/mergers/resolve?query_name=Trung%20Phụng")
    m_data = r2.json()
    valid_m = r2.status_code == 200 and m_data.get("found") is True
    report.add(cat, "LOC-API-02", "API /api/v1/locations/mergers/resolve nhận diện phường sáp nhập", valid_m, duration_ms=(time.time()-t0)*1000)

    # API-03: GET /api/v1/locations/agencies/nearby
    t0 = time.time()
    r3 = client.get("/api/v1/locations/agencies/nearby?lat=21.0285&lng=105.8542&radius_km=10")
    near_data = r3.json()
    items = near_data.get("items", [])
    valid_sort = True
    if len(items) > 1:
        for i in range(len(items) - 1):
            if items[i]["distance_km"] > items[i+1]["distance_km"]:
                valid_sort = False
                break
    report.add(cat, "LOC-API-03", f"API /api/v1/locations/agencies/nearby sắp xếp cự ly tăng dần ({len(items)} kết quả)", r3.status_code == 200 and valid_sort and len(items) > 0, duration_ms=(time.time()-t0)*1000)

    # API-04: GET /api/v1/locations/directions-url (Google Maps Universal Scheme)
    t0 = time.time()
    r4 = client.get("/api/v1/locations/directions-url?agency_id=1&origin_lat=21.0285&origin_lng=105.8542")
    dir_data = r4.json()
    d_url = dir_data.get("directions_url", "")
    valid_gmap = (
        r4.status_code == 200 and
        d_url.startswith("https://www.google.com/maps/dir/?api=1") and
        "destination=21.018942,105.834125" in d_url and
        "travelmode=driving" in d_url
    )
    report.add(cat, "LOC-API-04", "Tạo đường dẫn Google Maps Directions chuẩn Universal URL Scheme", valid_gmap, f"URL: {d_url}", duration_ms=(time.time()-t0)*1000)


# ─────────────────────────────────────────────────────────────────────────────
# 5. KIỂM THỬ TÍCH HỢP TRÍ TUỆ NHÂN TẠO GEMINI (AI AGENT TOOLING)
# ─────────────────────────────────────────────────────────────────────────────
def test_ai_agent_integration():
    cat = "5. AI AGENT TOOL"
    t0 = time.time()

    gemini = GeminiService()
    res = gemini.tool_tra_cuu_dia_diem_co_quan("Trung Phụng")
    valid_ai = (
        "1199/NQ-UBTVQH15" in res and
        "Khâm Thiên" in res and
        "Số 18 Ngõ Thổ Quan" in res and
        "Chỉ đường trên Google Maps" in res
    )
    report.add(cat, "LOC-AI-01", "Tool tra cứu địa điểm cung cấp đầy đủ căn cứ sáp nhập và link Google Maps cho AI", valid_ai, f"Snippet: {res[:150]}...", duration_ms=(time.time()-t0)*1000)


# ─────────────────────────────────────────────────────────────────────────────
# 6. KIỂM THỬ BẢO MẬT & TUÂN THỦ NGHỊ ĐỊNH 13/2023/NĐ-CP (PRIVACY)
# ─────────────────────────────────────────────────────────────────────────────
def test_security_and_privacy():
    cat = "6. BẢO MẬT & QUYỀN RIÊNG TƯ"
    t0 = time.time()

    # Kiểm tra xem trong toàn bộ bảng CSDL có cột nào lưu GPS cá nhân người dùng không
    conn = sqlite3.connect(DEFAULT_LOCATION_DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table';")
    schemas = [r[0] for r in cur.fetchall() if r[0]]
    conn.close()

    # Toạ độ trong agencies là toạ độ của cơ quan công quyền, KHÔNG phải của người dân
    no_user_tracking_table = not any("user_locations" in s or "user_gps" in s for s in schemas)
    report.add(cat, "LOC-SEC-01", "Tuân thủ NĐ 13/2023/NĐ-CP: Tuyệt đối không lưu toạ độ cá nhân của người dùng", no_user_tracking_table, duration_ms=(time.time()-t0)*1000)


def main():
    print("=" * 80)
    print("VINALEX — KIỂM THỬ TOÀN DIỆN PHÂN HỆ ĐỊA ĐIỂM & CHỈ ĐƯỜNG CƠ QUAN HÀNH CHÍNH")
    print("=" * 80 + "\n")

    test_database_integrity()
    test_merger_accuracy()
    test_haversine_and_geofence()
    test_api_endpoints_and_google_maps()
    test_ai_agent_integration()
    test_security_and_privacy()

    total, passed, failed = report.summary()
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
