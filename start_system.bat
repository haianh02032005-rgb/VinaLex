@echo off
chcp 65001 >nul
title VinaLex - He thong Chay Tu Dong Cloudflare Tunnel
echo ===================================================================
echo     VINALEX - KHỞI ĐỘNG HỆ THỐNG TRỰC TUYẾN QUA CLOUDFLARE
echo ===================================================================

echo [1/3] Đang khởi động Backend FastAPI (Port 8000)...
start "VinaLex Backend (Port 8000)" cmd /k ".\venv\Scripts\python.exe main.py"

echo [2/3] Đang khởi động Frontend Next.js (Port 3000)...
start "VinaLex Frontend (Port 3000)" cmd /k "cd frontend && npm run dev"

echo Đang chờ dịch vụ ổn định trong 5 giây...
timeout /t 5 /nobreak >nul

echo [3/3] Đang tạo đường hầm kết nối Cloudflare Tunnel...
echo -------------------------------------------------------------------
echo Nhìn vào cửa sổ Cloudflare Tunnel bên dưới để lấy link:
echo Dạng: https://xxxx.trycloudflare.com
echo -------------------------------------------------------------------
.\cloudflared.exe tunnel --url http://localhost:3000
