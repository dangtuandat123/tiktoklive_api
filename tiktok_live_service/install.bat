@echo off
title Cai Dat TikTok Live Service

echo ===================================================
echo   CAI DAT THU VIEN CHO TIKTOK LIVE SERVICE
echo ===================================================
echo.

echo [1/3] Dang kiem tra Python...
python --version
if errorlevel 1 (
    echo.
    echo [LOI] Khong tim thay Python tren he thong!
    echo Vui long cai dat Python tu python.org va tick chon "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

echo.
echo [2/3] Dang cai dat cac thu vien tu requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [LOI] Cai dat requirements.txt that bai!
    pause
    exit /b 1
)

echo.
echo [3/3] Dang cai dat Playwright Chromium...
python -m playwright install chromium
if errorlevel 1 (
    echo.
    echo [LOI] Cai dat Chromium that bai!
    pause
    exit /b 1
)

echo.
echo ===================================================
echo [THANH CONG] Da cai dat xong 100%%!
echo Ban co the mo start_server.bat de bat dau chay.
echo ===================================================
echo.
pause
