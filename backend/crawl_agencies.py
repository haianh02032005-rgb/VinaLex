"""
VinaLex — CLI Tool: Thu Thập & Chuẩn Hoá Địa Điểm Cơ Quan Dịch Vụ Công
Tích hợp trực tiếp vào Cơ sở dữ liệu riêng (data/administrative_locations.db).

Cách chạy:
    # 1. Cào LIÊN TỤC 63 tỉnh thành, tự động dừng khi cập nhật chính xác 100% tất cả địa điểm:
    python -m backend.crawl_agencies --continuous

    # 2. Khởi tạo / Đồng bộ dữ liệu gốc chuẩn hoá (Master Data):
    python -m backend.crawl_agencies --seed

    # 3. Xem thống kê dữ liệu hiện có trong CSDL riêng:
    python -m backend.crawl_agencies --stats

    # 4. Tra cứu biến động sáp nhập (VD: Trung Phụng, Cầu Dền):
    python -m backend.crawl_agencies --resolve-merger "Trung Phụng"

    # 5. Tìm kiếm cơ quan hành chính gần toạ độ GPS:
    python -m backend.crawl_agencies --nearby --lat 21.0285 --lng 105.8542 --radius 5
"""

import os
import sys
import argparse
from typing import Optional

# Tự động phát hiện và chuyển sang môi trường virtualenv (venv) nếu người dùng chạy python toàn cục
workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
venv_python = os.path.join(workspace_root, "venv", "Scripts", "python.exe")
if os.path.exists(venv_python) and os.path.abspath(sys.executable).lower() != os.path.abspath(venv_python).lower():
    import subprocess
    try:
        res = subprocess.run([venv_python, "-m", "backend.crawl_agencies"] + sys.argv[1:])
        sys.exit(res.returncode)
    except KeyboardInterrupt:
        sys.exit(0)

# Thiết lập UTF-8 an toàn cho console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.db.agency_location_db import agency_location_db, DEFAULT_LOCATION_DB_PATH
from backend.services.agency_crawler import agency_crawler, calculate_haversine_distance


def print_banner():
    banner = r"""
╔═════════════════════════════════════════════════════════════════════════╗
║   🏛️  VinaLex — Administrative Agency Location & Navigation Engine      ║
║   Tra cứu địa điểm & dẫn đường cơ quan dịch vụ hành chính công          ║
║   Chuẩn hoá địa giới sáp nhập 2023-2025 theo Nghị quyết UBTVQH          ║
╚═════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)


def show_statistics():
    stats = agency_location_db.get_statistics()
    print("\n" + "═" * 65)
    print("  📊 BÁO CÁO THỐNG KÊ CSDL ĐỊA ĐIỂM HÀNH CHÍNH RIÊNG BIỆT")
    print("═" * 65)
    print(f"  • Đường dẫn CSDL            : {stats['db_path']}")
    print(f"  • Dung lượng CSDL           : {stats['db_size_bytes'] / 1024:.2f} KB")
    print(f"  • Số lượng Tỉnh/Thành phố   : {stats['total_provinces']} tỉnh thành (chuẩn 63)")
    print(f"  • Số lượng Quận/Huyện       : {stats['total_districts']} quận/huyện trọng điểm")
    print(f"  • Số lượng Xã/Phường        : {stats['total_wards']} xã/phường")
    print(f"  • Biến động sáp nhập ghi nhận: {stats['total_mergers_recorded']} trường hợp NQ UBTVQH")
    print(f"  • Cơ quan tiếp nhận hồ sơ    : {stats['total_active_agencies']} trụ sở chuẩn GPS")
    print(f"  • Ánh xạ dịch vụ thủ tục    : {stats['total_linked_services']} liên kết")
    print("═" * 65 + "\n")


def main():
    print_banner()
    parser = argparse.ArgumentParser(description="VinaLex — Quản trị CSDL Địa Điểm & Cơ Quan Hành Chính")
    parser.add_argument("--continuous", action="store_true", help="Cào liên tục 63/63 tỉnh thành phố, tự động dừng khi cập nhật chính xác 100% tất cả các địa điểm")
    parser.add_argument("--delay", type=float, default=0.15, help="Độ trễ giữa các tỉnh thành phố (giây, mặc định 0.15s)")
    parser.add_argument("--seed", action="store_true", help="Nạp dữ liệu chuẩn hoá ĐVHC, biến động sáp nhập và danh bạ cơ quan")
    parser.add_argument("--crawl-online", action="store_true", help="Cào trực tuyến danh bạ cơ quan hành chính từ Cổng DVC và Một Cửa địa phương")
    parser.add_argument("--province", type=str, default="all", help="Mã tỉnh/thành phố cần cào (VD: 01: Hà Nội, 79: TP.HCM, all: Toàn quốc)")
    parser.add_argument("--limit", type=int, default=20, help="Số lượng cơ quan hành chính tối đa cần cào")
    parser.add_argument("--sync-mergers", action="store_true", help="Đồng bộ danh mục biến động sáp nhập đơn vị hành chính 2023 - 2025")
    parser.add_argument("--stats", action="store_true", help="Hiển thị báo cáo thống kê CSDL")
    parser.add_argument("--resolve-merger", type=str, help="Tra cứu biến động sáp nhập theo tên xã/phường cũ")
    parser.add_argument("--nearby", action="store_true", help="Tìm kiếm cơ quan gần toạ độ GPS")
    parser.add_argument("--lat", type=float, default=21.0285, help="Vĩ độ (Latitude)")
    parser.add_argument("--lng", type=float, default=105.8542, help="Kinh độ (Longitude)")
    parser.add_argument("--radius", type=float, default=10.0, help="Bán kính tìm kiếm (km)")

    args = parser.parse_args()

    if args.continuous:
        print("[Mode] Kích hoạt chế độ CÀO LIÊN TỤC 63 TỈNH THÀNH PHỐ.")
        print("[Info] Tiến trình sẽ tự động hoàn tất và ngừng khi cập nhật chính xác 100% tất cả các địa điểm.")
        print("[Tip] Bạn có thể bấm phím Ctrl+C bất cứ lúc nào để dừng an toàn.\n")
        try:
            agency_crawler.crawl_continuous_until_complete(delay=args.delay)
        except (KeyboardInterrupt, SystemExit):
            print("\n[!] Đã nhận tín hiệu Ctrl+C: Đã lưu an toàn toàn bộ dữ liệu cào được vào CSDL.")
            show_statistics()
        return

    if args.seed:
        print("[*] Đang khởi tạo và chuẩn hóa Master Data địa giới hành chính...")
        res = agency_crawler.seed_master_data()
        print(f"[✓] Đã nạp thành công: {res}")
        show_statistics()
        return

    if args.crawl_online:
        print(f"[*] Đang cào dữ liệu cơ quan hành chính công (Tỉnh: {args.province}, Giới hạn: {args.limit})...")
        res = agency_crawler.crawl_online_agencies(province_code=args.province, limit=args.limit)
        print(f"[✓] Kết quả: Đã cào và lưu thành công {res['agencies_crawled']} cơ quan hành chính!")
        show_statistics()
        return

    if args.sync_mergers:
        print("[*] Đang đồng bộ danh mục sáp nhập đơn vị hành chính theo Nghị quyết UBTVQH...")
        res = agency_crawler.sync_mergers_data()
        print(f"[✓] Kết quả: Đã đồng bộ {res['mergers_synced']} hồ sơ biến động sáp nhập.")
        show_statistics()
        return

    if args.resolve_merger:
        print(f"[*] Tra cứu thông tin sáp nhập cho địa danh: '{args.resolve_merger}'")
        merger = agency_location_db.resolve_merger(args.resolve_merger)
        if merger:
            print("\n" + "─" * 60)
            print("  🔔 THÔNG BÁO BIẾN ĐỘNG SÁP NHẬP ĐƠN VỊ HÀNH CHÍNH")
            print("─" * 60)
            print(f"  • Tên đơn vị cũ     : {merger['old_unit_name']} ({merger['old_district']}, {merger['old_province']})")
            print(f"  • Tên đơn vị mới    : {merger['new_unit_name']}")
            print(f"  • Căn cứ pháp lý    : Nghị quyết {merger['resolution_code']}")
            print(f"  • Ngày có hiệu lực  : {merger['effective_date']}")
            print(f"  • Trụ sở tiếp nhận  : {merger['headquarters_address']}")
            print(f"  • Hướng dẫn chi tiết: {merger['notes']}")
            print("─" * 60 + "\n")
        else:
            print(f"[-] Không tìm thấy biến động sáp nhập nào khớp với '{args.resolve_merger}'.")
        return

    if args.nearby:
        print(f"[*] Đang tìm kiếm cơ quan hành chính quanh toạ độ ({args.lat}, {args.lng}) trong bán kính {args.radius} km...")
        all_agencies = agency_location_db.get_all_agencies_for_geo()
        results = []
        for ag in all_agencies:
            dist = calculate_haversine_distance(args.lat, args.lng, ag["latitude"], ag["longitude"])
            if dist <= args.radius:
                ag["distance_km"] = dist
                results.append(ag)
        results.sort(key=lambda x: x["distance_km"])

        print(f"[+] Tìm thấy {len(results)} cơ quan hành chính gần bạn:")
        for idx, r in enumerate(results, 1):
            print(f"\n  {idx}. {r['name']}")
            print(f"     • Khoảng cách   : {r['distance_km']} km")
            print(f"     • Địa chỉ       : {r['address']}")
            print(f"     • Giờ làm việc  : {r['working_hours']}")
            print(f"     • Điện thoại    : {r.get('phone', 'Chưa cập nhật')}")
            print(f"     • Google Maps   : {r.get('google_maps_url', 'N/A')}")
        return

    # Mặc định hiển thị thống kê nếu không có tham số
    show_statistics()


if __name__ == "__main__":
    main()
