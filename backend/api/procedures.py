"""
VinaLex — API Routes: Thủ tục Hành chính

Tuân thủ README.md §5: backend/api/ = Các routes (thủ tục, users, ai_chat, upload_ocr)
Endpoint prefix: /api/v1/procedures (đăng ký trong main.py)

Phần Admin CRUD (POST/PUT/DELETE) được bảo vệ bằng X-Admin-Key header.
"""

import os
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional

from backend.db.postgres import get_db
from backend.models.procedure import ProcedureModel
from backend.models.schemas import ProcedureResponse, ProcedureListResponse, ProcedureCreateRequest
from backend.core.config import settings
from backend.services.pdf_service import PdfTemplateService, sanitize_document_name


router = APIRouter()
_pdf_service = PdfTemplateService()


def _verify_admin_key(x_admin_key: Optional[str] = Header(None, description="Admin API Key")) -> None:
    """Xác thực Admin Key từ header X-Admin-Key."""
    if not x_admin_key or x_admin_key != settings.ADMIN_SECRET_KEY:
        raise HTTPException(status_code=403, detail="Không có quyền truy cập Admin")


import json
from datetime import datetime


def _load_fallback_procedures() -> list:
    """Đọc dữ liệu thủ tục dự phòng từ cả dvc_procedures.json và crawled_procedures.json nếu database offline."""
    items = []
    seen_slugs = set()
    idx = 1
    for filename in ["dvc_procedures.json", "crawled_procedures.json"]:
        file_path = os.path.join("data", filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_items = json.load(f)
                for p in raw_items:
                    slug = p.get("slug")
                    if not slug or slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                    item = dict(p)
                    item["id"] = idx
                    idx += 1
                    item["updated_at"] = datetime.utcnow()
                    items.append(item)
            except Exception:
                pass
    return items


import re
import unicodedata


def _strip_accents(text: str) -> str:
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
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

STOP_WORDS = {
    "thu", "tuc", "lam", "xin", "cap", "cho", "cua", "tai", "o", "ve",
    "giay", "va", "cac", "mot", "nhung", "duoc", "co", "la", "toi", "muon",
    "can", "hoi", "theo", "den", "tu", "trong", "de", "ngay", "nam"
}

def _has_word(pattern: str, text: str) -> bool:
    """Kiểm tra cụm từ hoặc từ khóa có xuất hiện nguyên vẹn theo ranh giới từ (tránh khớp nhầm từ con)."""
    if not pattern or not text:
        return False
    return bool(re.search(r'(?:\b|^)' + re.escape(pattern) + r'(?:\b|$)', text))

COMPOUND_PHRASES = [
    "khai sinh", "khai tu", "ket hon", "ly hon", "tam tru", "thuong tru",
    "ho khau", "can cuoc", "can cuoc cong dan", "chung minh nhan dan",
    "so do", "so hong", "quyen su dung dat", "gcnqsdd",
    "bang lai", "bang lai xe", "giay phep lai xe", "dang ky xe", "bien so xe",
    "thanh lap cong ty", "dang ky kinh doanh", "dang ky doanh nghiep",
    "bao hiem xa hoi", "bhxh", "bao hiem y te", "bhyt", "that nghiep",
    "ho chieu", "visa", "xuat nhap canh", "ly lich tu phap",
    "thue thu nhap", "thue tncn", "quyet toan thue", "ma so thue",
    "giay phep xay dung", "chuyen nhuong", "tang cho", "thua ke"
]

SYNONYMS = [
    (["khai sinh", "giay khai sinh"], ["khai sinh", "chung sinh", "dang ky khai sinh"]),
    (["can cuoc", "cccd", "chung minh", "cmnd"], ["can cuoc", "cccd", "vneid", "dinh danh"]),
    (["so do", "so hong", "gcnqsdd"], ["so do", "so hong", "quyen su dung dat", "gcnqsdd", "giay chung nhan quyen su dung dat"]),
    (["dat dai", "nha dat"], ["dat dai", "nha dat", "dia chinh", "thua dat", "bat dong san"]),
    (["ket hon", "hon nhan"], ["ket hon", "hon nhan", "tinh trang hon nhan", "hon thu"]),
    (["ly hon"], ["ly hon", "don phuong ly hon", "thuan tinh ly hon"]),
    (["bang lai", "gplx", "lai xe"], ["bang lai", "lai xe", "gplx", "giay phep lai xe", "doi bang lai"]),
    (["tam tru", "ho khau", "thuong tru"], ["tam tru", "ho khau", "thuong tru", "cu tru", "so ho khau"]),
    (["thue", "thue tncn", "quyet toan thue"], ["thue", "quyet toan", "dang ky thue", "ma so thue", "ke khai thue", "thue tncn", "thue gtgt"]),
    (["thanh lap cong ty", "dang ky doanh nghiep"], ["thanh lap", "doanh nghiep", "cong ty", "kinh doanh", "giay phep kinh doanh"]),
    (["bao hiem xa hoi", "bhxh"], ["bao hiem xa hoi", "bhxh", "so bhxh", "che do bhxh"]),
]

def filter_and_rank_procedures(items: list, search: Optional[str] = None, category: Optional[str] = None) -> list:
    """Lọc và chấm điểm xếp hạng thủ tục: Loại bỏ 100% thủ tục không khớp từ khóa (Hard Pruning Filter)."""
    filtered = items
    if category:
        cat_clean = _strip_accents(category)
        filtered = [
            p for p in filtered
            if _strip_accents(p.get("category_slug", "") if isinstance(p, dict) else getattr(p, "category_slug", "")) == cat_clean
            or _strip_accents(p.get("category", "") if isinstance(p, dict) else getattr(p, "category", "")) == cat_clean
        ]

    if not search or not search.strip():
        # Không tìm kiếm -> sắp xếp theo lượt xem giảm dần
        return sorted(
            filtered,
            key=lambda p: (p.get("view_count", 0) if isinstance(p, dict) else getattr(p, "view_count", 0)) or 0,
            reverse=True
        )

    s = search.lower().strip()
    s_clean = _strip_accents(s)

    raw_tokens = [t for t in re.split(r"[\s,\.\?\!\:\;]+", s_clean) if t]
    search_tokens = [t for t in raw_tokens if t not in STOP_WORDS and len(t) > 1]
    if not search_tokens:
        search_tokens = raw_tokens

    scored_items = []
    for p in filtered:
        title = (p.get("title") if isinstance(p, dict) else getattr(p, "title", "")) or ""
        desc = (p.get("description") if isinstance(p, dict) else getattr(p, "description", "")) or ""
        tags = (p.get("tags") if isinstance(p, dict) else getattr(p, "tags", [])) or []
        cat_slug = (p.get("category_slug") if isinstance(p, dict) else getattr(p, "category_slug", "")) or ""
        view_count = (p.get("view_count") if isinstance(p, dict) else getattr(p, "view_count", 0)) or 0

        title_lower = title.lower()
        title_clean = _strip_accents(title)
        tags_str = _safe_join(tags).lower()
        tags_clean = _strip_accents(tags_str)
        desc_clean = _strip_accents(desc)

        # ── TẦNG 1: BỘ LỌC BẮT BUỘC (Hard Pruning Filter) ──
        matched_compounds = [cp for cp in COMPOUND_PHRASES if _has_word(cp, s_clean)]
        if matched_compounds:
            compound_hit = False
            for cp in matched_compounds:
                if _has_word(cp, title_clean) or _has_word(cp, tags_clean):
                    compound_hit = True
                    break
                for q_pats, t_pats in SYNONYMS:
                    if any(qp in cp for qp in q_pats):
                        if any(_has_word(tp, title_clean) or _has_word(tp, tags_clean) for tp in t_pats):
                            compound_hit = True
                            break
                if compound_hit:
                    break
            is_strict_match = compound_hit
        else:
            exact_in_title_or_tags = _has_word(s_clean, title_clean) or _has_word(s_clean, tags_clean)
            all_tokens_in_title_or_tags = bool(search_tokens) and all(
                (_has_word(t, title_clean) or _has_word(t, tags_clean)) for t in search_tokens
            )

            synonym_match = False
            for q_pats, t_pats in SYNONYMS:
                if any(qp in s_clean for qp in q_pats):
                    for tp in t_pats:
                        if _has_word(tp, title_clean) or _has_word(tp, tags_clean):
                            synonym_match = True
                            break

            multi_token_partial = False
            if len(search_tokens) >= 2:
                has_at_least_one_in_title = any(_has_word(t, title_clean) or _has_word(t, tags_clean) for t in search_tokens)
                has_all_in_full = all(_has_word(t, title_clean) or _has_word(t, tags_clean) or _has_word(t, desc_clean) for t in search_tokens)
                if has_at_least_one_in_title and has_all_in_full:
                    multi_token_partial = True

            is_strict_match = (
                exact_in_title_or_tags
                or all_tokens_in_title_or_tags
                or synonym_match
                or multi_token_partial
            )

        # NẾU KHÔNG THỎA MÃN TẦNG 1 -> LOẠI BỎ TRIỆT ĐỂ
        if not is_strict_match:
            continue

        # ── TẦNG 2: CHẤM ĐIỂM XẾP HẠNG (Relevance Ranking) ──
        score = 0.0

        if s in title_lower:
            score += 150.0
        elif _has_word(s_clean, title_clean):
            score += 120.0

        if _has_word(s_clean, tags_clean):
            score += 70.0

        for cp in matched_compounds:
            if _has_word(cp, title_clean):
                score += 80.0
            if _has_word(cp, tags_clean):
                score += 50.0

        for t in search_tokens:
            if _has_word(t, title_clean):
                score += 20.0
            if _has_word(t, tags_clean):
                score += 15.0
            if _has_word(t, desc_clean):
                score += 5.0

        for q_pats, t_pats in SYNONYMS:
            if any(qp in s_clean for qp in q_pats):
                if any(qp in _strip_accents(cat_slug) for qp in ["dat-dai", "ho-tich", "doanh-nghiep", "thue", "giao-thong"]):
                    score += 15.0

        scored_items.append((score, view_count, p))

    scored_items.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [x[2] for x in scored_items]


@router.get("", response_model=ProcedureListResponse)
async def get_procedures(
    category: Optional[str] = Query(None, description="Lọc theo danh mục"),
    search: Optional[str] = Query(None, description="Tìm kiếm theo tên/từ khóa"),
    page: int = Query(1, ge=1),
    limit: int = Query(12, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """
    Lấy danh sách thủ tục hành chính có phân trang và lọc từ khóa.
    Áp dụng thuật toán 2 tầng: Loại bỏ 100% thủ tục không khớp từ khóa (Hard Pruning Filter).
    Tự động fallback đọc từ database / JSON an toàn.
    """
    try:
        if search:
            # Khi có từ khóa tìm kiếm: Nạp các thủ tục khả dĩ từ DB để áp dụng Hard Filter & Ranking
            query = select(ProcedureModel).where(ProcedureModel.is_published == True)
            if category:
                query = query.where(ProcedureModel.category_slug == category)
            result = await db.execute(query)
            all_records = result.scalars().all()
            
            # Áp dụng thuật toán 2 tầng
            ranked_records = filter_and_rank_procedures(all_records, search=search, category=category)
            total = len(ranked_records)
            offset = (page - 1) * limit
            paged = ranked_records[offset : offset + limit]

            return ProcedureListResponse(
                items=[ProcedureResponse.model_validate(p) for p in paged],
                total=total,
                page=page,
                limit=limit,
            )
        else:
            # Không tìm kiếm: Thực hiện phân trang trực tiếp trên SQL
            query = select(ProcedureModel).where(ProcedureModel.is_published == True)
            if category:
                query = query.where(ProcedureModel.category_slug == category)

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
        # Fallback offline khi DB offline
        fallback_data = _load_fallback_procedures()
        ranked = filter_and_rank_procedures(fallback_data, search=search, category=category)
        total = len(ranked)
        offset = (page - 1) * limit
        paged = ranked[offset : offset + limit]

        return ProcedureListResponse(
            items=[ProcedureResponse(**p) for p in paged],
            total=total,
            page=page,
            limit=limit,
        )


@router.get("/download-template")
async def download_procedure_document_template(
    doc_name: str = Query(..., description="Tên mục giấy tờ cần tải biểu mẫu"),
    title: Optional[str] = Query("", description="Tên thủ tục hành chính"),
    slug: Optional[str] = Query("", description="Slug của thủ tục"),
    category: Optional[str] = Query("", description="Lĩnh vực thủ tục"),
    agency: Optional[str] = Query("", description="Cơ quan có thẩm quyền giải quyết"),
    preview: Optional[bool] = Query(False, description="Nếu true, hiển thị xem trước inline"),
    db: AsyncSession = Depends(get_db),
):
    """
    Sinh và tải xuống hoặc xem trước file PDF biểu mẫu hành chính chuẩn pháp lý Việt Nam.
    Tự động truy xuất thông tin thủ tục để định danh biểu mẫu chuyên ngành chuẩn xác nhất.
    """
    if slug and (not title or not category or not agency):
        try:
            result = await db.execute(select(ProcedureModel).where(ProcedureModel.slug == slug))
            proc_obj = result.scalar_one_or_none()
            if proc_obj:
                title = title or proc_obj.title
                category = category or proc_obj.category
                agency = agency or proc_obj.agency
        except Exception:
            pass

    clean_name = sanitize_document_name(doc_name)
    pdf_bytes = _pdf_service.generate_document_pdf(
        doc_name=clean_name,
        procedure_title=title or "Thủ tục hành chính",
        slug=slug or "",
        category=category or "",
        agency=agency or "",
    )

    full_str = f"{clean_name} {title or ''} {slug or ''} {category or ''}".lower()
    safe_raw = _strip_accents(full_str)

    if any(k in safe_raw for k in ["11/dk", "11-dk", "xac dinh lai", "bien dong"]):
        filename = "don_dang_ky_bien_dong_dat_dai_mau_11_dk.pdf"
    elif any(k in safe_raw for k in ["04/dk", "04-dk", "dang ky dat dai", "cap gcn", "so do"]) and any(k in safe_raw for k in ["dat", "dia chinh", "so do"]):
        filename = "don_dang_ky_cap_gcn_dat_dai_mau_04_dk.pdf"
    elif any(k in safe_raw for k in ["doanh nghiep", "cong ty", "ho kinh doanh"]):
        filename = "giay_de_nghi_dang_ky_doanh_nghiep.pdf"
    elif any(k in safe_raw for k in ["xay dung", "gpxd"]):
        filename = "don_de_nghi_cap_giay_phep_xay_dung_mau_01.pdf"
    elif any(k in safe_raw for k in ["lai xe", "gplx", "bang lai"]):
        filename = "don_de_nghi_doi_gplx_phu_luc_19.pdf"
    elif any(k in safe_raw for k in ["kham benh", "chua benh", "hanh nghe y"]):
        filename = "don_de_nghi_cap_giay_phep_hanh_nghe_y.pdf"
    elif any(k in safe_raw for k in ["bao hiem xa hoi", "bhxh", "14-hsb"]):
        filename = "don_de_nghi_huong_che_do_bhxh_mau_14_hsb.pdf"
    elif "ket hon" in safe_raw:
        filename = "to_khai_dang_ky_ket_hon.pdf"
    elif "khai sinh" in safe_raw:
        filename = "to_khai_dang_ky_khai_sinh.pdf"
    elif "chung sinh" in safe_raw:
        filename = "giay_cam_doan_ve_viec_sinh_con.pdf"
    elif any(k in safe_raw for k in ["cu tru", "ho khau", "tam tru", "thuong tru"]):
        filename = "to_khai_thay_doi_thong_tin_cu_tru_ct01.pdf"
    elif any(k in safe_raw for k in ["can cuoc", "cccd", "cmnd"]):
        filename = "to_khai_can_cuoc_dc01.pdf"
    elif any(k in safe_raw for k in ["thue", "qtt", "tncn"]):
        filename = "to_khai_quyet_toan_thue_tncn_mau_02_qtt.pdf"
    elif any(k in safe_raw for k in ["lao dong", "giay phep lao dong", "khong thuoc dien"]):
        filename = "van_ban_de_nghi_xac_nhan_khong_thuoc_dien_cap_gpld_mau_09.pdf"
    else:
        safe_clean = re.sub(r"[^a-zA-Z0-9]+", "_", _strip_accents(clean_name)).strip("_")[:40]
        filename = f"don_de_nghi_{safe_clean}.pdf" if safe_clean else "bieu_mau_hanh_chinh.pdf"

    disposition = "inline" if preview else "attachment"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
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

