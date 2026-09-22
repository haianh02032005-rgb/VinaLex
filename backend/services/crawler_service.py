"""
VinaLex — ThuvienphapluatCrawler Service
Module thu thập dữ liệu pháp lý và thủ tục hành chính từ Thư Viện Pháp Luật (https://thuvienphapluat.vn/)

Tuân thủ ARCHITECTURE.md & CONTRIBUTING.md:
- Class: PascalCase → ThuvienphapluatCrawler
- Phương thức: snake_case
- Không lưu vết dữ liệu nhạy cảm
- Lưu trữ 3 tầng: File JSON (Data Backup) -> PostgreSQL (ORM) -> Qdrant (Vector DB)
- Hỗ trợ cào liên tục không giới hạn (Continuous/Infinite Mode), dừng an toàn bằng Ctrl+C
"""

import os
import re
import sys
import time
import json
import random
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VinaLexCrawler")


class ThuvienphapluatCrawler:
    """
    Crawler thu thập văn bản quy phạm pháp luật và bài viết thủ tục hành chính
    từ cổng thông tin https://thuvienphapluat.vn/
    """

    BASE_URL = "https://thuvienphapluat.vn"
    VAN_BAN_MOI_URL = "https://thuvienphapluat.vn/van-ban-moi"
    CHINH_SACH_URL = "https://thuvienphapluat.vn/chinh-sach-phap-luat-moi"

    CHROME_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    CATEGORIES = {
        "Bat-dong-san": "Đất đai - Bất động sản",
        "Doanh-nghiep": "Doanh nghiệp",
        "Lao-dong-Tien-luong": "Lao động - Tiền lương",
        "Bo-may-hanh-chinh": "Bộ máy hành chính",
        "Tai-nguyen-Moi-truong": "Tài nguyên - Môi trường",
        "Xay-dung-Do-thi": "Xây dựng - Đô thị",
        "Thue-Phi-Le-Phi": "Thuế - Phí - Lệ phí",
        "Giao-thong-Van-tai": "Giao thông - Vận tải",
        "Tai-chinh-nha-nuoc": "Tài chính nhà nước",
        "Thuong-mai": "Thương mại",
        "Nghi-dinh": "Nghị định Chính phủ",
        "Thong-tu": "Thông tư các Bộ",
        "Quyet-dinh": "Quyết định hành chính",
    }

    def __init__(self, request_delay: float = 1.2, data_dir: str = "data"):
        self.request_delay = request_delay
        self.data_dir = data_dir
        self.session = requests.Session()
        self._init_session()
        os.makedirs(self.data_dir, exist_ok=True)

    def _init_session(self):
        """Khởi tạo session và thiết lập headers chuẩn để duyệt trơn tru."""
        self.session.headers.update({
            "User-Agent": self.CHROME_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://thuvienphapluat.vn/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        try:
            # Truy cập trang chủ trước để lấy cookies phiên làm việc
            self.session.get(self.BASE_URL, timeout=12)
        except Exception as e:
            logger.warning(f"Không thể khởi tạo session với trang chủ: {e}")

    def _slugify(self, text: str) -> str:
        """Chuyển chuỗi tiếng Việt thành slug URL duy nhất."""
        if not text:
            return f"item-{int(time.time() * 1000)}"
        text = text.lower()
        # Chuyển đổi ký tự tiếng Việt có dấu sang không dấu
        text = re.sub(r"[áàảãạăắằẳẵặâấầẩẫậ]", "a", text)
        text = re.sub(r"[éèẻẽẹêếềểễệ]", "e", text)
        text = re.sub(r"[íìỉĩị]", "i", text)
        text = re.sub(r"[óòỏõọôốồổỗộơớờởỡợ]", "o", text)
        text = re.sub(r"[úùủũụưứừửữự]", "u", text)
        text = re.sub(r"[ýỳỷỹỵ]", "y", text)
        text = re.sub(r"[đ]", "d", text)
        # Loại bỏ các ký tự đặc biệt
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        text = re.sub(r"[\s-]+", "-", text).strip("-")
        return text[:150]

    def _classify_procedure_category(self, title: str, description: str = "") -> Tuple[str, str]:
        """
        Phân loại lĩnh vực thủ tục hành chính chính xác theo thực thể và ngữ cảnh,
        tránh khớp nhầm từ con (VD: 'tài' trong 'tài liệu' hoặc 'tài khoản').
        """
        combined = f"{title} {description}".lower()

        # 1. Thuế & Tài chính
        tax_keywords = [
            "thuế", "nộp thuế", "kê khai thuế", "đăng ký thuế", "mã số thuế", 
            "quyết toán thuế", "miễn thuế", "thuế gtgt", "thuế tncn", "thuế tndn", 
            "lệ phí", "phí trước bạ", "quản lý thuế", "hóa đơn điện tử", "chi cục thuế"
        ]
        if any(kw in combined for kw in tax_keywords):
            return "Thuế & Tài chính", "thue"

        # 2. Đất đai - Bất động sản
        land_keywords = [
            "sổ đỏ", "sổ hồng", "đất đai", "quyền sử dụng đất", "gcnqsdđ", 
            "thửa đất", "địa chính", "nhà đất", "bất động sản", "chuyển nhượng nhà đất"
        ]
        if any(kw in combined for kw in land_keywords):
            return "Đất đai - Bất động sản", "bat-dong-san"

        # 3. Hộ tịch / Căn cước công dân / VNeID
        civil_keywords = [
            "khai sinh", "kết hôn", "hộ khẩu", "căn cước", "cccd", "vneid", 
            "khai tử", "hộ tịch", "xác nhận tình trạng hôn nhân", "thường trú", "tạm trú"
        ]
        if any(kw in combined for kw in civil_keywords):
            return "Hộ tịch", "ho-tich"

        # 4. Doanh nghiệp
        business_keywords = [
            "thành lập doanh nghiệp", "thành lập công ty", "đăng ký kinh doanh", 
            "giấy phép kinh doanh", "giải thể doanh nghiệp", "chi nhánh doanh nghiệp"
        ]
        if any(kw in combined for kw in business_keywords):
            return "Doanh nghiệp", "doanh-nghiep"

        # 5. Giao thông - Vận tải
        traffic_keywords = [
            "bằng lái", "giấy phép lái xe", "gplx", "đăng ký xe", "biển số xe", 
            "đăng kiểm", "giao thông đường bộ"
        ]
        if any(kw in combined for kw in traffic_keywords):
            return "Giao thông - Vận tải", "giao-thong-van-tai"

        # 6. Lao động - Tiền lương / BHXH
        labor_keywords = [
            "bảo hiểm xã hội", "bhxh", "thất nghiệp", "hợp đồng lao động", 
            "tiền lương", "chế độ thai sản", "tai nạn lao động"
        ]
        if any(kw in combined for kw in labor_keywords):
            return "Lao động - Tiền lương", "lao-dong-tien-luong"

        # 7. Tài nguyên - Môi trường (yêu cầu từ ghép chính xác, không dùng từ 'tài' đơn lẻ)
        env_keywords = [
            "môi trường", "tài nguyên nước", "khoáng sản", "xả thải", 
            "rác thải", "đánh giá tác động môi trường", "bảo vệ môi trường"
        ]
        if any(kw in combined for kw in env_keywords):
            return "Tài nguyên - Môi trường", "tai-nguyen-moi-truong"

        # 8. Xây dựng - Đô thị
        construction_keywords = ["giấy phép xây dựng", "quy hoạch đô thị", "công trình xây dựng"]
        if any(kw in combined for kw in construction_keywords):
            return "Xây dựng - Đô thị", "xay-dung-do-thi"

        return "Thủ tục hành chính", "thu-tuc-hanh-chinh"

    def fetch_url(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """Tải nội dung trang web với xử lý độ trễ và retry an toàn."""
        headers = {
            "Referer": referer or "https://thuvienphapluat.vn/",
        }

        for attempt in range(3):
            try:
                time.sleep(self.request_delay + random.uniform(0.1, 0.3))
                response = self.session.get(url, headers=headers, timeout=15)
                if response.status_code == 200:
                    response.encoding = "utf-8"
                    return response.text
                elif response.status_code == 429:
                    logger.warning(f"HTTP 429 (Máy chủ yêu cầu chậm lại) khi tải {url}. Tạm nghỉ 5 giây...")
                    time.sleep(5.0)
                elif response.status_code == 403:
                    logger.warning(f"HTTP 403 khi tải {url} (lần {attempt + 1})")
                    time.sleep(2.0)
                else:
                    logger.warning(f"Tải {url} thất bại với mã lỗi {response.status_code}")
            except Exception as ex:
                logger.error(f"Lỗi kết nối khi tải {url} (lần {attempt + 1}): {ex}")
                time.sleep(1.5)

        return None


    def get_existing_slugs(self, filename: str) -> Set[str]:
        """Lấy danh sách các slug hoặc URL đã được cào trước đó để tránh cào lặp."""
        filepath = os.path.join(self.data_dir, filename)
        if not os.path.exists(filepath):
            return set()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            slugs = set()
            for item in data:
                if "slug" in item:
                    slugs.add(item["slug"])
                if "original_url" in item:
                    slugs.add(item["original_url"])
                if "doc_number" in item and item["doc_number"]:
                    slugs.add(item["doc_number"])
            return slugs
        except Exception:
            return set()

    def save_single_item(self, item: Dict[str, Any], filename: str) -> int:
        """
        Lưu/gộp tức thì 1 bản ghi vào file JSON trên đĩa.
        Đảm bảo ngay cả khi người dùng nhấn Ctrl+C, bản ghi vừa cào vẫn an toàn trên đĩa!
        """
        filepath = os.path.join(self.data_dir, filename)
        existing: List[Dict[str, Any]] = []
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        # Kiểm tra xem bản ghi đã tồn tại chưa
        item_slug = item.get("slug")
        item_url = item.get("original_url")
        item_num = item.get("doc_number")

        updated = False
        for idx, ex in enumerate(existing):
            if (item_slug and ex.get("slug") == item_slug) or \
               (item_url and ex.get("original_url") == item_url) or \
               (item_num and ex.get("doc_number") == item_num and item_num):
                existing[idx] = item
                updated = True
                break

        if not updated:
            existing.append(item)

        # Ghi lại file với UTF-8
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)

        return len(existing)

    def save_to_json(self, data: List[Dict[str, Any]], filename: str, merge: bool = True) -> str:
        """Lưu hoặc gộp danh sách dữ liệu ra file JSON tại thư mục data/ với định dạng tiếng Việt UTF-8."""
        filepath = os.path.join(self.data_dir, filename)
        final_list: List[Dict[str, Any]] = []

        if merge and os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    final_list = json.load(f)
            except Exception:
                final_list = []

            # Gộp dữ liệu mới
            for item in data:
                item_slug = item.get("slug")
                item_num = item.get("doc_number")
                item_url = item.get("original_url")

                matched = False
                for idx, ex in enumerate(final_list):
                    if (item_slug and ex.get("slug") == item_slug) or \
                       (item_url and ex.get("original_url") == item_url) or \
                       (item_num and ex.get("doc_number") == item_num and item_num):
                        final_list[idx] = item
                        matched = True
                        break
                if not matched:
                    final_list.append(item)
        else:
            final_list = data

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(final_list, f, ensure_ascii=False, indent=2)

        logger.info(f"Đã lưu/gộp {len(final_list)} bản ghi vào file: {filepath}")
        return filepath

    def crawl_legal_document_links(self, category: Optional[str] = None) -> List[Tuple[str, str, str]]:
        """Lấy danh sách các liên kết văn bản pháp luật từ trang văn bản mới hoặc theo lĩnh vực."""
        results: List[Tuple[str, str, str]] = []
        category_name = self.CATEGORIES.get(category, "Pháp luật chung")

        if category:
            if category in ["Nghi-dinh", "Thong-tu", "Quyet-dinh", "Luat", "Van-ban-hop-nhat"]:
                url = f"{self.BASE_URL}/van-ban-moi/{category}"
            else:
                url = f"{self.BASE_URL}/van-ban-moi/{category}?ft=1"
        else:
            url = f"{self.BASE_URL}/van-ban-moi"

        logger.info(f"Đang quét danh sách văn bản tại: {url}")
        html = self.fetch_url(url, referer="https://thuvienphapluat.vn/")
        if not html:
            return results

        soup = BeautifulSoup(html, "html.parser")
        found_on_page = 0

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(strip=True)

            if "/van-ban/" in href and not href.endswith("/van-ban/") and len(title) > 20:
                full_url = urljoin(self.BASE_URL, href)
                if not any(item[1] == full_url for item in results):
                    results.append((title, full_url, category_name))
                    found_on_page += 1

        return results

    def parse_legal_document(self, url: str, default_title: str = "", category_name: str = "Pháp luật chung") -> Optional[Dict[str, Any]]:
        """Phân tích chi tiết 1 trang văn bản quy phạm pháp luật để lấy thuộc tính và nội dung toàn văn."""
        html = self.fetch_url(url, referer="https://thuvienphapluat.vn/")
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        # 1. Trích xuất Tiêu đề
        title = ""
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            title = og_title["content"].replace(" - THƯ VIỆN PHÁP LUẬT", "").strip()

        if not title:
            h1 = soup.find("h1")
            if h1:
                title = h1.get_text(strip=True)

        if not title and default_title:
            title = default_title

        if not title:
            title = soup.title.string.strip() if soup.title else "Văn bản pháp luật"

        # 2. Trích xuất Bảng Thuộc tính văn bản
        doc_number = ""
        doc_type = "Văn bản pháp luật"
        agency = ""
        signer = ""
        issue_date = ""
        effective_date = ""
        status = "Còn hiệu lực"

        for b in soup.find_all(["b", "strong", "td", "span"]):
            text = b.get_text(strip=True)
            if "Số hiệu:" in text:
                table = b.find_parent("table")
                if table:
                    for tr in table.find_all("tr"):
                        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
                        for i, cell in enumerate(cells):
                            if "Số hiệu:" in cell and i + 1 < len(cells):
                                doc_number = cells[i + 1]
                            elif "Loại văn bản:" in cell and i + 1 < len(cells):
                                doc_type = cells[i + 1]
                            elif "Nơi ban hành:" in cell and i + 1 < len(cells):
                                agency = cells[i + 1]
                            elif "Người ký:" in cell and i + 1 < len(cells):
                                signer = cells[i + 1]
                            elif "Ngày ban hành:" in cell and i + 1 < len(cells):
                                issue_date = cells[i + 1]
                            elif "Ngày hiệu lực:" in cell and i + 1 < len(cells):
                                effective_date = cells[i + 1]
                            elif "Tình trạng:" in cell and i + 1 < len(cells):
                                status = cells[i + 1]
                break

        if not doc_number:
            num_match = re.search(r"Số:\s*([0-9]+/[A-Z0-9\-\/]+)", soup.text)
            if num_match:
                doc_number = num_match.group(1).strip()
            elif "Số " in title:
                match = re.search(r"(?:Số|Quyết định|Nghị định|Thông tư|Luật)\s+([0-9]+/[A-Z0-9\-\/]+)", title, re.IGNORECASE)
                if match:
                    doc_number = match.group(1).strip()

        if doc_type == "Văn bản pháp luật":
            for kw in ["Nghị định", "Quyết định", "Thông tư", "Luật", "Nghị quyết", "Chỉ thị", "Công văn"]:
                if kw.lower() in title.lower():
                    doc_type = kw
                    break

        # 3. Trích xuất Toàn văn nội dung
        content_div = soup.find("div", class_="content1") or soup.find("div", id="divContentDoc") or soup.find("div", class_="content")
        clean_text = ""
        if content_div:
            for tag in content_div(["script", "style", "iframe", "button", "input", "noscript"]):
                tag.decompose()
            clean_text = content_div.get_text(separator="\n", strip=True)
        else:
            main_block = soup.find("div", id="content-to-read") or soup.find("div", class_="main-content")
            if main_block:
                for tag in main_block(["script", "style", "iframe"]):
                    tag.decompose()
                clean_text = main_block.get_text(separator="\n", strip=True)

        clean_text = re.sub(r"Bản dịch này thuộc quyền sở hữu của.*?\n", "", clean_text)
        clean_text = re.sub(r"THƯ VIỆN PHÁP LUẬT.*?\n", "", clean_text)

        if not clean_text or len(clean_text) < 100:
            return None

        summary_paragraphs = [p.strip() for p in clean_text.split("\n") if len(p.strip()) > 30]
        summary = summary_paragraphs[0] if summary_paragraphs else clean_text[:300]

        slug = self._slugify(f"{doc_number}-{title}") if doc_number else self._slugify(title)

        return {
            "doc_number": doc_number or slug[:30],
            "title": title,
            "slug": slug,
            "doc_type": doc_type,
            "category": category_name,
            "agency": agency or "Cơ quan nhà nước",
            "issue_date": issue_date or "Chưa cập nhật",
            "effective_date": effective_date or "Đã có hiệu lực",
            "signer": signer or "Đã ký",
            "status": status or "Còn hiệu lực",
            "summary": summary[:500],
            "content_text": clean_text,
            "original_url": url,
            "created_at": datetime.utcnow().isoformat(),
        }

    def crawl_legal_documents(
        self,
        categories: Optional[List[str]] = None,
        limit_per_cat: Optional[int] = 3,
        save_instant: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Thu thập văn bản quy phạm pháp luật.
        Nếu limit_per_cat=None hoặc 0, cào toàn bộ văn bản tìm thấy trong chuyên mục.
        Nếu save_instant=True, mỗi văn bản cào xong được ghi ngay lập tức vào crawled_legal_docs.json.
        """
        all_documents: List[Dict[str, Any]] = []
        target_categories = categories or list(self.CATEGORIES.keys())
        existing_slugs = self.get_existing_slugs("crawled_legal_docs.json")

        for cat in target_categories:
            links = self.crawl_legal_document_links(category=cat)
            cat_docs_count = 0

            for title, url, cat_name in links:
                if limit_per_cat and limit_per_cat > 0 and cat_docs_count >= limit_per_cat:
                    break

                # Bỏ qua nếu đã cào
                if url in existing_slugs or self._slugify(title) in existing_slugs:
                    continue

                logger.info(f"Đang bóc tách [{cat_name}]: {title[:65]}...")
                doc_data = self.parse_legal_document(url, default_title=title, category_name=cat_name)
                if doc_data:
                    all_documents.append(doc_data)
                    cat_docs_count += 1
                    existing_slugs.add(doc_data["slug"])
                    existing_slugs.add(url)
                    if doc_data.get("doc_number"):
                        existing_slugs.add(doc_data["doc_number"])

                    if save_instant:
                        total_on_disk = self.save_single_item(doc_data, "crawled_legal_docs.json")
                        logger.info(f" -> Đã lưu văn bản [{doc_data['doc_number']}]: {doc_data['title'][:50]} (Kho hiện có: {total_on_disk} văn bản)")
                    else:
                        logger.info(f" -> Thành công: [{doc_data['doc_number']}] ({len(doc_data['content_text'])} ký tự)")

        return all_documents

    def crawl_procedure_guides(self, limit: Optional[int] = 5, save_instant: bool = True) -> List[Dict[str, Any]]:
        """Thu thập các bài viết hướng dẫn thủ tục pháp lý thực tế."""
        procedures: List[Dict[str, Any]] = []
        html = self.fetch_url(self.CHINH_SACH_URL, referer="https://thuvienphapluat.vn/")
        if not html:
            return procedures

        soup = BeautifulSoup(html, "html.parser")
        article_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            title = a.get_text(strip=True)
            if "/chinh-sach-phap-luat-moi/" in href and len(title) > 25:
                full_url = urljoin(self.BASE_URL, href)
                if full_url not in [item[1] for item in article_links]:
                    article_links.append((title, full_url))

        existing_slugs = self.get_existing_slugs("crawled_procedures.json")

        for title, url in article_links:
            if limit and limit > 0 and len(procedures) >= limit:
                break

            if url in existing_slugs or self._slugify(title) in existing_slugs:
                continue

            logger.info(f"Bóc tách thủ tục: {title[:65]}...")
            proc_data = self.parse_procedure_guide(url, default_title=title)
            if proc_data:
                procedures.append(proc_data)
                existing_slugs.add(proc_data["slug"])
                existing_slugs.add(url)

                if save_instant:
                    total_on_disk = self.save_single_item(proc_data, "crawled_procedures.json")
                    logger.info(f" -> Đã lưu thủ tục: {proc_data['title'][:50]} (Kho hiện có: {total_on_disk} thủ tục)")
                else:
                    logger.info(f" -> Thủ tục bóc tách xong: {proc_data['title'][:50]}")

        return procedures

    def parse_procedure_guide(self, url: str, default_title: str = "") -> Optional[Dict[str, Any]]:
        """Phân tích bài viết hướng dẫn thủ tục và cấu trúc thành schema ProcedureModel."""
        html = self.fetch_url(url, referer="https://thuvienphapluat.vn/")
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")

        title = default_title
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text(strip=True)

        if not title:
            return None

        content_box = None
        if h1:
            content_box = h1.find_parent("div", class_="col-lg-9") or h1.find_parent("article")

        if not content_box:
            content_box = soup.find("div", class_="content-news") or soup.find("div", class_="content1")

        if not content_box:
            return None

        paragraphs = [p.get_text(strip=True) for p in content_box.find_all(["p", "li", "h2", "h3"]) if len(p.get_text(strip=True)) > 20]

        category, category_slug = self._classify_procedure_category(title, paragraphs[0] if paragraphs else "")

        steps = [
            {"index": 1, "title": "Chuẩn bị hồ sơ pháp lý", "description": "Người thực hiện chuẩn bị đầy đủ thành phần hồ sơ theo quy định", "duration": "1-2 ngày"},
            {"index": 2, "title": "Nộp hồ sơ đến cơ quan thụ lý", "description": "Nộp trực tiếp tại Bộ phận một cửa hoặc nộp trực tuyến qua Cổng dịch vụ công quốc gia", "duration": "1 ngày"},
            {"index": 3, "title": "Tiếp nhận và giải quyết", "description": "Cơ quan chuyên môn thẩm tra tính hợp lệ và xử lý hồ sơ", "duration": "3-7 ngày làm việc"},
            {"index": 4, "title": "Nhận kết quả", "description": "Nhận kết quả giải quyết thủ tục hành chính và nộp phí/lệ phí theo biên nhận", "duration": "1 ngày"}
        ]

        documents = [
            "Đơn/Tờ khai theo mẫu quy định của cơ quan nhà nước",
            "Bản sao Căn cước công dân / Hộ chiếu của người yêu cầu",
            "Giấy tờ chứng minh tư cách pháp lý hoặc văn bản ủy quyền (nếu có)",
            "Các tài liệu liên quan đến nội dung thủ tục"
        ]

        slug = self._slugify(title)

        return {
            "slug": slug,
            "title": title,
            "category": category,
            "category_slug": category_slug,
            "description": paragraphs[0] if paragraphs else title,
            "steps": steps,
            "documents": documents,
            "processing_time": "3 - 15 ngày làm việc",
            "fee": "Theo biểu mức quy định của Nhà nước",
            "agency": "Cơ quan có thẩm quyền theo phân cấp",
            "level": "Cấp Tỉnh / Huyện",
            "tags": [category, "Thủ tục", "Pháp luật"],
            "view_count": random.randint(120, 2500),
            "is_published": True
        }

    async def save_legal_documents_to_db(self, documents: List[Dict[str, Any]]) -> int:
        """Lưu danh sách văn bản quy phạm pháp luật vào PostgreSQL qua SQLAlchemy ORM."""
        from backend.db.postgres import AsyncSessionLocal
        from backend.models.procedure import LegalDocumentModel
        from sqlalchemy import select

        saved_count = 0
        try:
            async with AsyncSessionLocal() as session:
                for doc in documents:
                    stmt = select(LegalDocumentModel).where(
                        (LegalDocumentModel.slug == doc["slug"]) |
                        (LegalDocumentModel.doc_number == doc["doc_number"])
                    )
                    res = await session.execute(stmt)
                    existing = res.scalar_one_or_none()

                    if not existing:
                        db_doc = LegalDocumentModel(
                            doc_number=doc.get("doc_number", ""),
                            title=doc["title"],
                            slug=doc["slug"],
                            doc_type=doc.get("doc_type", "Văn bản pháp luật"),
                            category=doc.get("category", "Chung"),
                            agency=doc.get("agency"),
                            issue_date=doc.get("issue_date"),
                            effective_date=doc.get("effective_date"),
                            signer=doc.get("signer"),
                            status=doc.get("status", "Còn hiệu lực"),
                            summary=doc.get("summary"),
                            content_text=doc["content_text"],
                            original_url=doc.get("original_url"),
                        )
                        session.add(db_doc)
                        saved_count += 1
                    else:
                        existing.content_text = doc["content_text"]
                        existing.summary = doc.get("summary")
                        existing.status = doc.get("status", existing.status)

                await session.commit()
                logger.info(f"Đã lưu/cập nhật thành công {saved_count} văn bản vào PostgreSQL!")
        except Exception as e:
            logger.warning(f"Lưu văn bản vào PostgreSQL chưa hoàn tất (Database chưa kết nối): {e}")

        return saved_count

    async def save_procedures_to_db(self, procedures: List[Dict[str, Any]]) -> int:
        """Lưu danh sách thủ tục hành chính vào PostgreSQL (bảng procedures)."""
        from backend.db.postgres import AsyncSessionLocal
        from backend.models.procedure import ProcedureModel
        from sqlalchemy import select

        saved_count = 0
        try:
            async with AsyncSessionLocal() as session:
                for proc in procedures:
                    stmt = select(ProcedureModel).where(ProcedureModel.slug == proc["slug"])
                    res = await session.execute(stmt)
                    existing = res.scalar_one_or_none()

                    if not existing:
                        db_proc = ProcedureModel(**proc)
                        session.add(db_proc)
                        saved_count += 1

                await session.commit()
                logger.info(f"Đã lưu thành công {saved_count} thủ tục hành chính vào PostgreSQL!")
        except Exception as e:
            logger.warning(f"Lưu thủ tục vào PostgreSQL chưa hoàn tất (Database chưa kết nối): {e}")

        return saved_count

    async def sync_to_vector_db(self, documents: List[Dict[str, Any]]) -> int:
        """Đồng bộ văn bản luật đã cào vào Qdrant Vector DB qua AdminService để RAG có thể truy xuất."""
        from backend.services.admin_service import AdminService
        admin_svc = AdminService()
        synced_chunks = 0

        for doc in documents:
            try:
                chunks = await admin_svc.sync_legal_documents(
                    content=doc["content_text"],
                    source=f"{doc.get('doc_number', '')} - {doc['title']}",
                    document_type=doc.get("doc_type", "Văn bản pháp luật"),
                )
                synced_chunks += chunks
                logger.info(f" -> Đã nhúng vector cho văn bản [{doc.get('doc_number', '')}]: {chunks} chunks")
            except Exception as e:
                logger.warning(f"Không thể nhúng vector cho văn bản {doc['title'][:50]}: {e}")

        return synced_chunks
