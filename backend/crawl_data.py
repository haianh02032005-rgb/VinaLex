"""
VinaLex — CLI Tool thu thập dữ liệu Thư Viện Pháp Luật
Hỗ trợ cào có giới hạn hoặc cào liên tục không giới hạn (chỉ dừng khi bấm Ctrl+C).

Cách chạy:
    # Cào không giới hạn (chỉ dừng khi bạn bấm Ctrl + C):
    python -m backend.crawl_data --continuous

    # Cào số lượng cụ thể:
    python -m backend.crawl_data --limit 20 --category Bat-dong-san
"""

import os
import sys
import time
import json
import socket
import asyncio
import argparse

# Thiết lập encoding UTF-8 cho Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.services.crawler_service import ThuvienphapluatCrawler
try:
    from backend.core.config import settings
except ImportError:
    settings = None


def is_postgres_running(host: str = "localhost", port: int = 5432, timeout: float = 0.5) -> bool:
    """Kiểm tra nhanh xem cổng PostgreSQL có đang mở và kết nối được không."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def count_records(filepath: str) -> int:
    """Đếm số bản ghi trong file JSON nếu tồn tại."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return len(json.load(f))
    except Exception:
        return 0


async def main():
    parser = argparse.ArgumentParser(
        description="VinaLex — Công cụ thu thập dữ liệu pháp luật từ thuvienphapluat.vn"
    )
    parser.add_argument(
        "--mode",
        choices=["docs", "procedures", "all"],
        default="all",
        help="Chế độ thu thập: docs (văn bản quy phạm), procedures (thủ tục hành chính), hoặc all (cả hai)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        help="Chuyên mục cần cào (ví dụ: Bat-dong-san, Doanh-nghiep, Lao-dong-Tien-luong...). Mặc định duyệt toàn bộ.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Số lượng bản ghi tối đa (đặt 0 hoặc dùng cờ --continuous để cào không giới hạn)",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        default=False,
        help="Cào liên tục không giới hạn cho đến khi người dùng bấm phím Ctrl + C để dừng",
    )
    parser.add_argument(
        "--save-db",
        action="store_true",
        default=True,
        help="Lưu dữ liệu trực tiếp vào cơ sở dữ liệu PostgreSQL (nếu có)",
    )
    parser.add_argument(
        "--no-save-db",
        action="store_false",
        dest="save_db",
        help="Không lưu vào cơ sở dữ liệu (chỉ lưu file JSON)",
    )
    parser.add_argument(
        "--sync-rag",
        action="store_true",
        default=False,
        help="Đồng bộ văn bản vào Qdrant Vector DB để phục vụ RAG AI Chat",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        help="Độ trễ giữa các request tính bằng giây (mặc định 1.2s để tránh bị giới hạn request)",
    )

    args = parser.parse_args()

    is_continuous = args.continuous or args.limit == 0

    print("=" * 70)
    print("  🚀 VinaLex — Thu thập dữ liệu từ Thư Viện Pháp Luật (TVPL)")
    print(f"  • Chế độ: {args.mode}")
    print(f"  • Chuyên mục: {args.category or 'Toàn bộ chuyên mục pháp luật'}")
    print(f"  • Độ trễ request: {args.delay} giây (an toàn, tránh lỗi HTTP 429)")
    if is_continuous:
        print("  • Giới hạn: ♾️  KHÔNG GIỚI HẠN (CONTINUOUS MODE)")
        print("  👉 NHẤN PHÍM [Ctrl + C] BẤT KỲ LÚC NÀO ĐỂ DỪNG LẠI AN TOÀN")
    else:
        print(f"  • Giới hạn: {args.limit} bản ghi")
    print(f"  • Lưu vào PostgreSQL: {'CÓ (khi DB hoạt động)' if args.save_db else 'KHÔNG'}")
    print(f"  • Đồng bộ vào Qdrant: {'CÓ' if args.sync_rag else 'KHÔNG'}")

    print("=" * 70)

    crawler = ThuvienphapluatCrawler(request_delay=args.delay)

    all_categories = list(crawler.CATEGORIES.keys())
    if args.category:
        categories = [args.category]
    else:
        categories = all_categories

    start_time = time.time()
    total_new_docs = 0
    total_new_procs = 0
    stopped_by_user = False

    try:
        if is_continuous:
            print("\n[*] Đang chạy cào liên tục... Mỗi bản ghi cào xong sẽ được LƯU NGAY vào ổ đĩa.")
            print("[*] Khi muốn dừng, bạn hãy nhấn Ctrl + C trên bàn phím.\n")

            cycle = 1
            while True:
                print(f"\n--- [Chu kỳ duyệt chuyên mục #{cycle}] ---")
                if args.mode in ["docs", "all"]:
                    for cat in categories:
                        docs = crawler.crawl_legal_documents(categories=[cat], limit_per_cat=None, save_instant=True)
                        total_new_docs += len(docs)

                if args.mode in ["procedures", "all"]:
                    procs = crawler.crawl_procedure_guides(limit=None, save_instant=True)
                    total_new_procs += len(procs)

                cycle += 1
                time.sleep(3)
        else:
            if args.mode in ["docs", "all"]:
                limit_per_cat = max(1, args.limit // len(categories))
                print(f"\n[*] Đang thu thập văn bản quy phạm pháp luật (~{limit_per_cat} bản ghi/chuyên mục)...")
                docs = crawler.crawl_legal_documents(categories=categories, limit_per_cat=limit_per_cat, save_instant=True)
                total_new_docs += len(docs)

            if args.mode in ["procedures", "all"]:
                proc_limit = max(3, args.limit // 2) if args.mode == "all" else args.limit
                print(f"\n[*] Đang thu thập bài viết hướng dẫn thủ tục (tối đa {proc_limit} bài)...")
                procs = crawler.crawl_procedure_guides(limit=proc_limit, save_instant=True)
                total_new_procs += len(procs)

    except (KeyboardInterrupt, asyncio.CancelledError, BaseException):
        stopped_by_user = True
        print("\n" + "=" * 70)
        print("  🛑 ĐÃ NHẬN LỆNH DỪNG QUÁ TRÌNH CÀO DỮ LIỆU (Ctrl + C)")
        print("  [*] Đang chốt an toàn toàn bộ dữ liệu...")
        print("=" * 70)

    # ── Tổng kết & Đồng bộ Database (An toàn, không văng lỗi) ──
    docs_file = os.path.join("data", "crawled_legal_docs.json")
    procs_file = os.path.join("data", "crawled_procedures.json")

    final_docs_count = count_records(docs_file)
    final_procs_count = count_records(procs_file)
    elapsed = round(time.time() - start_time, 1)

    # Kiểm tra PostgreSQL trước khi lưu để tránh lỗi kết nối
    if args.save_db:
        pg_host = getattr(settings, "POSTGRES_SERVER", "localhost") if settings else "localhost"
        pg_port = getattr(settings, "POSTGRES_PORT", 5432) if settings else 5432
        if is_postgres_running(pg_host, pg_port):
            print(f"\n[*] Đang đồng bộ toàn bộ kho dữ liệu vào PostgreSQL ({pg_host}:{pg_port})...")
            try:
                if os.path.exists(docs_file):
                    with open(docs_file, "r", encoding="utf-8") as f:
                        docs_data = json.load(f)
                    await crawler.save_legal_documents_to_db(docs_data)

                if os.path.exists(procs_file):
                    with open(procs_file, "r", encoding="utf-8") as f:
                        procs_data = json.load(f)
                    await crawler.save_procedures_to_db(procs_data)
            except BaseException as ex:
                print(f"[!] Bỏ qua lưu DB: {ex}")
        else:
            print(f"\n[i] PostgreSQL hiện chưa được bật ({pg_host}:{pg_port}).")
            print(f"[i] Toàn bộ dữ liệu đã được lưu an toàn 100% trong thư mục 'data/'.")
            print(f"[i] Khi bạn khởi động PostgreSQL, chỉ cần chạy: python -m backend.init_db để nạp dữ liệu.")

    if args.sync_rag and os.path.exists(docs_file):
        try:
            print("[*] Đang đồng bộ vào Qdrant Vector DB...")
            with open(docs_file, "r", encoding="utf-8") as f:
                docs_data = json.load(f)
            await crawler.sync_to_vector_db(docs_data)
        except BaseException as ex:
            print(f"[!] Bỏ qua đồng bộ Vector DB: {ex}")

    print("\n" + "=" * 70)
    print(f"  🎉 TỔNG KẾT DỮ LIỆU HIỆN TẠI (Thời gian chạy: {elapsed}s)")
    print(f"  • Tổng văn bản quy phạm pháp luật: {final_docs_count} bản ghi ({docs_file})")
    print(f"  • Tổng hướng dẫn thủ tục hành chính: {final_procs_count} bản ghi ({procs_file})")
    print("  • TẤT CẢ DỮ LIỆU ĐÃ ĐƯỢC BẢO TOÀN TRONG THƯ MỤC ./data/")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
