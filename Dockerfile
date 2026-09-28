# ==============================================================================
# VinaLex — Production Dockerfile
# Chạy Backend FastAPI (Python 3.11), PyMuPDF, SQLite, FTS5 & VietOCR
# ==============================================================================

FROM python:3.11-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    APP_ENV=production

# Cài đặt các thư viện hệ thống cần thiết cho OpenCV, PyMuPDF và xử lý tiếng Việt
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Sao chép và cài đặt các phụ thuộc Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn
COPY . .

# Mở cổng dịch vụ
EXPOSE 8000

# Khởi chạy server FastAPI
CMD ["python", "main.py"]
