# -*- coding: utf-8 -*-
"""把 LISP 里的八进制转义还原成中文，确认插件会显示什么。"""
import re
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "deliverables" / "offline-plugin" / "cad-plugin" / "cable-summary-cad.lsp"
text = p.read_text(encoding="ascii")

def unesc(m):
    raw = bytes(int(x, 8) for x in re.findall(r"\\([0-7]{3})", m.group(1)))
    try:
        return '"' + raw.decode("gbk") + '"'
    except UnicodeDecodeError:
        return m.group(0)

print("插件实际会显示的提示（前 12 条含中文的）：")
shown = 0
for line in text.splitlines():
    if re.search(r"\\[0-7]{3}", line):
        pretty = re.sub(r'"((?:[^"\\]|\\.)*)"', unesc, line)
        print("  ", pretty.strip()[:96])
        shown += 1
        if shown >= 12:
            break
