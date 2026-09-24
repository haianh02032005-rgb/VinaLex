"""
VinaLex - Backend API Server Runner
Chay: python Main.py
"""
import sys
import uvicorn

# Dam bao output UTF-8 tren Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    print("==================================================")
    print("  Khoi dong VinaLex Backend API Server...")
    print("  Swagger UI Docs: http://localhost:8000/api/docs")
    print("  Health Check:    http://localhost:8000/api/v1/health")
    print("==================================================")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)