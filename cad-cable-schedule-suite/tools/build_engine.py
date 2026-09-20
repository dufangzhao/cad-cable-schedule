# -*- coding: utf-8 -*-
"""把离线版打包成单文件 cable-summary.exe。

    .venv\Scripts\python.exe tools\build_engine.py

产物：deliverables/menu-plugin/cad-plugin/cable-summary.exe
      —— 不依赖 Python、不依赖服务、不联网，拷到装了 AutoCAD 的机器即可用。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "deliverables" / "menu-plugin"
ENTRY = PLUGIN / "main.py"
DEST = PLUGIN / "cad-plugin" / "cable-summary.exe"
BUILD = ROOT / "build" / "pyinstaller"


def main() -> int:
    for path, label in ((ENTRY, "入口 main.py"), (PLUGIN / "core" / "aggregate.py", "内核 aggregate.py")):
        if not path.exists():
            print(f"缺少{label}：{path}", file=sys.stderr)
            return 2

    BUILD.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",                       # 单文件，方便拷贝
        # 无控制台（GUI 子系统）：插件用 startapp 直接拉起 exe 时不再弹黑窗口。
        # 被 cmd/.bat 调用时，main.py 会 AttachConsole 挂到父控制台，输出照常可见。
        "--noconsole",
        "--name", "cable-summary",
        "--distpath", str(DEST.parent),
        "--workpath", str(BUILD / "work"),
        "--specpath", str(BUILD),
        # core 是通过 sys.path 显式加入后 import 的，PyInstaller 静态分析看不到，
        # 必须把整个 core 包收进来
        "--hidden-import", "core.aggregate",
        # --self-test 会 import tools/preflight.py，静态分析看不到，显式收进来
        "--hidden-import", "preflight",
        "--hidden-import", "setup_plugin",
        "--paths", str(PLUGIN),
        "--paths", str(PLUGIN / "tools"),
        # 排除明显用不到的大件，压缩体积
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "PIL",
        "--exclude-module", "pytest",
        "--exclude-module", "fastapi",
        "--exclude-module", "uvicorn",
        str(ENTRY),
    ]
    print("运行 PyInstaller …")
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        print("PyInstaller 失败", file=sys.stderr)
        return proc.returncode

    built = DEST.parent / "cable-summary.exe"
    if not built.exists():
        print("未找到构建产物", file=sys.stderr)
        return 3
    size_mb = built.stat().st_size / 1024 / 1024
    print(f"构建完成：{built}  ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
