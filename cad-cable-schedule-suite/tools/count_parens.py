# -*- coding: utf-8 -*-
r"""独立数括号：按行累计深度，找出深度变负的位置（多余右括号）。

不依赖 validate_lisp.py —— 那个校验器显然漏判了，这里用最直白的扫描重算一遍。
"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="ascii", errors="replace")
depth = 0
in_string = False
in_comment = False
line_no = 1
first_negative = None
history = []
for i, ch in enumerate(text):
    if ch == "\n":
        history.append((line_no, depth, text.splitlines()[line_no - 1].strip()[:70]))
        line_no += 1
        in_comment = False
        continue
    if in_comment:
        continue
    if in_string:
        if ch == chr(92):
            continue
        if ch == '"':
            in_string = False
        continue
    if ch == ";":
        in_comment = True
        continue
    if ch == '"':
        in_string = True
        continue
    if ch == "(":
        depth += 1
    elif ch == ")":
        depth -= 1
        if depth < 0 and first_negative is None:
            first_negative = (line_no, text.splitlines()[line_no - 1].strip()[:90])

print("文件:", p.name, f"({len(text)} 字符)")
print("最终深度:", depth, "(0 = 配平)")
print("首次出现负深度:", first_negative if first_negative else "无")
print("字符串未闭合:", in_string)
if first_negative:
    n = first_negative[0]
    lines = text.splitlines()
    print("\n出错行附近：")
    for k in range(max(1, n - 6), min(len(lines), n + 2) + 1):
        mark = ">>" if k == n else "  "
        print(f"{mark} {k:4} {lines[k-1][:100]}")
