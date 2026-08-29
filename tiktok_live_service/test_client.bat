@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title Test Client Python - TikTok Live WebSocket

where python >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    where py >nul 2>nul
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo [❌ LỖI] Không tìm thấy Python!
        pause
        exit /b 1
    )
)

echo =====================================================================
echo   🧪 TEST CLIENT WEBSOCKET (TIKTOK LIVE)
echo =====================================================================
echo.
set /p STREAMER="👉 Nhập username TikTok muốn theo dõi (mặc định: swatchesbybaobao): "
if "%STREAMER%"=="" set STREAMER=swatchesbybaobao

echo.
echo [*] Đang kết nối tới ws://localhost:8765/live?username=%STREAMER%...
echo.
%PYTHON_CMD% ws_client_example.py %STREAMER%
echo.
pause
