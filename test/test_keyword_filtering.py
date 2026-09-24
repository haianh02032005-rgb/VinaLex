"""
VinaLex — Test Bộ Lọc Từ Khóa (Keyword Filtering & Pruning Test)

Kiểm thử xác minh:
1. Loại bỏ 100% các thủ tục không chứa từ khóa (Hard Pruning Filter).
2. Khớp đúng từ khóa có dấu / không dấu / từ đồng nghĩa.
3. Trả về danh sách rỗng (0 items) khi tìm từ khóa không tồn tại.
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
from backend.api.procedures import _load_fallback_procedures

def run_tests():
    client = TestClient(app)
    all_fallback = _load_fallback_procedures()
    print(f"[*] Tổng số thủ tục trong kho dữ liệu: {len(all_fallback)}")

    print("\n--- TEST 1: Tìm kiếm 'khai sinh' ---")
    res1 = client.get("/api/v1/procedures?search=khai+sinh&limit=50")
    assert res1.status_code == 200
    data1 = res1.json()
    items1 = data1.get("items", [])
    print(f"[+] Tìm thấy {len(items1)} thủ tục cho 'khai sinh'")
    assert len(items1) > 0, "Phải tìm thấy ít nhất 1 thủ tục khai sinh"
    for item in items1:
        title = item["title"].lower()
        desc = (item["description"] or "").lower()
        tags = " ".join(item.get("tags") or []).lower()
        full_text = f"{title} {desc} {tags}"
        # Phải chứa khai sinh hoặc chứng sinh
        has_match = ("khai sinh" in full_text) or ("chung sinh" in full_text)
        assert has_match, f"Lỗi: Thủ tục '{item['title']}' không chứa từ khóa khai sinh nhưng vẫn xuất hiện!"
        # Tuyệt đối không được là thủ tục đất đai hay thành lập công ty
        assert "sổ đỏ" not in title, f"Lỗi: Thủ tục sổ đỏ '{item['title']}' lọt vào kết quả khai sinh!"
    print("  => PASS: 100% kết quả khớp từ khóa 'khai sinh'!")

    print("\n--- TEST 2: Tìm kiếm 'sổ đỏ' ---")
    res2 = client.get("/api/v1/procedures?search=so+do&limit=50")
    assert res2.status_code == 200
    data2 = res2.json()
    items2 = data2.get("items", [])
    print(f"[+] Tìm thấy {len(items2)} thủ tục cho 'sổ đỏ'")
    assert len(items2) > 0, "Phải tìm thấy ít nhất 1 thủ tục sổ đỏ"
    valid_keywords = ["sổ đỏ", "so do", "quyền sử dụng đất", "quyen su dung dat", "gcnqsdd", "đất đai", "sổ hồng", "đất ở"]
    for item in items2:
        title = item["title"].lower()
        tags = " ".join(item.get("tags") or []).lower()
        has_valid_term = any(k in title or k in tags for k in valid_keywords)
        assert has_valid_term, f"Lỗi: Thủ tục '{item['title']}' không liên quan sổ đỏ/đất đai!"
    print("  => PASS: 100% kết quả khớp từ khóa liên quan 'sổ đỏ'!")

    print("\n--- TEST 3: Tìm kiếm 'thành lập công ty' ---")
    res3 = client.get("/api/v1/procedures?search=thanh+lap+cong+ty&limit=50")
    assert res3.status_code == 200
    data3 = res3.json()
    items3 = data3.get("items", [])
    print(f"[+] Tìm thấy {len(items3)} thủ tục cho 'thành lập công ty'")
    assert len(items3) > 0, "Phải tìm thấy thủ tục đăng ký doanh nghiệp / công ty"
    for item in items3:
        title = item["title"].lower()
        tags = " ".join(item.get("tags") or []).lower()
        assert any(k in title or k in tags for k in ["công ty", "doanh nghiệp", "thành lập", "kinh doanh"]), (
            f"Lỗi: Thủ tục '{item['title']}' không liên quan đến doanh nghiệp/công ty!"
        )
    print("  => PASS: 100% kết quả khớp 'thành lập công ty'!")

    print("\n--- TEST 4: Tìm kiếm từ khóa vô nghĩa 'xyz123khongtontai' ---")
    res4 = client.get("/api/v1/procedures?search=xyz123khongtontai")
    assert res4.status_code == 200
    data4 = res4.json()
    items4 = data4.get("items", [])
    print(f"[+] Số kết quả trả về cho từ khóa vô nghĩa: {len(items4)}")
    assert len(items4) == 0, f"Lỗi: Từ khóa vô nghĩa phải trả về 0 kết quả nhưng nhận được {len(items4)} kết quả!"
    print("  => PASS: Đã loại bỏ triệt để 100% thủ tục không khớp từ khóa!")

    print("\n🎉 TẤT CẢ CÁC BÀI KIỂM THỬ TỪ KHÓA ĐÃ THÀNH CÔNG VƯỢT TRỘI!")

if __name__ == "__main__":
    run_tests()
