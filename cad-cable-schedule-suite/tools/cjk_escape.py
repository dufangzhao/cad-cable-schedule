# -*- coding: utf-8 -*-
"""把中文转成 AutoLISP 的八进制转义形式，使 .lsp 源码保持纯 ASCII 而显示为中文。

AutoLISP 字符串里三位八进制表示一个字节。中文 Windows 的系统 ANSI 代码页是 GBK，
一个汉字两字节，所以把 GBK 字节逐字节写成转义即可：源码全 ASCII（不会被 AutoCAD 的
ANSI 解析搞坏），运行时字符串就是正确的 GBK 中文。

    to_lisp("电缆汇总")  ->  "\265\347\300\300\273\343\327\334"
"""
import sys


def to_lisp(text: str, encoding: str = "gbk") -> str:
    out = []
    for b in text.encode(encoding):
        ch = chr(b)
        if b < 128 and ch not in chr(34) + chr(92):
            out.append(ch)
        else:
            out.append(chr(92) + format(b, "03o"))
    return "".join(out)


def main() -> int:
    for arg in sys.argv[1:]:
        print(f"{arg}  ->  {chr(34)}{to_lisp(arg)}{chr(34)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
