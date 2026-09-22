"""
VinaLex — AdminService: Quản lý nội dung CMS & đồng bộ Vector DB

Tuân thủ README.md §5: admin_service.py = Quản lý nội dung CMS
Tuân thủ README.md §2: Admin CMS — tự động đồng bộ kiến thức mới vào Vector DB (Qdrant)

Tuân thủ CONTRIBUTING.md §2.1:
  - Class: PascalCase → AdminService
  - Hàm: snake_case → sync_legal_documents, create_procedure, update_procedure
"""

from typing import List, Optional
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter

from backend.services.rag_service import RagService


class AdminService:
    """
    Dịch vụ quản lý nội dung CMS và đồng bộ tài liệu pháp luật vào Qdrant.

    Chỉ dành cho Admin — không tiếp xúc với dữ liệu cá nhân người dùng.
    """

    def __init__(self):
        self._rag_service = RagService()
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ".", "!", "?", ","],
        )

    def parse_legal_document(
        self,
        content: str,
        source: str,
        document_type: str = "Văn bản pháp luật",
    ) -> List[Document]:
        """
        Phân tách văn bản pháp luật thành các chunk nhỏ để lưu vào Vector DB.

        Args:
            content: Nội dung văn bản pháp luật (toàn văn)
            source: Tên văn bản (VD: "Nghị định 13/2023/NĐ-CP")
            document_type: Loại văn bản (Nghị định, Thông tư, Luật, ...)

        Returns:
            Danh sách Document (chunk) sẵn sàng để embed và lưu vào Qdrant
        """
        chunks = self._text_splitter.split_text(content)
        documents = []
        for i, chunk in enumerate(chunks):
            doc = Document(
                page_content=chunk,
                metadata={
                    "source": source,
                    "document_type": document_type,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            )
            documents.append(doc)
        return documents

    async def sync_legal_documents(
        self,
        content: str,
        source: str,
        document_type: str = "Văn bản pháp luật",
    ) -> int:
        """
        Đồng bộ văn bản pháp luật mới vào Qdrant Vector DB.

        Đây là tính năng Admin CMS — tự động embed và lưu kiến thức mới
        để Chatbot RAG có thể tra cứu.

        Args:
            content: Nội dung văn bản
            source: Tên/mã số văn bản
            document_type: Loại văn bản

        Returns:
            Số chunk đã đồng bộ thành công
        """
        documents = self.parse_legal_document(content, source, document_type)
        self._rag_service.add_documents(documents)
        return len(documents)

    def get_sync_status(self) -> dict:
        """
        Trả về trạng thái đồng bộ của Vector DB.

        Returns:
            Dict thông tin trạng thái Qdrant
        """
        return {
            "qdrant_host": "localhost",
            "collection": "vinalex_legal_docs",
            "status": "connected" if self._rag_service._initialized else "not_initialized",
        }
