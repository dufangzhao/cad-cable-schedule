# -*- coding: utf-8 -*-
"""逐行累积括号深度，找出未配平发生在哪一行。"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="ascii")
depth = 0
in_string = False
in_comment = False
report = []
for i, line in enumerate(text.splitlines(), 1):
    start = depth
    j = 0
    in_comment = False
    while j < len(line):
        ch = line[j]
        if in_comment:
            break
        if in_string:
            if ch == chr(92):
                j += 2
                continue
            if ch == '"':
                in_string = False
            j += 1
            continue
        if ch == ";":
            in_comment = True
            break
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        j += 1
    if start == 0 and depth > 0 and line.strip().startswith("(defun"):
        report.append(("DEFUN-CLOSES-AT", i, depth, line.strip()[:70]))
# 找出"顶层 defun 结束后深度没有回到 0"的位置
print("最终深度:", depth)
depth = 0
in_string = False
prev_top = 0
for i, line in enumerate(text.splitlines(), 1):
    j = 0
    in_comment = False
    while j < len(line):
        ch = line[j]
        if in_comment:
            break
        if in_string:
            if ch == chr(92):
                j += 2
                continue
            if ch == '"':
                in_string = False
            j += 1
            continue
        if ch == ";":
            in_comment = True
            break
        if ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        j += 1
    if line.strip() and not line.lstrip().startswith(";") and depth == 0:
        prev_top = i
print("最后一个深度归零的行:", prev_top)
for i, line in enumerate(text.splitlines(), 1):
    if i > prev_top:
        print(f"  {i}: {line[:90]}")
