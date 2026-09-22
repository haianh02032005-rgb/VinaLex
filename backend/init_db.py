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
    }
]


async def init_database():
    print(f"[*] Đang kết nối PostgreSQL tại: {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}...")
    try:
        async with engine.begin() as conn:
            print("[*] Đang tạo các bảng (users, procedures, user_procedures)...")
            await conn.run_sync(Base.metadata.create_all)
        print("[+] Tạo bảng thành công!")

        # Seed sample procedures
        async with AsyncSessionLocal() as session:
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
        print("[!] Lưu ý: Nếu bạn chưa cài đặt hoặc bật PostgreSQL, bạn vẫn có thể chạy Frontend độc lập với dữ liệu mẫu có sẵn.")


if __name__ == "__main__":
    asyncio.run(init_database())
