@echo off
chcp 65001 >nul
title Online Test Bot
color 0A

echo ==========================================
echo     ONLINE TEST BOT - Ishga tushmoqda
echo ==========================================
echo.

cd /d %~dp0

set PYTHON=C:\Users\user\AppData\Local\Python\pythoncore-3.15-64\python.exe

echo [1] Kutubxonalar o'rnatilmoqda...
%PYTHON% -m pip install flask flask-cors pyngrok requests -q
echo [OK] Kutubxonalar tayyor
echo.

echo [2] BOT TOKEN kiriting (config.py da ham o'zgartiring):
echo     Hozir config.py dagi tokendan foydalaniladi
echo.

echo [3] Bot va server ishga tushmoqda...
echo     Ngrok URL avtomatik olinadi...
echo.
%PYTHON% run.py

pause
