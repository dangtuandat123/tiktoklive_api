@echo off
title Test Client Python - TikTok Live

echo ===================================================
echo   TEST CLIENT WEBSOCKET
echo ===================================================
echo.
set /p TARGET="Nhap username TikTok (mac dinh: swatchesbybaobao): "
if "%TARGET%"=="" set TARGET=swatchesbybaobao

echo.
echo Dang ket noi toi phong: %TARGET%...
python ws_client_example.py %TARGET%
echo.
pause
