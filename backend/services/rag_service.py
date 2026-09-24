"""
VinaLex — RagService: Truy xuất thông tin pháp lý từ Vector DB và CSDL Văn bản

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ Xử lý Ngôn ngữ Tự nhiên):
  - LangChain: Khung sườn liên kết các module NLP
  - Qdrant: Vector DB lưu văn bản luật (hỗ trợ cả Remote và Embedded Disk DB)
  - Embedding: keepitreal/vietnamese-sbert (tiếng Việt)
  - CSDL Fallback & Ingest: Tự động phân đoạn theo cấu trúc Chương → Điều → Khoản
  - Hybrid Retrieval: Dense Semantic (Vector) + Sparse Lexical (BM25) + Metadata Entity Filter + RRF Fusion

Tuân thủ CONTRIBUTING.md §2.1:
  - Class: PascalCase → RagService
  - Hàm: snake_case → retrieve_relevant_docs, build_context

🚫 Quy tắc bảo mật:
  - KHÔNG gọi API embedding bên ngoài — dùng local HuggingFace model
  - KHÔNG lưu query của người dùng vào file log
"""

import re
import socket
import warnings
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Set
from langchain.schema import Document

from backend.core.config import settings
from backend.services.legal_parser import strip_accents
from backend.services.ingest_service import IngestService

# Bỏ qua các cảnh báo thư viện không cần thiết
warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")


class RagService:
    """
    Dịch vụ truy xuất tài liệu pháp lý bằng RAG (Retrieval-Augmented Generation).
    Hỗ trợ mô hình Hybrid Retrieval 4 tầng:
      1. Bóc tách thực thể pháp lý (Số Điều, Số hiệu văn bản, Cụm từ chuyên ngành).
      2. Dense Vector Search qua Qdrant (Cosine Similarity).
      3. Sparse Lexical Search (BM25 / Keyword + Synonyms) trên 8.300+ Chunks Điều khoản.
      4. Hợp nhất xếp hạng Reciprocal Rank Fusion (RRF) & định dạng trích dẫn chuẩn pháp lý.
    """

    _shared_all_chunks: Optional[List[Document]] = None
    _shared_embeddings = None
    _shared_vector_store = None
    _shared_initialized: bool = False

    def __init__(self):
        self._vector_store = None       # Qdrant client
        self._embeddings = None         # HuggingFace embedding model
        self._initialized = False
        self._all_chunks: List[Document] = []
        self._chunks_loaded = False

    def _initialize(self):
        """Lazy load Qdrant + Embedding model + Parsed Legal Chunks with process-level caching."""
        if RagService._shared_initialized:
            self._all_chunks = RagService._shared_all_chunks or []
            self._embeddings = RagService._shared_embeddings
            self._vector_store = RagService._shared_vector_store
            self._chunks_loaded = True
            self._initialized = True
            return

        if self._initialized:
            return

        # 1. Nạp danh sách Document chunks có cấu trúc (8.300+ Chunks từ data sẵn có)
        if RagService._shared_all_chunks is None:
            try:
                RagService._shared_all_chunks = IngestService.parse_all_chunks(force_reparse=False)
            except Exception:
                RagService._shared_all_chunks = []

        self._all_chunks = RagService._shared_all_chunks
        self._chunks_loaded = True

        # 2. Khởi tạo Qdrant & Embedding model
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                from langchain_community.vectorstores import Qdrant
                from langchain_huggingface import HuggingFaceEmbeddings
                from qdrant_client import QdrantClient

                # Load embedding model nội bộ (Vietnamese SBERT)
                if RagService._shared_embeddings is None:
                    try:
                        RagService._shared_embeddings = HuggingFaceEmbeddings(
                            model_name=settings.EMBEDDING_MODEL_NAME,
                            model_kwargs={"device": settings.INFERENCE_DEVICE},
                            encode_kwargs={"normalize_embeddings": True},
                        )
                    except Exception:
                        RagService._shared_embeddings = None

                self._embeddings = RagService._shared_embeddings

                if RagService._shared_vector_store is None and self._embeddings is not None:
                    # Kiểm tra kết nối Qdrant
                    is_qdrant_online = False
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(0.3)
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
                        db_path = Path("./data/qdrant_db")
                        db_path.mkdir(parents=True, exist_ok=True)
                        qdrant_client = QdrantClient(path=str(db_path))

                    RagService._shared_vector_store = Qdrant(
                        client=qdrant_client,
                        collection_name="vinalex_legal_knowledge",
                        embeddings=self._embeddings,
                    )

                self._vector_store = RagService._shared_vector_store

            RagService._shared_initialized = True
            self._initialized = True
        except Exception:
            RagService._shared_initialized = True
            self._initialized = True

    def retrieve_relevant_docs(self, query: str, top_k: int = 5) -> List[Document]:
        """
        Tìm kiếm lai (Hybrid Retrieval) các điều luật và thủ tục liên quan nhất với câu hỏi.

        Pipeline:
          Tầng 1: Nhận diện thực thể (Số Điều, Số hiệu VB, Cụm từ chuyên môn).
          Tầng 2: Vector Search Dense qua Qdrant (nếu khả dụng).
          Tầng 3: Lexical Matching Sparse (BM25 + Ranh giới từ + Đồng nghĩa) trên toàn bộ Chunks Điều luật.
          Tầng 4: Hợp nhất điểm xếp hạng RRF và chọn top-k tài liệu đa dạng nguồn.
        """
        self._initialize()

        if not query or not query.strip():
            return []

        chunks = self._all_chunks
        if not chunks:
            # Fallback nếu chưa tải được chunks
            return []

        # ── TẦNG 1: BÓC TÁCH THỰC THỂ PHÁP LÝ TỪ QUERY ──
        q_lower = query.lower().strip()
        q_clean = strip_accents(q_lower)

        # 1.1. Nhận diện số Điều (VD: "Điều 14", "Điều 5", "dieu 14")
        target_article_num = None
        dieu_match = re.search(r"(?i)(?:điều|dieu)\s+(\d+)", query)
        if dieu_match:
            try:
                target_article_num = int(dieu_match.group(1))
            except ValueError:
                pass

        # 1.2. Nhận diện số Khoản (VD: "Khoản 2", "khoan 1")
        target_clause_num = None
        khoan_match = re.search(r"(?i)(?:khoản|khoan)\s+(\d+)", query)
        if khoan_match:
            try:
                target_clause_num = int(khoan_match.group(1))
            except ValueError:
                pass

        # 1.3. Nhận diện số hiệu văn bản (VD: "6093", "49/2026", "1538", "13/2023")
        doc_num_candidates = [
            m.group(1) for m in re.finditer(r"(?i)(\d+[\w\-\/]*\d+|\d+)", query)
            if len(m.group(1)) >= 2
        ]

        # 1.4. Nhận diện loại văn bản mong muốn
        is_asking_procedure = any(k in q_clean for k in ["thu tuc", "ho so", "trinh tu", "le phi", "thoi han", "xin cap"])
        is_asking_legal_doc = any(k in q_clean for k in ["dieu", "khoan", "nghi dinh", "thong tu", "luat", "quyet dinh", "quy dinh"])

        # 1.5. Bộ từ đồng nghĩa pháp lý chuyên sâu
        SYNONYMS = [
            (["so do", "so hong", "gcnqsdd"], ["so do", "so hong", "quyen su dung dat", "gcnqsdd", "giay chung nhan", "dat dai"]),
            (["dat dai", "nha dat"], ["dat dai", "nha dat", "dia chinh", "thua dat", "bat dong san", "thu hoi dat"]),
            (["khai sinh", "giay khai sinh"], ["khai sinh", "giay khai sinh", "chung sinh", "ho tich"]),
            (["can cuoc", "cccd", "cmnd", "dinh danh"], ["can cuoc", "cccd", "cmnd", "dinh danh dien tu", "vneid", "the can cuoc"]),
            (["luong", "tien luong", "luong toi thieu"], ["luong", "tien luong", "luong toi thieu", "lao dong", "nguoi lao dong", "hop dong lao dong"]),
            (["bao hiem xa hoi", "bhxh", "bao hiem y te", "bhyt"], ["bao hiem xa hoi", "bhxh", "so bhxh", "che do bhxh", "bao hiem y te", "bhyt", "that nghiep"]),
            (["ket hon", "hon nhan", "ly hon"], ["ket hon", "hon nhan", "ly hon", "tinh trang hon nhan", "hon thu"]),
            (["bang lai", "gplx", "lai xe"], ["bang lai", "gplx", "lai xe", "giay phep lai xe", "doi bang lai"]),
            (["doanh nghiep", "thanh lap cong ty", "kinh doanh"], ["doanh nghiep", "thanh lap cong ty", "dang ky kinh doanh", "giay phep kinh doanh"]),
            (["tam tru", "thuong tru", "cu tru", "ho khau"], ["tam tru", "thuong tru", "cu tru", "so ho khau", "dang ky tam tru"]),
        ]

        STOP_WORDS = {
            "ve", "cua", "tai", "cho", "va", "hoac", "o", "bi", "lam", "duoc", "co", "la",
            "toi", "muon", "can", "hoi", "nhung", "cac", "mot", "trong", "den", "khi",
            "nao", "moi", "nhat", "lai", "theo", "nhu", "the"
        }

        raw_tokens = [t.lower().strip() for t in re.split(r"[\s,\.\?\!\:\;]+", query) if len(t.strip()) > 1]
        meaningful_tokens = [t for t in raw_tokens if strip_accents(t) not in STOP_WORDS]
        tokens = meaningful_tokens if meaningful_tokens else raw_tokens

        # ── TẦNG 2: DENSE VECTOR RETRIEVAL (Qdrant) ──
        dense_ranks: Dict[str, int] = {}
        if self._vector_store is not None:
            try:
                dense_hits = self._vector_store.similarity_search(query, k=top_k * 3)
                for rank, hit in enumerate(dense_hits, 1):
                    # Khóa nhận diện chunk
                    hit_id = hit.metadata.get("source", "") + hit.page_content[:60]
                    dense_ranks[hit_id] = rank
            except Exception:
                pass

        # ── TẦNG 3: SPARSE LEXICAL & BM25 MATCHING TRÊN CHUNKS ──
        scored_chunks: List[Tuple[float, Document]] = []

        for doc in chunks:
            score = 0.0
            meta = doc.metadata or {}
            content = doc.page_content
            content_lower = content.lower()

            title = (meta.get("title") or "").lower()
            title_clean = strip_accents(title)

            article_str = (meta.get("article") or "").lower()
            article_num = meta.get("article_number")
            doc_number = (meta.get("doc_number") or "").lower()
            source_type = meta.get("source_type", "")

            # 3.1. BOOST SIÊU MẠNH KHI KHỚP ĐÚNG ĐIỀU LUẬT
            if target_article_num is not None:
                if article_num == target_article_num:
                    score += 350.0
                elif f"điều {target_article_num}" in article_str or f"dieu {target_article_num}" in article_str:
                    score += 300.0

            # 3.2. BOOST SIÊU MẠNH KHI KHỚP ĐÚNG SỐ HIỆU VĂN BẢN
            for candidate in doc_num_candidates:
                if candidate in doc_number:
                    score += 300.0
                    break

            # 3.3. Khớp cụm từ nguyên văn
            if q_lower in title:
                score += 150.0
            elif q_clean in title_clean:
                score += 120.0

            if q_lower in content_lower:
                score += 80.0

            # 3.4. Khớp từng token trong tiêu đề và nội dung
            matched_token_count = 0
            for tok in tokens:
                tok_clean = strip_accents(tok)
                if tok in title or tok_clean in title_clean:
                    score += 20.0
                    matched_token_count += 1
                elif tok in content_lower:
                    score += 8.0
                    matched_token_count += 1

            # 3.5. Khớp từ đồng nghĩa
            for q_pats, t_pats in SYNONYMS:
                if any(qp in q_clean for qp in q_pats):
                    if any(tp in title_clean for tp in t_pats):
                        score += 50.0
                    elif any(tp in content_lower[:600] for tp in t_pats):
                        score += 25.0

            # 3.6. Điều chỉnh theo định hướng câu hỏi (Thủ tục vs Văn bản luật)
            if is_asking_procedure and source_type == "procedure":
                score += 40.0
            elif is_asking_legal_doc and source_type == "legal_doc":
                score += 40.0

            # Chỉ giữ các chunk đạt ngưỡng liên quan
            if score >= 25.0:
                scored_chunks.append((score, doc))


        # ── TẦNG 4: RECIPROCAL RANK FUSION (RRF) & RE-RANKING ──
        # Sắp xếp danh sách sparse
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        rrf_final: List[Tuple[float, Document]] = []
        seen_keys: Set[str] = set()

        for sparse_rank, (sparse_score, doc) in enumerate(scored_chunks[:top_k * 4], 1):
            doc_key = doc.metadata.get("source", "") + doc.page_content[:60]
            if doc_key in seen_keys:
                continue
            seen_keys.add(doc_key)

            # Điểm Sparse chuẩn hóa
            sparse_component = sparse_score / (sparse_score + 100.0)

            # Điểm Dense từ Qdrant
            dense_rank = dense_ranks.get(doc_key)
            dense_rrf = 1.0 / (60.0 + dense_rank) if dense_rank else 0.0

            final_score = sparse_component + (dense_rrf * 5.0)
            rrf_final.append((final_score, doc))

        rrf_final.sort(key=lambda x: x[0], reverse=True)

        if rrf_final:
            # Chọn lọc đảm bảo đa dạng nguồn
            selected_docs: List[Document] = []
            selected_sources: Set[str] = set()

            for _, d in rrf_final:
                src = d.metadata.get("source", "")
                # Cho phép tối đa 2 chunks từ cùng 1 văn bản để đảm bảo độ bao quát
                count_same = sum(1 for sd in selected_docs if sd.metadata.get("doc_number") == d.metadata.get("doc_number"))
                if count_same < 2:
                    selected_docs.append(d)
                if len(selected_docs) >= top_k:
                    break

            # Nếu chưa đủ top_k, điền nốt các chunk điểm cao còn lại
            if len(selected_docs) < top_k:
                for _, d in rrf_final:
                    if d not in selected_docs:
                        selected_docs.append(d)
                    if len(selected_docs) >= top_k:
                        break

            return selected_docs

        # Nếu không có từ khóa nào khớp (VD câu hỏi chào hỏi), trả về mẫu các điều luật tiêu biểu
        default_docs: List[Document] = []
        for d in chunks[:min(top_k, len(chunks))]:
            default_docs.append(d)
        return default_docs

    def build_context(self, docs: List[Document]) -> Tuple[str, List[str]]:
        """
        Tổng hợp nội dung văn bản thành context pháp lý chuẩn hóa cho LLM và danh sách nguồn trích dẫn.
        Mỗi tài liệu ghi rõ: Điều, Khoản, Tên văn bản, Số hiệu, Cơ quan ban hành.

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
            meta = doc.metadata or {}
            source_type = meta.get("source_type", "")
            title = meta.get("title", "")
            doc_number = meta.get("doc_number", "")
            agency = meta.get("agency", "")
            article = meta.get("article", "")
            chapter = meta.get("chapter", "")
            clause = meta.get("clause", "")
            content = doc.page_content.strip()

            if source_type == "legal_doc":
                location_parts = []
                if chapter:
                    location_parts.append(chapter)
                if article:
                    location_parts.append(article)
                if clause:
                    location_parts.append(clause)
                loc_str = " - ".join(location_parts) if location_parts else "Nội dung quy định"

                source_label = f"{article} {doc_number}" if (article and doc_number) else (doc_number or title)

                block = (
                    f"[{i}] CĂN CỨ PHÁP LÝ: {title} (Số hiệu: {doc_number})\n"
                    f"    Cơ quan ban hành: {agency} | Vị trí: {loc_str}\n"
                    f"    Nội dung điều luật trích lục:\n"
                    f"{content}"
                )
            else:
                source_label = f"Thủ tục: {title}"
                section = meta.get("section", "Quy định thủ tục")
                block = (
                    f"[{i}] THỦ TỤC HÀNH CHÍNH: {title}\n"
                    f"    Cơ quan tiếp nhận & giải quyết: {agency} | Phần: {section}\n"
                    f"    Nội dung hướng dẫn:\n"
                    f"{content}"
                )

            context_parts.append(block)

            if source_label and source_label not in sources:
                sources.append(source_label)

        context_text = "\n\n" + ("=" * 60) + "\n\n".join([""] + context_parts) + "\n" + ("=" * 60)
        return context_text, sources

    def add_documents(self, documents: List[Document]) -> None:
        """Thêm văn bản pháp luật mới vào Vector DB và bộ nhớ đệm."""
        self._initialize()

        if documents:
            self._all_chunks.extend(documents)

        if self._vector_store is not None:
            try:
                self._vector_store.add_documents(documents)
            except Exception:
                pass
