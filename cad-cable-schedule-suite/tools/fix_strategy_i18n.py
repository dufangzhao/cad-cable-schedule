# -*- coding: utf-8 -*-
"""更新对照表里 A/B 两条方案文案。"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / "deliverables" / "offline-plugin" / "tools" / "cblsum_i18n.py"
s = p.read_text(encoding="utf-8")

a_old = chr(34) + "  A) add the cad-plugin folder to AutoCAD" + chr(39) + "s support search path:" + chr(34)
a_new = chr(34) + "  A) add the cad-plugin folder to AutoCAD" + chr(39) + "s support search path (no setup needed):" + chr(34)
if a_old in s:
    s = s.replace(a_old, a_new)
    print("A 已更新")

# B：从 B) 开头到该元组结束，整体替换
marker = chr(34) + "  B) or move the whole cad-plugin folder to C:"
i = s.find(marker)
if i >= 0:
    start = s.rfind(chr(10), 0, i) + 1
    # 找到该条目的右括号 + 逗号所在行
    tail = s.find("再试一次", i)
    end = s.find(chr(10), tail) + 1
    end = s.find(chr(10), end) + 1        # 跳过条目结束行
    newb = (
        chr(34) + "  B) or just double-click configure.bat once in the cad-plugin folder;" + chr(34) + ","
        + chr(10) +
        "     " + chr(34) + "     it writes the absolute paths into the config, so the folder can live anywhere." + chr(34) + "),"
        + chr(10)
    )
    s = s[:start] + newb + s[end:]
    print("B 已替换")

p.write_text(s, encoding="utf-8")
