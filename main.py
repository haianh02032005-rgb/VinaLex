"""
VinaLex - Backend API Server Runner
Chay: python Main.py
"""
import sys
import os
import subprocess

# Tu dong chuyen sang Python cua moi truong ao venv neu chay bang Python toan cuc
try:
    import uvicorn
except ModuleNotFoundError:
    venv_win = os.path.join(os.path.dirname(__file__), "venv", "Scripts", "python.exe")
    venv_unix = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    target_py = venv_win if os.path.exists(venv_win) else (venv_unix if os.path.exists(venv_unix) else None)
    if target_py and os.path.abspath(sys.executable) != os.path.abspath(target_py):
        print(f"[*] Phat hien Python toan cuc. Dang tu dong chuyen sang: {target_py}")
        ret = subprocess.call([target_py] + sys.argv)
        sys.exit(ret)
    else:
        print("[!] Loi: Khong tim thay uvicorn. Vui long kich hoat moi truong ao: .\\venv\\Scripts\\activate")
        sys.exit(1)

# Dam bao output UTF-8 tren Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0" if os.environ.get("PORT") else "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("APP_ENV", "development").lower() == "development" and not os.environ.get("PORT")
    print("==================================================")
    print(f"  Khoi dong VinaLex Backend API Server ({host}:{port})...")
    print(f"  Swagger UI Docs: http://{host}:{port}/api/docs")
    print(f"  Health Check:    http://{host}:{port}/api/v1/health")
    print("==================================================")
    uvicorn.run("backend.main:app", host=host, port=port, reload=reload)