# -*- coding: utf-8 -*-
"""列出离线包内容，并标明关键判据：ini 在不在、lsp 是哪一版。"""
import sys
import zipfile
from pathlib import Path

z = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/cable-summary-offline-plugin-1.0.0.zip")
with zipfile.ZipFile(z) as zf:
    names = sorted(zf.namelist())
    print(f"包：{z.name}  共 {len(names)} 项")
    for n in names:
        info = zf.getinfo(n)
        print(f"   {info.file_size:>9,}  {n}")
    lsp = zf.read("cad-plugin/cable-summary-cad.lsp").decode("ascii")
    print()
    print("lsp 版本      :", [l.strip() for l in lsp.splitlines() if "cblsum-version" in l][0])
    print("新版定位逻辑  :", "cblsum:dir-of" in lsp)
    print("失败提示（新）:", "you loaded this .lsp from somewhere else" in lsp)
    print("失败提示（旧）:", "cable-summary.ini was not found or was not configured" in lsp)
    if "cad-plugin/cable-summary.ini" in names:
        ini = zf.read("cad-plugin/cable-summary.ini").decode("ascii")
        print("包内 ini      : 有，runner 行 =", repr([l for l in ini.splitlines() if l.startswith("runner=")]))
    else:
        print("包内 ini      : 没有（严重问题）")
