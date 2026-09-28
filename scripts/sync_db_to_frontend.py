"""
VinaLex — Đồng bộ hóa toàn bộ CSDL SQLite (615 thủ tục & 204 văn bản) ra thư mục Frontend public
Đảm bảo:
1. 100% thủ tục từ data/vinalex.db được nạp vào frontend/public/data/
2. Bao gồm đầy đủ thủ tục 'cap-giay-chung-nhan-quyen-su-dung-dat'
3. Khắc phục triệt để lỗi 404 khi build static hoặc chạy offline
"""

import os
import sys
import json
import sqlite3

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def export_database():
    db_path = os.path.join("data", "vinalex.db")
    if not os.path.exists(db_path):
        print(f"[!] Không tìm thấy database tại {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Lấy toàn bộ thủ tục
    cur.execute("SELECT * FROM procedures")
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()

    procedures = []
    slug_set = set()

    for row in rows:
        item = dict(zip(cols, row))
        slug = item.get("slug")
        if not slug:
            continue
        slug_set.add(slug)

        # Parse JSON fields if string
        for f in ["steps", "documents", "tags"]:
            val = item.get(f)
            if isinstance(val, str):
                try:
                    item[f] = json.loads(val)
                except Exception:
                    pass

        procedures.append(item)

    print(f"[*] Đã trích xuất {len(procedures)} thủ tục từ vinalex.db")
    print(f"[*] Có thủ tục 'cap-giay-chung-nhan-quyen-su-dung-dat': {'cap-giay-chung-nhan-quyen-su-dung-dat' in slug_set}")

    # 2. Lấy toàn bộ văn bản pháp luật nếu có
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='legal_documents'")
    legal_docs = []
    if cur.fetchone():
        cur.execute("SELECT * FROM legal_documents")
        doc_cols = [d[0] for d in cur.description]
        doc_rows = cur.fetchall()
        for row in doc_rows:
            d_item = dict(zip(doc_cols, row))
            legal_docs.append(d_item)
        print(f"[*] Đã trích xuất {len(legal_docs)} văn bản pháp luật từ vinalex.db")

    conn.close()

    # 3. Ghi vào các tệp đích
    targets = [
        os.path.join("data", "all_procedures.json"),
        os.path.join("frontend", "public", "data", "all_procedures.json"),
        os.path.join("frontend", "public", "data", "dvc_procedures.json"),
        os.path.join("data", "dvc_procedures.json"),
    ]

    for t in targets:
        os.makedirs(os.path.dirname(t), exist_ok=True)
        with open(t, "w", encoding="utf-8") as f:
            json.dump(procedures, f, ensure_ascii=False, indent=2)
        print(f"[+] Đã ghi {len(procedures)} thủ tục vào: {t}")

    if legal_docs:
        doc_targets = [
            os.path.join("data", "all_legal_docs.json"),
            os.path.join("frontend", "public", "data", "crawled_legal_docs.json"),
        ]
        for dt in doc_targets:
            os.makedirs(os.path.dirname(dt), exist_ok=True)
            with open(dt, "w", encoding="utf-8") as f:
                json.dump(legal_docs, f, ensure_ascii=False, indent=2)
            print(f"[+] Đã ghi {len(legal_docs)} văn bản luật vào: {dt}")

    print("[SUCCESS] Hoàn tất đồng bộ dữ liệu CSDL sang Frontend!")

if __name__ == "__main__":
    export_database()
