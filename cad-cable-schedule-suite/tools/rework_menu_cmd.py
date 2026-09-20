# -*- coding: utf-8 -*-
"""用 COM 版实现替换 make_menu_lisp.py 里的 CABLE_SUM_MENU（块文本放在 menu_cmd.lsp.part）。"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
gen = ROOT / "tools" / "make_menu_lisp.py"
part = (ROOT / "tools" / "menu_cmd.lsp.part").read_text(encoding="ascii")

s = gen.read_text(encoding="utf-8")
lines = s.splitlines()

# 找到 EXTRA 里的 CABLE_SUM_MENU 段：从它的 defun 起，到 EXTRA 结束的三引号前
start = next(i for i, l in enumerate(lines) if "c:CABLE_SUM_MENU" in l)
# 往上包含注释行
while start > 0 and (lines[start - 1].strip().startswith(";;") or lines[start - 1].strip() == ""):
    start -= 1
end = next(i for i, l in enumerate(lines) if l.strip() == chr(34) * 3 and i > start)

block = [ln for ln in part.splitlines()] + [""]
lines[start:end] = block
gen.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
print(f"替换了第 {start}~{end} 行，插入 {len(block)} 行")
