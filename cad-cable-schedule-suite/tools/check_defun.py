# -*- coding: utf-8 -*-
r"""逐函数检查括号边界：每个 defun 结束时深度必须回到 0。

这是**判据明确**的检查，不依赖对转义规则的猜测：
只要某个 defun 结束时深度不是 1（defun 自身还未闭合）或 0，就说明该函数括号有问题。
"""
import re
import sys
from pathlib import Path

Q = chr(34)
p = Path(sys.argv[1])
text = p.read_text(encoding="ascii", errors="replace")

# 按 defun 切段
starts = [m.start() for m in re.finditer(r"\(defun\s", text)]
if not starts:
    print("没有 defun")
    raise SystemExit
starts.append(len(text))
names = [m.group(1) for m in re.finditer(r"\(defun\s+([^\s()]+)", text)]

bad = 0
depth_at_end = None
for k in range(len(starts) - 1):
    seg = text[starts[k]:starts[k + 1]]
    depth = 0
    in_string = False
    in_comment = False
    for ch_i, ch in enumerate(seg):
        if ch == chr(10):
            in_comment = False
            continue
        if in_comment:
            continue
        if in_string:
            if ch == Q:
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
    # 段末深度应为 0（该 defun 已闭合，后面是注释/空行）
    name = names[k] if k < len(names) else "?"
    if depth != 0:
        print(f"  [不平衡] {name:<28} 段末深度={depth}")
        bad += 1

print(f"检查 {len(names)} 个 defun，不平衡 {bad} 个")
