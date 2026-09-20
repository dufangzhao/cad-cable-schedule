# -*- coding: utf-8 -*-
"""从 git 历史取回英文版 LISP 模板（避免 PowerShell 重定向写成 UTF-16）。"""
import subprocess
import sys
from pathlib import Path

rev = sys.argv[1] if len(sys.argv) > 1 else "0865143"
rel = "deliverables/offline-plugin/cad-plugin/cable-summary-cad.lsp"
root = Path(__file__).resolve().parents[1]
data = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=str(root),
                      capture_output=True, check=True).stdout
target = root / rel
target.write_bytes(data)
print(f"已从 {rev} 恢复 {rel}（{len(data)} 字节）")
b = target.read_bytes()
print("BOM:", b[:3] == b"\xef\xbb\xbf", "| 非 ASCII 字节:", sum(1 for x in b if x > 127))
