"""
VinaLex — Cấu hình hệ thống (Core Config)

Sử dụng Pydantic Settings để đọc biến môi trường từ file .env
Tuân thủ ARCHITECTURE.md: backend/core/ = File cấu hình, bảo mật (.env)
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # ── Server ──
    APP_ENV: str = "development"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "change-me-in-production"
    ADMIN_SECRET_KEY: str = "vinalex-admin-2024"  # Đổi trong production!
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # ── PostgreSQL ──
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "vinalex_db"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis (In-memory / RAM-only — tuân thủ NĐ 13/2023) ──
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    FILE_SESSION_TTL: int = 300  # 5 phút — thời gian sống tối đa của session file

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── AI Models (Local inference — KHÔNG dùng API bên thứ 3) ──
    YOLO_OBB_WEIGHTS: str = "./data/weights/yolo_layout_obb.pt"
    VIETOCR_WEIGHTS: str = "./data/weights/vgg_seq2seq.pth"
    INFERENCE_DEVICE: str = "cpu"  # hoặc "cuda:0" nếu có NVIDIA GPU

    # ── Ollama (Local LLM) ──
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL_NAME: str = "qwen2.5:latest"

    # ── Qdrant (Vector DB — ưu tiên theo ARCHITECTURE.md) ──
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333

    # ── Embedding (Vietnamese) ──
    EMBEDDING_MODEL_NAME: str = "keepitreal/vietnamese-sbert"

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
