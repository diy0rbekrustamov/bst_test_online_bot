@echo off
chcp 65001 >nul
title Online Test Bot
color 0A

echo ==========================================
echo     ONLINE TEST BOT - Ishga tushmoqda
echo ==========================================
echo.

cd /d %~dp0

rem Python ni avtomatik topadi (py launcher yoki python)
set PYTHON=
where py >nul 2>nul && set PYTHON=py
if not defined PYTHON (
    where python >nul 2>nul && set PYTHON=python
)
if not defined PYTHON (
    echo [XATO] Python topilmadi. https://python.org dan o'rnating.
    pause
    exit /b 1
)

if not exist .env (
    echo [XATO] .env fayl topilmadi.
    echo        Shu papkada .env fayl yarating va ichiga yozing:
    echo        BOT_TOKEN=1234567890:ABCdef...
    pause
    exit /b 1
)

echo [1] Kutubxonalar o'rnatilmoqda...
%PYTHON% -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [XATO] Kutubxonalarni o'rnatib bo'lmadi.
    pause
    exit /b 1
)
echo [OK] Kutubxonalar tayyor
echo.

echo [2] Bot va server ishga tushmoqda...
echo     Ngrok URL avtomatik olinadi...
echo.
%PYTHON% run.py

pause
