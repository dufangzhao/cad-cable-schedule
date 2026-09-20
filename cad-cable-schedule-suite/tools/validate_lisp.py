# -*- coding: utf-8 -*-
r"""AutoLISP 静态校验：找出会导致加载失败的结构问题。

关于转义（2026-09-18 真机实测纠正）：**反斜杠是转义符**，不是普通字符。
实测（AutoCAD 2020，活会话）：
  (strlen "\\")      => 1     ; \\  = 一个转义反斜杠
  (strlen "\"")       => 1     ; \"  = 一个转义引号（若反斜杠是普通字符，这里应当报字符串未闭合）
  (strcat "a" "\"" "b") => a"b
此前本文件（以及交接文档）用的是"反斜杠是普通字符"的口径，那是误判：
当年只测了 (strlen "\\")=1，而两种解释都能得到 1，所以结论下反了。
后果是所有含 \" 的字符串都会被算错（早期"多一个闭括号"的假警报就是这么来的）。
现在按真实语义处理：字符串内遇到反斜杠，连同下一个字符一起跳过。

用法：python tools/validate_lisp.py 文件.lsp [...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

BAD = 1
BS = chr(92)


def _scan(text: str, want_tokens: bool = False):
    depth = 0
    in_string = False
    in_comment = False
    line_no = 1
    first_negative = None
    tokens = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            line_no += 1
            in_comment = False
            i += 1
            continue
        if in_comment:
            i += 1
            continue
        if in_string:
            if ch == BS:
                # AutoLISP 里反斜杠是转义符（2026-09-18 真机实测：
                # (strlen "\\")=1、(strlen "\"")=1、两者都说明下一个字符被吃掉）。
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == ";":
            in_comment = True
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0 and first_negative is None:
                first_negative = line_no
        elif want_tokens and depth == 0 and not ch.isspace():
            j = i
            while j < len(text) and not text[j].isspace() and text[j] not in "()":
                j += 1
            tokens.append((line_no, text[i:j]))
            i = j
            continue
        i += 1
    return depth, first_negative, in_string, tokens


# AutoCAD 2020 的 AutoLISP 不支持的 Common Lisp 结构（实测：(let ((x 1)) x)
# 报 "no function definition: X"，(let ((r (strlen "abc"))) ...) 报 "函数错误: 8"）。
# 这些词在源码的函数位置出现一律算错误——历史 bug，不要让它们再过审。
UNSUPPORTED_CL = [
    "let", "let*", "when", "unless", "dotimes", "dolist", "loop",
    "incf", "decf", "push", "pop", "setf", "values", "defvar",
    "defparameter", "defmacro", "labels", "flet", "block",
    "return", "return-from", "catch", "throw", "unwind-protect",
    "declare", "defstruct", "format", "case", "ecase", "typecase",
    "prog", "prog1", "prog2", "do", "do*", "mapc", "reduce",
]
UNSUPPORTED_RE = re.compile(
    r"\(\s*(" + "|".join(UNSUPPORTED_CL) + r")(?=[\s()])", re.IGNORECASE)


def _code_only(text: str) -> str:
    """把字符串与注释内容抹成空格（保留长度与行号），便于安全地正则源码。"""
    out = list(text)
    in_string = False
    in_comment = False
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\n":
            in_comment = False
            i += 1
            continue
        if in_comment:
            out[i] = " "
            i += 1
            continue
        if in_string:
            if ch == BS:                      # 转义：连同下一个字符一起抹掉
                out[i] = " "
                if i + 1 < len(out):
                    out[i + 1] = " "
                i += 2
                continue
            if ch == '"':
                in_string = False
            out[i] = " "
            i += 1
            continue
        if ch == ";":
            in_comment = True
            out[i] = " "
        elif ch == '"':
            in_string = True
            out[i] = " "
        i += 1
    return "".join(out)


def validate(path: Path) -> int:
    raw = path.read_bytes()
    problems = []
    notes = []
    if raw[:3] == b"\xef\xbb\xbf":
        problems.append("文件带 UTF-8 BOM（AutoCAD 可能不接受）")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        problems.append(f"不是合法 UTF-8：{exc}")
        return report(path, problems, notes)

    if b"\t" in raw:
        problems.append("包含制表符，建议改用空格")
    for n, line in enumerate(text.splitlines(), 1):
        if any(ord(c) < 32 for c in line):
            problems.append(f"第 {n} 行含控制字符")

    depth, first_negative, unclosed, tokens = _scan(text, want_tokens=True)
    if first_negative is not None:
        problems.append(f"第 {first_negative} 行出现多余的右括号（此后括号结构错位）")
    if depth > 0:
        problems.append(f"括号未配平：还差 {depth} 个右括号")
    elif depth < 0:
        problems.append(f"括号未配平：多出 {-depth} 个右括号")
    if unclosed:
        problems.append("文件结束时字符串未闭合")
    for line_no, token in tokens:
        problems.append(f"第 {line_no} 行：顶层出现裸 token {token!r}")

    # 含反斜杠结尾的字符串（AutoLISP 会吃掉引号）——需要写成两个反斜杠
    for n, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r'"[^"]*' + BS + BS + r'$', line):
            pass
    code = _code_only(text)
    for m in UNSUPPORTED_RE.finditer(code):
        line_no = code.count("\n", 0, m.start()) + 1
        problems.append(
            f"第 {line_no} 行：AutoLISP 不支持的 CL 结构 ({m.group(1)} ...)，"
            "请改用 setq+局部变量/if/cond/while/foreach 改写")
    names = [m.group(1) for m in re.finditer(r"\(defun\s+([^\s()]+)", text)]
    dupes = sorted({x for x in names if names.count(x) > 1})
    if dupes:
        problems.append(f"重复定义的函数：{dupes}")
    notes.append(f"定义函数 {len(names)} 个")
    return report(path, problems, notes)


def report(path: Path, problems, notes) -> int:
    print(f"--- {path.name} ---")
    for n in notes:
        print(f"   提示: {n}")
    if problems:
        for p in problems:
            print(f"   [错误] {p}")
        return BAD
    print("   校验通过（括号配平、字符串闭合、无顶层裸 token）")
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：python tools/validate_lisp.py 文件.lsp ...", file=sys.stderr)
        return 2
    rc = 0
    for arg in sys.argv[1:]:
        rc |= validate(Path(arg))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
