"""
VinaLex — API Routes: Admin CMS & Vector DB Sync

Endpoint prefix: /api/v1/admin (đăng ký trong main.py)

🔒 Bảo mật: Tất cả endpoint đều yêu cầu header X-Admin-Key khớp với
   settings.ADMIN_SECRET_KEY (biến môi trường ADMIN_SECRET_KEY trong .env).

Chức năng:
  - GET  /api/v1/admin/procedures     — Lấy toàn bộ thủ tục (kể cả chưa publish)
  - POST /api/v1/admin/sync-legal-doc — Đồng bộ văn bản pháp luật vào Vector DB
  - GET  /api/v1/admin/sync-status    — Kiểm tra trạng thái Vector DB (Qdrant)
  - GET  /api/v1/admin/stats          — Thống kê tổng quan hệ thống
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.postgres import get_db
from backend.models.procedure import ProcedureModel, LegalDocumentModel
from backend.models.schemas import (
    ProcedureResponse,
    ProcedureListResponse,
    SyncLegalDocRequest,
    AdminSyncStatusResponse,
    LegalDocumentResponse,
    LegalDocumentListResponse,
    CrawlRequest,
    CrawlResponse,
)
from backend.services.admin_service import AdminService
from backend.services.crawler_service import ThuvienphapluatCrawler
from backend.core.config import settings



router = APIRouter()
_admin_service = AdminService()


# ── Dependency: Xác thực Admin Key ──

def _verify_admin_key(x_admin_key: str = Header(..., description="Admin API Key")) -> None:
    """Xác thực Admin Key từ header X-Admin-Key."""
    if x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập Admin")


# ── Endpoints ──

@router.get("/procedures", response_model=ProcedureListResponse)
async def admin_get_all_procedures(
    page: int = 1,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_admin_key),
):
    """
    [Admin] Lấy toàn bộ thủ tục hành chính — bao gồm cả bài chưa publish.

    Khác với GET /api/v1/procedures (chỉ trả về is_published=True),
    endpoint này trả về tất cả để Admin quản lý.
    """
    count_result = await db.execute(select(func.count()).select_from(ProcedureModel))
    total = count_result.scalar_one()

    offset = (page - 1) * limit
    result = await db.execute(
        select(ProcedureModel)
        .order_by(ProcedureModel.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    procedures = result.scalars().all()

    return ProcedureListResponse(
        items=[ProcedureResponse.model_validate(p) for p in procedures],
        total=total,
        page=page,
        limit=limit,
    )


@router.post("/sync-legal-doc")
async def admin_sync_legal_document(
    request: SyncLegalDocRequest,
    _: None = Depends(_verify_admin_key),
):
    """
    [Admin] Đồng bộ văn bản pháp luật mới vào Qdrant Vector DB.

    AdminService sẽ:
      1. Phân tách văn bản thành các chunk (RecursiveCharacterTextSplitter)
      2. Embed từng chunk bằng PhoBERT/Vietnamese-SBERT
      3. Lưu vào Qdrant collection 'vinalex_legal_docs'

    Chatbot RAG sẽ tự động có thể tra cứu văn bản mới ngay lập tức.
    """
    try:
        num_chunks = await _admin_service.sync_legal_documents(
            content=request.content,
            source=request.source,
            document_type=request.document_type,
        )
        return {
            "success": True,
            "message": f"Đã đồng bộ '{request.source}' thành công",
            "chunks_synced": num_chunks,
            "document_type": request.document_type,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi đồng bộ Vector DB: {str(e)}",
        )


@router.get("/sync-status", response_model=AdminSyncStatusResponse)
async def admin_get_sync_status(
    _: None = Depends(_verify_admin_key),
):
    """[Admin] Kiểm tra trạng thái kết nối Qdrant Vector DB."""
    try:
        status = _admin_service.get_sync_status()
        return AdminSyncStatusResponse(**status)
    except Exception as e:
        return AdminSyncStatusResponse(
            qdrant_host=settings.QDRANT_HOST,
            collection="vinalex_legal_docs",
            status="error",
        )


@router.get("/stats")
async def admin_get_stats(
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_admin_key),
):
    """[Admin] Thống kê tổng quan hệ thống."""
    # Tổng số thủ tục
    total_result = await db.execute(select(func.count()).select_from(ProcedureModel))
    total_procedures = total_result.scalar_one()

    # Số thủ tục đã publish
    published_result = await db.execute(
        select(func.count()).select_from(ProcedureModel).where(ProcedureModel.is_published == True)
    )
    published_procedures = published_result.scalar_one()

    # Tổng lượt xem
    views_result = await db.execute(select(func.sum(ProcedureModel.view_count)))
    total_views = views_result.scalar_one() or 0

    # Trạng thái Vector DB
    sync_status = _admin_service.get_sync_status()

    return {
        "procedures": {
            "total": total_procedures,
            "published": published_procedures,
            "draft": total_procedures - published_procedures,
        },
        "total_views": total_views,
        "vector_db": sync_status,
    }


@router.post("/crawler/run", response_model=CrawlResponse)
async def admin_crawl_tvpl(
    request: CrawlRequest,
    _: None = Depends(_verify_admin_key),
):
    """
    [Admin] Kích hoạt cào dữ liệu từ Thư Viện Pháp Luật (thuvienphapluat.vn).
    """
    try:
        crawler = ThuvienphapluatCrawler()
        categories = [request.category] if request.category else ["Bat-dong-san", "Doanh-nghiep", "Lao-dong-Tien-luong"]
        limit_per_cat = max(1, request.limit // len(categories))

        crawled_docs = crawler.crawl_legal_documents(categories=categories, limit_per_cat=limit_per_cat)
        crawler.save_to_json(crawled_docs, "crawled_legal_docs.json")

        saved_to_db = 0
        synced_to_rag = 0

        if request.save_to_db and crawled_docs:
            saved_to_db = await crawler.save_legal_documents_to_db(crawled_docs)

        if request.sync_to_rag and crawled_docs:
            synced_to_rag = await crawler.sync_to_vector_db(crawled_docs)

        return CrawlResponse(
            success=True,
            crawled_count=len(crawled_docs),
            saved_to_db_count=saved_to_db,
            synced_to_rag_count=synced_to_rag,
            message=f"Đã thu thập thành công {len(crawled_docs)} văn bản từ Thư Viện Pháp Luật",
            items=[{"doc_number": d.get("doc_number"), "title": d["title"], "slug": d["slug"]} for d in crawled_docs],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi quá trình cào dữ liệu: {str(e)}")


@router.get("/legal-documents", response_model=LegalDocumentListResponse)
async def admin_get_legal_documents(
    page: int = 1,
    limit: int = 20,
    category: str = None,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_admin_key),
):
    """
    [Admin] Danh sách các văn bản pháp luật đã thu thập trong PostgreSQL.
    """
    query = select(LegalDocumentModel)
    if category:
        query = query.where(LegalDocumentModel.category == category)

    count_query = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_query)
    total = total_res.scalar_one()

    offset = (page - 1) * limit
    result = await db.execute(
        query.order_by(LegalDocumentModel.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    docs = result.scalars().all()

    return LegalDocumentListResponse(
        items=[LegalDocumentResponse.model_validate(d) for d in docs],
        total=total,
        page=page,
        limit=limit,
    )

