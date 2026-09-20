# -*- coding: utf-8 -*-
"""把 LISP 的 cblsum-ini 重置为模板（nil + 哨兵），供打包使用。

configure.bat 会把本机绝对路径烧进这一行；打包时必须重置，
否则包里带的是打包者机器的路径，收件人没跑 configure.bat 就会指向错误位置。
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lisp = root / "tools" / "templates" / "cable-summary-base.lsp"
SENTINEL = "; <<CBLSUM-INI>>"
# IMPORTANT: this line closes the top-level (setq ...). Keep the trailing ")".
# Losing it made the whole file unbalanced and AutoCAD reported a syntax error.
TEMPLATE = f"      cblsum-ini     nil)   {SENTINEL} install.bat bakes the absolute path here"

text = lisp.read_text(encoding="ascii")
lines = []
changed = False
for line in text.splitlines():
    if SENTINEL in line:
        if line != TEMPLATE:
            changed = True
        lines.append(TEMPLATE)
    else:
        lines.append(line)
lisp.write_text(chr(10).join(lines) + chr(10), encoding="ascii")
print(f"LISP cblsum-ini reset to template (changed={changed})")
