# -*- coding: utf-8 -*-
"""检查 LISP 文件的字节层特征：编码、行尾、制表符、可疑字符。"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
b = p.read_bytes()
print("bytes:", len(b))
print("BOM:", b[:3] == b"\xef\xbb\xbf")
print("CRLF:", b.count(b"\r\n"), " lone LF:", b.count(b"\n") - b.count(b"\r\n"))
print("tab:", b.count(b"\t"), " NUL:", b.count(b"\x00"))
try:
    s = b.decode("utf-8")
    print("utf-8 解码: OK")
except UnicodeDecodeError as e:
    print("utf-8 解码失败:", e)
    s = b.decode("gbk", errors="replace")
    print("gbk 解码后的首行:", s.splitlines()[0])

lines = s.splitlines()
print("行数:", len(lines), " 最长行:", max(len(l) for l in lines))
bad = [(i + 1, l) for i, l in enumerate(lines) if any(ord(c) < 32 and c != "\t" for c in l)]
print("控制字符行:", bad[:5])

# 列出所有 defun 名，便于核对是否有重复/非法符号
import re
for m in re.finditer(r"\(defun\s+([^\s()]+)", s):
    print("defun:", m.group(2))
