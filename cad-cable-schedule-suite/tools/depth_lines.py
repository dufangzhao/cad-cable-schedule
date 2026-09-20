# -*- coding: utf-8 -*-
r"""按正确规则（A：" 为转义引号）逐行累计深度，定位不平衡点。"""
import sys
from pathlib import Path

BS = chr(92)
Q = chr(34)
p = Path(sys.argv[1])
lines = p.read_text(encoding="ascii", errors="replace").splitlines()

depth = 0
in_string = False
report = []
for n, line in enumerate(lines, 1):
    start = depth
    i = 0
    in_comment = False
    while i < len(line):
        ch = line[i]
        if in_comment:
            break
        if in_string:
            if ch == Q and not (i > 0 and line[i - 1] == BS):
                in_string = False
            i += 1
            continue
        if ch == ";":
            in_comment = True
            break
        if ch == Q:
            in_string = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        i += 1
    report.append((n, start, depth, line))

print("最终深度:", depth)
print("深度为负的行:")
for n, s, d, line in report:
    if d < 0:
        print(f"  {n:4} {s:>2} -> {d:>2}  {line.strip()[:80]}")
        break
print()
print("定位：深度首次回到 0 之后的残留（说明前面少闭合）")
last_zero = 0
for n, s, d, line in report:
    if d == 0:
        last_zero = n
print("  最后一个深度为 0 的行:", last_zero)
print()
print("文件末尾 12 行及其深度:")
for n, s, d, line in report[-12:]:
    print(f"  {n:4} {s:>2} -> {d:>2}  {line.strip()[:78]}")
