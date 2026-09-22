"""
VinaLex — RagService: Truy xuất thông tin pháp lý từ Vector DB và CSDL Văn bản

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ Xử lý Ngôn ngữ Tự nhiên):
  - LangChain: Khung sườn liên kết các module NLP
  - Qdrant: Vector DB lưu văn bản luật (hỗ trợ cả Remote và Embedded Disk DB)
  - Embedding: keepitreal/vietnamese-sbert (tiếng Việt)
  - CSDL Fallback: Tự động tra cứu trực tiếp từ 175+ văn bản và 118+ thủ tục đã cào

Tuân thủ CONTRIBUTING.md §2.1:
  - Class: PascalCase → RagService
  - Hàm: snake_case → retrieve_relevant_docs, build_context

🚫 Quy tắc bảo mật:
  - KHÔNG gọi API embedding bên ngoài — dùng local HuggingFace model
  - KHÔNG lưu query của người dùng vào file log
"""

import json
import re
import socket
import warnings
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from langchain.schema import Document

from backend.core.config import settings

# Bỏ qua các cảnh báo thư viện không cần thiết
warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")


class RagService:
    """
    Dịch vụ truy xuất tài liệu pháp lý bằng RAG (Retrieval-Augmented Generation).

    Pipeline:
      1. Nhận câu hỏi (query) từ người dùng
      2. Tìm kiếm top-k văn bản liên quan trong Qdrant Vector DB
      3. Nếu Qdrant chưa chạy -> Tự động Fallback tra cứu thông minh từ CSDL văn bản & thủ tục đã cào
      4. Trả về context và nguồn trích dẫn pháp lý chính xác
    """

    def __init__(self):
        self._vector_store = None   # Qdrant client
        self._embeddings = None     # HuggingFace embedding model
        self._initialized = False
        self._local_docs_cache: Optional[List[Dict[str, Any]]] = None
        self._local_proc_cache: Optional[List[Dict[str, Any]]] = None

    def _initialize(self):
        """Lazy load Qdrant + Embedding model với kiểm tra kết nối an toàn."""
        if self._initialized:
            return
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from langchain_community.vectorstores import Qdrant
                from langchain_huggingface import HuggingFaceEmbeddings
                from qdrant_client import QdrantClient

                # 1. Load embedding model nội bộ (Vietnamese SBERT)
                try:
                    self._embeddings = HuggingFaceEmbeddings(
                        model_name=settings.EMBEDDING_MODEL_NAME,
                        model_kwargs={"device": settings.INFERENCE_DEVICE},
                        encode_kwargs={"normalize_embeddings": True},
                    )
                except Exception:
                    self._embeddings = None

                # 2. Kiểm tra xem Qdrant Server remote có đang chạy không
                is_qdrant_online = False
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(0.4)
                    res = s.connect_ex((settings.QDRANT_HOST, settings.QDRANT_PORT))
                    s.close()
                    is_qdrant_online = (res == 0)
                except Exception:
                    is_qdrant_online = False

                if is_qdrant_online:
                    qdrant_client = QdrantClient(
                        host=settings.QDRANT_HOST,
                        port=settings.QDRANT_PORT,
                    )
                else:
                    # Chạy Embedded Disk DB cục bộ không cần Docker
                    db_path = Path("./data/qdrant_db")
                    db_path.mkdir(parents=True, exist_ok=True)
                    qdrant_client = QdrantClient(path=str(db_path))

                if self._embeddings is not None:
                    self._vector_store = Qdrant(
                        client=qdrant_client,
                        collection_name="vinalex_legal_docs",
                        embeddings=self._embeddings,
                    )

            self._initialized = True
        except Exception:
            # Qdrant hoặc model chưa sẵn sàng — hệ thống vẫn chạy mượt qua local fallback
            self._initialized = True

    def retrieve_relevant_docs(self, query: str, top_k: int = 5) -> List[Document]:
        """
        Tìm các đoạn văn bản pháp luật liên quan nhất với câu hỏi.
        Hỗ trợ 2 lớp truy xuất:
          Lớp 1: Qdrant Vector Store (Similarity Search)
          Lớp 2: Fallback CSDL thông minh từ kho 175+ văn bản và thủ tục đã cào

        Args:
            query: Câu hỏi của người dùng
            top_k: Số lượng văn bản trả về (mặc định 5)

        Returns:
            Danh sách Document có nội dung và metadata (nguồn trích dẫn)
        """
        self._initialize()

        # Lớp 1: Thử tìm trong Qdrant Vector DB
        if self._vector_store is not None:
            try:
                docs = self._vector_store.similarity_search(query, k=top_k)
                if docs and len(docs) > 0:
                    return docs
            except Exception:
                # Qdrant rỗng hoặc kết nối bị từ chối -> tự động chuyển sang Fallback CSDL
                pass

        # Lớp 2: Fallback tìm kiếm chính xác từ kho CSDL văn bản và thủ tục
        return self._search_local_docs(query, top_k=top_k)

    def _load_local_data(self):
        """Đọc và cache dữ liệu văn bản và thủ tục đã cào từ đĩa."""
        if self._local_docs_cache is None:
            docs_path = Path("data/crawled_legal_docs.json")
            if docs_path.exists():
                try:
                    with open(docs_path, "r", encoding="utf-8") as f:
                        self._local_docs_cache = json.load(f)
                except Exception:
                    self._local_docs_cache = []
            else:
                self._local_docs_cache = []

        if self._local_proc_cache is None:
            proc_path = Path("data/crawled_procedures.json")
            if proc_path.exists():
                try:
                    with open(proc_path, "r", encoding="utf-8") as f:
                        self._local_proc_cache = json.load(f)
                except Exception:
                    self._local_proc_cache = []
            else:
                self._local_proc_cache = []

    def _search_local_docs(self, query: str, top_k: int = 5) -> List[Document]:
        """
        Tìm kiếm thông minh từ CSDL văn bản pháp luật và thủ tục hành chính đã lưu.
        Tính điểm liên quan theo trọng số: Số hiệu (20x) > Tiêu đề (4x) > Lĩnh vực (2x) > Nội dung (1x).
        """
        self._load_local_data()
        docs_list = self._local_docs_cache or []
        proc_list = self._local_proc_cache or []

        if not docs_list and not proc_list:
            return []

        # Tách từ khóa tìm kiếm (bỏ qua từ quá ngắn 1 ký tự)
        raw_tokens = [t.lower().strip() for t in re.split(r"[\s,\.\?\!\:\;]+", query) if len(t.strip()) > 1]
        tokens = list(set(raw_tokens))
        query_lower = query.lower()

        scored_results = []

        # ── 1. Đánh giá Văn bản pháp luật (crawled_legal_docs) ──
        for doc in docs_list:
            score = 0.0
            doc_num = (doc.get("doc_number") or "").strip()
            title = (doc.get("title") or "").strip()
            category = (doc.get("category") or "").strip()
            content = (doc.get("content_text") or "").strip()

            doc_num_lower = doc_num.lower()
            title_lower = title.lower()
            category_lower = category.lower()
            content_lower = content.lower()

            # Trùng số hiệu văn bản (rất cao)
            if doc_num and doc_num_lower in query_lower:
                score += 30.0

            for token in tokens:
                if doc_num_lower and token in doc_num_lower:
                    score += 15.0
                if token in title_lower:
                    score += 5.0
                if token in category_lower:
                    score += 2.5
                if token in content_lower[:3000]:  # ưu tiên phần đầu văn bản
                    score += 1.0

            if score > 0:
                # Trích xuất đoạn nội dung liên quan nhất (snippet quanh từ khóa)
                snippet = self._extract_relevant_snippet(content, tokens, max_len=750)
                if not snippet and content:
                    snippet = content[:750]

                scored_results.append((
                    score,
                    Document(
                        page_content=snippet,
                        metadata={
                            "source": f"{doc.get('doc_type', 'Văn bản')} {doc_num}: {title}".strip(),
                            "doc_number": doc_num,
                            "agency": doc.get("agency", ""),
                            "issue_date": doc.get("issue_date", ""),
                            "category": category,
                            "url": doc.get("original_url", ""),
                        }
                    )
                ))

        # ── 2. Đánh giá Thủ tục hành chính (crawled_procedures) ──
        for proc in proc_list:
            score = 0.0
            title = (proc.get("title") or "").strip()
            category = (proc.get("category") or "").strip()
            desc = (proc.get("description") or "").strip()
            docs_req = proc.get("documents") or []
            steps = proc.get("steps") or []

            title_lower = title.lower()
            desc_lower = desc.lower()

            # Chuẩn hóa siêu dữ liệu lĩnh vực nếu dữ liệu gốc bị gán nhầm
            if any(k in title_lower for k in ["thuế", "thue", "nộp thuế", "đăng ký thuế", "mã số thuế"]):
                if category != "Thuế & Tài chính":
                    category = "Thuế & Tài chính"
            elif "vneid" in title_lower and category == "Tài nguyên - Môi trường":
                category = "Hộ tịch"

            for token in tokens:
                if token in title_lower:
                    score += 6.0
                if token in desc_lower:
                    score += 2.0

            if score > 0:
                # Định dạng nội dung thủ tục gồm mô tả + hồ sơ + các bước
                lines = [desc]
                if docs_req:
                    lines.append("Thành phần hồ sơ yêu cầu:")
                    for d in docs_req[:4]:
                        lines.append(f"- {d}")
                if steps:
                    lines.append("Trình tự thực hiện:")
                    for s in steps[:3]:
                        lines.append(f"+ Bước {s.get('index', '')}: {s.get('title', '')} - {s.get('description', '')}")

                snippet = "\n".join(lines)[:750]

                scored_results.append((
                    score,
                    Document(
                        page_content=snippet,
                        metadata={
                            "source": f"Thủ tục: {title}",
                            "doc_number": "Thủ tục hành chính",
                            "agency": proc.get("authority", "Cơ quan hành chính nhà nước"),
                            "issue_date": "Hiện hành",
                            "category": category,
                            "url": f"/procedures/{proc.get('slug', '')}",
                        }
                    )
                ))

        # Sắp xếp theo điểm liên quan giảm dần
        scored_results.sort(key=lambda x: x[0], reverse=True)

        if scored_results:
            return [doc for _, doc in scored_results[:top_k]]

        # Nếu không có từ khóa nào khớp (ví dụ câu chào hỏi chung), trả về 2 văn bản mới nhất làm mẫu
        default_docs = []
        for doc in docs_list[:min(3, len(docs_list))]:
            snippet = (doc.get("content_text") or "")[:600]
            default_docs.append(Document(
                page_content=snippet,
                metadata={
                    "source": doc.get("title", ""),
                    "doc_number": doc.get("doc_number", ""),
                    "agency": doc.get("agency", ""),
                    "issue_date": doc.get("issue_date", ""),
                    "category": doc.get("category", ""),
                }
            ))
        return default_docs

    def _extract_relevant_snippet(self, text: str, tokens: List[str], max_len: int = 750) -> str:
        """Trích xuất đoạn văn bản chứa mật độ từ khóa cao nhất."""
        if not text:
            return ""
        text_clean = text.replace("\r\n", "\n").replace("\r", "\n")
        lines = [line.strip() for line in text_clean.split("\n") if line.strip()]
        
        # Tìm dòng đầu tiên chứa một trong các từ khóa
        best_idx = 0
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(tok in line_lower for tok in tokens):
                best_idx = max(0, i - 1)
                break

        selected_lines = lines[best_idx:best_idx + 8]
        snippet = "\n".join(selected_lines)
        if len(snippet) > max_len:
            snippet = snippet[:max_len] + "..."
        return snippet

    def build_context(self, docs: List[Document]) -> Tuple[str, List[str]]:
        """
        Tổng hợp nội dung văn bản thành context cho LLM và danh sách nguồn trích dẫn.

        Args:
            docs: Danh sách Document từ retrieve_relevant_docs

        Returns:
            Tuple (context_text, sources_list)
        """
        if not docs:
            return "", []

        context_parts: List[str] = []
        sources: List[str] = []

        for i, doc in enumerate(docs, 1):
            content = doc.page_content.strip()
            source = doc.metadata.get("source", f"Văn bản {i}")
            doc_number = doc.metadata.get("doc_number", "")

            label = f"[{i}] {source}"
            context_parts.append(f"{label}:\n{content}")

            source_label = doc_number if doc_number else source
            if source_label and source_label not in sources:
                sources.append(source_label)

        context_text = "\n\n".join(context_parts)
        return context_text, sources

    def add_documents(self, documents: List[Document]) -> None:
        """
        Thêm văn bản pháp luật mới vào Vector DB.
        Được gọi bởi AdminService khi đồng bộ kiến thức mới.

        Args:
            documents: Danh sách Document cần thêm vào Qdrant
        """
        self._initialize()

        if self._vector_store is not None:
            try:
                self._vector_store.add_documents(documents)
            except Exception:
                pass

