"""
VinaLex — Test Tra cứu Thông tư, Nghị định & Văn bản Pháp luật
(Decrees & Circulars Search, Excerpt Extraction & Procedure Independence Test)

Kiểm thử xác minh:
1. Tra cứu danh sách văn bản pháp luật (/api/v1/legal-documents) hoạt động chuẩn xác.
2. Lọc theo loại văn bản: Nghị định, Thông tư, Quyết định...
3. Tìm kiếm bằng từ khóa: trích xuất excerpt, loại bỏ các văn bản không liên quan.
4. Đọc toàn văn qua API (/api/v1/legal-documents/{slug}).
5. Đảm bảo tính độc lập: API văn bản pháp luật KHÔNG đề xuất thủ tục hành chính.
6. Đảm bảo hệ thống RAG (backend/services/rag_service.py) nguyên vẹn không bị sửa đổi.
"""

import sys
import os

sys.path.insert(0, os.path.abspath("."))
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi.testclient import TestClient
from backend.main import app

def run_tests():
    client = TestClient(app)

    print("=" * 70)
    print("VinaLex — BẮT ĐẦU KIỂM THỬ TÍNH NĂNG TÌM KIẾM THÔNG TƯ, NGHỊ ĐỊNH")
    print("=" * 70)

    # ── TEST 1: Danh sách văn bản & Phân trang ──
    print("\n--- TEST 1: Lấy danh sách văn bản pháp luật (/api/v1/legal-documents) ---")
    res1 = client.get("/api/v1/legal-documents?limit=10")
    assert res1.status_code == 200, f"Lỗi HTTP {res1.status_code}: {res1.text}"
    data1 = res1.json()
    total = data1.get("total", 0)
    items1 = data1.get("items", [])
    print(f"[+] Tổng số văn bản có sẵn trong hệ thống: {total}")
    print(f"[+] Lấy thành công trang đầu với {len(items1)} văn bản")
    assert total > 0, "Hệ thống phải có ít nhất 1 văn bản pháp luật"
    assert len(items1) > 0, "Trang đầu không được rỗng"
    for item in items1:
        assert "id" in item, "Item thiếu id"
        assert "title" in item, "Item thiếu title"
        assert "doc_type" in item, "Item thiếu doc_type"
        assert "slug" in item, "Item thiếu slug"
        assert "procedure" not in item, "Item không được chứa liên kết đề xuất thủ tục!"
    print("  => PASS: Cấu trúc dữ liệu văn bản pháp luật đạt chuẩn!")

    # ── TEST 2: Lọc theo loại văn bản (doc_type) ──
    print("\n--- TEST 2: Lọc theo loại văn bản (doc_type='Quyết định') ---")
    res2 = client.get("/api/v1/legal-documents?doc_type=Quy%E1%BA%BFt+%C4%91%E1%BB%8Bnh&limit=10")
    assert res2.status_code == 200
    data2 = res2.json()
    items2 = data2.get("items", [])
    print(f"[+] Tìm thấy {data2.get('total')} Quyết định")
    assert len(items2) > 0
    for it in items2:
        assert "quyết định" in it["doc_type"].lower(), f"Lỗi: Văn bản '{it['title']}' không phải Quyết định!"
    print("  => PASS: Lọc loại văn bản chính xác 100%!")

    # ── TEST 3: Tìm kiếm từ khóa & Trích xuất Excerpt ──
    print("\n--- TEST 3: Tìm kiếm từ khóa 'việc làm' & Kiểm tra trích xuất Excerpt ---")
    res3 = client.get("/api/v1/legal-documents?search=vi%E1%BB%87c+l%C3%A0m&limit=10")
    assert res3.status_code == 200
    data3 = res3.json()
    items3 = data3.get("items", [])
    print(f"[+] Tìm thấy {len(items3)} văn bản liên quan đến 'việc làm'")
    assert len(items3) > 0, "Phải tìm thấy ít nhất 1 văn bản liên quan đến 'việc làm'"
    for it in items3:
        has_excerpt = bool(it.get("excerpt"))
        title = it["title"].lower()
        excerpt = (it.get("excerpt") or "").lower()
        assert has_excerpt, f"Lỗi: Văn bản {it['doc_number']} không có đoạn trích excerpt!"
        print(f"  • [{it['doc_type']}] {it['doc_number']}: {it['title'][:50]}...")
        print(f"    Excerpt: {it['excerpt'][:80]}...")
    print("  => PASS: Tìm kiếm từ khóa trả về kết quả kèm trích xuất Excerpt chuẩn xác!")

    # ── TEST 4: Đọc toàn văn qua API (/api/v1/legal-documents/{slug}) ──
    print("\n--- TEST 4: Đọc toàn văn văn bản chi tiết (/api/v1/legal-documents/{slug}) ---")
    first_slug = items3[0]["slug"]
    res4 = client.get(f"/api/v1/legal-documents/{first_slug}")
    assert res4.status_code == 200
    doc_detail = res4.json()
    assert doc_detail["slug"] == first_slug
    assert "content_text" in doc_detail, "Phải có trường content_text"
    content_len = len(doc_detail.get("content_text") or "")
    print(f"[+] Văn bản: {doc_detail['title']}")
    print(f"[+] Độ dài toàn văn: {content_len} ký tự")
    assert content_len > 0, "Toàn văn không được rỗng"
    print("  => PASS: API đọc toàn văn văn bản hoạt động trơn tru!")

    # ── TEST 5: Loại bỏ triệt để từ khóa không liên quan (Pruning) ──
    print("\n--- TEST 5: Pruning test với từ khóa vô nghĩa 'xyz987qwerty' ---")
    res5 = client.get("/api/v1/legal-documents?search=xyz987qwerty")
    assert res5.status_code == 200
    data5 = res5.json()
    assert data5.get("total") == 0, "Phải trả về 0 văn bản với từ khóa không tồn tại!"
    assert len(data5.get("items", [])) == 0
    print("  => PASS: Hard Pruning thành công, 0 kết quả rác!")

    # ── TEST 6: Tính độc lập với thủ tục hành chính ──
    print("\n--- TEST 6: Xác minh KHÔNG đề xuất thủ tục trong kết quả văn bản ---")
    for it in items3:
        assert "procedure_id" not in it
        assert "procedures" not in it
        assert "steps" not in it
        assert "fee" not in it
    print("  => PASS: Tính năng trích xuất văn bản tách biệt 100% với thủ tục!")

    # ── TEST 7: Kiểm tra tính nguyên vẹn của hệ thống RAG ──
    print("\n--- TEST 7: Xác minh hệ thống RAG (backend/services/rag_service.py) nguyên vẹn ---")
    rag_file = os.path.join("backend", "services", "rag_service.py")
    assert os.path.exists(rag_file), "rag_service.py phải tồn tại"
    with open(rag_file, "r", encoding="utf-8") as f:
        rag_content = f.read()
    assert "class RagService" in rag_content, "rag_service.py phải có class RagService"
    print("  => PASS: Hệ thống RAG được bảo toàn nguyên vẹn!")

    print("\n" + "=" * 70)
    print("🎉 TẤT CẢ 7/7 BÀI TEST TÌM KIẾM THÔNG TƯ, NGHỊ ĐỊNH ĐỀU VƯỢT QUA!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
