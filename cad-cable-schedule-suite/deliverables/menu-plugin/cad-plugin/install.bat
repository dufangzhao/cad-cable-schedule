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
echo Installing the plugin for AutoCAD (official Autoloader bundle)...
echo This writes the plugin configuration and copies it into:
echo   %%APPDATA%%\\Autodesk\\ApplicationPlugins\\CableSummary.bundle
echo.
set "CBLSUM_LOG=%TEMP%\cblsum-install.txt"
start /wait "" "cable-summary.exe" --install-bundle --log "%CBLSUM_LOG%"
if exist "%CBLSUM_LOG%" type "%CBLSUM_LOG%"
if exist "%CBLSUM_LOG%" del "%CBLSUM_LOG%" >nul 2>&1
echo.
echo Finished. Restart AutoCAD to see the menu. Press any key to close.
pause >nul
exit /b 0
