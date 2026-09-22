"""
VinaLex — Kết nối Redis (In-memory / RAM-only)

🔒 TUÂN THỦ BẮT BUỘC (ARCHITECTURE.md + CONTRIBUTING.md):
- Dữ liệu file tải lên và kết quả OCR thô CHỈ được phép tồn tại trên RAM qua Redis
- Không lưu file của người dùng vào ổ cứng (Hard Drive/SSD)
- Sau khi Backend trả kết quả về Frontend, PHẢI lập tức xóa toàn bộ dữ liệu
  của Session ID đó trên Redis (Garbage Collection)
- TTL tối đa: FILE_SESSION_TTL giây (mặc định 300s = 5 phút)
"""

import redis.asyncio as aioredis
from typing import Optional

from backend.core.config import settings


# ── Redis Client (async) ──
redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Trả về Redis client đã kết nối (singleton pattern)."""
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=False,  # Giữ binary để lưu dữ liệu file ảnh
        )
    return redis_client


# Fallback RAM-only storage khi Redis server chua duoc khoi dong
_memory_store: dict = {}


async def store_session_data(session_id: str, key: str, data: bytes) -> None:
    """
    Lưu dữ liệu phiên vào Redis với TTL tự động (hoặc RAM-only fallback).

    Dữ liệu sẽ tự động hết hạn sau FILE_SESSION_TTL giây.
    Không có bất kỳ dữ liệu nào được ghi ra ổ cứng.

    Args:
        session_id: ID phiên làm việc (do Frontend tạo ra)
        key: Khóa con (vd: "raw_image", "ocr_result")
        data: Dữ liệu nhị phân (bytes) — file ảnh, kết quả OCR
    """
    redis_key = f"session:{session_id}:{key}"
    try:
        client = await get_redis()
        await client.setex(redis_key, settings.FILE_SESSION_TTL, data)
    except Exception:
        _memory_store[redis_key] = data


async def get_session_data(session_id: str, key: str) -> Optional[bytes]:
    """
    Lấy dữ liệu phiên từ Redis hoặc RAM-only fallback.

    Args:
        session_id: ID phiên làm việc
        key: Khóa con

    Returns:
        Dữ liệu bytes hoặc None nếu đã hết hạn / không tồn tại
    """
    redis_key = f"session:{session_id}:{key}"
    try:
        client = await get_redis()
        return await client.get(redis_key)
    except Exception:
        return _memory_store.get(redis_key)


async def delete_session(session_id: str) -> None:
    """
    🔒 XÓA TOÀN BỘ DỮ LIỆU PHIÊN — Bắt buộc gọi sau khi trả kết quả về Frontend.

    Tuân thủ cơ chế Garbage Collection theo ARCHITECTURE.md:
    FastAPI → Redis → AI Services → Trả JSON → XÓA REDIS

    Args:
        session_id: ID phiên làm việc cần xóa hoàn toàn
    """
    prefix = f"session:{session_id}:"
    try:
        client = await get_redis()
        pattern = f"session:{session_id}:*"
        keys = await client.keys(pattern)
        if keys:
            await client.delete(*keys)
    except Exception:
        pass
    
    # Don sach bo nho RAM memory fallback
    keys_to_del = [k for k in _memory_store if k.startswith(prefix)]
    for k in keys_to_del:
        _memory_store.pop(k, None)


async def close_redis() -> None:
    """Đóng kết nối Redis khi server shutdown."""
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
