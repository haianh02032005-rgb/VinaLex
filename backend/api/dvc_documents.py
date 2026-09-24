"""
VinaLex — API Routes: Hồ Sơ Thủ Tục & Tệp PDF Từ DVC
Cung cấp các endpoints tra cứu, tìm kiếm và tải tệp PDF được thu thập từ dichvucong.gov.vn
lưu trữ trong Database riêng (data/dvc_documents.db).

Prefix: /api/v1/dvc-documents
"""

import os
from fastapi import APIRouter, HTTPException, Query, Response
from typing import Optional, List, Dict, Any

from backend.db.dvc_document_db import DVCDocumentDatabase, DEFAULT_DB_PATH

router = APIRouter()
_db = DVCDocumentDatabase()


@router.get("/stats")
async def get_dvc_documents_statistics() -> Dict[str, Any]:
    """Lấy số liệu thống kê tổng quan về kho giấy tờ và file PDF đã thu thập."""
    return _db.get_database_statistics()


@router.get("/procedures")
async def list_dvc_procedures(
    category: Optional[str] = Query(None, description="Slug lĩnh vực (ví dụ: dat-dai, ho-tich)"),
    search: Optional[str] = Query(None, description="Từ khóa tìm kiếm tên thủ tục hoặc mã TTHC"),
    page: int = Query(1, ge=1, description="Số trang hiện tại"),
    limit: int = Query(20, ge=1, le=100, description="Số bản ghi trên mỗi trang"),
) -> Dict[str, Any]:
    """Danh sách các thủ tục hành chính trong CSDL riêng có hỗ trợ lọc và phân trang."""
    offset = (page - 1) * limit
    items, total = _db.list_procedures(
        category_slug=category,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if total > 0 else 1,
    }


@router.get("/procedures/{code}")
async def get_dvc_procedure_detail(code: str) -> Dict[str, Any]:
    """Lấy chi tiết thủ tục hành chính, danh mục giấy tờ thành phần và danh sách file PDF sẵn có."""
    proc = _db.get_procedure_by_code(code)
    if not proc:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy thủ tục có mã '{code}' trong kho")

    docs = _db.get_procedure_documents(proc["id"])
    pdfs = _db.get_procedure_pdf_files(proc["id"])

    return {
        "procedure": proc,
        "documents": docs,
        "pdf_files": pdfs,
    }


@router.get("/search")
async def search_dvc_documents(
    q: str = Query(..., min_length=1, description="Từ khóa tra cứu giấy tờ, biểu mẫu hoặc thủ tục"),
    limit: int = Query(20, ge=1, le=50, description="Số lượng kết quả tối đa"),
) -> Dict[str, Any]:
    """Tìm kiếm siêu tốc với Full-Text Search FTS5."""
    results = _db.search_full_text(q, limit=limit)
    return {
        "query": q,
        "count": len(results),
        "results": results,
    }


import unicodedata
import re
from urllib.parse import quote


def _make_safe_filename(name: str) -> str:
    """Chuyển đổi tên file sang ASCII an toàn cho HTTP Header."""
    if not name:
        return "tailieu.pdf"
    # Bỏ dấu tiếng Việt
    t = name.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", t)
    stripped = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
    clean = re.sub(r"[^a-zA-Z0-9_\.\-]", "_", stripped)
    clean = re.sub(r"_+", "_", clean).strip("_")
    if not clean.lower().endswith(".pdf"):
        clean += ".pdf"
    return clean


@router.get("/pdfs/{pdf_id}/download")
async def download_dvc_pdf_file(pdf_id: int):
    """Tải xuống tệp PDF biểu mẫu hoặc hồ sơ hướng dẫn TTHC."""
    pdf_info = _db.get_pdf_by_id(pdf_id)
    if not pdf_info:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp PDF")

    file_path = pdf_info["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Tệp tin không còn tồn tại trên máy chủ")

    with open(file_path, "rb") as f:
        content = f.read()

    raw_filename = pdf_info["file_name"]
    safe_name = _make_safe_filename(raw_filename)
    encoded_name = quote(raw_filename)

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"; filename*=UTF-8\'\'{encoded_name}',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/pdfs/{pdf_id}/preview")
async def preview_dvc_pdf_file(pdf_id: int):
    """Xem trước tệp PDF inline trực tiếp trên trình duyệt."""
    pdf_info = _db.get_pdf_by_id(pdf_id)
    if not pdf_info:
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp PDF")

    file_path = pdf_info["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Tệp tin không còn tồn tại trên máy chủ")

    with open(file_path, "rb") as f:
        content = f.read()

    raw_filename = pdf_info["file_name"]
    safe_name = _make_safe_filename(raw_filename)
    encoded_name = quote(raw_filename)

    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"; filename*=UTF-8\'\'{encoded_name}',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )
