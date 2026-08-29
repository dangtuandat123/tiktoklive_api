@echo off
chcp 65001 > nul
title Cài Đặt Môi Trường TikTok Live Service
echo ===================================================
echo   CÀI ĐẶT THƯ VIỆN & CHROMIUM CHO TIKTOK LIVE SERVICE
echo ===================================================
echo.
echo [*] Đang cài đặt các thư viện phụ thuộc từ requirements.txt...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [-] Có lỗi khi cài đặt thư viện!
    pause
    exit /b %errorlevel%
)

echo.
echo [*] Đang cài đặt trình duyệt Playwright Chromium (để bypass anti-bot TikTok)...
playwright install chromium
if %errorlevel% neq 0 (
    echo [-] Có lỗi khi cài đặt Playwright Chromium!
    pause
    exit /b %errorlevel%
)

echo.
echo ===================================================
echo [+] CÀI ĐẶT THÀNH CÔNG 100%!
echo [+] Bạn có thể nhấp đúp vào 'start_server.bat' để khởi chạy máy chủ.
echo ===================================================
echo.
pause
