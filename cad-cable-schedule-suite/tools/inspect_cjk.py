# -*- coding: utf-8 -*-
"""列出备份 LISP 里出现的所有非 ASCII 字符，排查是否有异常码位。"""
import collections
import sys
from pathlib import Path

p = Path(sys.argv[1])
text = p.read_text(encoding="utf-8")
chars = collections.Counter(c for c in text if ord(c) > 127)
print("非 ASCII 字符种类:", len(chars), " 总数:", sum(chars.values()))
suspicious = []
for ch, n in sorted(chars.items(), key=lambda kv: -kv[1]):
    cp = ord(ch)
    ok = (0x4E00 <= cp <= 0x9FFF) or (0x3000 <= cp <= 0x303F) or (0xFF00 <= cp <= 0xFFEF)
    if not ok:
        suspicious.append((ch, hex(cp), n))
print("非常规中文标点/符号（可疑）:", suspicious if suspicious else "无")
print("高频字符示例:", "".join(c for c, _ in chars.most_common(15)))
