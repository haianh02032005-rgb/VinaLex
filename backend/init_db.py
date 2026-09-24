"""
VinaLex — Khởi tạo & Seed Database (PostgreSQL)

Chạy script này để tạo bảng và nạp dữ liệu mẫu ban đầu:
    python -m backend.init_db
"""

import asyncio
import sys
import hashlib
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from backend.core.config import settings
from backend.db.postgres import Base, engine, AsyncSessionLocal
from backend.models.procedure import ProcedureModel, UserModel, LegalDocumentModel
import json
import os



INITIAL_PROCEDURES = [
    {
        "slug": "cap-giay-chung-nhan-quyen-su-dung-dat",
        "title": "Cấp giấy chứng nhận quyền sử dụng đất lần đầu",
        "category": "Đất đai & Nhà ở",
        "category_slug": "dat-dai",
        "description": "Thủ tục cấp giấy chứng nhận quyền sử dụng đất, quyền sở hữu nhà ở và tài sản khác gắn liền với đất cho hộ gia đình, cá nhân lần đầu.",
        "steps": [
            {"index": 1, "title": "Chuẩn bị hồ sơ", "description": "Thu thập đầy đủ giấy tờ theo danh sách quy định", "duration": "1-3 ngày"},
            {"index": 2, "title": "Nộp hồ sơ", "description": "Nộp tại Bộ phận một cửa UBND cấp huyện hoặc văn phòng đăng ký đất đai", "duration": "1 ngày"},
            {"index": 3, "title": "Thẩm tra hồ sơ", "description": "Cán bộ địa chính kiểm tra tính hợp lệ của hồ sơ", "duration": "5-10 ngày"},
            {"index": 4, "title": "Đo đạc thực địa", "description": "Đơn vị đo đạc tiến hành đo đạc tại thực địa (nếu cần)", "duration": "3-7 ngày"},
            {"index": 5, "title": "Cấp giấy chứng nhận", "description": "Nhận kết quả và ký vào sổ cấp", "duration": "1 ngày"}
        ],
        "documents": [
            "Đơn đăng ký cấp Giấy chứng nhận (Mẫu 04/ĐK)",
            "Chứng minh nhân dân / CCCD của chủ sử dụng",
            "Giấy tờ về quyền sử dụng đất (nếu có)",
            "Trích lục bản đồ địa chính thửa đất",
            "Giấy tờ chứng minh nguồn gốc đất"
        ],
        "processing_time": "30 ngày làm việc",
        "fee": "100.000 - 500.000 VNĐ",
        "agency": "Văn phòng Đăng ký đất đai",
        "level": "Quận/Huyện",
        "tags": ["Sổ đỏ", "Đất đai", "GCNQSDĐ"],
        "is_published": True,
        "view_count": 12540,
    },
    {
        "slug": "dang-ky-khai-sinh",
        "title": "Đăng ký khai sinh cho trẻ em mới sinh",
        "category": "Hộ tịch",
        "category_slug": "ho-tich",
        "description": "Thủ tục đăng ký khai sinh cho trẻ em được sinh ra tại Việt Nam, do UBND cấp xã nơi cư trú của người mẹ hoặc người cha thực hiện.",
        "steps": [
            {"index": 1, "title": "Chuẩn bị hồ sơ", "description": "Chuẩn bị Giấy chứng sinh và CCCD của bố/mẹ", "duration": "1 ngày"},
            {"index": 2, "title": "Nộp hồ sơ", "description": "Nộp tại UBND phường/xã nơi cư trú", "duration": "1 ngày"},
            {"index": 3, "title": "Nhận kết quả", "description": "Nhận Giấy khai sinh tại UBND", "duration": "1-3 ngày"}
        ],
        "documents": [
            "Giấy chứng sinh (do bệnh viện/cơ sở y tế cấp)",
            "CCCD hoặc hộ chiếu của bố/mẹ",
            "Giấy đăng ký kết hôn (nếu có)",
            "Hộ khẩu gia đình"
        ],
        "processing_time": "5 ngày làm việc",
        "fee": "Miễn phí",
        "agency": "UBND Phường/Xã",
        "level": "Phường/Xã",
        "tags": ["Khai sinh", "Hộ tịch", "Trẻ em"],
        "is_published": True,
        "view_count": 9870,
    },
    {
        "slug": "dang-ky-thanh-lap-cong-ty-tnhh",
        "title": "Đăng ký thành lập Công ty TNHH một thành viên",
        "category": "Doanh nghiệp",
        "category_slug": "doanh-nghiep",
        "description": "Thủ tục đăng ký thành lập doanh nghiệp theo loại hình Công ty TNHH một thành viên tại Phòng Đăng ký kinh doanh - Sở KH&ĐT.",
        "steps": [
            {"index": 1, "title": "Chuẩn bị hồ sơ", "description": "Soạn thảo Điều lệ công ty, danh sách thành viên", "duration": "2-3 ngày"},
            {"index": 2, "title": "Đăng ký qua Cổng thông tin quốc gia", "description": "Nộp hồ sơ tại dangkykinhdoanh.gov.vn", "duration": "1 ngày"},
            {"index": 3, "title": "Thẩm định hồ sơ", "description": "Phòng ĐKKD xem xét hồ sơ", "duration": "3 ngày"},
            {"index": 4, "title": "Nhận Giấy chứng nhận ĐKDN", "description": "Nhận kết quả và khắc con dấu", "duration": "1 ngày"}
        ],
        "documents": [
            "Giấy đề nghị đăng ký doanh nghiệp",
            "Điều lệ công ty",
            "CCCD của chủ sở hữu công ty",
            "Văn bản ủy quyền (nếu nộp qua người đại diện)"
        ],
        "processing_time": "3 ngày làm việc",
        "fee": "50.000 VNĐ",
        "agency": "Sở Kế hoạch và Đầu tư",
        "level": "Tỉnh/TP",
        "tags": ["Doanh nghiệp", "TNHH", "Thành lập công ty"],
        "is_published": True,
        "view_count": 7320,
    },
    {
        "slug": "cap-bang-lai-xe-b1",
        "title": "Cấp giấy phép lái xe hạng B1",
        "category": "Giao thông",
        "category_slug": "giao-thong",
        "description": "Thủ tục thi và cấp giấy phép lái xe hạng B1 (xe ô tô dưới 9 chỗ ngồi, không hành nghề lái xe) tại các Sở GTVT hoặc cơ sở đào tạo được cấp phép.",
        "steps": [
            {"index": 1, "title": "Đăng ký học & thi", "description": "Đăng ký tại cơ sở đào tạo lái xe được cấp phép", "duration": "1 ngày"},
            {"index": 2, "title": "Học lý thuyết", "description": "Hoàn thành ít nhất 90 giờ học lý thuyết", "duration": "1 tháng"},
            {"index": 3, "title": "Học thực hành", "description": "Hoàn thành ít nhất 420 km thực hành", "duration": "2-3 tháng"},
            {"index": 4, "title": "Thi sát hạch", "description": "Thi lý thuyết và thực hành lái xe", "duration": "1 ngày"},
            {"index": 5, "title": "Nhận bằng lái", "description": "Nhận giấy phép lái xe tại Sở GTVT", "duration": "5-7 ngày"}
        ],
        "documents": [
            "CCCD hoặc hộ chiếu còn hạn",
            "Giấy khám sức khỏe (theo Mẫu BV2)",
            "Ảnh 3x4 nền trắng (6 ảnh)",
            "Sổ hộ khẩu hoặc KT3 (để xác nhận cư trú)"
        ],
        "processing_time": "3-6 tháng",
        "fee": "3.000.000 - 5.000.000 VNĐ",
        "agency": "Sở Giao thông Vận tải",
        "level": "Tỉnh/TP",
        "tags": ["Bằng lái xe", "B1", "GPLX"],
        "is_published": True,
        "view_count": 15680,
    },
    {
        "slug": "dang-ky-tam-tru",
        "title": "Đăng ký tạm trú",
        "category": "Hộ tịch",
        "category_slug": "ho-tich",
        "description": "Thủ tục đăng ký tạm trú cho công dân Việt Nam khi lưu trú tại địa phương khác nơi đăng ký hộ khẩu thường trú từ 30 ngày trở lên.",
        "steps": [
            {"index": 1, "title": "Chuẩn bị hồ sơ", "description": "Điền tờ khai đăng ký tạm trú", "duration": "30 phút"},
            {"index": 2, "title": "Nộp hồ sơ", "description": "Nộp tại Công an phường/xã nơi tạm trú", "duration": "1 ngày"},
            {"index": 3, "title": "Nhận kết quả", "description": "Nhận sổ tạm trú hoặc thông báo kết quả", "duration": "1-3 ngày"}
        ],
        "documents": [
            "Tờ khai thay đổi thông tin cư trú (theo Mẫu CT01)",
            "CCCD hoặc hộ chiếu",
            "Giấy tờ chứng minh chỗ ở hợp pháp (hợp đồng thuê nhà...)"
        ],
        "processing_time": "3 ngày làm việc",
        "fee": "Miễn phí",
        "agency": "Công an Phường/Xã",
        "level": "Phường/Xã",
        "tags": ["Tạm trú", "Hộ khẩu", "Cư trú"],
        "is_published": True,
        "view_count": 11200,
    },
    {
        "slug": "quyet-toan-thue-tncn",
        "title": "Quyết toán thuế thu nhập cá nhân",
        "category": "Thuế & Tài chính",
        "category_slug": "thue",
        "description": "Thủ tục quyết toán thuế TNCN hàng năm cho cá nhân có thu nhập từ tiền lương, tiền công, qua ứng dụng iCanhan hoặc nộp trực tiếp tại cơ quan thuế.",
        "steps": [
            {"index": 1, "title": "Tổng hợp thu nhập", "description": "Thu thập chứng từ khấu trừ thuế từ tất cả nguồn thu", "duration": "1-2 ngày"},
            {"index": 2, "title": "Khai quyết toán online", "description": "Đăng nhập thuedientu.gdt.gov.vn và điền tờ khai", "duration": "1 ngày"},
            {"index": 3, "title": "Nộp thuế hoặc hoàn thuế", "description": "Nộp số thuế còn thiếu hoặc yêu cầu hoàn thuế", "duration": "1-30 ngày"}
        ],
        "documents": [
            "Tờ khai quyết toán thuế TNCN (Mẫu 02/QTT-TNCN)",
            "Chứng từ khấu trừ thuế TNCN",
            "Giấy tờ chứng minh người phụ thuộc (nếu có)",
            "Hóa đơn bảo hiểm nhân thọ, từ thiện... (nếu có)"
        ],
        "processing_time": "1-3 ngày (online)",
        "fee": "Miễn phí",
        "agency": "Cục Thuế / Chi cục Thuế",
        "level": "Quận/Huyện",
        "tags": ["Thuế TNCN", "Quyết toán", "Hoàn thuế"],
        "is_published": True,
        "view_count": 8900,
    },
    {
        "slug": "cap-ban-sao-trich-luc-khai-sinh",
        "title": "Cấp bản sao trích lục khai sinh (Làm lại / Cấp lại giấy khai sinh)",
        "category": "Hộ tịch",
        "category_slug": "ho-tich",
        "description": "Thủ tục cấp bản sao trích lục khai sinh khi bị mất, rách nát hoặc cần bổ sung hồ sơ giấy tờ, nộp tại cơ quan quản lý hộ tịch bất kỳ trên toàn quốc.",
        "steps": [
            {"index": 1, "title": "Chuẩn bị tờ khai", "description": "Điền tờ khai cấp bản sao trích lục hộ tịch", "duration": "15 phút"},
            {"index": 2, "title": "Nộp hồ sơ trực tiếp hoặc trực tuyến", "description": "Nộp tại UBND cấp xã hoặc nộp qua Cổng dịch vụ công quốc gia", "duration": "1 ngày"},
            {"index": 3, "title": "Nhận bản sao trích lục", "description": "Cơ quan hộ tịch tra cứu cơ sở dữ liệu và in cấp trích lục", "duration": "Trong ngày làm việc"}
        ],
        "documents": [
            "Tờ khai cấp bản sao trích lục hộ tịch",
            "CCCD/Hộ chiếu người yêu cầu",
            "Giấy tờ chứng minh quan hệ nhân thân (nếu được ủy quyền)"
        ],
        "processing_time": "Trong ngày làm việc",
        "fee": "8.000 VNĐ / bản sao",
        "agency": "UBND Phường/Xã hoặc Trung tâm phục vụ HCC",
        "level": "Phường/Xã",
        "tags": ["Làm lại giấy khai sinh", "Cấp lại giấy khai sinh", "Trích lục khai sinh", "Giấy khai sinh", "Khai sinh", "Hộ tịch"],
        "is_published": True,
        "view_count": 14200,
    },
    {
        "slug": "cap-the-can-cuoc",
        "title": "Cấp thẻ Căn cước công dân gắn chip (Làm thẻ Căn cước / CCCD)",
        "category": "Hộ tịch",
        "category_slug": "ho-tich",
        "description": "Thủ tục cấp thẻ Căn cước cho công dân từ đủ 14 tuổi hoặc trẻ em dưới 14 tuổi theo Luật Căn cước mới nhất.",
        "steps": [
            {"index": 1, "title": "Đăng ký hẹn lịch", "description": "Đăng ký qua VNeID hoặc đến trực tiếp cơ quan Công an", "duration": "1 ngày"},
            {"index": 2, "title": "Thu nhận thông tin", "description": "Chụp ảnh chân dung, thu nhận vân tay và mống mắt", "duration": "15 phút"},
            {"index": 3, "title": "Nhận thẻ Căn cước", "description": "Nhận trực tiếp hoặc chuyển phát bưu chính về tận nhà", "duration": "7 ngày làm việc"}
        ],
        "documents": [
            "Thông tin định danh trên VNeID",
            "Thẻ CCCD/CMND cũ (nếu có để thu hồi)",
            "Giấy khai sinh (đối với trẻ em dưới 14 tuổi)"
        ],
        "processing_time": "7 ngày làm việc",
        "fee": "Miễn phí lần đầu / 30.000 - 50.000 VNĐ cấp đổi",
        "agency": "Công an Quận/Huyện/Thị xã",
        "level": "Quận/Huyện",
        "tags": ["Làm căn cước", "Căn cước công dân", "CCCD", "Làm thẻ căn cước", "Định danh", "VNeID"],
        "is_published": True,
        "view_count": 25300,
    },
    {
        "slug": "dang-ky-ket-hon",
        "title": "Đăng ký kết hôn trong nước",
        "category": "Hộ tịch",
        "category_slug": "ho-tich",
        "description": "Thủ tục đăng ký kết hôn giữa hai công dân Việt Nam cư trú tại Việt Nam tại UBND cấp xã.",
        "steps": [
            {"index": 1, "title": "Chuẩn bị tờ khai", "description": "Hai bên nam nữ điền tờ khai đăng ký kết hôn", "duration": "1 ngày"},
            {"index": 2, "title": "Nộp hồ sơ trực tiếp", "description": "Cả hai bên có mặt tại UBND cấp xã nơi cư trú của một trong hai bên", "duration": "1 ngày"},
            {"index": 3, "title": "Ký và trao Giấy chứng nhận", "description": "Hai bên cùng ký vào Sổ hộ tịch và Giấy chứng nhận kết hôn", "duration": "Trong ngày làm việc"}
        ],
        "documents": [
            "Tờ khai đăng ký kết hôn (theo mẫu)",
            "CCCD hoặc Hộ chiếu của hai bên nam, nữ",
            "Giấy xác nhận tình trạng hôn nhân (nếu cư trú khác địa bàn)"
        ],
        "processing_time": "Trong ngày làm việc",
        "fee": "Miễn phí",
        "agency": "Ủy ban nhân dân Phường/Xã/Thị trấn",
        "level": "Phường/Xã",
        "tags": ["Đăng ký kết hôn", "Kết hôn", "Hộ tịch", "Giấy kết hôn"],
        "is_published": True,
        "view_count": 16890,
    }
]


import argparse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


async def init_database(use_sqlite: bool = False):
    if use_sqlite:
        db_uri = "sqlite+aiosqlite:///./data/vinalex.db"
        print("[*] Đang khởi tạo cơ sở dữ liệu SQLite tại: ./data/vinalex.db...")
        target_engine = create_async_engine(db_uri, echo=(settings.APP_ENV == "development"))
        target_session = async_sessionmaker(bind=target_engine, class_=AsyncSession, expire_on_commit=False)
    else:
        db_uri = settings.SQLALCHEMY_DATABASE_URI or ""
        if "sqlite" in db_uri:
            print("[*] Đang khởi tạo cơ sở dữ liệu SQLite tại: ./data/vinalex.db...")
            target_engine = create_async_engine(db_uri, echo=(settings.APP_ENV == "development"))
            target_session = async_sessionmaker(bind=target_engine, class_=AsyncSession, expire_on_commit=False)
        else:
            print(f"[*] Đang kết nối PostgreSQL tại: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}...")
            target_engine = engine
            target_session = AsyncSessionLocal

    try:
        async with target_engine.begin() as conn:
            print("[*] Đang tạo các bảng (users, procedures, user_procedures, legal_documents)...")
            await conn.run_sync(Base.metadata.create_all)
        print("[+] Tạo bảng thành công!")

        # Seed sample procedures
        async with target_session() as session:
            for item in INITIAL_PROCEDURES:
                res = await session.execute(
                    select(ProcedureModel).where(ProcedureModel.slug == item["slug"])
                )
                if not res.scalar_one_or_none():
                    proc = ProcedureModel(**item)
                    session.add(proc)
            
            # Seed crawled procedures if available in data/crawled_procedures.json
            crawled_proc_path = os.path.join("data", "crawled_procedures.json")
            if os.path.exists(crawled_proc_path):
                try:
                    with open(crawled_proc_path, "r", encoding="utf-8") as f:
                        crawled_procs = json.load(f)
                    for item in crawled_procs:
                        res = await session.execute(
                            select(ProcedureModel).where(ProcedureModel.slug == item["slug"])
                        )
                        if not res.scalar_one_or_none():
                            session.add(ProcedureModel(**item))
                    print(f"[+] Đã seed thêm các thủ tục từ {crawled_proc_path}")
                except Exception as ex:
                    print(f"[!] Lỗi khi nạp crawled_procedures.json: {ex}")

            # Seed DVC procedures if available in data/dvc_procedures.json
            dvc_proc_path = os.path.join("data", "dvc_procedures.json")
            if os.path.exists(dvc_proc_path):
                try:
                    with open(dvc_proc_path, "r", encoding="utf-8") as f:
                        dvc_procs = json.load(f)
                    allowed_fields = {
                        "slug", "title", "category", "category_slug", "description",
                        "steps", "documents", "processing_time", "fee", "agency",
                        "level", "tags", "is_published", "view_count"
                    }
                    for item in dvc_procs:
                        res = await session.execute(
                            select(ProcedureModel).where(ProcedureModel.slug == item["slug"])
                        )
                        if not res.scalar_one_or_none():
                            model_data = {k: v for k, v in item.items() if k in allowed_fields}
                            session.add(ProcedureModel(**model_data))
                    print(f"[+] Đã seed thêm các thủ tục từ {dvc_proc_path}")
                except Exception as ex:
                    print(f"[!] Lỗi khi nạp dvc_procedures.json: {ex}")

            # Seed crawled legal documents if available in data/crawled_legal_docs.json
            crawled_docs_path = os.path.join("data", "crawled_legal_docs.json")
            if os.path.exists(crawled_docs_path):
                try:
                    with open(crawled_docs_path, "r", encoding="utf-8") as f:
                        crawled_docs = json.load(f)
                    for item in crawled_docs:
                        res = await session.execute(
                            select(LegalDocumentModel).where(
                                (LegalDocumentModel.slug == item["slug"]) |
                                (LegalDocumentModel.doc_number == item.get("doc_number", ""))
                            )
                        )
                        if not res.scalar_one_or_none():
                            session.add(LegalDocumentModel(
                                doc_number=item.get("doc_number", ""),
                                title=item["title"],
                                slug=item["slug"],
                                doc_type=item.get("doc_type", "Văn bản pháp luật"),
                                category=item.get("category", "Chung"),
                                agency=item.get("agency"),
                                issue_date=item.get("issue_date"),
                                effective_date=item.get("effective_date"),
                                signer=item.get("signer"),
                                status=item.get("status", "Còn hiệu lực"),
                                summary=item.get("summary"),
                                content_text=item["content_text"],
                                original_url=item.get("original_url"),
                            ))
                    print(f"[+] Đã seed các văn bản pháp luật từ {crawled_docs_path}")
                except Exception as ex:
                    print(f"[!] Lỗi khi nạp crawled_legal_docs.json: {ex}")

            # Seed admin user
            admin_email = "admin@vinalex.vn"
            res = await session.execute(
                select(UserModel).where(UserModel.email == admin_email)
            )
            if not res.scalar_one_or_none():
                hashed_pw = hashlib.sha256("vinalex_salt_2024admin123".encode()).hexdigest()
                admin_user = UserModel(
                    name="Quản trị viên VinaLex",
                    email=admin_email,
                    hashed_password=hashed_pw,
                    is_active=True
                )
                session.add(admin_user)

            await session.commit()
            print("[+] Seed dữ liệu mẫu hoàn tất!")

    except Exception as e:
        print(f"[-] Không thể kết nối cơ sở dữ liệu: {e}")
        print("[!] Lưu ý: Máy tính của bạn hiện chưa có dịch vụ PostgreSQL đang chạy trên cổng 5432.")
        print("")
        print("  💡 GIẢI PHÁP 1 (Khuyến nghị — Chạy ngay với SQLite cục bộ không cần cài đặt):")
        print("     python -m backend.init_db --sqlite")
        print("")
        print("  💡 GIẢI PHÁP 2 (Chạy trực tiếp Backend & Frontend không cần Database):")
        print("     Hệ thống VinaLex đã tích hợp sẵn cơ chế Fallback nạp 551 thủ tục từ file JSON.")
        print("     Chỉ cần khởi động:")
        print("     .\\venv\\Scripts\\uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload")
        print("")
        print("  💡 GIẢI PHÁP 3 (Nếu muốn dùng PostgreSQL):")
        print("     Bật dịch vụ PostgreSQL trong services.msc hoặc chạy Docker:")
        print("     docker run --name vinalex-postgres -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=vinalex_db -d postgres:16")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VinaLex Database Initializer")
    parser.add_argument("--sqlite", action="store_true", help="Sử dụng SQLite cục bộ (data/vinalex.db) thay vì PostgreSQL")
    args = parser.parse_args()
    asyncio.run(init_database(use_sqlite=args.sqlite))

