"""
VinaLex — Ingestion Service: Bóc tách, chỉ mục hóa và nạp dữ liệu RAG

Tuân thủ ARCHITECTURE.md Lớp 3 (Phân hệ RAG):
- Đọc 100% dữ liệu có sẵn của hệ thống:
    + data/crawled_legal_docs.json (204 văn bản toàn văn)
    + data/dvc_procedures.json & data/crawled_procedures.json (550+ thủ tục)
- Bóc tách cấu trúc pháp lý qua LegalDocParser và ProcedureParser.
- Lưu cache phân đoạn ra data/parsed_rag_chunks.json để tải siêu tốc (<50ms).
- Hỗ trợ nạp vector embeddings vào Qdrant (cục bộ hoặc remote).
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from langchain.schema import Document

from backend.services.legal_parser import LegalDocParser, ProcedureParser

logger = logging.getLogger("vinalex.ingest")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

DATA_DIR = Path("data")
CHUNKS_CACHE_FILE = DATA_DIR / "parsed_rag_chunks.json"


class IngestService:
    """
    Dịch vụ nạp và chuẩn hóa dữ liệu kiến thức cho hệ thống RAG VinaLex.
    """

    @classmethod
    def load_raw_data(cls) -> Dict[str, Any]:
        """Đọc toàn bộ dữ liệu thô sẵn có trong hệ thống."""
        legal_docs = []
        procedures = []

        # 1. Văn bản pháp luật
        legal_path = DATA_DIR / "crawled_legal_docs.json"
        if legal_path.exists():
            try:
                with open(legal_path, "r", encoding="utf-8") as f:
                    legal_docs = json.load(f)
            except Exception as e:
                logger.error(f"Lỗi đọc {legal_path}: {e}")

        # 2. Thủ tục hành chính (dvc + crawled)
        seen_slugs = set()
        for filename in ["dvc_procedures.json", "crawled_procedures.json"]:
            proc_path = DATA_DIR / filename
            if proc_path.exists():
                try:
                    with open(proc_path, "r", encoding="utf-8") as f:
                        items = json.load(f)
                    for item in items:
                        slug = item.get("slug") or item.get("id")
                        if slug and slug not in seen_slugs:
                            seen_slugs.add(slug)
                            procedures.append(item)
                except Exception as e:
                    logger.error(f"Lỗi đọc {proc_path}: {e}")

        return {
            "legal_docs": legal_docs,
            "procedures": procedures,
        }

    _in_memory_chunks: Optional[List[Document]] = None

    @classmethod
    def parse_all_chunks(cls, force_reparse: bool = False) -> List[Document]:
        """
        Bóc tách toàn bộ văn bản và thủ tục thành các Document chunks chuẩn.
        Tự động lưu và đọc từ cache disk data/parsed_rag_chunks.json để tối ưu hiệu năng.
        """
        if not force_reparse and cls._in_memory_chunks is not None:
            return cls._in_memory_chunks

        if not force_reparse and CHUNKS_CACHE_FILE.exists():
            try:
                with open(CHUNKS_CACHE_FILE, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                documents = [
                    Document(page_content=item["content"], metadata=item["metadata"])
                    for item in cached_data
                ]
                cls._in_memory_chunks = documents
                logger.info(f"Đã tải {len(documents)} chunks từ bộ nhớ đệm: {CHUNKS_CACHE_FILE}")
                return documents
            except Exception as e:
                logger.warning(f"Không thể đọc cache chunks ({e}), tiến hành phân tích lại...")

        raw_data = cls.load_raw_data()
        legal_docs = raw_data["legal_docs"]
        procedures = raw_data["procedures"]

        all_documents: List[Document] = []

        # 1. Parse văn bản pháp luật
        logger.info(f"Bắt đầu bóc tách {len(legal_docs)} văn bản pháp luật...")
        for doc in legal_docs:
            chunks = LegalDocParser.parse_legal_document(doc)
            all_documents.extend(chunks)

        # 2. Parse thủ tục hành chính
        logger.info(f"Bắt đầu bóc tách {len(procedures)} thủ tục hành chính...")
        for proc in procedures:
            chunks = ProcedureParser.parse_procedure(proc)
            all_documents.extend(chunks)

        logger.info(f"Tổng kết phân đoạn: {len(all_documents)} chunks chất lượng cao.")

        # Lưu cache để các lần khởi động sau chạy tức thì (<50ms)
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            serializable = [
                {"content": d.page_content, "metadata": d.metadata}
                for d in all_documents
            ]
            with open(CHUNKS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False, indent=2)
            logger.info(f"Đã lưu cache phân đoạn vào {CHUNKS_CACHE_FILE}")
        except Exception as e:
            logger.error(f"Lỗi lưu cache chunks: {e}")

        cls._in_memory_chunks = all_documents
        return all_documents

    @classmethod
    def ingest_to_qdrant(cls, limit: Optional[int] = None, batch_size: int = 50) -> int:
        """
        Nạp embeddings của các chunks vào Qdrant Vector Store.
        """
        from backend.core.config import settings
        from langchain_community.vectorstores import Qdrant
        from langchain_huggingface import HuggingFaceEmbeddings
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams

        chunks = cls.parse_all_chunks()
        if limit:
            chunks = chunks[:limit]

        logger.info(f"Khởi tạo HuggingFaceEmbeddings ({settings.EMBEDDING_MODEL_NAME})...")
        embeddings = HuggingFaceEmbeddings(
            model_name=settings.EMBEDDING_MODEL_NAME,
            model_kwargs={"device": settings.INFERENCE_DEVICE},
            encode_kwargs={"normalize_embeddings": True},
        )

        db_path = DATA_DIR / "qdrant_db"
        db_path.mkdir(parents=True, exist_ok=True)
        client = QdrantClient(path=str(db_path))

        collection_name = "vinalex_legal_knowledge"

        # Kiểm tra và tạo collection nếu chưa có
        existing_colls = [c.name for c in client.get_collections().collections]
        if collection_name not in existing_colls:
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=768, distance=Distance.COSINE),
            )
            logger.info(f"Đã tạo collection Qdrant mới: {collection_name}")

        vector_store = Qdrant(
            client=client,
            collection_name=collection_name,
            embeddings=embeddings,
        )

        total = len(chunks)
        logger.info(f"Đang nạp {total} chunks vào Qdrant (batch size = {batch_size})...")

        for i in range(0, total, batch_size):
            batch = chunks[i : i + batch_size]
            vector_store.add_documents(batch)
            logger.info(f"  -> Đã nạp {min(i + batch_size, total)}/{total} chunks...")

        logger.info("Hoàn tất nạp dữ liệu vào Qdrant Vector Store!")
        return total


if __name__ == "__main__":
    force = "--reindex" in sys.argv or "--force" in sys.argv
    chunks = IngestService.parse_all_chunks(force_reparse=force)
    print(f"\n[DONE] Hệ thống đã sẵn sàng với {len(chunks)} chunks pháp lý & thủ tục.")
