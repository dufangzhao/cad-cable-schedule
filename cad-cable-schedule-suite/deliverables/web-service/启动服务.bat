@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\\Scripts\\python.exe" goto novenv

".venv\\Scripts\\python.exe" -m app.server --host 0.0.0.0 --port 8100
echo.
echo Server stopped. Press any key to close.
pause >nul
exit /b 0

:novenv
echo [ERROR] .venv not found. Run these first:
echo     python -m venv .venv
echo     .venv\\Scripts\\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 2
