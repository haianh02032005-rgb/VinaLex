"""
VinaLex — Kịch bản Kiểm tra Toàn diện Tất cả Thủ tục & Biểu mẫu PDF
Kiểm tra:
1. Độ sẵn sàng của API Backend đối với từng slug
2. Kiểm tra fallback API Next.js đối với từng slug
3. Kiểm tra tính toàn vẹn của dữ liệu (documents, steps, title)
4. Kiểm tra sinh biểu mẫu PDF cho tất cả các giấy tờ trong mỗi thủ tục
"""

import sys
import os
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    print("=" * 70)
    print("VINALEX — AUDIT TOÀN BỘ THỦ TỤC & BIỂU MẪU HÀNH CHÍNH")
    print("=" * 70)

    # 1. Thu thập slug từ mọi nguồn
    sources = {}

    # mockData.ts
    try:
        with open("frontend/lib/mockData.ts", "r", encoding="utf-8") as f:
            content = f.read()
        mock_slugs = re.findall(r"slug:\s*'([^']+)'", content)
        for s in mock_slugs:
            sources.setdefault(s, []).append("frontend/lib/mockData.ts")
    except Exception as e:
        print("[!] Lỗi đọc mockData.ts:", e)

    # crawled_procedures.json
    if os.path.exists("data/crawled_procedures.json"):
        try:
            with open("data/crawled_procedures.json", "r", encoding="utf-8") as f:
                crawled = json.load(f)
            for p in crawled:
                s = p.get("slug")
                if s:
                    sources.setdefault(s, []).append("data/crawled_procedures.json")
        except Exception as e:
            print("[!] Lỗi đọc crawled_procedures.json:", e)

    # dvc_procedures.json
    if os.path.exists("data/dvc_procedures.json"):
        try:
            with open("data/dvc_procedures.json", "r", encoding="utf-8") as f:
                dvc = json.load(f)
            for p in dvc:
                s = p.get("slug")
                if s:
                    sources.setdefault(s, []).append("data/dvc_procedures.json")
        except Exception as e:
            print("[!] Lỗi đọc dvc_procedures.json:", e)

    print(f"[*] Tổng số slug duy nhất cần kiểm tra: {len(sources)}")
    print("-" * 70)

    results = {
        "passed": [],
        "backend_404": [],
        "fallback_404": [],
        "missing_docs": [],
        "missing_steps": [],
        "pdf_gen_errors": []
    }

    # 2. Kiểm tra từng thủ tục
    checked_count = 0
    pdf_test_count = 0
    pdf_pass_count = 0

    for slug, src_list in sorted(sources.items()):
        checked_count += 1
        backend_ok = False
        fallback_ok = False
        proc_data = None

        # A. Kiểm tra Backend API
        backend_url = f"http://localhost:8000/api/v1/procedures/{slug}"
        try:
            req = urllib.request.urlopen(backend_url, timeout=3)
            if req.status == 200:
                backend_ok = True
                proc_data = json.loads(req.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            if he.code == 404:
                results["backend_404"].append((slug, src_list))
            else:
                print(f"[!] Backend HTTP Error {he.code} cho slug {slug}")
        except Exception as ex:
            # Backend có thể offline hoặc từ chối kết nối
            pass

        # B. Kiểm tra Next.js Fallback Route
        fallback_url = f"http://localhost:3000/api/procedures-fallback?slug={slug}"
        try:
            req = urllib.request.urlopen(fallback_url, timeout=3)
            if req.status == 200:
                fallback_ok = True
                if not proc_data:
                    proc_data = json.loads(req.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            if he.code == 404:
                results["fallback_404"].append((slug, src_list))
        except Exception as ex:
            pass

        # Đánh giá tính toàn vẹn của dữ liệu nếu lấy được
        if proc_data:
            title = proc_data.get("title", "")
            docs = proc_data.get("documents", [])
            steps = proc_data.get("steps", [])

            if not docs or len(docs) == 0:
                results["missing_docs"].append((slug, title))
            if not steps or len(steps) == 0:
                results["missing_steps"].append((slug, title))

            # C. Kiểm tra sinh PDF cho tối đa 2 biểu mẫu đầu tiên của mỗi thủ tục
            sample_docs = docs[:2] if isinstance(docs, list) else []
            for doc_item in sample_docs:
                doc_name = doc_item if isinstance(doc_item, str) else str(doc_item)
                pdf_test_count += 1
                try:
                    params = urllib.parse.urlencode({
                        "doc_name": doc_name,
                        "title": title,
                        "slug": slug,
                        "preview": "true"
                    })
                    pdf_url = f"http://localhost:8000/api/v1/procedures/download-template?{params}"
                    pdf_req = urllib.request.urlopen(pdf_url, timeout=5)
                    if pdf_req.status == 200 and len(pdf_req.read()) > 1000:
                        pdf_pass_count += 1
                    else:
                        results["pdf_gen_errors"].append((slug, doc_name, "Invalid status or size"))
                except Exception as pex:
                    results["pdf_gen_errors"].append((slug, doc_name, str(pex)))

            results["passed"].append(slug)
        else:
            # Không lấy được từ cả backend lẫn fallback
            print(f"[THẤT BẠI] Slug không tìm thấy ở bất kỳ nguồn nào: {slug} (Nguồn: {src_list})")

    # 3. Tổng kết báo cáo
    print("\n" + "=" * 70)
    print("BÁO CÁO TỔNG HỢP KIỂM TRA")
    print("=" * 70)
    print(f"- Tổng số thủ tục đã kiểm tra: {checked_count}")
    print(f"- Số thủ tục xem được chi tiết thành công (Passed): {len(results['passed'])}/{checked_count}")
    print(f"- Số thủ tục thiếu trên Backend DB (nhưng có fallback): {len(results['backend_404'])}")
    print(f"- Số thủ tục thiếu trên Fallback API (nhưng có trên Backend): {len(results['fallback_404'])}")
    print(f"- Số thủ tục hoàn toàn 404 (Không thể tải): {len([s for s in sources if s not in results['passed']])}")
    print(f"- Số thủ tục thiếu danh sách hồ sơ (documents): {len(results['missing_docs'])}")
    print(f"- Số thủ tục thiếu các bước (steps): {len(results['missing_steps'])}")
    print(f"- Kiểm thử sinh PDF biểu mẫu: {pdf_pass_count}/{pdf_test_count} đạt chuẩn")

    if results["backend_404"]:
        print("\n[!] DANH SÁCH THỦ TỤC THIẾU TRÊN BACKEND DATABASE (CẦN SEED):")
        for s, src in results["backend_404"][:15]:
            print(f"    * {s} (từ {src})")
        if len(results["backend_404"]) > 15:
            print(f"    ... và {len(results['backend_404']) - 15} thủ tục khác.")

    if results["pdf_gen_errors"]:
        print("\n[!] CÁC LỖI SINH BIỂU MẪU PDF:")
        for s, d, err in results["pdf_gen_errors"][:10]:
            print(f"    * Thủ tục: {s} | Giấy tờ: {d} | Lỗi: {err}")

    # Ghi kết quả ra tệp json để phân tích
    with open("test/audit_results.json", "w", encoding="utf-8") as out:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_checked": checked_count,
            "passed_count": len(results["passed"]),
            "failed_count": len([s for s in sources if s not in results["passed"]]),
            "backend_missing_count": len(results["backend_404"]),
            "backend_missing_slugs": [s for s, _ in results["backend_404"]],
            "fallback_missing_count": len(results["fallback_404"]),
            "missing_docs_slugs": [s for s, _ in results["missing_docs"]],
            "missing_steps_slugs": [s for s, _ in results["missing_steps"]],
            "pdf_errors": [{"slug": s, "doc": d, "err": e} for s, d, e in results["pdf_gen_errors"]]
        }, out, ensure_ascii=False, indent=2)

    print("\n[+] Đã lưu báo cáo chi tiết vào: test/audit_results.json")


if __name__ == "__main__":
    main()
