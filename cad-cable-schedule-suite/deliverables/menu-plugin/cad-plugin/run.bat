@echo off
rem Cable summary runner, invoked by the AutoCAD plugin.
rem Prefers the bundled engine; falls back to local Python for development.
setlocal
rem Remember the caller's directory so relative --input/--response still resolve
set "CBLSUM_CWD=%CD%"
cd /d "%~dp0"

if exist "cable-summary.exe" (
  "cable-summary.exe" %*
  exit /b %errorlevel%
)

if exist "..\\main.py" (
  if exist "..\\.venv\\Scripts\\python.exe" (
    "..\\.venv\\Scripts\\python.exe" "..\\main.py" %*
    exit /b %errorlevel%
  )
  python "..\\main.py" %*
  exit /b %errorlevel%
)

echo [ERROR] cable-summary.exe not found and no python fallback available. 1>&2
exit /b 2
