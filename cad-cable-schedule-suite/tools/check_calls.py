# -*- coding: utf-8 -*-
"""独立的 LISP 调用-定义一致性检查。

背景：曾出现"删掉 cblsum:fixed-ini 的定义却留下调用"，AutoCAD 运行到那里才报
no function definition，而用户已经拿到坏包。这类错误必须在打包前静态拦住。

用法：python tools/check_calls.py 文件.lsp
"""
import re
import sys
from pathlib import Path

DEF_RE = re.compile(r"\(defun\s+([^\s()]+)", re.I)
CALL_RE = re.compile(r"\(([A-Za-z][A-Za-z0-9:._-]*)")
PREFIXES = ("cblsum:", "c:")


def main() -> int:
    bad = 0
    for arg in sys.argv[1:]:
        p = Path(arg)
        text = p.read_text(encoding="ascii", errors="replace")
        defined = {m.group(1).lower() for m in DEF_RE.finditer(text)}
        called = {m.group(1).lower() for m in CALL_RE.finditer(text)}
        mine = {c for c in called if c.startswith(PREFIXES)}
        unknown = sorted(c for c in mine if c not in defined)
        print("--- " + p.name + " ---")
        print("   自定义函数：定义 " + str(len(defined)) + " 个，调用 " + str(len(mine)) + " 个")
        if unknown:
            print("   [错误] 调用了未定义的函数: " + str(unknown))
            bad = 1
        else:
            print("   调用与定义一致")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
