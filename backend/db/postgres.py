"""
VinaLex — Kết nối PostgreSQL (Async)

Tuân thủ ARCHITECTURE.md Lớp 4: Lưu trữ & Quản lý Trạng thái
- PostgreSQL: lưu tài khoản người dùng, danh sách thủ tục, bài viết
- Dùng asyncpg để hỗ trợ async/await (không block event loop của FastAPI)
"""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from backend.core.config import settings


# ── Async Engine ──
engine = create_async_engine(
    settings.SQLALCHEMY_DATABASE_URI,
    echo=(settings.APP_ENV == "development"),
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# ── Session Factory ──
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Base class cho tất cả SQLAlchemy ORM models."""
    pass


async def get_db() -> AsyncSession:
    """
    Dependency injection cho FastAPI routes.
    Sử dụng: async with get_db() as db: ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
