"""
VinaLex — Backend Entry Point (FastAPI)

Tuân thủ ARCHITECTURE.md:
- Lớp 2: Giao tiếp & Điều phối (Backend / API Gateway)
- FastAPI (Python 3.11) + Uvicorn
- Xử lý bất đồng bộ (async/await)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.api.procedures import router as procedures_router
from backend.api.ai import router as ai_router
from backend.api.auth import router as auth_router
from backend.api.admin import router as admin_router


app = FastAPI(
    title="VinaLex API",
    description="Nền tảng Tư vấn Pháp lý & Thủ tục Hành chính — Backend FastAPI",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — cho phép Frontend (Next.js) kết nối
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Đăng ký các Router ──
app.include_router(procedures_router, prefix="/api/v1/procedures", tags=["Thủ tục"])
app.include_router(ai_router,         prefix="/api/v1/ai",         tags=["AI & OCR"])
app.include_router(auth_router,       prefix="/api/v1/auth",       tags=["Auth"])
app.include_router(admin_router,      prefix="/api/v1/admin",      tags=["Admin CMS"])


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """Kiểm tra trạng thái server."""
    return {"status": "ok", "service": "VinaLex API"}
