"""
VinaLex — API Routes: AI Chat + OCR Upload

Tuân thủ README.md §5: backend/api/ = routes (ai_chat, upload_ocr)
Endpoint prefix: /api/v1/ai (đăng ký trong main.py)

🔒 LUỒNG BẮT BUỘC (ARCHITECTURE.md Data Flow):
  Upload: Frontend → FastAPI → Redis (RAM) → CvService → OcrService → Trả JSON → XÓA REDIS
  Chat:   Frontend → FastAPI → RagService (Qdrant) → AgentService (Ollama) → Trả JSON

🚫 Quy tắc bảo mật (CONTRIBUTING.md):
  - KHÔNG lưu file tải lên vào ổ cứng — chỉ đọc vào RAM rồi lưu Redis
  - KHÔNG log kết quả OCR chứa dữ liệu cá nhân
  - PHẢI xóa Redis session ngay sau khi trả kết quả về Frontend
  - KHÔNG gọi API AI bên ngoài (OpenAI, Gemini, v.v.)
"""

import time
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.db.redis import store_session_data, get_session_data, delete_session
from backend.services.cv_service import CvService
from backend.services.ocr_service import OcrService
from backend.services.agent_service import AgentService
from backend.models.schemas import ChatRequest, ChatResponse, OcrResponse


router = APIRouter()

# ── Singleton Services (lazy init bên trong mỗi class) ──
_cv_service = CvService()
_ocr_service = OcrService()
_agent_service = AgentService()


@router.post("/chat", response_model=ChatResponse)
async def ai_chat(request: ChatRequest):
    """
    Chatbot pháp lý RAG.

    Luồng: FastAPI → Qdrant (retrieve) → Ollama (generate) → Trả JSON
    session_id dùng để track phiên hội thoại (lưu trên Redis nếu cần cache context).

    🚫 KHÔNG gọi API LLM bên ngoài — chỉ dùng Ollama local.
    """
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Câu hỏi không được để trống")

    answer, sources = await _agent_service.generate_answer(request.message)

    return ChatResponse(
        answer=answer,
        sources=sources,
        session_id=request.session_id,
    )


@router.post("/ocr", response_model=OcrResponse)
async def upload_for_ocr(
    file: UploadFile = File(..., description="File ảnh CMND/CCCD/PDF để OCR"),
    session_id: str = Form(..., description="Session ID từ Frontend để track Redis cleanup"),
):
    """
    Upload tài liệu để bóc tách dữ liệu OCR.

    🔒 LUỒNG BẢO MẬT BẮT BUỘC:
      1. Đọc file vào RAM (bytes) — KHÔNG ghi ra ổ cứng
      2. Lưu vào Redis với TTL (session_id làm key)
      3. Tiền xử lý bằng CvService (OpenCV + YOLO-OBB)
      4. OCR bằng OcrService (VietOCR local)
      5. Phân tích bằng AgentService (Ollama local)
      6. Trả kết quả JSON về Frontend
      7. **XÓA TOÀN BỘ session khỏi Redis** (bắt buộc theo ARCHITECTURE.md)

    🚫 KHÔNG log extracted_fields (chứa dữ liệu cá nhân).
    🚫 KHÔNG gọi Google Vision hay bất kỳ OCR API bên ngoài.
    """
    # Kiểm tra định dạng file
    allowed_types = {"image/jpeg", "image/png", "image/heic", "application/pdf"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Định dạng không hỗ trợ: {file.content_type}. Chấp nhận: JPG, PNG, HEIC, PDF",
        )

    # Giới hạn kích thước file (10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    image_bytes = await file.read()
    if len(image_bytes) > max_size:
        raise HTTPException(status_code=413, detail="File vượt quá giới hạn 10MB")

    start_time = time.time()

    try:
        # ── Bước 1: Lưu file tạm thời vào Redis RAM ──
        # Không ghi ra ổ cứng — tuân thủ Cơ chế RAM-only (ARCHITECTURE.md)
        await store_session_data(session_id, "raw_image", image_bytes)

        # ── Bước 2 & 3: Tiền xử lý + OCR (chạy trong thread pool vì CPU-bound) ──
        extracted_fields = await run_in_threadpool(
            _ocr_service.extract_from_image_bytes, image_bytes
        )

        # ── Bước 4: Xác định loại tài liệu ──
        document_type = _ocr_service.get_document_type(extracted_fields)

        # ── Bước 5: AgentService phân tích tính hợp lệ ──
        summary = await _agent_service.analyze_ocr_result(extracted_fields, document_type)

        processing_time_ms = int((time.time() - start_time) * 1000)

        response = OcrResponse(
            success=True,
            document_type=document_type,
            extracted_fields=extracted_fields,
            summary=summary,
            confidence=0.92,  # TODO: Tính từ VietOCR confidence score
            processing_time_ms=processing_time_ms,
            session_id=session_id,
        )

    except Exception as e:
        response = OcrResponse(
            success=False,
            document_type="Không xác định",
            extracted_fields={},
            summary=f"Lỗi xử lý: Định dạng không hỗ trợ hoặc chất lượng ảnh quá thấp.",
            confidence=0.0,
            processing_time_ms=int((time.time() - start_time) * 1000),
            session_id=session_id,
        )

    finally:
        # ── Bước 6: XÓA TOÀN BỘ DỮ LIỆU SESSION KHỎI REDIS ──
        # Bắt buộc thực thi ngay lập tức — KHÔNG được bỏ qua bước này
        # Tuân thủ: ARCHITECTURE.md Data Flow + CONTRIBUTING.md §1 + NĐ 13/2023/NĐ-CP
        await delete_session(session_id)

    return response
