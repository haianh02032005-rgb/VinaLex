"""
VinaLex — CLI Tool thu thập dữ liệu Cổng Dịch Vụ Công Quốc Gia
(https://dichvucong.gov.vn/)

Hỗ trợ:
  - Cào liên tục không giới hạn, chỉ dừng khi bấm Ctrl+C (--continuous)
  - Cào số lượng cụ thể (--limit)
  - Lọc theo lĩnh vực (--linh-vuc)
  - Chọn loại dữ liệu: thủ tục / tin tức / tất cả (--mode)

Cách chạy:
    # Cào không giới hạn (chỉ dừng khi bấm Ctrl+C):
    python -m backend.crawl_dichvucong --continuous

    # Cào 50 thủ tục từ lĩnh vực đất đai và giao thông:
    python -m backend.crawl_dichvucong --limit 50 --mode procedures --linh-vuc dat-dai giao-thong

    # Chỉ cào tin tức, tối đa 20 bài:
    python -m backend.crawl_dichvucong --mode news --limit 20

    # Thay đổi delay (mặc định 1.2s):
    python -m backend.crawl_dichvucong --continuous --delay 2.0
"""

import sys
import asyncio
import argparse
import signal

# Thiết lập encoding UTF-8 cho Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.services.dichvucong_crawler import DichVuCongCrawler, LINH_VUC_MAP


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crawl_dichvucong",
        description=(
            "VinaLex — Công cụ thu thập dữ liệu thủ tục hành chính, "
            "tin tức và biểu mẫu từ Cổng Dịch Vụ Công Quốc Gia (dichvucong.gov.vn)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ sử dụng:
  # Cào liên tục không giới hạn:
  python -m backend.crawl_dichvucong --continuous

  # Cào 30 thủ tục lĩnh vực đất đai:
  python -m backend.crawl_dichvucong --limit 30 --mode procedures --linh-vuc dat-dai

  # Chỉ cào tin tức, 20 bài, delay 2 giây:
  python -m backend.crawl_dichvucong --mode news --limit 20 --delay 2.0

Danh sách lĩnh vực hỗ trợ:
""" + "\n".join(f"  {k:<25} → {v}" for k, v in LINH_VUC_MAP.items()),
    )

    parser.add_argument(
        "--mode",
        choices=["procedures", "news", "all"],
        default="all",
        help=(
            "Loại dữ liệu cần thu thập:\n"
            "  procedures = Thủ tục hành chính\n"
            "  news       = Tin tức / Sự kiện\n"
            "  all        = Cả hai (mặc định)"
        ),
    )

    parser.add_argument(
        "--continuous",
        action="store_true",
        default=False,
        help=(
            "Cào liên tục không giới hạn cho đến khi nhấn Ctrl+C. "
            "Khi bật cờ này, --limit bị bỏ qua."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Số lượng bản ghi tối đa cho mỗi loại dữ liệu. "
            "0 hoặc không truyền = không giới hạn (tương đương --continuous)."
        ),
    )

    parser.add_argument(
        "--linh-vuc",
        nargs="+",
        default=None,
        metavar="SLUG",
        help=(
            "Danh sách slug lĩnh vực cần cào (cách nhau bởi dấu cách). "
            "Mặc định: tất cả lĩnh vực. "
            f"Ví dụ: --linh-vuc dat-dai giao-thong ho-tich"
        ),
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        metavar="SECONDS",
        help=(
            "Độ trễ tối thiểu giữa các request tính bằng giây. "
            "Mặc định: 1.2s (đủ an toàn, tránh HTTP 429). "
            "Không nên đặt dưới 0.5s."
        ),
    )

    parser.add_argument(
        "--jitter",
        type=float,
        default=0.3,
        metavar="SECONDS",
        help=(
            "Biên ngẫu nhiên thêm vào delay để tránh pattern đều đặn (giây). "
            "Mặc định: 0.3s. Thực tế delay = delay + random(0, jitter)."
        ),
    )

    parser.add_argument(
        "--data-dir",
        type=str,
        default="data",
        metavar="PATH",
        help="Thư mục lưu dữ liệu JSON. Mặc định: data/",
    )

    parser.add_argument(
        "--cycle-interval",
        type=float,
        default=3.0,
        metavar="SECONDS",
        help=(
            "Thời gian nghỉ giữa 2 chu kỳ quét toàn bộ (chỉ áp dụng khi --continuous). "
            "Mặc định: 3.0s."
        ),
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Validate lĩnh vực
    if args.linh_vuc:
        invalid = [lv for lv in args.linh_vuc if lv not in LINH_VUC_MAP]
        if invalid:
            parser.error(
                f"Lĩnh vực không hợp lệ: {', '.join(invalid)}. "
                f"Các lĩnh vực hỗ trợ: {', '.join(LINH_VUC_MAP.keys())}"
            )

    is_continuous = args.continuous or args.limit == 0
    limit = None if is_continuous else (args.limit or None)

    # ── In banner ──
    print("=" * 65)
    print("  🏛️  VinaLex — Cào Dữ Liệu Cổng Dịch Vụ Công Quốc Gia")
    print(f"  • Nguồn      : https://dichvucong.gov.vn/")
    print(f"  • Chế độ     : {args.mode}")
    print(f"  • Delay/req  : {args.delay}s (+ jitter ≤{args.jitter}s)")
    print(f"  • Thư mục    : {args.data_dir}/")
    if args.linh_vuc:
        lv_names = [LINH_VUC_MAP.get(lv, lv) for lv in args.linh_vuc]
        print(f"  • Lĩnh vực   : {', '.join(lv_names)}")
    else:
        print(f"  • Lĩnh vực   : TẤT CẢ ({len(LINH_VUC_MAP)} lĩnh vực)")

    if is_continuous:
        print("  • Giới hạn   : ♾️  KHÔNG GIỚI HẠN — CONTINUOUS MODE")
        print("  👉 NHẤN Ctrl+C BẤT KỲ LÚC NÀO ĐỂ DỪNG AN TOÀN")
    else:
        print(f"  • Giới hạn   : {limit} bản ghi / loại dữ liệu")
    print("=" * 65)

    # ── Khởi tạo crawler ──
    crawler = DichVuCongCrawler(
        request_delay=args.delay,
        data_dir=args.data_dir,
        jitter=args.jitter,
    )

    # ── Đăng ký SIGINT/SIGTERM để dừng nhẹ nhàng ──
    def handle_signal(signum, frame):
        print(f"\n[Signal] Nhận tín hiệu {signum}. Đang yêu cầu dừng...")
        crawler.stop()

    signal.signal(signal.SIGINT, handle_signal)
    try:
        signal.signal(signal.SIGTERM, handle_signal)
    except (OSError, AttributeError):
        pass  # SIGTERM không khả dụng trên Windows

    # ── Thực thi ──
    try:
        if is_continuous:
            crawler.run_continuous(
                mode=args.mode,
                linh_vuc_slugs=args.linh_vuc,
                cycle_interval=args.cycle_interval,
            )
        else:
            stats = crawler.run_once(
                mode=args.mode,
                linh_vuc_slugs=args.linh_vuc,
                limit=limit,
            )
            print("\n[Hoàn tất]")
            print(f"  • Thủ tục mới  : {stats.get('procedures', 0)}")
            print(f"  • Tin tức mới  : {stats.get('news', 0)}")
            print(f"  • Biểu mẫu mới : {stats.get('forms', 0)}")

    except KeyboardInterrupt:
        crawler.stop()

    except Exception as exc:
        print(f"\n[Lỗi nghiêm trọng] {exc}")
        crawler.stop()
        raise


if __name__ == "__main__":
    main()
