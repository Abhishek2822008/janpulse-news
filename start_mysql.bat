@echo off
echo Starting MySQL Server for JanPulse...
cd /d "%~dp0"
"C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqld.exe" --datadir="%~dp0mysql_data" --port=3306 --console
pause
