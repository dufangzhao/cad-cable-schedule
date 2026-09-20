@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

if exist "cable-summary.exe" goto run
echo [ERROR] cable-summary.exe not found in this folder.
echo.
pause
exit /b 2

:run
echo Removing the plugin from AutoCAD...
echo.
set "CBLSUM_LOG=%TEMP%\cblsum-uninstall.txt"
start /wait "" "cable-summary.exe" --uninstall-bundle --log "%CBLSUM_LOG%"
if exist "%CBLSUM_LOG%" type "%CBLSUM_LOG%"
if exist "%CBLSUM_LOG%" del "%CBLSUM_LOG%" >nul 2>&1
echo.
echo Finished. Press any key to close.
pause >nul
exit /b 0
