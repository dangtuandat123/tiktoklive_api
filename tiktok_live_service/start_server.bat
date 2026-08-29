@echo off
title TikTok Live WebSocket Gateway (Port 8765)

echo ===================================================
echo   TIKTOK LIVE WEBSOCKET GATEWAY SERVER
echo   Listening on: ws://0.0.0.0:8765
echo ===================================================
echo.

python ws_server.py
if errorlevel 1 (
    echo.
    echo [LOI] Server gap su co khi khoi dong.
    pause
)
