# -*- coding: utf-8 -*-
import sys
from pathlib import Path
p = Path(sys.argv[1]); n = int(sys.argv[2])
line = p.read_text(encoding="ascii").splitlines()[n - 1]
print("repr:", repr(line))
print("len :", len(line))
odd = [(i, c, hex(ord(c))) for i, c in enumerate(line) if ord(c) > 126 or ord(c) < 32]
print("非普通字符:", odd[:10])
needle = "not baked in - run configure.bat to fix that"
print("needle 存在:", needle in line)
if needle not in line:
    for i, c in enumerate(line):
        if line[i:i+5] == "not b":
            print("上下文:", repr(line[i-20:i+50]))
