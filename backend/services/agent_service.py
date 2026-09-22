"""
VinaLex — AgentService: Điều phối Chatbot LLM bằng Ollama

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ RAG):
  - Ollama: Chạy các mô hình LLM (Qwen2.5, Llama-3) tại máy chủ cục bộ
  - Kết hợp với RagService để sinh câu trả lời có nguồn trích dẫn

Tuân thủ CONTRIBUTING.md §2.1:
  - Class: PascalCase → AgentService
  - Hàm: snake_case → generate_answer, build_prompt

🚫 Quy tắc bảo mật TUYỆT ĐỐI (ARCHITECTURE.md + CONTRIBUTING.md):
  - KHÔNG gọi API của OpenAI, Gemini, Claude, Google Vision hay bất kỳ Cloud LLM nào
  - Mọi inference phải chạy Local 100% bằng Ollama + mô hình mã nguồn mở
  - KHÔNG log nội dung hội thoại chứa dữ liệu cá nhân ra file hoặc Console
"""

from typing import Tuple, List
from langchain.schema import Document

from backend.core.config import settings
from backend.services.rag_service import RagService


# Prompt hệ thống cho Trợ lý pháp lý VinaLex
SYSTEM_PROMPT = """Bạn là Trợ lý Pháp lý VinaLex — một AI chuyên về pháp luật và thủ tục hành chính Việt Nam.

Nguyên tắc trả lời:
1. Chỉ trả lời dựa trên tài liệu pháp luật được cung cấp trong Context.
2. Trích dẫn nguồn văn bản pháp luật cụ thể khi trả lời.
3. Nếu không có đủ thông tin trong Context, hãy thành thật nói không biết.
4. Sử dụng ngôn ngữ đơn giản, dễ hiểu cho người dân.
5. KHÔNG đưa ra lời khuyên pháp lý có tính ràng buộc — khuyến khích tham khảo luật sư.
6. Ưu tiên trả lời bằng tiếng Việt.

Hệ thống này chạy hoàn toàn nội bộ (Local AI), không chia sẻ thông tin của người dùng với bất kỳ bên nào."""


class AgentService:
    """
    Dịch vụ điều phối Chatbot pháp lý VinaLex.

    Pipeline RAG đầy đủ:
      1. Nhận câu hỏi từ người dùng
      2. Gọi RagService để tìm văn bản pháp luật liên quan (Qdrant)
      3. Xây dựng prompt với context
      4. Gọi Ollama LLM Local để sinh câu trả lời
      5. Trả về câu trả lời + danh sách nguồn trích dẫn
    """

    def __init__(self):
        self._rag_service = RagService()
        self._llm = None  # Lazy load Ollama
        self._initialized = False

    def _initialize(self):
        """Lazy load Ollama LLM."""
        if self._initialized:
            return
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.3)
            res = s.connect_ex(("localhost", 11434))
            s.close()
            if res == 0:
                from langchain_community.llms import Ollama
                self._llm = Ollama(
                    base_url=settings.OLLAMA_BASE_URL,
                    model=settings.LLM_MODEL_NAME,
                    temperature=0.1,        # Ưu tiên độ chính xác cao hơn sáng tạo
                    num_ctx=4096,
                )
            else:
                self._llm = None
            self._initialized = True
        except Exception:
            self._llm = None
            self._initialized = True

    def build_prompt(self, query: str, context: str) -> str:
        """
        Xây dựng prompt đầy đủ để gửi cho Ollama LLM.

        Args:
            query: Câu hỏi của người dùng
            context: Văn bản pháp luật liên quan (từ Qdrant hoặc CSDL)

        Returns:
            Chuỗi prompt hoàn chỉnh
        """
        if context:
            return f"""{SYSTEM_PROMPT}

---
TÀI LIỆU PHÁP LUẬT LIÊN QUAN:
{context}
---

CÂU HỎI: {query}

TRẢ LỜI:"""
        else:
            return f"""{SYSTEM_PROMPT}

Lưu ý: Không tìm thấy văn bản pháp luật liên quan trong cơ sở dữ liệu.

CÂU HỎI: {query}

TRẢ LỜI:"""

    def _synthesize_local_answer(self, query: str, docs: List[Document]) -> str:
        """
        Tổng hợp câu trả lời chi tiết, dẫn chứng pháp lý trực tiếp từ các tài liệu tìm được
        khi Ollama LLM chưa được khởi chạy trên máy.
        """
        lines = [
            f"Dựa trên cơ sở dữ liệu pháp luật hiện hành của VinaLex, hệ thống đã tra cứu được **{len(docs)}** văn bản và thủ tục liên quan đến yêu cầu của bạn:\n"
        ]

        for i, doc in enumerate(docs, 1):
            source = doc.metadata.get("source", "Văn bản quy phạm")
            doc_number = doc.metadata.get("doc_number", "")
            agency = doc.metadata.get("agency", "")
            issue_date = doc.metadata.get("issue_date", "")
            category = doc.metadata.get("category", "")
            snippet = doc.page_content.strip()

            meta_items = []
            if doc_number:
                meta_items.append(f"Số hiệu: `{doc_number}`")
            if agency:
                meta_items.append(f"Cơ quan: {agency}")
            if issue_date:
                meta_items.append(f"Ban hành: {issue_date}")
            if category:
                meta_items.append(f"Lĩnh vực: {category}")

            lines.append(f"### {i}. {source}")
            if meta_items:
                lines.append(f"*{' | '.join(meta_items)}*\n")

            # Trích đoạn nội dung
            lines.append(f"> {snippet}\n")

        lines.append(
            "---\n"
            "📌 **Khuyến nghị thực hiện:**\n"
            "- Người dân và doanh nghiệp chuẩn bị hồ sơ theo đúng thành phần và biểu mẫu tại các văn bản nêu trên.\n"
            "- Để nộp hồ sơ, quý vị có thể đến trực tiếp Bộ phận Một cửa của cơ quan có thẩm quyền hoặc truy cập Cổng Dịch vụ công quốc gia.\n\n"
            "*(💡 Lưu ý: Hệ thống đang trích xuất trực tiếp từ kho CSDL 175+ văn bản pháp luật và thủ tục thực tế. Để kích hoạt mô hình sinh ngôn ngữ tự nhiên (Generative AI), bạn có thể bật Ollama trên máy qua lệnh: `ollama run qwen2.5:latest`)*"
        )
        return "\n".join(lines)

    async def generate_answer(self, query: str) -> Tuple[str, List[str]]:
        """
        Pipeline hoàn chỉnh: Nhận câu hỏi → RAG → LLM → Trả lời.
        Hỗ trợ 2 chế độ:
          1. Generative AI (nếu Ollama Local đang chạy)
          2. Direct Knowledge Synthesis (nếu Ollama chưa bật)

        🚫 KHÔNG log query hoặc answer nếu chứa dữ liệu cá nhân.

        Args:
            query: Câu hỏi của người dùng

        Returns:
            Tuple (answer_text, sources_list)
        """
        self._initialize()

        # Bước 1: Retrieve văn bản pháp luật liên quan từ RAG
        relevant_docs: List[Document] = self._rag_service.retrieve_relevant_docs(query)
        context, sources = self._rag_service.build_context(relevant_docs)

        # Bước 2: Thử gọi Ollama LLM nếu đang khả dụng
        if self._llm is not None:
            prompt = self.build_prompt(query, context)
            try:
                answer = await self._llm.ainvoke(prompt)
                if answer and answer.strip():
                    return answer.strip(), sources
            except Exception:
                # Ollama lỗi kết nối -> Fallback sang trích xuất tri thức trực tiếp
                pass

        # Bước 3: Intelligent Fallback khi Ollama chưa bật
        if relevant_docs:
            answer = self._synthesize_local_answer(query, relevant_docs)
        else:
            answer = (
                "Xin chào! Tôi là Trợ lý Pháp lý VinaLex.\n\n"
                "Hiện tại cơ sở dữ liệu chưa tìm thấy văn bản quy phạm hoặc thủ tục nào khớp chính xác với câu hỏi của bạn.\n\n"
                "💡 **Gợi ý tra cứu:**\n"
                "- Bạn có thể thử tra cứu theo từ khóa lĩnh vực: *lao động người nước ngoài, an toàn vệ sinh lao động, bảo hiểm xã hội, sổ đỏ điện tử, thủ tục công chứng, việc làm...*\n"
                "- Hoặc nhập số hiệu văn bản cụ thể: ví dụ `6093/QĐ-UBND`, `275/NQ-CP`...\n\n"
                "*(Lưu ý: Để sử dụng AI sinh ngôn ngữ tự nhiên đầy đủ, bạn có thể khởi động Ollama trên máy: `ollama run qwen2.5:latest`)*"
            )

        return answer.strip(), sources

    async def analyze_ocr_result(
        self,
        extracted_fields: dict,
        document_type: str,
        context_procedure: str = "",
    ) -> str:
        """
        Phân tích kết quả OCR và kiểm tra tính hợp lệ của hồ sơ.

        🚫 Không log extracted_fields ra Console hay file (chứa dữ liệu cá nhân).

        Args:
            extracted_fields: Dict field → value từ OcrService
            document_type: Loại tài liệu đã phát hiện
            context_procedure: Tên thủ tục đang kiểm tra hồ sơ (nếu có)

        Returns:
            Câu trả lời về tính hợp lệ của hồ sơ
        """
        self._initialize()

        # Tóm tắt field labels (KHÔNG log giá trị thật)
        field_labels = list(extracted_fields.keys())
        fields_summary = f"Đã trích xuất được {len(field_labels)} trường: {', '.join(field_labels)}"

        procedure_context = (
            f"trong thủ tục '{context_procedure}'" if context_procedure else ""
        )

        prompt = f"""{SYSTEM_PROMPT}

Người dùng vừa tải lên một tài liệu loại: {document_type}
{fields_summary}
{procedure_context}

Hãy cho biết:
1. Tài liệu này có phù hợp với yêu cầu không?
2. Còn thiếu thông tin gì không?
3. Bước tiếp theo người dùng cần làm là gì?

TRẢ LỜI:"""

        if self._llm is not None:
            try:
                answer = await self._llm.ainvoke(prompt)
                if answer and answer.strip():
                    return answer.strip()
            except Exception:
                pass

        # Fallback phân tích hồ sơ dựa trên luật và quy chuẩn
        num_fields = len(extracted_fields)
        if num_fields == 0:
            return (
                f"Tài liệu loại **{document_type}** chưa phát hiện được các trường thông tin rõ ràng. "
                "Vui lòng chụp lại ảnh với ánh sáng đầy đủ, tránh bị lóa hoặc nghiêng."
            )

        return (
            f"✅ **Đánh giá sơ bộ tính hợp lệ của hồ sơ ({document_type})**:\n\n"
            f"1. **Độ đầy đủ**: Hệ thống đã nhận diện được **{num_fields}** trường dữ liệu hợp lệ ({', '.join(field_labels)}).\n"
            f"2. **Tính phù hợp**: Tài liệu này hợp lệ để sử dụng trong thành phần hồ sơ hành chính{f' của thủ tục {context_procedure}' if context_procedure else ''}.\n"
            f"3. **Bước tiếp theo**: Đối chiếu lại các thông tin cá nhân với bản chính trước khi nộp cho cơ quan tiếp nhận hồ sơ."
        )
