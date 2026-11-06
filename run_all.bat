@echo off
title JanPulse Launcher
cd /d "%~dp0"

echo =======================================================
echo           JanPulse Bilingual News Portal Launcher
echo =======================================================
echo.

echo [1/3] Starting MySQL Database Server...
start "JanPulse MySQL Database" "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" --datadir="%~dp0mysql_data" --port=3306 --console

echo Waiting 3 seconds for database to initialize...
timeout /t 3 /nobreak >nul

echo [2/3] Starting Flask Application...
start "JanPulse Flask App" cmd /k "cd /d %~dp0 && python app.py"

echo [3/3] Opening Browser...
timeout /t 2 /nobreak >nul
start http://127.0.0.1:5000

echo.
echo =======================================================
echo  JanPulse is now running!
echo  - Public Portal: http://127.0.0.1:5000
echo  - Admin CMS:     http://127.0.0.1:5000/admin/login
echo.
echo  Keep the opened database and Flask windows running!
echo =======================================================
pause
