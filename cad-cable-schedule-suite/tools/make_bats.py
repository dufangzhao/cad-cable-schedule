# -*- coding: utf-8 -*-
"""生成各交付物的一键 .bat（纯 ASCII、无 BOM、CRLF）。

.bat 里**不出现任何非 ASCII 字符**：cmd.exe 按控制台代码页解析批处理，
编码不对会吃掉中文后面的 ASCII（'if not exist' -> 'xist'），
某些环境下还会让首行 @echo off 失效、整屏回显命令。
中文提示一律交给 Python / exe 输出，并在 .bat 里先 chcp 65001 保证一致。

    .venv\\Scripts\\python.exe tools\\make_bats.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# ---- 离线插件：不依赖 Python，直接调用 exe ----
PLUGIN_CHECK = r"""@echo off
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
"""


# ---- 官方 Autoloader：安装 / 卸载（双击即可，中文提示由 exe 打印）----
PLUGIN_INSTALL_BUNDLE = r"""@echo off
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
"""

PLUGIN_UNINSTALL_BUNDLE = r"""@echo off
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
"""

# ---- 网页服务 ----
SERVICE_SERVE = r"""@echo off
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
"""

SERVICE_CHECK = r"""@echo off
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
"""

# ---- 离线插件：CAD 插件调用的启动器（优先 exe，开发机退回 Python） ----
PLUGIN_RUNNER = r"""@echo off
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
"""

# 文件名也一律用 ASCII：AutoCAD 的命令行与 LISP 的 (findfile "…") 在 ANSI 代码页下
# 处理中文文件名不可靠，中文名会变成新的故障点。
TARGETS = {
    ROOT / "deliverables" / "menu-plugin" / "cad-plugin" / "run.bat": PLUGIN_RUNNER,
    ROOT / "deliverables" / "menu-plugin" / "cad-plugin" / "check.bat": PLUGIN_CHECK,
    # 只留一个安装脚本：它内部已经包含原来的 configure 动作（--install-bundle 会先配置本目录，
    # 再装成官方 Autoloader 插件）。旧的 configure.bat 不再分发；--setup 仍作为高级 CLI 参数保留。
    ROOT / "deliverables" / "menu-plugin" / "cad-plugin" / "install.bat": PLUGIN_INSTALL_BUNDLE,
    ROOT / "deliverables" / "menu-plugin" / "cad-plugin" / "uninstall.bat": PLUGIN_UNINSTALL_BUNDLE,
    ROOT / "deliverables" / "web-service" / "启动服务.bat": SERVICE_SERVE,
    ROOT / "deliverables" / "web-service" / "自检.bat": SERVICE_CHECK,
}


def main() -> int:
    for path, text in TARGETS.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = text.replace("\n", "\r\n").encode("ascii")   # 非 ASCII 会在此直接报错
        path.write_bytes(data)
        print(f"已生成 {path.relative_to(ROOT)}（纯 ASCII 无 BOM, {len(data)} 字节）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
