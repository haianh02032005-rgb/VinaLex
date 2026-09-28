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
from backend.api.legal_documents import router as legal_docs_router
from backend.api.dvc_documents import router as dvc_docs_router
from backend.api.locations import router as locations_router


app = FastAPI(
    title="VinaLex API",
    description="Nền tảng Tư vấn Pháp lý & Thủ tục Hành chính — Backend FastAPI",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS — cho phép Frontend kết nối từ mọi domain (localhost, Vercel, Cloudflare Tunnel, chatgpt.site...)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type", "Content-Length"],
)

# ── Đăng ký các Router ──
app.include_router(procedures_router,   prefix="/api/v1/procedures",      tags=["Thủ tục"])
app.include_router(legal_docs_router,   prefix="/api/v1/legal-documents", tags=["Văn bản pháp luật & Thông tư, Nghị định"])
app.include_router(dvc_docs_router,     prefix="/api/v1/dvc-documents",   tags=["Hồ sơ & PDF DVC Quốc Gia"])
app.include_router(locations_router,    prefix="/api/v1/locations",       tags=["Địa điểm & Bản đồ Cơ quan Hành chính"])
app.include_router(ai_router,           prefix="/api/v1/ai",              tags=["AI & OCR"])
app.include_router(auth_router,         prefix="/api/v1/auth",            tags=["Auth"])
app.include_router(admin_router,        prefix="/api/v1/admin",           tags=["Admin CMS"])



@app.get("/", tags=["Root"])
async def root():
    """Trang chủ API VinaLex."""
    return {
        "service": "VinaLex API",
        "status": "online",
        "docs_url": "/api/docs",
        "health_check": "/api/v1/health",
        "version": "1.0.0",
    }


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    """Kiểm tra trạng thái server."""
    return {"status": "ok", "service": "VinaLex API"}
