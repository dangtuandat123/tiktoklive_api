@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title [2/2] TikTok Live WebSocket Gateway Server (ws://localhost:8765)

:: 1. Tìm lệnh Python
where python >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo.
        echo [❌ LỖI] Không tìm thấy Python trên máy tính!
        echo 👉 Vui lòng chạy file 'install.bat' trước để kiểm tra môi trường.
        echo.
        pause
        exit /b 1
    )
)

echo =====================================================================
echo   🚀 TIKTOK LIVE WEBSOCKET GATEWAY SERVER ĐANG KHỞI ĐỘNG...
echo   📌 Cổng lắng nghe: ws://localhost:8765
echo   📌 Kết nối nhanh: ws://localhost:8765/live?username=^<streamer_username^>
echo   🌐 Mở file 'ws_client_example.html' trên trình duyệt để xem giao diện web.
echo =====================================================================
echo.

%PYTHON_CMD% ws_server.py
if %errorlevel% neq 0 (
    echo.
    echo [❌ LỖI] Server đã dừng hoặc gặp sự cố.
    pause
)
