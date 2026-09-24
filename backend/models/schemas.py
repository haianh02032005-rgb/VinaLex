"""
VinaLex — Pydantic Schemas (Request / Response)

Tuân thủ CONTRIBUTING.md §2.1:
- Tên Class: PascalCase (VD: ProcedureResponse, OcrRequest)
- Tên field: snake_case (VD: session_id, processing_time)

Mở rộng: Admin schemas (ProcedureCreateRequest, SyncLegalDocRequest, ...)
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


# ── Auth Schemas ──
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Procedure Schemas ──
class ProcedureStepSchema(BaseModel):
    index: int
    title: str
    description: str
    duration: Optional[str] = None


class ProcedureResponse(BaseModel):
    id: int
    slug: str
    title: str
    category: str
    category_slug: str
    description: str
    steps: List[ProcedureStepSchema]
    documents: List[str]
    processing_time: str
    fee: str
    agency: str
    level: str
    tags: List[str]
    view_count: int
    updated_at: datetime

    class Config:
        from_attributes = True


class ProcedureListResponse(BaseModel):
    items: List[ProcedureResponse]
    total: int
    page: int
    limit: int


# ── AI Chat Schemas ──
class ChatRequest(BaseModel):
    message: str
    session_id: str  # Bắt buộc — dùng để track Redis session và xóa sau khi trả kết quả


class ChatResponse(BaseModel):
    answer: str
    sources: List[str] = []
    session_id: str


# ── OCR Schemas ──
class OcrResponse(BaseModel):
    """
    Kết quả OCR trả về Frontend.

    🔒 Lưu ý bảo mật (ARCHITECTURE.md + CONTRIBUTING.md):
    - Field extracted_fields CHỈ chứa nhãn (label), KHÔNG chứa giá trị thật
      khi ghi log. Giá trị thật chỉ được truyền qua RAM và trả về trong response.
    - Sau khi response này được gửi, Backend phải xóa session_id khỏi Redis.
    """
    success: bool
    document_type: str
    extracted_fields: Dict[str, str]  # {"Họ và tên": "...", "Số CCCD": "..."}
    summary: str  # Tóm tắt ngắn gọn (không chứa dữ liệu nhạy cảm trực tiếp)
    confidence: float
    processing_time_ms: int
    session_id: str


# ── Document Verification Schemas ──
class DocumentVerificationCheckItem(BaseModel):
    check: str
    status: str  # passed | failed | warning
    note: str


class DocumentVerificationResponse(BaseModel):
    """
    Kết quả thẩm định tính hợp lệ của tài liệu theo thành phần hồ sơ.
    """
    is_valid: bool
    status: str  # passed | rejected
    document_type: str
    expected_document: str
    extracted_fields: Dict[str, str] = {}
    validation_checks: List[DocumentVerificationCheckItem] = []
    errors: List[str] = []
    suggestions: str = ""
    processing_time_ms: int = 0
    session_id: str



# ── User Procedure (Hồ sơ) Schemas ──
class UserProcedureResponse(BaseModel):
    id: int
    procedure_id: int
    procedure_title: str
    progress: int = 0
    status: str = "pending"
    due_date: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SaveUserProcedureRequest(BaseModel):
    procedure_id: int
    progress: Optional[int] = 0
    status: Optional[str] = "pending"
    notes: Optional[str] = None
    due_date: Optional[datetime] = None



# ── Admin Schemas ──

class ProcedureStepCreateSchema(BaseModel):
    """Schema tạo/sửa 1 bước trong thủ tục."""
    index: int
    title: str
    description: str
    duration: Optional[str] = None


class ProcedureCreateRequest(BaseModel):
    """Schema dùng cho Admin: tạo hoặc cập nhật thủ tục hành chính."""
    slug: str
    title: str
    category: str
    category_slug: str
    description: str
    steps: List[ProcedureStepCreateSchema] = []
    documents: List[str] = []
    processing_time: str = ""
    fee: str = "Miễn phí"
    agency: str = ""
    level: str = "Cấp xã/phường"
    tags: List[str] = []
    is_published: bool = True


class SyncLegalDocRequest(BaseModel):
    """Schema Admin: đồng bộ văn bản pháp luật vào Vector DB."""
    content: str          # Toàn văn văn bản
    source: str           # Tên văn bản, VD: "Nghị định 13/2023/NĐ-CP"
    document_type: str = "Văn bản pháp luật"  # Nghị định, Thông tư, Luật, ...


class AdminSyncStatusResponse(BaseModel):
    """Trạng thái kết nối Vector DB — trả về cho Admin Dashboard."""
    qdrant_host: str
    collection: str
    status: str  # "connected" | "not_initialized" | "error"


# ── Legal Document & Crawler Schemas ──
class LegalDocumentResponse(BaseModel):
    id: int
    doc_number: str
    title: str
    slug: str
    doc_type: str
    category: str
    agency: Optional[str] = None
    issue_date: Optional[str] = None
    effective_date: Optional[str] = None
    signer: Optional[str] = None
    status: str
    summary: Optional[str] = None
    excerpt: Optional[str] = None
    content_text: Optional[str] = None
    original_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class LegalDocumentListResponse(BaseModel):
    items: List[LegalDocumentResponse]
    total: int
    page: int
    limit: int


class CrawlRequest(BaseModel):
    category: Optional[str] = None  # None = cào văn bản mới chung, hoặc slug category như 'Bat-dong-san'
    limit: int = 10
    save_to_db: bool = True
    sync_to_rag: bool = True


class CrawlResponse(BaseModel):
    success: bool
    crawled_count: int
    saved_to_db_count: int
    synced_to_rag_count: int
    message: str
    items: List[Dict[str, Any]] = []

