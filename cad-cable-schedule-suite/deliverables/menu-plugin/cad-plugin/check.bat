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
echo Running self-test...
echo.
rem The engine has no console of its own (built without one so the plugin does not
rem flash a black window). It writes the report with --log and we show that file here.
set "CBLSUM_LOG=%TEMP%\cblsum-selfcheck.txt"
start /wait "" "cable-summary.exe" --self-test --log "%CBLSUM_LOG%"
if exist "%CBLSUM_LOG%" type "%CBLSUM_LOG%"
if exist "%CBLSUM_LOG%" del "%CBLSUM_LOG%" >nul 2>&1
echo.
echo Finished. Press any key to close.
pause >nul
exit /b 0
