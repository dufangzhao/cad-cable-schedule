# -*- coding: utf-8 -*-
r"""两种口径各数一遍括号，判断哪条规则与事实相符。"""
import sys
from pathlib import Path

BS = chr(92)
Q = chr(34)
p = Path(sys.argv[1])
text = p.read_text(encoding="ascii", errors="replace")


def count(escape_quote: bool):
    depth = 0
    in_string = False
    in_comment = False
    line_no = 1
    first_neg = None
    for i, ch in enumerate(text):
        if ch == chr(10):
            line_no += 1
            in_comment = False
            continue
        if in_comment:
            continue
        if in_string:
            if ch == Q:
                if not (escape_quote and i > 0 and text[i - 1] == BS):
                    in_string = False
            continue
        if ch == ";":
            in_comment = True
            continue
        if ch == Q:
            in_string = True
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0 and first_neg is None:
                first_neg = line_no
    return depth, first_neg, in_string


for label, esc in (("A: 把 " + BS + Q + " 当转义引号", True), ("B: 反斜杠是普通字符", False)):
    d, neg, unclosed = count(esc)
    print(f"{label:26} 深度={d:>3}  首次负深度={neg}  字符串未闭合={unclosed}")

print()
print("含反斜杠且含引号的行（前 10）：")
shown = 0
for n, line in enumerate(text.splitlines(), 1):
    if BS in line and Q in line:
        print(f"  {n:4}: {line.strip()[:94]}")
        shown += 1
        if shown >= 10:
            break
