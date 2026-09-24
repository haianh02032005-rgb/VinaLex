"""
Kiểm thử tính chính xác của Số liệu Thống kê & Danh mục Thủ tục (VinaLex)
Đảm bảo:
1. CSDL thực tế khớp hoàn toàn với số liệu công bố.
2. Không còn bất kỳ số liệu người dùng ảo nào trong mockData và giao diện.
3. Các huy hiệu danh mục phản ánh chính xác số lượng thủ tục lọc được.
"""

import os
import sys
import sqlite3
import json
import re

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)


def test_real_database_counts():
    print("\n--- TEST 1: Kiểm tra số liệu thực tế trong CSDL SQLite (vinalex.db) ---")
    db_path = os.path.join(ROOT_DIR, "data", "vinalex.db")
    assert os.path.exists(db_path), f"Không tìm thấy CSDL {db_path}"

    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # 1. Tổng số thủ tục hành chính
    c.execute("SELECT count(*) FROM procedures")
    total_procedures = c.fetchone()[0]
    print(f"  -> Tổng số thủ tục hành chính thực tế: {total_procedures}")
    assert total_procedures == 556, f"Expected 556 procedures, got {total_procedures}"

    # 2. Tổng số văn bản quy phạm pháp luật
    c.execute("SELECT count(*) FROM legal_documents")
    total_docs = c.fetchone()[0]
    print(f"  -> Tổng số văn bản quy phạm pháp luật thực tế: {total_docs}")
    assert total_docs == 204, f"Expected 204 legal documents, got {total_docs}"

    # 3. Tổng số điều khoản quy phạm (RAG Chunks)
    rag_path = os.path.join(ROOT_DIR, "data", "parsed_rag_chunks.json")
    if os.path.exists(rag_path):
        with open(rag_path, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        total_chunks = len(chunks)
        print(f"  -> Tổng số điều khoản quy phạm (RAG Chunks): {total_chunks}")
        assert total_chunks >= 8300, f"Expected >= 8300 chunks, got {total_chunks}"

    conn.close()
    print("PASS: CSDL thực tế đã được xác nhận (556 TTHC, 204 văn bản, 8.300+ điều khoản).")


def test_category_counts_accuracy():
    print("\n--- TEST 2: Kiểm tra số lượng thủ tục theo 8 nhóm danh mục lớn ---")
    db_path = os.path.join(ROOT_DIR, "data", "vinalex.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT category_slug, category FROM procedures")
    rows = c.fetchall()
    conn.close()

    cats = {
        'dat-dai': 0,
        'ho-tich': 0,
        'doanh-nghiep': 0,
        'giao-thong': 0,
        'giao-duc': 0,
        'y-te': 0,
        'thue': 0,
        'lao-dong': 0,
    }

    for p_slug, p_cat in rows:
        p_slug = (p_slug or '').lower()
        p_cat = (p_cat or '').lower()

        if p_slug in ['dat-dai', 'bat-dong-san'] or any(k in p_cat for k in ['đất', 'nhà', 'bất động sản']):
            cats['dat-dai'] += 1
        if p_slug == 'ho-tich' or 'hộ tịch' in p_cat or 'căn cước' in p_cat:
            cats['ho-tich'] += 1
        if p_slug in ['doanh-nghiep', 'thuong-mai'] or any(k in p_cat for k in ['doanh nghiệp', 'thương mại']):
            cats['doanh-nghiep'] += 1
        if p_slug in ['giao-thong', 'giao-thong-van-tai'] or any(k in p_cat for k in ['giao thông', 'vận tải']):
            cats['giao-thong'] += 1
        if p_slug == 'giao-duc' or 'giáo dục' in p_cat:
            cats['giao-duc'] += 1
        if p_slug == 'y-te' or 'y tế' in p_cat:
            cats['y-te'] += 1
        if p_slug in ['thue', 'thue-phi-le-phi', 'tai-chinh-nha-nuoc'] or any(k in p_cat for k in ['thuế', 'tài chính']):
            cats['thue'] += 1
        if p_slug in ['lao-dong', 'lao-dong-tien-luong', 'bao-hiem'] or any(k in p_cat for k in ['lao động', 'tiền lương', 'bhxh', 'bảo hiểm']):
            cats['lao-dong'] += 1

    expected_counts = {
        'dat-dai': 50,
        'ho-tich': 39,
        'doanh-nghiep': 19,
        'giao-thong': 10,
        'giao-duc': 13,
        'y-te': 24,
        'thue': 55,
        'lao-dong': 58,
    }

    for cat_slug, expected in expected_counts.items():
        actual = cats[cat_slug]
        print(f"  -> Danh mục '{cat_slug}': {actual} thủ tục (Kỳ vọng: {expected})")
        assert actual == expected, f"Lệch số lượng ở {cat_slug}: thực tế {actual} != kỳ vọng {expected}"

    print("PASS: Toàn bộ 8 nhóm danh mục khớp 100% số lượng trong CSDL.")


def test_frontend_mockdata_and_stats():
    print("\n--- TEST 3: Kiểm tra tệp frontend/lib/mockData.ts ---")
    mock_file = os.path.join(ROOT_DIR, "frontend", "lib", "mockData.ts")
    assert os.path.exists(mock_file), f"Không tìm thấy {mock_file}"

    with open(mock_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Tuyệt đối không còn "người dùng" hoặc "50,000+"
    assert "người dùng hàng tháng" not in content.lower(), "Vẫn còn xuất hiện 'Người dùng hàng tháng' trong mockData.ts"
    assert "50,000+" not in content, "Vẫn còn xuất hiện '50,000+' trong mockData.ts"
    assert "2,500+" not in content, "Vẫn còn xuất hiện '2,500+' trong mockData.ts"
    assert "15,000+" not in content, "Vẫn còn xuất hiện '15,000+' trong mockData.ts"
    assert "120,000+" not in content, "Vẫn còn xuất hiện '120,000+' trong mockData.ts"

    # 2. Kiểm tra các số liệu mới trong STATS
    assert "550+" in content, "Thiếu '550+' trong STATS"
    assert "200+" in content, "Thiếu '200+' trong STATS"
    assert "8,300+" in content, "Thiếu '8,300+' trong STATS"
    assert "100%" in content, "Thiếu '100%' trong STATS"

    # 3. Kiểm tra số lượng trong CATEGORIES
    expected_category_defs = [
        ("dat-dai", 50),
        ("ho-tich", 39),
        ("doanh-nghiep", 19),
        ("giao-thong", 10),
        ("giao-duc", 13),
        ("y-te", 24),
        ("thue", 55),
        ("lao-dong", 58),
    ]
    for slug, cnt in expected_category_defs:
        pattern = rf"slug:\s*'{slug}',[^}}]*count:\s*{cnt}"
        assert re.search(pattern, content), f"Không tìm thấy định nghĩa category {slug} với count {cnt} trong mockData.ts"
        print(f"  -> CATEGORIES[{slug}] count={cnt} verified.")

    print("PASS: frontend/lib/mockData.ts hoàn toàn chuẩn hóa theo số liệu thực tế.")


if __name__ == "__main__":
    test_real_database_counts()
    test_category_counts_accuracy()
    test_frontend_mockdata_and_stats()
    print("\n[SUCCESS] TẤT CẢ CÁC KIỂM THỬ SỐ LIỆU VÀ DANH MỤC ĐỀU ĐẠT 100%!")
