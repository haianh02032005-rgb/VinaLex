"""
VinaLex — CLI Tool: Thu Thập Dữ Liệu Hồ Sơ, Giấy Tờ & Tệp PDF Từ dichvucong.gov.vn
Tích hợp trực tiếp vào Cơ sở dữ liệu riêng (data/dvc_documents.db).

Cách chạy:
    # 1. Cào 10 thủ tục và toàn bộ hồ sơ, biểu mẫu PDF thuộc lĩnh vực đất đai:
    python -m backend.crawl_dvc_pdf --limit 10 --category dat-dai

    # 2. Cào chính xác 1 mã thủ tục cụ thể:
    python -m backend.crawl_dvc_pdf --code 1.116461

    # 3. Cào liên tục không giới hạn (dừng bằng Ctrl+C):
    python -m backend.crawl_dvc_pdf --continuous

    # 4. Kiểm tra thống kê CSDL riêng hiện tại:
    python -m backend.crawl_dvc_pdf --stats

    # 5. Tìm kiếm giấy tờ, biểu mẫu trong kho:
    python -m backend.crawl_dvc_pdf --search "sổ đỏ"
"""

import os
import sys
import time
import signal
import argparse
from typing import Optional

# Tự động phát hiện và chuyển sang môi trường virtualenv (venv) nếu người dùng chạy python toàn cục
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_python = os.path.join(workspace_root, "venv", "Scripts", "python.exe")
if os.path.exists(venv_python) and os.path.abspath(sys.executable).lower() != os.path.abspath(venv_python).lower():
    import subprocess
    try:
        res = subprocess.run([venv_python, "-m", "backend.crawl_dvc_pdf"] + sys.argv[1:])
        sys.exit(res.returncode)
    except KeyboardInterrupt:
        sys.exit(0)

# Thiết lập encoding UTF-8 an toàn cho Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.services.dvc_pdf_crawler import DVCPdfCrawler, LINH_VUC_MAP
from backend.db.dvc_document_db import DVCDocumentDatabase, DEFAULT_DB_PATH


def print_banner():
    banner = r"""
╔═════════════════════════════════════════════════════════════════════════╗
║   🏛️  VinaLex — DVC PDF & Document Ingestion Engine v1.0              ║
║   Thu thập dữ liệu giấy tờ, hồ sơ TTHC & PDF từ dichvucong.gov.vn       ║
║   Chuẩn hoá thể thức văn bản hành chính theo Nghị định 30/2020/NĐ-CP    ║
╚═════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def show_statistics(db: DVCDocumentDatabase):
    stats = db.get_database_statistics()
    print("\n" + "═" * 65)
    print("  📊 BÁO CÁO THỐNG KÊ CƠ SỞ DỮ LIỆU RIÊNG (DVC_DOCUMENTS.DB)")
    print("═" * 65)
    print(f"  • Đường dẫn CSDL       : {stats['db_path']}")
    print(f"  • Tổng số thủ tục (TTHC): {stats['total_procedures']:,} thủ tục")
    print(f"  • Tổng số mục giấy tờ   : {stats['total_documents']:,} giấy tờ thành phần")
    print(f"  • Tổng số tệp PDF đã lưu: {stats['total_pdfs']:,} tệp")
    print(f"  • Tổng dung lượng tệp PDF: {stats['total_pdf_size_mb']} MB")
    print("\n  📂 Phân bố theo loại file PDF:")
    for ftype, count in stats.get("pdfs_by_type", {}).items():
        print(f"    - {ftype:<22}: {count:,} files")
    print("\n  📑 Phân bố theo chuyên mục:")
    for cat, count in list(stats.get("procedures_by_category", {}).items())[:8]:
        print(f"    - {cat:<25}: {count:,} thủ tục")
    print("═" * 65 + "\n")


def search_in_database(db: DVCDocumentDatabase, keyword: str):
    print(f"\n🔍 Đang tìm kiếm với từ khóa: '{keyword}'...")
    results = db.search_full_text(keyword, limit=10)
    if not results:
        print("  -> Không tìm thấy kết quả phù hợp trong kho.")
        return

    print(f"  -> Tìm thấy {len(results)} thủ tục phù hợp:")
    for idx, r in enumerate(results, 1):
        code = r.get("code")
        title = r.get("title")
        docs = db.get_procedure_documents(r["id"])
        pdfs = db.get_procedure_pdf_files(r["id"])
        print(f"\n  [{idx}] [{code}] {title}")
        print(f"      Lĩnh vực: {r.get('category')} | Cơ quan: {r.get('agency')}")
        print(f"      Số giấy tờ: {len(docs)} | Số tệp PDF: {len(pdfs)}")
        if pdfs:
            for p in pdfs[:3]:
                print(f"       📎 [PDF] {p.get('file_name')} ({round(p.get('file_size_bytes', 0)/1024, 1)} KB)")


def main():
    print_banner()

    parser = argparse.ArgumentParser(
        prog="crawl_dvc_pdf",
        description="VinaLex — Công cụ thu thập giấy tờ, hồ sơ TTHC & PDF từ dichvucong.gov.vn",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--category",
        nargs="+",
        default=None,
        help="Danh sách lĩnh vực cần cào (ví dụ: dat-dai, ho-tich, doanh-nghiep...)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Số lượng thủ tục tối đa cần thu thập (mặc định: 5)",
    )
    parser.add_argument(
        "--code",
        type=str,
        default=None,
        help="Cào chính xác một mã thủ tục (ví dụ: 1.116461)",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        default=False,
        help="Chạy liên tục cho đến khi bấm Ctrl+C",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        help="Khoảng nghỉ giữa các request (giây), mặc định 1.2s",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=DEFAULT_DB_PATH,
        help=f"Đường dẫn file SQLite cơ sở dữ liệu riêng (mặc định: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        default=False,
        help="Xem thống kê dữ liệu hiện tại trong database riêng",
    )
    parser.add_argument(
        "--search",
        type=str,
        default=None,
        help="Tìm kiếm thủ tục hoặc giấy tờ trong CSDL riêng",
    )

    args = parser.parse_args()
    db = DVCDocumentDatabase(db_path=args.db_path)

    # 1. Chế độ xem thống kê
    if args.stats:
        show_statistics(db)
        return

    # 2. Chế độ tìm kiếm
    if args.search:
        search_in_database(db, args.search)
        return

    # 3. Khởi tạo Crawler Engine
    crawler = DVCPdfCrawler(
        db_path=args.db_path,
        request_delay=args.delay,
        auto_generate_templates=True,
    )

    # Thiết lập xử lý dừng graceful khi bấm Ctrl+C
    def sig_handler(sig, frame):
        print("\n\n[Control] 🛑 Nhận tín hiệu dừng từ người dùng. Đang đóng kết nối an toàn...")
        crawler.stop()

    signal.signal(signal.SIGINT, sig_handler)

    # 4. Chế độ cào theo mã thủ tục cụ thể
    if args.code:
        res = crawler.crawl_by_code(args.code)
        if res:
            print(f"\n✅ Đã thu thập thành công thủ tục {args.code} và đồng bộ vào CSDL riêng!")
        show_statistics(db)
        return

    # 5. Chế độ cào liên tục hoặc theo giới hạn
    if args.continuous:
        print("[Mode] Chế độ cào LIÊN TỤC không giới hạn. Nhấn Ctrl+C để dừng.\n")
        try:
            cycle = 1
            while not crawler._should_stop():
                print(f"\n--- [Vòng lặp #{cycle}] Bắt đầu chu kỳ quét ---")
                crawler.crawl_categories(
                    linh_vuc_slugs=args.category,
                    limit_per_category=10,
                    max_total=None,
                )
                cycle += 1
                if crawler._should_stop():
                    break
                print("[Nghỉ] Nghỉ 5 giây trước chu kỳ tiếp theo...")
                time.sleep(5.0)
        except (KeyboardInterrupt, SystemExit):
            pass
    else:
        print(f"[Mode] Thu thập tối đa {args.limit} thủ tục...")
        crawler.crawl_categories(
            linh_vuc_slugs=args.category,
            limit_per_category=max(1, args.limit // (len(args.category) if args.category else 3)),
            max_total=args.limit,
        )

    # Hiển thị báo cáo kết quả cuối cùng
    show_statistics(db)


if __name__ == "__main__":
    main()
