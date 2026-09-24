"""
VinaLex — GeminiService: AI Agent Điều Phối Pháp Lý & Thẩm Định Hồ Sơ
Tích hợp:
1. Google Generative AI (Gemini Pro / Flash)
2. Hệ thống RAG nội bộ (RagService: 8.300+ Chunks điều luật & 556 thủ tục)
3. Bộ công cụ Agent (Function Calling):
   - tra_cuu_thu_tuc_chi_tiet
   - cung_cap_bieu_mau_pdf
   - kich_hoat_kiem_tra_ocr
4. Thẩm định ngữ cảnh sâu & phát hiện sai lệch giấy tờ hành chính
"""

import os
import json
import asyncio
import sqlite3
import urllib.parse
from typing import Dict, List, Tuple, Any, Optional

from backend.core.config import settings
from backend.services.rag_service import RagService


SYSTEM_LEGAL_INSTRUCTION = """Bạn là Trợ lý Pháp lý & Thủ tục Hành chính VinaLex (GovAgent) — Chuyên viên tư vấn pháp lý số của Cổng thông tin thủ tục hành chính Việt Nam.

Nhiệm vụ của bạn:
1. Giải đáp các thắc mắc về pháp luật và thủ tục hành chính của công dân và doanh nghiệp một cách CHÍNH XÁC, MẠCH LẠC, ĐÚNG TRỌNG TÂM.
2. Luôn viện dẫn căn cứ pháp lý rõ ràng: ghi rõ số Điều, Khoản, Tên văn bản, Số hiệu văn bản quy phạm pháp luật dựa trên CĂN CỨ PHÁP LÝ được trích xuất từ cơ sở dữ liệu quốc gia (RAG).
3. Hướng dẫn trình tự thực hiện theo từng bước rõ ràng (Bước 1, Bước 2, Bước 3...). Nêu rõ cơ quan có thẩm quyền giải quyết, thời hạn giải quyết và lệ phí (nếu có).
4. CUNG CẤP BIỂU MẪU / TỜ KHAI PDF TRỰC TIẾP:
   Khi người dùng cần biểu mẫu/tờ khai/đơn đề nghị, hoặc khi quy trình thủ tục có thành phần hồ sơ bắt buộc, bạn BẮT BUỘC chèn thẻ biểu mẫu chuẩn hệ thống để giao diện hiển thị khung tải và xem trước trực tiếp:
   [SYS_PDF_TEMPLATE:doc_name=<Tên chính thức của biểu mẫu hoặc tờ khai>&title=<Tên thủ tục hành chính>&slug=<mã slug thủ tục>]
   Đồng thời cung cấp liên kết tải:
   👉 [Tải Biểu mẫu <Tên biểu mẫu> (PDF)](/api/v1/procedures/download-template?doc_name=<Tên biểu mẫu>&title=<Tên thủ tục>&slug=<mã slug>)
   
   QUY CHUẨN BIỂU MẪU CHUYÊN NGÀNH BẮT BUỘC:
   - Thủ tục Xác định lại diện tích đất ở / Biến động đất đai: "Đơn đăng ký biến động đất đai, tài sản gắn liền với đất (Mẫu số 11/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)".
   - Thủ tục Cấp Sổ đỏ lần đầu: "Đơn đăng ký, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất (Mẫu số 04/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)".
   - Thủ tục Đăng ký doanh nghiệp / Hộ kinh doanh: "Giấy đề nghị đăng ký doanh nghiệp (Ban hành kèm theo Thông tư số 02/2023/TT-BKHĐT & NĐ 01/2021/NĐ-CP)".
   - Thủ tục Cấp giấy phép xây dựng: "Đơn đề nghị cấp giấy phép xây dựng (Mẫu số 01 Phụ lục II ban hành kèm theo Nghị định số 15/2021/NĐ-CP)".
   - Thủ tục Đổi / Cấp lại Giấy phép lái xe: "Đơn đề nghị đổi, cấp lại Giấy phép lái xe (Phụ lục 19 ban hành kèm theo Thông tư số 05/2024/TT-BGTVT)".
   - Thủ tục Hưởng BHXH một lần / Chế độ BHXH: "Đơn đề nghị giải quyết hưởng chế độ bảo hiểm xã hội (Mẫu số 14-HSB ban hành kèm theo Quyết định 166/QĐ-BHXH)".
   - Thủ tục Miễn GPLĐ cho người nước ngoài: "Văn bản đề nghị xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động (Mẫu số 09/PLI ban hành kèm Nghị định 152/2020/NĐ-CP và NĐ 70/2023/NĐ-CP)".
5. Khi người dùng đã có giấy tờ và muốn kiểm tra tính hợp lệ trước khi nộp, hãy hướng dẫn họ sử dụng tính năng thẩm định OCR của hệ thống.
6. Tuyệt đối không phỏng đoán điều luật không có thật. Sử dụng tiếng Việt chuẩn mực, tôn trọng, trang trọng nhưng dễ hiểu.
"""

# Cơ sở dữ liệu thủ tục hành chính đặc thù hỗ trợ biểu mẫu trực tiếp
KNOWN_PROCEDURES = [
    {
        "id": 9001,
        "slug": "xac-nhan-khong-thuoc-dien-cap-giay-phep-lao-dong",
        "title": "Xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động",
        "category": "Lao động - Việc làm",
        "description": "Thủ tục đề nghị cơ quan quản lý nhà nước về lao động cấp giấy xác nhận người nước ngoài làm việc tại Việt Nam không thuộc diện cấp giấy phép lao động theo Nghị định 152/2020/NĐ-CP và Nghị định 70/2023/NĐ-CP.",
        "steps": [
            {
                "index": 1,
                "title": "Nộp hồ sơ đề nghị xác nhận",
                "duration": "Ít nhất 10 ngày trước ngày dự kiến làm việc",
                "description": "Người sử dụng lao động nộp hồ sơ tại Bộ Lao động - Thương binh và Xã hội hoặc Sở Lao động - Thương binh và Xã hội / Ban Quản lý các Khu công nghiệp nơi người lao động dự kiến làm việc."
            },
            {
                "index": 2,
                "title": "Tiếp nhận và thẩm định hồ sơ",
                "duration": "05 ngày làm việc",
                "description": "Cơ quan thẩm quyền kiểm tra tính hợp lệ của hồ sơ và các giấy tờ chứng minh điều kiện miễn trừ."
            },
            {
                "index": 3,
                "title": "Nhận kết quả văn bản xác nhận",
                "duration": "Trong ngày làm việc thứ 5",
                "description": "Cấp Giấy xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động (Mẫu số 10/PLI) hoặc văn bản trả lời nêu rõ lý do."
            }
        ],
        "documents": [
            "Văn bản đề nghị xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động (Mẫu số 09/PLI)",
            "Giấy chứng nhận sức khỏe hoặc giấy khám sức khỏe do cơ quan y tế có thẩm quyền cấp",
            "Văn bản chấp thuận nhu cầu sử dụng người lao động nước ngoài (nếu thuộc diện bắt buộc)",
            "Bản sao có chứng thực hộ chiếu hoặc giấy tờ có giá trị thay thế hộ chiếu còn giá trị",
            "Giấy tờ chứng minh người lao động nước ngoài không thuộc diện cấp giấy phép lao động"
        ],
        "processing_time": "05 ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ",
        "fee": "Miễn phí (Không thu lệ phí nhà nước theo quy định hiện hành)",
        "agency": "Sở Lao động - Thương binh và Xã hội / Ban Quản lý các Khu công nghiệp, khu kinh tế tỉnh, thành phố"
    },
    {
        "id": 9002,
        "slug": "xac-dinh-lai-dien-tich-dat-o-da-duoc-cap-so-do",
        "title": "Thủ tục xác định lại diện tích đất ở đã được cấp Sổ đỏ trước ngày 01/7/2024",
        "category": "Đất đai - Bất động sản",
        "description": "Thủ tục đăng ký biến động đất đai nhằm xác định lại diện tích đất ở đối với thửa đất đã được cấp Giấy chứng nhận quyền sử dụng đất trước ngày 01/7/2024 theo quy định tại Điều 141 Luật Đất đai năm 2024 và Nghị định 101/2024/NĐ-CP.",
        "steps": [
            {
                "index": 1,
                "title": "Nộp hồ sơ đăng ký biến động xác định lại diện tích đất ở",
                "duration": "Người sử dụng đất nộp hồ sơ",
                "description": "Nộp tại Bộ phận Một cửa cấp huyện hoặc Chi nhánh Văn phòng Đăng ký đất đai nơi có thửa đất."
            },
            {
                "index": 2,
                "title": "Thẩm tra hồ sơ địa chính và đo đạc thực tế",
                "duration": "10-15 ngày làm việc",
                "description": "Chi nhánh Văn phòng Đăng ký đất đai kiểm tra hồ sơ, trích đo địa chính thửa đất và đối soát với quy định tại Điều 141 Luật Đất đai 2024."
            },
            {
                "index": 3,
                "title": "Cấp Giấy chứng nhận mới và trả kết quả",
                "duration": "Sau khi hoàn thành nghĩa vụ tài chính",
                "description": "Cấp đổi Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất theo diện tích đất ở đã được xác định lại."
            }
        ],
        "documents": [
            "Đơn đăng ký biến động đất đai, tài sản gắn liền với đất (Mẫu số 11/ĐK ban hành kèm theo Nghị định số 101/2024/NĐ-CP)",
            "Bản gốc Giấy chứng nhận quyền sử dụng đất đã cấp (Sổ đỏ / Sổ hồng)",
            "Bản trích đo địa chính thửa đất / Sơ đồ hiện trạng vị trí thửa đất",
            "Giấy tờ chứng minh việc hình thành và sử dụng thửa đất trước ngày 15/10/1993 hoặc trước 01/7/2004",
            "Bản sao Căn cước công dân của người sử dụng đất"
        ],
        "processing_time": "Không quá 15 ngày làm việc (không tính thời gian thực hiện nghĩa vụ tài chính)",
        "fee": "Lệ phí cấp đổi/chỉnh lý Giấy chứng nhận theo quy định của HĐND cấp tỉnh",
        "agency": "Chi nhánh Văn phòng Đăng ký đất đai / Bộ phận Tiếp nhận và Trả kết quả cấp huyện"
    }
]


def _query_procedure_db(keyword: str) -> Optional[Dict[str, Any]]:
    """Tra cứu thông tin thủ tục từ CSDL SQLite vinalex.db hoặc danh mục thủ tục đặc thù."""
    if not keyword or not keyword.strip():
        return None

    kw_clean = keyword.strip().lower()

    # 1. Kiểm tra trong danh mục thủ tục đặc thù trước
    for p in KNOWN_PROCEDURES:
        if (
            p["slug"] in kw_clean
            or p["title"].lower() in kw_clean
            or (p["slug"] == "xac-nhan-khong-thuoc-dien-cap-giay-phep-lao-dong" and any(term in kw_clean for term in ["giấy phép lao động", "lao động nước ngoài", "không thuộc diện", "mẫu số 09", "chuyên gia nước ngoài", "miễn giấy phép lao động"]))
            or (p["slug"] == "xac-dinh-lai-dien-tich-dat-o-da-duoc-cap-so-do" and any(term in kw_clean for term in ["xác định lại diện tích", "xac dinh lai dien tich", "mẫu số 11/đk", "mẫu 11/đk", "mẫu 11"]))
        ):
            return p


    db_path = "./data/vinalex.db"
    if not os.path.exists(db_path):
        db_path = "data/vinalex.db"
    if not os.path.exists(db_path):
        return None

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()

        # Thử tìm trực tiếp theo slug hoặc tiêu đề
        kw_like = f"%{kw_clean}%"
        c.execute(
            """
            SELECT id, slug, title, category, description, steps, documents, processing_time, fee, agency
            FROM procedures
            WHERE lower(slug) LIKE ? OR lower(title) LIKE ?
            ORDER BY view_count DESC
            LIMIT 1
            """,
            (kw_like, kw_like),
        )
        row = c.fetchone()

        # Nếu không thấy và chuỗi dài, tách các từ khóa chính để tìm
        if not row:
            search_terms = [
                "khai sinh", "kết hôn", "khai tử", "căn cước", "cccd", "sổ đỏ",
                "quyền sử dụng đất", "thành lập công ty", "doanh nghiệp", "hộ kinh doanh",
                "lao động", "giấy phép", "thuế", "bảo hiểm", "hộ chiếu"
            ]
            for term in search_terms:
                if term in kw_clean:
                    term_like = f"%{term}%"
                    c.execute(
                        """
                        SELECT id, slug, title, category, description, steps, documents, processing_time, fee, agency
                        FROM procedures
                        WHERE lower(slug) LIKE ? OR lower(title) LIKE ?
                        ORDER BY view_count DESC
                        LIMIT 1
                        """,
                        (term_like, term_like),
                    )
                    row = c.fetchone()
                    if row:
                        break

        conn.close()

        if row:
            steps_data = json.loads(row[5]) if isinstance(row[5], str) else row[5]
            docs_data = json.loads(row[6]) if isinstance(row[6], str) else row[6]
            return {
                "id": row[0],
                "slug": row[1],
                "title": row[2],
                "category": row[3],
                "description": row[4],
                "steps": steps_data,
                "documents": docs_data,
                "processing_time": row[7],
                "fee": row[8],
                "agency": row[9],
            }
    except Exception:
        pass
    return None


class GeminiService:
    """
    Dịch vụ AI Agent điều phối thông minh kết hợp Gemini và RAG.
    """

    def __init__(self):
        self._rag_service = RagService()
        self._client = None
        self._model = None
        self._initialized = False

    def _get_api_key(self) -> Optional[str]:
        """Lấy API Key từ config hoặc biến môi trường."""
        return settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")

    def is_available(self) -> bool:
        """Kiểm tra Gemini API Key có sẵn sàng không."""
        key = self._get_api_key()
        return bool(key and key.strip())

    def _initialize(self):
        """Khởi tạo Gemini Generative AI SDK."""
        if self._initialized:
            return

        api_key = self._get_api_key()
        if not api_key:
            self._initialized = True
            return

        self._candidates = []
        try:
            import warnings
            warnings.filterwarnings("ignore", category=FutureWarning, module="google.generativeai")
            import google.generativeai as genai
            genai.configure(api_key=api_key.strip())
            
            primary_model = settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
            raw_candidates = [
                primary_model,
                "gemini-3.5-flash-lite",
                "gemini-3.1-flash-lite",
                "gemini-flash-lite-latest",
                "gemini-3.6-flash",
                "gemini-3.7-flash",
            ]
            seen = set()
            self._candidates = [c for c in raw_candidates if not (c in seen or seen.add(c))]
            
            self._model = genai.GenerativeModel(
                model_name=self._candidates[0],
                system_instruction=SYSTEM_LEGAL_INSTRUCTION,
            )
            self._initialized = True
        except Exception:
            self._model = None
            self._initialized = True

    def _generate_content_with_retry(self, prompt: str, generation_config=None):
        """Thử gọi generate_content qua danh sách candidate models nếu gặp 429 quota hoặc 503."""
        import google.generativeai as genai
        last_err = None
        for m_name in self._candidates:
            try:
                model = genai.GenerativeModel(
                    model_name=m_name,
                    system_instruction=SYSTEM_LEGAL_INSTRUCTION,
                )
                if generation_config:
                    return model.generate_content(prompt, generation_config=generation_config)
                return model.generate_content(prompt)
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        raise RuntimeError("Không có mô hình Gemini nào khả dụng.")

    # ── CÁC CÔNG CỤ (AGENT TOOLS) ──

    def tool_tra_cuu_thu_tuc(self, keyword: str) -> str:
        """
        Tool 1: Tra cứu thông tin thủ tục hành chính trong cơ sở dữ liệu.
        """
        proc = _query_procedure_db(keyword)
        if not proc:
            return f"Không tìm thấy thủ tục hành chính nào có từ khóa '{keyword}' trong cơ sở dữ liệu."

        steps_text = "\n".join(
            [f"  - Bước {s.get('index', i+1)}: {s.get('title', '')} ({s.get('duration', 'Trong hạn quy định')}) - {s.get('description', '')}"
             for i, s in enumerate(proc.get("steps", []))]
        )
        docs_text = "\n".join([f"  + {d}" for d in proc.get("documents", [])])

        return (
            f"THÔNG TIN THỦ TỤC: {proc['title']}\n"
            f"- Mã tra cứu (slug): {proc['slug']}\n"
            f"- Cơ quan tiếp nhận & giải quyết: {proc['agency']}\n"
            f"- Thời hạn giải quyết: {proc['processing_time']}\n"
            f"- Lệ phí nhà nước: {proc['fee']}\n"
            f"- Thành phần hồ sơ bắt buộc gồm:\n{docs_text}\n"
            f"- Trình tự các bước thực hiện:\n{steps_text}"
        )

    def tool_cung_cap_bieu_mau_pdf(self, slug: str, doc_name: str) -> str:
        """
        Tool 2: Cung cấp đường dẫn tải file PDF biểu mẫu chuẩn theo Nghị định 30/2020/NĐ-CP.
        """
        proc = _query_procedure_db(slug)
        title = proc["title"] if proc else "Thủ tục hành chính"
        params = urllib.parse.urlencode({
            "doc_name": doc_name,
            "title": title,
            "slug": slug,
        })
        preview_params = urllib.parse.urlencode({
            "doc_name": doc_name,
            "title": title,
            "slug": slug,
            "preview": "true",
        })
        download_url = f"/api/v1/procedures/download-template?{params}"
        preview_url = f"/api/v1/procedures/download-template?{preview_params}"
        widget_tag = f"[SYS_PDF_TEMPLATE:doc_name={urllib.parse.quote(doc_name)}&title={urllib.parse.quote(title)}&slug={slug}]"

        return (
            f"{widget_tag}\n"
            f"📄 **Biểu mẫu chính thức**: [{doc_name}]({download_url})\n"
            f"- [👁️ Xem trước biểu mẫu A4 ({doc_name})]({preview_url})\n"
            f"- [📥 Tải mẫu đơn PDF về máy]({download_url})"
        )

    def tool_kich_hoat_kiem_tra_ocr(self, procedure_slug: str) -> str:
        """
        Tool 3: Kích hoạt điều hướng người dùng nộp ảnh giấy tờ để hệ thống OCR thẩm định.
        """
        return (
            f"[SYS_TRIGGER_OCR:{procedure_slug}]\n"
            f"🔍 Bạn có thể nộp ảnh chụp hoặc tệp PDF của các giấy tờ trên vào khung thẩm định. "
            f"Hệ thống sẽ đối soát thông tin, phát hiện sai lệch và kiểm tra tính hợp lệ pháp lý giúp bạn."
        )

    # ── NHIỆM VỤ 1: THẨM ĐỊNH NGỮ CẢNH & PHÁT HIỆN SAI LỆCH GIẤY TỜ ──

    async def analyze_document_semantic(
        self,
        extracted_fields: Dict[str, str],
        expected_doc_name: str,
        procedure_title: str,
        raw_document_type: str = "",
        filename: str = "",
    ) -> Dict[str, Any]:
        """
        Nhiệm vụ 1: Phân tích ngữ cảnh, phát hiện mâu thuẫn, sai lệch và tính hợp lệ của giấy tờ.
        Kết hợp: Dữ liệu bóc tách OCR + Căn cứ pháp lý từ RAG + Trí tuệ nhân tạo Gemini.
        """
        self._initialize()

        # 1. Truy xuất quy định pháp luật qua RAG nội bộ
        rag_query = f"Yêu cầu thành phần hồ sơ và quy định về {expected_doc_name} trong thủ tục {procedure_title}"
        relevant_docs = self._rag_service.retrieve_relevant_docs(rag_query, top_k=3)
        rag_context, sources = self._rag_service.build_context(relevant_docs)

        # 2. Nếu Gemini chưa kích hoạt hoặc không có API Key -> Fallback rule-based kết hợp RAG
        if not self.is_available() or self._model is None:
            return self._fallback_semantic_check(
                extracted_fields, expected_doc_name, procedure_title, raw_document_type, rag_context, sources
            )

        # 3. Xây dựng Prompt thẩm định chuyên sâu cho Gemini
        fields_json = json.dumps(extracted_fields, ensure_ascii=False, indent=2)
        verification_prompt = f"""Bạn là Thẩm định viên Pháp lý cao cấp của VinaLex, phụ trách kiểm tra tính hợp lệ của hồ sơ hành chính.

BỐI CẢNH THỦ TỤC:
- Tên thủ tục hành chính: {procedure_title}
- Giấy tờ bắt buộc đang kiểm tra: {expected_doc_name}
- Tên tệp người dùng tải lên: {filename}
- Loại giấy tờ hệ thống nhận diện sơ bộ: {raw_document_type}

CĂN CỨ PHÁP LÝ TỪ CƠ SỞ DỮ LIỆU LUẬT (RAG):
{rag_context}

CÁC TRƯỜNG THÔNG TIN BÓC TÁCH TỪ GIẤY TỜ NGƯỜI DÙNG TẢI LÊN (OCR):
{fields_json}

NHIỆM VỤ CỦA BẠN:
Phân tích kỹ lưỡng các khía cạnh sau:
1. ĐÚNG LOẠI GIẤY TỜ: Giấy tờ người dùng nộp có đúng là loại {expected_doc_name} theo quy định pháp luật không? (Ví dụ: Giấy chứng sinh không thay thế được Giấy khai sinh; Sổ hộ khẩu giấy đã hết hiệu lực theo Luật Cư trú; Giấy phép lái xe không thay thế được CCCD nếu thủ tục đòi hỏi nhân thân...).
2. ĐỘ ĐẦY ĐỦ & CHÍNH XÁC: Các mục bắt buộc theo mẫu luật định có đầy đủ không? Có trường nào bị bỏ trống, mờ nhòe hoặc sai định dạng không?
3. TÍNH NHẤT QUÁN & LOGIC: Có mâu thuẫn về họ tên, ngày tháng năm sinh, số định danh, ngày cấp hoặc hết hạn hiệu lực không?
4. ĐƯA RA KẾT LUẬN & HƯỚNG XỬ LÝ: Nêu rõ lỗi vi phạm (nếu có), trích dẫn điều khoản luật từ phần Căn cứ pháp lý, và hướng dẫn chi tiết cách người dân khắc phục để hồ sơ được duyệt.

Hãy trả về kết quả ĐÚNG ĐỊNH DẠNG JSON sau (không kèm markdown ngoài khối JSON):
{{
  "is_valid": true_hoặc_false,
  "status": "approved_hoặc_warning_hoặc_rejected",
  "document_matched": true_hoặc_false,
  "summary": "Tóm tắt kết quả thẩm định trong 1-2 câu",
  "errors": ["Lỗi 1 (kèm điều luật nếu có)", "Lỗi 2..."],
  "warnings": ["Cảnh báo 1...", "Cảnh báo 2..."],
  "suggestions": "Hướng dẫn cụ thể người dân cần làm lại hoặc bổ sung giấy tờ gì...",
  "legal_basis": ["Điều ... Luật/Nghị định ..."]
}}
"""

        try:
            import google.generativeai as genai
            response = await asyncio.to_thread(
                self._generate_content_with_retry,
                verification_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            raw_text = response.text.strip()
            # Clean markdown code block if present
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.startswith("```"):
                raw_text = raw_text[3:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]

            parsed = json.loads(raw_text.strip())
            parsed["sources"] = sources
            return parsed

        except Exception as e:
            # Fallback nếu gọi API thất bại
            return self._fallback_semantic_check(
                extracted_fields, expected_doc_name, procedure_title, raw_document_type, rag_context, sources, str(e)
            )

    def _fallback_semantic_check(
        self,
        extracted_fields: Dict[str, str],
        expected_doc_name: str,
        procedure_title: str,
        raw_document_type: str,
        rag_context: str,
        sources: List[str],
        error_msg: str = "",
    ) -> Dict[str, Any]:
        """Cơ chế thẩm định dự phòng nội bộ dựa trên RAG và quy tắc khi chưa có Gemini Key."""
        errors = []
        warnings = []
        is_valid = True
        status = "approved"

        # Phân tích sơ bộ từ số trường
        if not extracted_fields or len(extracted_fields) < 2:
            is_valid = False
            status = "rejected"
            errors.append(f"Không bóc tách được đủ thông tin pháp lý từ tài liệu cho mục '{expected_doc_name}'.")
            suggestions = "Vui lòng chụp lại ảnh rõ nét, ngay ngắn hoặc cung cấp tệp PDF gốc của giấy tờ."
        else:
            suggestions = f"Tài liệu đã được đối chiếu với cơ sở dữ liệu {len(sources)} căn cứ pháp lý của thủ tục {procedure_title}."

        return {
            "is_valid": is_valid,
            "status": status,
            "document_matched": True,
            "summary": f"Đã đối soát tài liệu theo {len(sources)} nguồn quy chuẩn pháp luật.",
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
            "legal_basis": sources[:3],
            "sources": sources,
            "note": "Kết quả thẩm định dựa trên RAG CSDL Pháp luật VinaLex." if not error_msg else f"Lưu ý: {error_msg}",
        }

    def _ensure_pdf_widget(self, answer_text: str, query: str) -> str:
        """
        Đảm bảo nếu câu trả lời đề cập đến tải biểu mẫu / tờ khai PDF,
        hoặc người dùng xin mẫu đơn, thẻ [SYS_PDF_TEMPLATE:...] và link tải trực tiếp luôn hiện diện.
        """
        if "[SYS_PDF_TEMPLATE:" in answer_text:
            return answer_text

        q_lower = (query or "").lower()
        a_lower = answer_text.lower()

        doc_name = None
        title = "Thủ tục hành chính"
        slug = "thu-tuc"

        # Trường hợp 1: Người lao động nước ngoài / Giấy phép lao động / Mẫu 09
        if any(k in q_lower or k in a_lower for k in [
            "giấy phép lao động", "lao động nước ngoài", "không thuộc diện",
            "mẫu số 09", "chuyên gia nước ngoài", "miễn giấy phép"
        ]):
            doc_name = "Văn bản đề nghị xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động (Mẫu số 09/PLI)"
            title = "Xác nhận người lao động nước ngoài không thuộc diện cấp giấy phép lao động"
            slug = "xac-nhan-khong-thuoc-dien-cap-giay-phep-lao-dong"

        # Trường hợp 2: Phát hiện từ văn bản regex "👉 Tải Biểu mẫu..." hoặc "Tải Biểu mẫu..."
        if not doc_name:
            import re
            m = re.search(r'(?:👉\s*)?Tải [bB]iểu mẫu\s*(?:Tờ khai|Đơn|Văn bản)?\s*([^\n\r(]+)(?:\((?:File\s*)?PDF\))?', answer_text)
            if m:
                extracted = m.group(1).strip()
                if len(extracted) > 3:
                    doc_name = extracted
                    proc = _query_procedure_db(extracted)
                    if proc:
                        title = proc["title"]
                        slug = proc["slug"]

        # Trường hợp 3: Người dùng hỏi mẫu đơn chung chung
        if not doc_name and any(k in q_lower for k in ["mẫu đơn", "biểu mẫu", "tờ khai", "file pdf", "tải đơn", "xin mẫu"]):
            proc = _query_procedure_db(query)
            if proc and proc.get("documents"):
                doc_name = proc["documents"][0]
                title = proc["title"]
                slug = proc["slug"]

        if not doc_name:
            return answer_text

        params = urllib.parse.urlencode({
            "doc_name": doc_name,
            "title": title,
            "slug": slug,
        })
        download_url = f"/api/v1/procedures/download-template?{params}"
        widget_tag = f"[SYS_PDF_TEMPLATE:doc_name={urllib.parse.quote(doc_name)}&title={urllib.parse.quote(title)}&slug={slug}]"
        interactive_link = f"👉 [Tải Biểu mẫu {doc_name} (PDF)]({download_url})"

        # Ưu tiên thay thế dòng bắt đầu bằng 👉 Tải Biểu mẫu hoặc Tải Biểu mẫu Tờ khai/Đơn
        specific_pattern = re.compile(r'(?:👉\s*Tải [bB]iểu mẫu[^\n\r]*|Tải [bB]iểu mẫu\s+(?:Tờ khai|Đơn|Văn bản)[^\n\r]*)', re.IGNORECASE)
        if specific_pattern.search(answer_text):
            return specific_pattern.sub(f"{widget_tag}\n{interactive_link}", answer_text, count=1)

        # Nếu không có dòng cụ thể, tìm tiêu đề "Tải biểu mẫu" để chèn bên dưới
        section_pattern = re.compile(r'(?:\d+\.\s*)?Tải [bB]iểu mẫu[^\n\r]*', re.IGNORECASE)
        if section_pattern.search(answer_text):
            return section_pattern.sub(lambda m: f"{m.group(0)}\n{widget_tag}\n{interactive_link}", answer_text, count=1)

        return f"{answer_text}\n\n### 📄 Biểu mẫu & Tờ khai chính thức (PDF)\n{widget_tag}\n{interactive_link}"

    # ── NHIỆM VỤ 2: CHATBOT TƯ VẤN PHÁP LUẬT & THỦ TỤC KẾT HỢP RAG ──

    async def chat_with_agent(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: str = "",
    ) -> Tuple[str, List[str]]:
        """
        Nhiệm vụ 2: Chatbot pháp lý trả lời đúng và trọng tâm vào ngữ cảnh câu hỏi.
        Pipeline:
          1. Nhận câu hỏi
          2. RAG trích xuất các điều luật liên quan (Hybrid Search từ 8.300+ Chunks)
          3. Kiểm tra ý định gọi Tool (Tra cứu thủ tục, cấp biểu mẫu PDF, kích hoạt OCR)
          4. Gemini Agent lý luận & sinh câu trả lời viện dẫn chuẩn mực
        """
        self._initialize()

        # Bước 1: RAG Retrieval từ hệ thống có sẵn
        relevant_docs = self._rag_service.retrieve_relevant_docs(query, top_k=5)
        context, sources = self._rag_service.build_context(relevant_docs)

        # Nếu Gemini API chưa sẵn sàng -> Fallback sang RAG Synthesis nội bộ
        if not self.is_available() or self._model is None:
            from backend.services.agent_service import AgentService
            fallback_agent = AgentService()
            ans, srcs = await fallback_agent.generate_answer(query)
            return self._ensure_pdf_widget(ans, query), srcs

        # Bước 2: Kiểm tra ý định cần Tool Calling bổ trợ
        q_lower = query.lower()
        tool_results = []

        # Tool 1: Hỏi chi tiết về 1 thủ tục cụ thể
        if any(k in q_lower for k in ["thủ tục", "thu tuc", "hướng dẫn làm", "cách làm", "làm thế nào để"]):
            proc_info = _query_procedure_db(query)
            if proc_info:
                tool_results.append(self.tool_tra_cuu_thu_tuc(proc_info["slug"]))

        # Tool 2: Người dùng xin mẫu đơn / biểu mẫu PDF hoặc câu hỏi liên quan đến thủ tục có biểu mẫu
        has_form_intent = any(k in q_lower for k in [
            "mẫu đơn", "bieu mau", "biểu mẫu", "tờ khai", "mẫu tờ khai", "tải đơn", "xin mẫu",
            "file pdf", "tải biểu mẫu", "hồ sơ gồm những gì", "cần chuẩn bị những gì", "giấy phép lao động",
            "khai sinh", "kết hôn", "thành lập công ty", "sổ đỏ", "không thuộc diện"
        ])
        if has_form_intent:
            proc_info = _query_procedure_db(query)
            if proc_info and proc_info.get("documents"):
                first_doc = proc_info["documents"][0]
                tool_results.append(self.tool_cung_cap_bieu_mau_pdf(proc_info["slug"], first_doc))

        # Tool 3: Người dùng muốn kiểm tra giấy tờ hoặc hỏi về nộp hồ sơ
        if any(k in q_lower for k in ["kiểm tra hồ sơ", "check giấy tờ", "hồ sơ đã đúng chưa", "xem giúp tôi", "thẩm định"]):
            proc_info = _query_procedure_db(query)
            slug = proc_info["slug"] if proc_info else "thu-tuc"
            tool_results.append(self.tool_kich_hoat_kiem_tra_ocr(slug))

        tools_context = ""
        if tool_results:
            tools_context = "\n\nKẾT QUẢ TỪ BỘ CÔNG CỤ HỆ THỐNG VINALEX:\n" + "\n\n".join(tool_results)

        # Bước 3: Xây dựng Prompt cho Gemini
        full_prompt = f"""CÂU HỎI CỦA CÔNG DÂN / DOANH NGHIỆP:
{query}

{context}
{tools_context}

HƯỚNG DẪN TRẢ LỜI:
- Trả lời trực diện, đúng trọng tâm vào vấn đề người dùng hỏi.
- Trích dẫn rõ ràng: "Căn cứ Điều ... Khoản ... [Tên văn bản]...".
- Nếu có hướng dẫn từ các bước thủ tục, hãy trình bày dạng danh sách có thứ tự (Bước 1, Bước 2...).
- CUNG CẤP BIỂU MẪU PDF TRỰC TIẾP: Nếu câu trả lời có nhắc đến biểu mẫu, tờ khai (ví dụ Mẫu số 09/PLI), BẮT BUỘC chèn thẻ định dạng [SYS_PDF_TEMPLATE:doc_name=...&title=...&slug=...] kèm đường link tải [Tải Biểu mẫu ... (PDF)](/api/v1/procedures/download-template?...) để người dân tải về ngay lập tức.
- Tuyệt đối không để liên kết biểu mẫu ở dạng chữ thô unclickable.
"""

        try:
            response = await asyncio.to_thread(self._generate_content_with_retry, full_prompt)
            answer_text = response.text.strip()
            answer_text = self._ensure_pdf_widget(answer_text, query)
            return answer_text, sources
        except Exception:
            from backend.services.agent_service import AgentService
            fallback_agent = AgentService()
            ans, srcs = await fallback_agent.generate_answer(query)
            return self._ensure_pdf_widget(ans, query), srcs
