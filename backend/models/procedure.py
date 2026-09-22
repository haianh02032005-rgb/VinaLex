"""
VinaLex — SQLAlchemy ORM Models

Tuân thủ ARCHITECTURE.md Lớp 4: PostgreSQL lưu dữ liệu hệ thống
- Tài khoản người dùng
- Danh sách thủ tục hành chính
- Bài viết CMS

Quy tắc đặt tên (CONTRIBUTING.md §2.1):
- Class: PascalCase (VD: ProcedureModel, UserModel)
- Cột/thuộc tính: snake_case (VD: created_at, procedure_title)
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.postgres import Base


class UserModel(Base):
    """Tài khoản người dùng."""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    saved_procedures: Mapped[List["UserProcedureModel"]] = relationship(back_populates="user")


class ProcedureModel(Base):
    """Thủ tục hành chính."""
    __tablename__ = "procedures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category_slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    documents: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    processing_time: Mapped[str] = mapped_column(String(100))
    fee: Mapped[str] = mapped_column(String(100))
    agency: Mapped[str] = mapped_column(String(255))
    level: Mapped[str] = mapped_column(String(50))
    tags: Mapped[dict] = mapped_column(JSON, nullable=False, default=list)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserProcedureModel(Base):
    """Hồ sơ người dùng đang theo dõi."""
    __tablename__ = "user_procedures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    procedure_id: Mapped[int] = mapped_column(ForeignKey("procedures.id"), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    status: Mapped[str] = mapped_column(String(50), default="pending")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["UserModel"] = relationship(back_populates="saved_procedures")


class LegalDocumentModel(Base):
    """Văn bản quy phạm pháp luật (thu thập từ Thư Viện Pháp Luật)."""
    __tablename__ = "legal_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_number: Mapped[str] = mapped_column(String(100), index=True, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(100), default="Văn bản pháp luật", index=True)
    category: Mapped[str] = mapped_column(String(100), default="Chung", index=True)
    agency: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    issue_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    effective_date: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    signer: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(100), default="Còn hiệu lực")
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

