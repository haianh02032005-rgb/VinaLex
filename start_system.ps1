# Script khởi động toàn bộ hệ sinh thái VinaLex và mở Cloudflare Tunnel
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "===================================================================" -ForegroundColor Cyan
Write-Host "    VINALEX - KHỞI ĐỘNG HỆ THỐNG TRỰC TUYẾN QUA CLOUDFLARE" -ForegroundColor Yellow
Write-Host "===================================================================" -ForegroundColor Cyan

# 1. Khởi động Backend
Write-Host "[1/3] Đang khởi động Backend FastAPI (Port 8000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; .\venv\Scripts\python.exe main.py"

# 2. Khởi động Frontend
Write-Host "[2/3] Đang khởi động Frontend Next.js (Port 3000)..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev"

Write-Host "Đang chờ 5 giây để các dịch vụ sẵn sàng..." -ForegroundColor DarkGray
Start-Sleep -Seconds 5

# 3. Khởi động Cloudflare Tunnel
Write-Host "[3/3] Đang mở đường hầm Cloudflare Tunnel (trycloudflare.com)..." -ForegroundColor Magenta
Write-Host "-------------------------------------------------------------------"
Write-Host "Lấy link có đuôi .trycloudflare.com từ màn hình bên dưới để truy cập:" -ForegroundColor Yellow
Write-Host "-------------------------------------------------------------------"
& "$PSScriptRoot\cloudflared.exe" tunnel --url http://localhost:3000
