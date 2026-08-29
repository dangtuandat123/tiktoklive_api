@echo off
chcp 65001 > nul
echo ======================================================================
echo           TIKTOK LIVE WEBSOCKET GATEWAY SERVER
echo ======================================================================
echo.
echo [*] Dang khoi chay WebSocket Server tai ws://0.0.0.0:8765...
echo [*] Ban co the ket noi tu Node.js, C#, PHP, Web, OBS: ws://localhost:8765/live?username=swatchesbybaobao
echo.
python ws_server.py
pause
