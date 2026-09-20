@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if not exist ".venv\\Scripts\\python.exe" goto novenv

echo Running preflight check (a temporary server will be started if needed)...
echo.
".venv\\Scripts\\python.exe" tools\\preflight.py
echo.
echo Finished. Press any key to close.
pause >nul
exit /b 0

:novenv
echo [ERROR] .venv not found. See README first.
echo.
pause
exit /b 2
