"""
VinaLex — API Routes: Thủ tục Hành chính

Tuân thủ README.md §5: backend/api/ = Các routes (thủ tục, users, ai_chat, upload_ocr)
Endpoint prefix: /api/v1/procedures (đăng ký trong main.py)

Phần Admin CRUD (POST/PUT/DELETE) được bảo vệ bằng X-Admin-Key header.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from backend.db.postgres import get_db
from backend.models.procedure import ProcedureModel
from backend.models.schemas import ProcedureResponse, ProcedureListResponse, ProcedureCreateRequest
from backend.core.config import settings


router = APIRouter()


def _verify_admin_key(x_admin_key: str = Header(..., description="Admin API Key")) -> None:
    """Xác thực Admin Key từ header X-Admin-Key."""
    if x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập Admin")


import json
from datetime import datetime


def _load_fallback_procedures() -> list:
    """Đọc dữ liệu thủ tục dự phòng từ file JSON nếu database offline."""
    file_path = os.path.join("data", "crawled_procedures.json")
    items = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_items = json.load(f)
            for idx, p in enumerate(raw_items, 1):
                item = dict(p)
                item["id"] = idx
                item["updated_at"] = datetime.utcnow()
                items.append(item)
        except Exception:
            pass
    return items


@router.get("", response_model=ProcedureListResponse)
async def get_procedures(
    category: Optional[str] = Query(None, description="Lọc theo danh mục"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên/từ khóa"),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy danh sách thủ tục hành chính có phân trang và lọc.
    Tự động fallback đọc từ crawled_procedures.json nếu PostgreSQL chưa bật.
    """
    try:
        query = select(ProcedureModel).where(ProcedureModel.is_published == True)

        if category:
            query = query.where(ProcedureModel.category_slug == category)

        if search:
            search_filter = f"%{search}%"
            query = query.where(
                ProcedureModel.title.ilike(search_filter) |
                ProcedureModel.description.ilike(search_filter)
            )

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar_one()

        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).order_by(ProcedureModel.view_count.desc())

        result = await db.execute(query)
        procedures = result.scalars().all()

        return ProcedureListResponse(
            items=[ProcedureResponse.model_validate(p) for p in procedures],
            total=total,
            page=page,
            limit=limit,
        )
    except Exception:
        # Fallback offline khi PostgreSQL chưa kết nối
        fallback_data = _load_fallback_procedures()
        filtered = fallback_data

        if category:
            filtered = [p for p in filtered if p.get("category_slug") == category]

        if search:
            import re
            import unicodedata

            def _strip_accents(text: str) -> str:
                text = text.replace("\u0111", "d").replace("\u0110", "D")
                nfd = unicodedata.normalize("NFD", text)
                return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()

            def _safe_join(arr) -> str:
                if not arr:
                    return ""
                parts = []
                for item in arr:
                    if isinstance(item, str):
                        parts.append(item)
                    elif isinstance(item, dict):
                        parts.append(item.get("title", ""))
                        parts.append(item.get("description", ""))
                return " ".join(filter(None, parts))

            s = search.lower().strip()
            s_clean = _strip_accents(s)

            stop_words = {
                "th\u1ee7", "t\u1ee5c", "l\u00e0m", "xin", "c\u1ea5p", "cho", "c\u1ee7a",
                "t\u1ea1i", "\u1edf", "v\u1ec1", "gi\u1ea5y", "v\u00e0", "c\u00e1c", "m\u1ed9t",
                "nh\u1eefng", "\u0111\u01b0\u1ee3c", "c\u00f3", "l\u00e0", "t\u00f4i", "mu\u1ed1n", "c\u1ea7n", "h\u1ecfi",
            }
            raw_tokens = [t for t in re.split(r"[\s,\.\?\!\:\;]+", s) if t]
            keywords = [t for t in raw_tokens if t not in stop_words and len(t) > 1]
            tokens = keywords if keywords else raw_tokens

            synonyms = [
                (["khai sinh"], ["khai sinh", "chung sinh"]),
                (["can cuoc", "cccd", "chung minh"], ["can cuoc", "cccd", "vneid"]),
                (["so do", "so hong", "dat dai", "quyen su dung dat"], ["so do", "so hong", "quyen su dung dat", "gcnqsdd", "dat dai", "nha dat"]),
                (["ket hon", "hon nhan"], ["ket hon", "hon nhan", "ly hon"]),
                (["bang lai", "gplx", "lai xe"], ["bang lai", "lai xe", "gplx", "giay phep lai xe"]),
                (["tam tru", "ho khau"], ["tam tru", "ho khau", "cu tru", "thuong tru"]),
                (["thue", "thue tncn", "quyet toan thue"], ["thue", "quyet toan", "dang ky thue", "ma so thue", "ke khai thue"]),
                (["thanh lap cong ty", "dang ky doanh nghiep"], ["thanh lap", "doanh nghiep", "cong ty", "kinh doanh"]),
            ]

            def _score_proc(p):
                title = (p.get("title") or "").lower()
                desc = (p.get("description") or "").lower()
                tags = _safe_join(p.get("tags")).lower()
                docs = _safe_join(p.get("documents")).lower()
                text = f"{title} {desc} {tags} {docs}"
                text_clean = _strip_accents(text)
                title_clean = _strip_accents(title)

                score = 0
                if s in title:
                    score += 100
                elif s_clean in title_clean:
                    score += 80

                if s in text:
                    score += 30
                elif s_clean in text_clean:
                    score += 20

                if tokens and all(_strip_accents(t) in text_clean for t in tokens):
                    score += 40

                for query_pats, text_pats in synonyms:
                    q_hit = any(qp in s_clean for qp in query_pats)
                    t_hit = any(tp in text_clean for tp in text_pats)
                    if q_hit and t_hit:
                        score += 60

                return score

            scored_items = []
            for p in filtered:
                sc = _score_proc(p)
                if sc > 0:
                    scored_items.append((sc, p))

            scored_items.sort(key=lambda x: (x[0], x[1].get("view_count", 0)), reverse=True)
            filtered = [item[1] for item in scored_items]

        total = len(filtered)
        offset = (page - 1) * limit
        paged = filtered[offset : offset + limit]

        return ProcedureListResponse(
            items=[ProcedureResponse(**p) for p in paged],
            total=total,
            page=page,
            limit=limit,
        )


@router.get("/{slug}", response_model=ProcedureResponse)
async def get_procedure_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Lấy chi tiết một thủ tục hành chính theo slug."""
    try:
        result = await db.execute(
            select(ProcedureModel).where(
                ProcedureModel.slug == slug,
                ProcedureModel.is_published == True,
            )
        )
        procedure = result.scalar_one_or_none()
        if procedure:
            procedure.view_count += 1
            await db.commit()
            return ProcedureResponse.model_validate(procedure)
    except Exception:
        pass

    # Fallback tìm trong file JSON
    fallback_data = _load_fallback_procedures()
    for p in fallback_data:
        if p.get("slug") == slug:
            return ProcedureResponse(**p)

    raise HTTPException(status_code=404, detail="Không tìm thấy thủ tục")



# ── Admin CRUD ── (Yêu cầu X-Admin-Key header)

@router.post("", response_model=ProcedureResponse, status_code=201)
async def admin_create_procedure(
    request: ProcedureCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_admin_key),
):
    """[Admin] Tạo thủ tục hành chính mới."""
    # Kiểm tra slug trùng
    result = await db.execute(
        select(ProcedureModel).where(ProcedureModel.slug == request.slug)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{request.slug}' đã tồn tại")

    new_proc = ProcedureModel(
        slug=request.slug,
        title=request.title,
        category=request.category,
        category_slug=request.category_slug,
        description=request.description,
        steps=[s.model_dump() for s in request.steps],
        documents=request.documents,
        processing_time=request.processing_time,
        fee=request.fee,
        agency=request.agency,
        level=request.level,
        tags=request.tags,
        is_published=request.is_published,
    )
    db.add(new_proc)
    await db.commit()
    await db.refresh(new_proc)
    return ProcedureResponse.model_validate(new_proc)


@router.put("/{slug}", response_model=ProcedureResponse)
async def admin_update_procedure(
    slug: str,
    request: ProcedureCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_admin_key),
):
    """[Admin] Cập nhật thủ tục hành chính theo slug."""
    result = await db.execute(
        select(ProcedureModel).where(ProcedureModel.slug == slug)
    )
    procedure = result.scalar_one_or_none()
    if procedure is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thủ tục")

    procedure.title = request.title
    procedure.category = request.category
    procedure.category_slug = request.category_slug
    procedure.description = request.description
    procedure.steps = [s.model_dump() for s in request.steps]
    procedure.documents = request.documents
    procedure.processing_time = request.processing_time
    procedure.fee = request.fee
    procedure.agency = request.agency
    procedure.level = request.level
    procedure.tags = request.tags
    procedure.is_published = request.is_published

    await db.commit()
    await db.refresh(procedure)
    return ProcedureResponse.model_validate(procedure)


@router.delete("/{slug}", status_code=204)
async def admin_delete_procedure(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(_verify_admin_key),
):
    """[Admin] Xóa thủ tục hành chính theo slug."""
    result = await db.execute(
        select(ProcedureModel).where(ProcedureModel.slug == slug)
    )
    procedure = result.scalar_one_or_none()
    if procedure is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy thủ tục")

    await db.delete(procedure)
    await db.commit()

