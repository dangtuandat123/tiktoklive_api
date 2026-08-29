@echo off
chcp 65001 > nul
title TikTok Live WebSocket Gateway Server
echo =================================================================
echo   🚀 TIKTOK LIVE WEBSOCKET GATEWAY SERVER (PORT 8765)
echo   📌 ws://localhost:8765/live?username=^<streamer_username^>
echo =================================================================
echo.
python ws_server.py
if %errorlevel% neq 0 (
    echo.
    echo [-] Server đã dừng hoặc gặp lỗi. Vui lòng kiểm tra lại.
    pause
)
