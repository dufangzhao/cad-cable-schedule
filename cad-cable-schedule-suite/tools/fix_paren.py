# -*- coding: utf-8 -*-
"""修两处：
1) 生成器里 cblsum:ini-set 少一个右括号（生成出的 .lsp 深度 -1）
2) validate_lisp.py 的转义处理有误：AutoLISP 里反斜杠是普通字符（只有 \\" 转义），
   我却把 \\ 当成转义符，遇到路径末尾的反斜杠就会误判字符串边界，
   导致括号统计不可靠——这正是它漏掉本次多余括号的原因。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# --- 1) 修生成器 ---
gen = ROOT / "tools" / "make_menu_lisp.py"
g = gen.read_text(encoding="utf-8")
old = '          (close f)\n          T)\n        nil)))))'
new = '          (close f)\n          T)\n        nil))))))'
if old in g:
    g = g.replace(old, new, 1)
    gen.write_text(g, encoding="utf-8")
    print("生成器已补一个右括号")
elif new in g:
    print("生成器已经是对的，无需修改")
else:
    print("生成器里没找到目标片段，需人工检查")

# --- 2) 校验器：不再把反斜杠当转义 ---
val = ROOT / "tools" / "validate_lisp.py"
v = val.read_text(encoding="utf-8")
v2 = v.replace("""        if in_string:\n            if ch == "\\\\":\n                # 转义：吃掉下一个字符（可能是引号或反斜杠）\n                if i + 1 >= n:\n                    problems.append(f"第 {line_no} 行：字符串以孤立反斜杠结尾，会吃掉引号")\n                    break\n                i += 2\n                continue\n            if ch == '"':\n                in_string = False\n            i += 1\n            continue""",
              """        if in_string:\n            # AutoLISP 里反斜杠是普通字符（Windows 路径里到处都是），\n            # 只有 \\" 表示转义引号。之前把 \\ 当转义符，遇到路径末尾的反斜杠\n            # 会误判字符串结束，括号统计随之失准。\n            if ch == '"' and (i == 0 or text[i - 1] != chr(92)):\n                in_string = False\n            i += 1\n            continue""")
if v2 != v:
    val.write_text(v2, encoding="utf-8")
    print("校验器已修正转义处理")
else:
    print("校验器替换未命中（脚本内联字符串需核对）")
