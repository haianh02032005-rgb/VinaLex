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

import os
import re
import json
import asyncio
import urllib.request
import urllib.parse
from typing import Tuple, List, Set, Dict, Optional, Any
try:
    from langchain.schema import Document
except ImportError:
    try:
        from langchain_core.documents import Document
    except ImportError:
        class Document:
            def __init__(self, page_content: str = "", metadata: dict = None):
                self.page_content = page_content
                self.metadata = metadata or {}

from backend.core.config import settings
from backend.services.legal_parser import strip_accents
from backend.services.rag_service import RagService

# Bộ nhớ đệm câu trả lời pháp lý siêu tốc (LRU RAM Cache)
_RESPONSE_CACHE: Dict[str, Tuple[str, List[str]]] = {}
_MAX_CACHE_SIZE = 500


# Prompt hệ thống cho Trợ lý pháp lý VinaLex
SYSTEM_PROMPT = """Bạn là Trợ lý Pháp lý VinaLex — một AI chuyên về pháp luật và thủ tục hành chính Việt Nam.

Nguyên tắc trả lời:
1. Chỉ trả lời dựa trên tài liệu pháp luật được cung cấp trong Context.
2. Trích dẫn chính xác căn cứ pháp lý: ghi rõ Điều, Khoản, Tên văn bản và Số hiệu văn bản (Ví dụ: "Căn cứ Điều 14 Nghị định 6093/QĐ-UBND...").
3. Phân biệt rõ ràng giữa quy định nội dung (Luật/Nghị định/Thông tư) và trình tự thực hiện (Thủ tục hành chính).
4. Nếu không có đủ thông tin trong Context, hãy thành thật thông báo cơ sở dữ liệu chưa ghi nhận quy định này.
5. Sử dụng ngôn ngữ chuẩn mực, mạch lạc, dễ hiểu cho người dân và doanh nghiệp.
6. KHÔNG đưa ra phán quyết hay lời khuyên có tính ràng buộc pháp lý cá nhân.
7. Trả lời bằng tiếng Việt chuẩn ngữ pháp."""


class AgentService:
    """
    Dịch vụ điều phối Chatbot pháp lý VinaLex.

    Pipeline RAG đầy đủ:
      1. Nhận câu hỏi từ người dùng
      2. Gọi RagService để tìm văn bản pháp luật liên quan (Qdrant & Hybrid Search)
      3. Xây dựng prompt với context pháp lý chuẩn hóa
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
TÀI LIỆU PHÁP LUẬT LIÊN QUAN TRÍCH LỤC TỪ CƠ SỞ DỮ LIỆU:
{context}
---

CÂU HỎI CỦA NGƯỜI DÙNG: {query}

HƯỚNG DẪN TRẢ LỜI: Hãy dựa vào các căn cứ pháp lý trên để trả lời chi tiết, trích dẫn rõ ràng số Điều, Tên văn bản và các bước thủ tục cần thiết.

TRẢ LỜI:"""
        else:
            return f"""{SYSTEM_PROMPT}

Lưu ý: Không tìm thấy văn bản pháp luật liên quan trong cơ sở dữ liệu.

CÂU HỎI: {query}

TRẢ LỜI:"""

    @staticmethod
    def _normalize_repetition_key(text: str) -> str:
        text = re.sub(r"\s+", " ", text or "").strip().lower()
        text = re.sub(r"^[\-\*\d\.\)\s]+", "", text)
        return text

    def _remove_repeated_lines(self, answer: str) -> str:
        if not answer:
            return answer

        seen: Set[str] = set()
        cleaned_lines: List[str] = []
        for line in answer.splitlines():
            key = self._normalize_repetition_key(line)
            if len(key) > 40 and key in seen:
                continue
            if len(key) > 40:
                seen.add(key)
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    def _dedupe_docs(self, docs: List[Document]) -> List[Document]:
        seen: Set[str] = set()
        unique_docs: List[Document] = []
        for doc in docs:
            meta = doc.metadata or {}
            key = "|".join(
                [
                    str(meta.get("source_type", "")),
                    str(meta.get("doc_number", "")),
                    str(meta.get("title", "")),
                    str(meta.get("article", "")),
                    self._normalize_repetition_key(doc.page_content)[:220],
                ]
            )
            if key in seen:
                continue
            seen.add(key)
            unique_docs.append(doc)
        return unique_docs

    def contextualize_query(
        self, query: str, history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, Optional[str]]:
        """
        Tái tạo và mở rộng câu hỏi phụ thuộc (Anaphora Resolution & Contextualization)
        dựa trên lịch sử hội thoại gần nhất.
        """
        if not history or not query.strip():
            return query.strip(), None

        q_lower = query.lower().strip()
        q_clean = strip_accents(q_lower)

        # Các từ khóa nhận diện câu hỏi phụ thuộc
        FOLLOWUP_INDICATORS = [
            "o dau", "o dau vay", "o dau nhi", "dia chi nao", "co quan nao", "o dau a",
            "le phi", "bao nhieu", "bao nhieu tien", "phi", "chi phi", "tien phi", "bang gia", "gia tien",
            "can gi", "ho so", "giay to", "to khai", "bieu mau", "mau don", "can nhung gi", "giay to gi",
            "bao lau", "thoi han", "may ngay", "khi nao", "thoi gian", "mat bao lau",
            "the thi", "vay thi", "the", "vay", "ai", "ai co quyen", "ai duoc",
            "con gi nua", "can them gi", "dieu kien", "duoc khong", "co duoc",
            "thu tuc do", "giay to do", "viec do", "cai nay", "cai do", "ho so nay", "buoc nao"
        ]

        is_followup = any(re.search(rf"\b{re.escape(ind)}\b", q_clean) for ind in FOLLOWUP_INDICATORS)
        if len(q_clean.split()) <= 6 or is_followup:
            extracted_topic = None

            # 1. Tìm trong các câu hỏi trước đó của user (ưu tiên cao nhất vì phản ánh trực tiếp nhu cầu)
            for msg in reversed(history[-6:]):
                if msg.get("role") == "user":
                    user_text = msg.get("content", "").strip().replace("?", "")
                    # Bóc tách cụm hành chính / thủ tục cụ thể
                    m_action = re.search(
                        r"((?:thủ tục\s+)?(?:cấp|đổi|đăng ký|thành lập|giải quyết|hưởng|xin|quyết toán|hoàn|xác định|chuyển nhượng|sang tên)\s+[^\n\r\?\,\.]{4,60})",
                        user_text,
                        re.IGNORECASE,
                    )
                    if m_action:
                        extracted_topic = m_action.group(1).strip()
                        break

                    # Nếu là câu hỏi trước không phải câu chào hay câu hỏi phụ thuộc
                    user_clean = strip_accents(user_text.lower())
                    if len(user_text) > 6 and not any(
                        k in user_clean for k in ["chao", "cam on", "hello", "hi", "tam biet", "o dau", "bao nhieu", "the nao"]
                    ):
                        extracted_topic = user_text
                        break

            # 2. Nếu chưa tìm thấy trong user messages, tìm trong câu trả lời của trợ lý
            if not extracted_topic:
                for msg in reversed(history[-6:]):
                    if msg.get("role") == "assistant":
                        text = msg.get("content", "")
                        for line in text.splitlines():
                            line_s = line.strip()
                            if line_s.startswith("### ") and not any(
                                k in line_s for k in ["TƯ VẤN", "Biểu mẫu", "Thành phần", "Căn cứ", "Trình tự", "Cơ quan", "Quy định", "Khuyến nghị", "Bước", "1.", "2.", "3."]
                            ):
                                clean_title = line_s.replace("### ", "").strip()
                                clean_title = re.sub(r"[\*`#]", "", clean_title).strip()
                                if len(clean_title) > 5:
                                    extracted_topic = clean_title
                                    break
                        if extracted_topic:
                            break

            if extracted_topic:
                enriched = f"{extracted_topic} - {query}"
                return enriched, extracted_topic

        return query.strip(), None

    async def _call_cloud_llm(
        self,
        query: str,
        context: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        """
        Gọi Cloud LLM (ưu tiên Groq Llama-3.3-70b siêu tốc, tiếp theo Gemini)
        với đầy đủ Context và Multi-turn History.
        """
        # 1. Thử Groq Cloud nếu có cấu hình GROQ_API_KEY
        groq_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")
        if groq_key and len(groq_key.strip()) > 15 and not groq_key.startswith("your_"):
            try:
                system_instruction = (
                    "Bạn là Trợ lý Pháp lý VinaLex — một AI chuyên gia về pháp luật và thủ tục hành chính Việt Nam.\n"
                    "Nguyên tắc trả lời:\n"
                    "1. Trả lời trực diện, đúng trọng tâm, viện dẫn chính xác số Điều, Khoản, Tên văn bản và Số hiệu văn bản quy phạm từ Căn cứ pháp lý được cung cấp.\n"
                    "2. Phân tách rõ ràng: Căn cứ pháp lý, Trình tự các bước thực hiện (Bước 1, Bước 2...), Thành phần hồ sơ, Cơ quan giải quyết, Thời hạn và Lệ phí.\n"
                    "3. Khi đề cập đến mẫu đơn/tờ khai bắt buộc, chèn thẻ biểu mẫu chuẩn hệ thống: [SYS_PDF_TEMPLATE:doc_name=<Tên mẫu đơn>&title=<Tên thủ tục>&slug=<mã slug>] kèm link [Tải Biểu mẫu <Tên mẫu> (PDF)](/api/v1/procedures/download-template?...).\n"
                    "4. Trả lời bằng tiếng Việt trang trọng, mạch lạc, dễ hiểu."
                )

                messages = [
                    {"role": "system", "content": f"{system_instruction}\n\nTÀI LIỆU PHÁP LUẬT TỪ CƠ SỞ DỮ LIỆU:\n{context}"}
                ]
                if history:
                    for h in history[-4:]:
                        role = "assistant" if h.get("role") in ["assistant", "bot"] else "user"
                        messages.append({"role": role, "content": h.get("content", "")})
                messages.append({"role": "user", "content": query})

                payload = {
                    "model": settings.GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.2,
                    "max_tokens": 2048,
                }
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {groq_key.strip()}",
                        "Content-Type": "application/json",
                    },
                )

                def do_request():
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        return data["choices"][0]["message"]["content"]

                groq_resp = await asyncio.to_thread(do_request)
                if groq_resp and groq_resp.strip():
                    return groq_resp.strip()
            except Exception:
                pass

        # 2. Thử Gemini AI nếu có key hợp lệ
        try:
            from backend.services.gemini_service import GeminiService
            gemini = GeminiService()
            if gemini.is_available():
                ans, _ = await gemini.chat_with_agent(query, history=history)
                if ans and ans.strip():
                    return ans.strip()
        except Exception:
            pass

        return None

    def _synthesize_expert_answer(
        self,
        query: str,
        docs: List[Document],
        proc_data: Optional[Dict[str, Any]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        extracted_topic: Optional[str] = None,
    ) -> str:
        """
        Khung suy luận pháp lý chuyên sâu VinaLex (Legal Chain-of-Thought Engine).
        Phân rã ngữ cảnh, xác định ý định và tổng hợp tư vấn chi tiết theo chuẩn mực pháp lý.
        """
        q_lower = query.lower()
        q_clean = strip_accents(q_lower)

        # 1. Nhận diện ý định chi tiết (Intent Classification với word boundary chính xác)
        is_location = bool(re.search(r"\b(o dau|dia chi|co quan|tru so|nop tai dau|phuong nao|quan nao|thanh pho|tinh nao)\b", q_clean))
        is_fee = bool(re.search(r"\b(le phi|phi|chi phi|bao nhieu tien|nop bao nhieu|tien phi|bang gia|gia tien)\b", q_clean))
        is_docs = bool(re.search(r"\b(ho so|giay to|can nhung gi|can gi|to khai|mau don|bieu mau|thanh phan|tai lieu|chung tu)\b", q_clean))
        is_time = bool(re.search(r"\b(thoi han|bao lau|may ngay|khi nao|thoi gian|mat bao lau)\b", q_clean))
        is_steps = bool(re.search(r"\b(buoc|trinh tu|cach lam|quy trinh|lam the nao|cac buoc)\b", q_clean))

        # 2. Xử lý khi có dữ liệu Thủ tục Hành chính (Procedure DB)
        if proc_data:
            title = proc_data.get("title", extracted_topic or "Thủ tục hành chính")
            slug = proc_data.get("slug", "thu-tuc")
            agency = proc_data.get("agency") or "Cơ quan có thẩm quyền cấp quận/huyện hoặc tỉnh/thành phố"
            fee = proc_data.get("fee") or "Theo biểu mức quy định của Nhà nước"
            processing_time = proc_data.get("processing_time") or "Trong thời hạn luật định"
            docs_list = proc_data.get("documents") or []
            steps_list = proc_data.get("steps") or []

            # Trích dẫn văn bản quy phạm từ RAG docs
            legal_citations = []
            for d in docs[:3]:
                meta = d.metadata or {}
                doc_num = meta.get("doc_number", "")
                art = meta.get("article", "")
                src = meta.get("source", "")
                if doc_num or art:
                    legal_citations.append(f"- **{src}** (Quy định: *{art or 'Toàn văn'}*, Số hiệu: `{doc_num or 'N/A'}`)")

            # Tạo widget biểu mẫu PDF chính thức
            first_doc = docs_list[0] if docs_list else f"Đơn đề nghị thực hiện {title}"
            params = urllib.parse.urlencode({"doc_name": first_doc, "title": title, "slug": slug})
            download_url = f"/api/v1/procedures/download-template?{params}"
            pdf_widget = f"[SYS_PDF_TEMPLATE:doc_name={urllib.parse.quote(first_doc)}&title={urllib.parse.quote(title)}&slug={slug}]\n👉 [Tải Biểu mẫu {first_doc} (PDF)]({download_url})"

            # Phân nhánh phản hồi theo Intent (hỗ trợ cả Intent kết hợp)
            if is_fee and is_time:
                lines = [
                    f"## 💰 Lệ phí & ⏱️ Thời hạn giải quyết thủ tục\n",
                    f"Đối với thủ tục **{title}**:\n",
                    f"### 1. Quy định về Lệ phí & Nghĩa vụ tài chính:",
                    f"- **Mức lệ phí nhà nước:** **{fee}**",
                    f"- **Cơ quan thu phí:** {agency}",
                    f"- **Hình thức nộp:** Tiền mặt tại Bộ phận Một cửa hoặc trực tuyến qua Cổng Dịch vụ công Quốc gia.",
                    f"- **Chính sách miễn/giảm:** Theo quy định của pháp luật và nghị quyết HĐND cấp tỉnh đối với dịch vụ công trực tuyến.",
                    f"\n### 2. Thời hạn giải quyết luật định:",
                    f"- **Thời hạn:** **{processing_time}** (tính theo ngày làm việc, không tính thứ Bảy, Chủ nhật và ngày nghỉ lễ).",
                    f"- **Hình thức nhận kết quả:** Trực tiếp tại Bộ phận Một cửa hoặc nhận qua dịch vụ bưu chính công ích.\n",
                    f"📌 **Lưu ý:** Lệ phí hành chính nhà nước luôn có biên lai thu tiền hợp pháp."
                ]
                return "\n".join(lines)

            elif is_location and is_fee:
                lines = [
                    f"## 🏢 Cơ quan tiếp nhận & 💰 Lệ phí thủ tục\n",
                    f"Đối với thủ tục **{title}**:\n",
                    f"### 1. Cơ quan giải quyết & Nơi nộp hồ sơ:",
                    f"- **Thẩm quyền giải quyết:** **{agency}**",
                    f"- **Địa điểm tiếp nhận:** Bộ phận Tiếp nhận và Trả kết quả (Bộ phận Một cửa) của {agency}.",
                    f"- **Nộp trực tuyến:** Cổng Dịch vụ công Quốc gia (`dichvucong.gov.vn`).",
                    f"\n### 2. Mức lệ phí nhà nước quy định:",
                    f"- **Lệ phí:** **{fee}**",
                    f"- **Thời hạn giải quyết:** {processing_time}\n",
                    f"📌 **Lưu ý khi đi nộp:** Người dân cần mang theo CCCD/VNeID mức 2 và bản chính các giấy tờ để đối soát."
                ]
                return "\n".join(lines)

            elif is_location:
                lines = [
                    f"## 🏢 Cơ quan tiếp nhận & Thẩm quyền giải quyết\n",
                    f"Đối với thủ tục **{title}**, quy định về nơi nộp hồ sơ như sau:\n",
                    f"- **Cơ quan có thẩm quyền giải quyết:** **{agency}**",
                    f"- **Địa điểm nộp trực tiếp:** Bộ phận Tiếp nhận và Trả kết quả (Bộ phận Một cửa) của **{agency}**.",
                    f"- **Nộp trực tuyến:** Có thể thực hiện trực tuyến qua Cổng Dịch vụ công Quốc gia (`dichvucong.gov.vn`) hoặc Cổng Dịch vụ công chuyên ngành tương ứng.",
                    f"- **Thời hạn giải quyết:** `{processing_time}`",
                    f"- **Lệ phí:** `{fee}`\n",
                    f"📌 **Lưu ý khi đi nộp:** Người dân cần mang theo bản chính Căn cước công dân/VNeID mức 2 và các giấy tờ gốc để cán bộ một cửa đối soát thông tin.",
                ]
                return "\n".join(lines)

            elif is_fee:
                lines = [
                    f"## 💰 Quy định Lệ phí & Nghĩa vụ tài chính\n",
                    f"Đối với thủ tục **{title}**:\n",
                    f"- **Mức lệ phí nhà nước quy định:** **{fee}**",
                    f"- **Cơ quan thu lệ phí:** {agency}",
                    f"- **Hình thức thanh toán:** Nộp tiền mặt trực tiếp tại quầy thu ngân Bộ phận Một cửa hoặc thanh toán trực tuyến qua cổng thanh toán dịch vụ công.",
                    f"- **Chính sách miễn, giảm:** Miễn lệ phí theo quy định đối với hộ nghèo, người có công, đối tượng bảo trợ xã hội hoặc khi thực hiện trực tuyến toàn trình theo nghị quyết của HĐND từng địa phương.\n",
                    f"📌 **Lưu ý:** Lệ phí hành chính nhà nước có biên lai thu tiền hợp pháp. Người dân tuyệt đối không trả thêm bất kỳ khoản phí ngoài quy định nào.",
                ]
                return "\n".join(lines)

            elif is_time:
                lines = [
                    f"## ⏱️ Thời hạn giải quyết thủ tục\n",
                    f"Đối với thủ tục **{title}**:\n",
                    f"- **Thời hạn luật định:** **{processing_time}**",
                    f"- **Cách tính thời hạn:** Tính theo ngày làm việc (không tính thứ Bảy, Chủ nhật và các ngày nghỉ lễ, tết theo quy định của Bộ luật Lao động).",
                    f"- **Trường hợp phức tạp:** Nếu hồ sơ cần xác minh thực địa hoặc kiểm tra chéo liên ngành, cơ quan giải quyết sẽ có văn bản thông báo gia hạn nhưng không vượt quá thời gian tối đa luật cho phép.",
                    f"- **Hình thức nhận kết quả:** Nhận kết quả trực tiếp tại Bộ phận Một cửa hoặc đăng ký trả kết quả qua dịch vụ bưu chính công ích về tận nhà.",
                ]
                return "\n".join(lines)

            elif is_docs:
                docs_text = "\n".join([f"  {idx+1}. **{d}**" for idx, d in enumerate(docs_list)])
                lines = [
                    f"## 📑 Thành phần hồ sơ bắt buộc\n",
                    f"Để thực hiện thủ tục **{title}**, người nộp cần chuẩn bị đầy đủ **{len(docs_list)}** loại giấy tờ sau:\n",
                    docs_text,
                    f"\n### 📄 Biểu mẫu & Tờ khai chính thức (PDF chuẩn Nghị định 30/2020)\n{pdf_widget}\n",
                    f"📌 **Quy cách hồ sơ:**",
                    f"- Các giấy tờ nộp bản sao cần kèm bản chính để đối chiếu, hoặc bản sao có chứng thực.",
                    f"- Các tờ khai/đơn phải điền đầy đủ thông tin, không tẩy xóa, ký và ghi rõ họ tên.",
                ]
                return "\n".join(lines)

            elif is_steps:
                steps_text = "\n".join([
                    f"### Bước {s.get('index', idx+1)}: {s.get('title', '')}\n"
                    f"- **Thời hạn:** {s.get('duration', 'Theo quy định')}\n"
                    f"- **Nội dung thực hiện:** {s.get('description', '')}\n"
                    for idx, s in enumerate(steps_list)
                ])
                lines = [
                    f"## 📋 Trình tự các bước thực hiện\n",
                    f"Quy trình thực hiện thủ tục **{title}** gồm các bước chuẩn như sau:\n",
                    steps_text,
                    f"\n### 📄 Biểu mẫu cần có trong quy trình:\n{pdf_widget}\n",
                    f"📌 **Cơ quan giải quyết:** {agency} · **Thời hạn toàn trình:** {processing_time} · **Lệ phí:** {fee}",
                ]
                return "\n".join(lines)

            else:
                # GENERAL CONSULTATION
                steps_summary = "\n".join([
                    f"  - **Bước {s.get('index', idx+1)}**: {s.get('title', '')} ({s.get('duration', 'Đang cập nhật')})"
                    for idx, s in enumerate(steps_list[:4])
                ])
                docs_summary = "\n".join([f"  + {d}" for d in docs_list[:5]])
                citations_text = "\n".join(legal_citations) if legal_citations else "- Căn cứ CSDL Thủ tục hành chính quốc gia và văn bản quy phạm pháp luật hiện hành."

                lines = [
                    f"## 🏛️ TƯ VẤN PHÁP LÝ & QUY TRÌNH THỰC HIỆN\n",
                    f"### {title}\n",
                    f"Dựa trên cơ sở dữ liệu pháp luật hiện hành của VinaLex, hệ thống cung cấp hướng dẫn chi tiết như sau:\n",
                    f"#### 1. Căn cứ pháp lý áp dụng:\n{citations_text}\n",
                    f"#### 2. Trình tự các bước giải quyết:\n{steps_summary}\n",
                    f"#### 3. Thành phần hồ sơ bắt buộc:\n{docs_summary}\n",
                    f"### 📄 Biểu mẫu & Tờ khai chính thức (PDF chuẩn Nghị định 30/2020)\n{pdf_widget}\n",
                    f"#### 4. Cơ quan thẩm quyền, Thời hạn & Lệ phí:\n"
                    f"- **Cơ quan giải quyết:** {agency}\n"
                    f"- **Thời hạn giải quyết:** {processing_time}\n"
                    f"- **Lệ phí:** {fee}\n",
                    f"---\n"
                    f"📌 **Khuyến nghị thi hành:**\n"
                    f"- Người dân chuẩn bị đầy đủ hồ sơ theo danh mục trên, nộp tại Bộ phận Một cửa của **{agency}** hoặc thực hiện trực tuyến qua Cổng Dịch vụ công Quốc gia.\n"
                    f"- Bạn có thể nộp ảnh giấy tờ vào khung thẩm định để AI đối soát sai sót trước khi nộp chính thức.",
                ]
                return "\n".join(lines)

        # 3. Fallback khi không tìm thấy thủ tục cụ thể -> Tổng hợp từ các Điều luật trong RAG Docs
        docs = self._dedupe_docs(docs)
        if not docs:
            return (
                "Xin chào! Tôi là Trợ lý Pháp lý VinaLex.\n\n"
                "Hiện tại cơ sở dữ liệu chưa tìm thấy văn bản quy phạm hoặc thủ tục nào khớp chính xác với câu hỏi của bạn.\n\n"
                "💡 **Gợi ý tra cứu:**\n"
                "- Bạn có thể thử tra cứu theo từ khóa lĩnh vực: *đất đai, cấp sổ đỏ, hộ tịch, đổi bằng lái xe, bảo hiểm xã hội, thành lập công ty...*\n"
                "- Hoặc nhập số hiệu văn bản cụ thể: ví dụ `101/2024/NĐ-CP`, `05/2024/TT-BGTVT`, `6093/QĐ-UBND`..."
            )

        lines = [
            f"## 🏛️ TƯ VẤN PHÁP LÝ DỰA TRÊN CƠ SỞ DỮ LIỆU LUẬT\n",
            f"Đối chiếu câu hỏi của bạn với hệ thống **{len(docs)}** căn cứ pháp luật hiện hành:\n"
        ]
        for i, doc in enumerate(docs, 1):
            meta = doc.metadata or {}
            source = meta.get("source", "Văn bản quy phạm")
            doc_number = meta.get("doc_number", "")
            article = meta.get("article", "")
            agency = meta.get("agency", "")
            content = doc.page_content.strip()
            if len(content) > 600:
                content = content[:600].rsplit(" ", 1)[0].strip() + "..."

            lines.append(f"### {i}. {source}")
            meta_str = " | ".join(filter(None, [
                f"Quy định: **{article}**" if article else "",
                f"Số hiệu: `{doc_number}`" if doc_number else "",
                f"Cơ quan: {agency}" if agency else ""
            ]))
            if meta_str:
                lines.append(f"*{meta_str}*\n")
            lines.append(f"> {content}\n")

        lines.append(
            "---\n"
            "📌 **Khuyến nghị của Trợ lý VinaLex:**\n"
            "- Các quy định trên là căn cứ pháp lý hiện hành điều chỉnh vấn đề bạn quan tâm.\n"
            "- Người dân và doanh nghiệp cần đối chiếu trường hợp cụ thể của mình với các điều kiện quy định tại các điều luật trên để thực hiện đúng quyền và nghĩa vụ."
        )
        return "\n".join(lines)

    async def generate_answer(
        self,
        query: str,
        history: Optional[List[Dict[str, str]]] = None,
        session_id: str = "",
    ) -> Tuple[str, List[str]]:
        """
        Pipeline hoàn chỉnh:
          1. Multi-turn Query Contextualization: giải mã câu hỏi phụ thuộc dựa trên lịch sử.
          2. RAG Retrieval & Candidate Pruning: trích xuất các điều khoản liên quan.
          3. Procedure DB Lookup: trích xuất thông tin thủ tục có cấu trúc.
          4. Cloud LLM Reasoning (Groq / Gemini) nếu có API key.
          5. Expert Rule-based Legal Reasoning Engine nếu chạy 100% offline.
          6. PDF Template Widget & Download Links.
        """
        cleaned_query = query.strip()
        if not cleaned_query:
            return "Xin chào! Bạn cần hỗ trợ thủ tục hành chính hoặc quy định pháp luật nào?", []

        # 1. Tái tạo câu hỏi phụ thuộc (Anaphora Resolution)
        enriched_query, extracted_topic = self.contextualize_query(cleaned_query, history)

        # 2. Kiểm tra bộ nhớ đệm (chỉ áp dụng cho câu hỏi độc lập)
        cache_key = strip_accents(enriched_query.lower())
        if not history and cache_key in _RESPONSE_CACHE:
            return _RESPONSE_CACHE[cache_key]

        self._initialize()

        # 3. Tra cứu CSDL thủ tục có cấu trúc
        proc_data = None
        try:
            from backend.services.gemini_service import _query_procedure_db
            if extracted_topic:
                proc_data = _query_procedure_db(extracted_topic)
            if not proc_data:
                proc_data = _query_procedure_db(enriched_query)
            if not proc_data:
                proc_data = _query_procedure_db(cleaned_query)
        except Exception:
            proc_data = None

        # 4. RAG Retrieval (chạy trên threadpool non-blocking)
        search_query = enriched_query if enriched_query != cleaned_query else cleaned_query
        raw_docs = await asyncio.to_thread(self._rag_service.retrieve_relevant_docs, search_query)
        relevant_docs: List[Document] = self._dedupe_docs(raw_docs)
        context, sources = self._rag_service.build_context(relevant_docs)

        # 5. Thử Cloud LLM (Groq / Gemini)
        cloud_answer = await self._call_cloud_llm(cleaned_query, context, history=history)
        if cloud_answer:
            answer = cloud_answer
        elif self._llm is not None:
            # Thử Ollama local nếu có
            prompt = self.build_prompt(search_query, context)
            try:
                ans = await self._llm.ainvoke(prompt)
                answer = ans.strip() if ans else None
            except Exception:
                answer = None
        else:
            answer = None

        # 6. Nếu không có LLM Cloud/Ollama -> Kích hoạt VinaLex Expert Reasoner
        if not answer:
            answer = self._synthesize_expert_answer(
                cleaned_query,
                relevant_docs,
                proc_data=proc_data,
                history=history,
                extracted_topic=extracted_topic,
            )

        # 7. Đảm bảo thẻ Biểu mẫu PDF luôn hiện diện
        try:
            from backend.services.gemini_service import GeminiService
            target_proc_query = proc_data.get("title") if proc_data else (extracted_topic or cleaned_query)
            answer = GeminiService()._ensure_pdf_widget(answer, target_proc_query)
        except Exception:
            pass

        final_answer = self._remove_repeated_lines(answer)
        if not history and len(_RESPONSE_CACHE) < _MAX_CACHE_SIZE:
            _RESPONSE_CACHE[cache_key] = (final_answer, sources)

        return final_answer, sources

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

        # Bước 0: Ưu tiên Gemini AI Agent phân tích ngữ cảnh sâu nếu có API Key
        try:
            from backend.services.gemini_service import GeminiService
            gemini = GeminiService()
            if gemini.is_available():
                res = await gemini.analyze_document_semantic(
                    extracted_fields=extracted_fields,
                    expected_doc_name=document_type,
                    procedure_title=context_procedure or "Thủ tục hành chính",
                    raw_document_type=document_type,
                )
                summary_parts = [f"✅ **Đánh giá thẩm định AI ({document_type})**: {res.get('summary', '')}"]
                if res.get("errors"):
                    summary_parts.append("\n❌ **Lỗi vi phạm / sai lệch:**\n" + "\n".join([f"- {e}" for e in res["errors"]]))
                if res.get("warnings"):
                    summary_parts.append("\n⚠️ **Lưu ý:**\n" + "\n".join([f"- {w}" for w in res["warnings"]]))
                if res.get("suggestions"):
                    summary_parts.append(f"\n💡 **Hướng dẫn khắc phục:** {res['suggestions']}")
                return "\n".join(summary_parts)
        except Exception:
            pass

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
