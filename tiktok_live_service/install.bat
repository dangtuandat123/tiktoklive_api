@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title [1/2] Cài Đặt Dịch Vụ TikTok Live WebSocket Gateway

echo =====================================================================
echo   🛠️ TỰ ĐỘNG CÀI ĐẶT MÔI TRƯỜNG TIKTOK LIVE SERVICE (WINDOWS)
echo =====================================================================
echo.

:: 1. Kiểm tra Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    where py >nul 2>nul
    if %errorlevel% neq 0 (
        echo [❌ LỖI] Không tìm thấy Python trên máy tính của bạn!
        echo 👉 Vui lòng cài đặt Python (phiên bản 3.10 trở lên) từ https://www.python.org/
        echo ⚠️ LƯU Ý QUAN TRỌNG: Hãy nhớ tick chọn "Add Python to PATH" khi cài đặt.
        echo.
        pause
        exit /b 1
    ) else (
        set PYTHON_CMD=py
    )
) else (
    set PYTHON_CMD=python
)

echo [✓] Đã tìm thấy Python: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

:: 2. Nâng cấp pip (tránh lỗi wheel cũ trên máy mới)
echo [1/3] Đang cập nhật công cụ pip...
%PYTHON_CMD% -m pip install --upgrade pip --quiet

:: 3. Cài đặt các thư viện cần thiết
echo [2/3] Đang cài đặt các thư viện từ requirements.txt...
%PYTHON_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [❌ LỖI] Cài đặt thư viện thất bại! Vui lòng kiểm tra kết nối mạng Internet.
    pause
    exit /b %errorlevel%
)

:: 4. Cài đặt trình duyệt Playwright Chromium
echo.
echo [3/3] Đang tải trình duyệt Playwright Chromium (để bypass anti-bot TikTok)...
%PYTHON_CMD% -m playwright install chromium
if %errorlevel% neq 0 (
    echo.
    echo [❌ LỖI] Tải Chromium thất bại!
    pause
    exit /b %errorlevel%
)

echo.
echo =====================================================================
echo   🎉 CÀI ĐẶT THÀNH CÔNG 100%! HỆ THỐNG ĐÃ SẴN SÀNG HOẠT ĐỘNG.
echo   👉 Bây giờ bạn có thể nhấp đúp vào file 'start_server.bat' để chạy!
echo =====================================================================
echo.
pause
