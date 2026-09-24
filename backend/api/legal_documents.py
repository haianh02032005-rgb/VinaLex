"""
VinaLex — API Routes: Văn bản quy phạm pháp luật, Thông tư & Nghị định

Cung cấp các endpoint tra cứu, tìm kiếm và trích xuất nội dung Thông tư, Nghị định,
Quyết định, Văn bản hợp nhất cho người dùng đọc trực tiếp.
Tuân thủ yêu cầu: KHÔNG đề xuất thủ tục hành chính trong phân hệ này; KHÔNG can thiệp hệ thống RAG.
"""

import os
import json
import re
import unicodedata
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.postgres import get_db
from backend.models.procedure import LegalDocumentModel
from backend.models.schemas import LegalDocumentResponse, LegalDocumentListResponse

router = APIRouter()


def _strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để đối sánh linh hoạt."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def _has_word(pattern: str, text: str) -> bool:
    """Kiểm tra cụm từ có xuất hiện nguyên vẹn theo ranh giới từ."""
    if not pattern or not text:
        return False
    return bool(re.search(r'(?:\b|^)' + re.escape(pattern) + r'(?:\b|$)', text))


def _extract_excerpt(content: str, query: str, max_len: int = 350) -> str:
    """Trích xuất đoạn văn bản (300-350 ký tự) xung quanh từ khóa tìm kiếm."""
    if not content:
        return ""
    if not query or not query.strip():
        clean_content = " ".join(content.split())
        return clean_content[:max_len] + ("..." if len(clean_content) > max_len else "")

    q_clean = _strip_accents(query.strip())
    content_clean = _strip_accents(content)

    # Thử tìm vị trí xuất hiện của toàn bộ cụm query
    pos = content_clean.find(q_clean)
    
    # Nếu không thấy cụm, thử tìm vị trí của token đầu tiên
    if pos == -1:
        tokens = [t for t in q_clean.split() if len(t) > 2]
        for tok in tokens:
            p = content_clean.find(tok)
            if p != -1:
                pos = p
                break

    if pos == -1:
        clean_content = " ".join(content.split())
        return clean_content[:max_len] + ("..." if len(clean_content) > max_len else "")

    # Lấy cửa sổ xung quanh vị trí tìm thấy
    start = max(0, pos - 80)
    end = min(len(content), pos + max_len - 80)

    snippet = content[start:end].strip()
    clean_snippet = " ".join(snippet.split())

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(content) else ""
    return f"{prefix}{clean_snippet}{suffix}"


def _load_fallback_legal_docs() -> list:
    """Đọc dữ liệu văn bản pháp luật dự phòng từ data/crawled_legal_docs.json."""
    docs_path = os.path.join("data", "crawled_legal_docs.json")
    if os.path.exists(docs_path):
        try:
            with open(docs_path, "r", encoding="utf-8") as f:
                raw_items = json.load(f)
            items = []
            idx = 1
            for d in raw_items:
                item = dict(d)
                item["id"] = idx
                idx += 1
                if not item.get("created_at"):
                    item["created_at"] = datetime.utcnow()
                items.append(item)
            return items
        except Exception:
            pass
    return []


STOP_WORDS = {
    "văn", "bản", "về", "của", "tại", "cho", "và", "hoặc", "ở", "bị", "làm", "được",
    "có", "là", "tôi", "muốn", "cần", "hỏi", "quy", "định", "những", "các", "một", "theo"
}


def filter_and_rank_legal_docs(items: list, search: Optional[str] = None, doc_type: Optional[str] = None, category: Optional[str] = None) -> list:
    """Lọc và chấm điểm xếp hạng văn bản pháp luật theo từ khóa."""
    filtered = items

    # 1. Lọc theo Loại văn bản (Nghị định, Thông tư, Quyết định...)
    if doc_type and doc_type.strip():
        dt_clean = _strip_accents(doc_type.strip())
        filtered = [
            d for d in filtered
            if _strip_accents(d.get("doc_type", "") if isinstance(d, dict) else getattr(d, "doc_type", "")) == dt_clean
        ]

    # 2. Lọc theo Lĩnh vực (category)
    if category and category.strip():
        cat_clean = _strip_accents(category.strip())
        filtered = [
            d for d in filtered
            if cat_clean in _strip_accents(d.get("category", "") if isinstance(d, dict) else getattr(d, "category", ""))
        ]

    # 3. Nếu không có từ khóa tìm kiếm -> Sắp xếp theo ngày ban hành hoặc thời gian mới nhất
    if not search or not search.strip():
        return filtered

    s = search.lower().strip()
    s_clean = _strip_accents(s)
    raw_tokens = [t for t in re.split(r"[\s,\.\?\!\:\;]+", s_clean) if t]
    search_tokens = [t for t in raw_tokens if t not in STOP_WORDS and len(t) > 1]
    if not search_tokens:
        search_tokens = raw_tokens

    scored_items = []
    for d in filtered:
        doc_num = (d.get("doc_number") if isinstance(d, dict) else getattr(d, "doc_number", "")) or ""
        title = (d.get("title") if isinstance(d, dict) else getattr(d, "title", "")) or ""
        content = (d.get("content_text") if isinstance(d, dict) else getattr(d, "content_text", "")) or ""
        summary = (d.get("summary") if isinstance(d, dict) else getattr(d, "summary", "")) or ""
        agency = (d.get("agency") if isinstance(d, dict) else getattr(d, "agency", "")) or ""
        doc_type_val = (d.get("doc_type") if isinstance(d, dict) else getattr(d, "doc_type", "")) or ""

        doc_num_clean = _strip_accents(doc_num)
        title_clean = _strip_accents(title)
        content_clean = _strip_accents(content[:5000])  # Quét 5000 ký tự đầu để tối ưu tốc độ
        summary_clean = _strip_accents(summary)
        doc_type_clean = _strip_accents(doc_type_val)

        # ── TẦNG 1: BỘ LỌC BẮT BUỘC (Hard Pruning Filter) ──
        # Phải khớp số hiệu, tiêu đề, loại văn bản hoặc các từ khóa cốt lõi
        exact_doc_num = s_clean in doc_num_clean or (s.replace(" ", "") in doc_num.lower().replace(" ", ""))
        exact_title = s_clean in title_clean
        all_tokens_in_title = bool(search_tokens) and all(t in title_clean for t in search_tokens)
        all_tokens_in_summary = bool(search_tokens) and all(t in summary_clean for t in search_tokens)
        has_token_in_content = bool(search_tokens) and any(t in content_clean for t in search_tokens)

        is_match = exact_doc_num or exact_title or all_tokens_in_title or all_tokens_in_summary or (has_token_in_content and any(t in title_clean for t in search_tokens))

        if not is_match:
            continue

        # ── TẦNG 2: CHẤM ĐIỂM XẾP HẠNG ──
        score = 0.0
        if exact_doc_num:
            score += 200.0
        if s in title.lower():
            score += 150.0
        elif exact_title:
            score += 120.0
        if all_tokens_in_title:
            score += 60.0

        for t in search_tokens:
            if t in title_clean:
                score += 20.0
            if t in summary_clean:
                score += 10.0
            if t in content_clean:
                score += 5.0

        # Gán excerpt trích xuất trực tiếp
        excerpt = _extract_excerpt(content or summary, s)
        scored_items.append((score, excerpt, d))

    scored_items.sort(key=lambda x: x[0], reverse=True)

    # Chuẩn hóa đối tượng trả về kèm excerpt
    results = []
    for item in scored_items:
        sc, exc, doc = item
        if isinstance(doc, dict):
            res_doc = dict(doc)
            res_doc["excerpt"] = exc
            results.append(res_doc)
        else:
            # SQLAlchemy model
            res_doc = {
                "id": doc.id,
                "doc_number": doc.doc_number,
                "title": doc.title,
                "slug": doc.slug,
                "doc_type": doc.doc_type,
                "category": doc.category,
                "agency": doc.agency,
                "issue_date": doc.issue_date,
                "effective_date": doc.effective_date,
                "signer": doc.signer,
                "status": doc.status,
                "summary": doc.summary,
                "excerpt": exc,
                "content_text": doc.content_text,
                "original_url": doc.original_url,
                "created_at": doc.created_at or datetime.utcnow(),
            }
            results.append(res_doc)

    return results


@router.get("", response_model=LegalDocumentListResponse)
async def get_legal_documents(
    search: Optional[str] = Query(None, description="Tìm kiếm theo số hiệu, tên văn bản, từ khóa"),
    doc_type: Optional[str] = Query(None, description="Lọc theo loại văn bản: Nghị định, Thông tư, Quyết định..."),
    category: Optional[str] = Query(None, description="Lọc theo chuyên mục pháp luật"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """
    Tra cứu danh sách văn bản quy phạm pháp luật (Thông tư, Nghị định, Quyết định...).
    Trích xuất đoạn điều khoản văn bản phù hợp với từ khóa cho người dùng đọc trực tiếp.
    Tuyệt đối không đề xuất thủ tục hành chính.
    """
    try:
        query = select(LegalDocumentModel)
        if doc_type:
            query = query.where(LegalDocumentModel.doc_type == doc_type)
        if category:
            query = query.where(LegalDocumentModel.category.ilike(f"%{category}%"))

        result = await db.execute(query)
        all_records = result.scalars().all()

        ranked = filter_and_rank_legal_docs(all_records, search=search, doc_type=doc_type, category=category)
        total = len(ranked)
        offset = (page - 1) * limit
        paged = ranked[offset : offset + limit]

        items = []
        for d in paged:
            if isinstance(d, dict):
                items.append(LegalDocumentResponse(**d))
            else:
                items.append(LegalDocumentResponse.model_validate(d))

        return LegalDocumentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )
    except Exception:
        # Fallback offline đọc từ data/crawled_legal_docs.json
        fallback_data = _load_fallback_legal_docs()
        ranked = filter_and_rank_legal_docs(fallback_data, search=search, doc_type=doc_type, category=category)
        total = len(ranked)
        offset = (page - 1) * limit
        paged = ranked[offset : offset + limit]

        items = []
        for d in paged:
            # Tạo excerpt nếu chưa có
            if not d.get("excerpt"):
                d["excerpt"] = _extract_excerpt(d.get("content_text") or d.get("summary") or "", search or "")
            items.append(LegalDocumentResponse(**d))

        return LegalDocumentListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )


@router.get("/{slug}", response_model=LegalDocumentResponse)
async def get_legal_document_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Lấy chi tiết toàn văn Thông tư / Nghị định theo slug để người dùng đọc toàn văn."""
    try:
        res = await db.execute(select(LegalDocumentModel).where(LegalDocumentModel.slug == slug))
        doc = res.scalar_one_or_none()
        if doc:
            return LegalDocumentResponse.model_validate(doc)
    except Exception:
        pass

    # Fallback JSON
    docs = _load_fallback_legal_docs()
    for d in docs:
        if d.get("slug") == slug:
            return LegalDocumentResponse(**d)

    raise HTTPException(status_code=404, detail="Không tìm thấy văn bản quy phạm pháp luật")
