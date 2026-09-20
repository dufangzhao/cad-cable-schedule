# -*- coding: utf-8 -*-
"""展示打包后（configure 已完成）的 LISP 会显示什么中文提示。"""
import re
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="ascii")

def fix(m):
    seg = m.group(1)
    out = bytearray()
    i = 0
    while i < len(seg):
        if seg[i] == chr(92) and i + 3 < len(seg) and seg[i + 1:i + 4].isdigit():
            out.append(int(seg[i + 1:i + 4], 8))
            i += 4
        else:
            out.append(ord(seg[i]) if ord(seg[i]) < 128 else 63)
            i += 1
    try:
        return '"' + out.decode("gbk") + '"'
    except UnicodeDecodeError:
        return m.group(0)

print("插件加载后会显示：")
shown = 0
for line in text.splitlines():
    if re.search(r"\\[0-7]{3}", line):
        pretty = re.sub(r'"([^"]*)"', fix, line)
        if any(ord(c) > 127 for c in pretty):
            print("   ", pretty.strip()[:100])
            shown += 1
            if shown >= 10:
                break
