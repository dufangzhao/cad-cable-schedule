# -*- coding: utf-8 -*-
"""使用说明：把菜单安装方式改成"推荐用 CABLE_SUM_MENU 命令"。"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / "deliverables" / "menu-plugin" / "使用说明.txt"
s = p.read_text(encoding="utf-8")

old = """   b) 菜单：命令行 CUILOAD → 浏览选 cable-summary.cuix → 打开

   加载菜单后，如果菜单栏没显示，命令行输入 MENUBAR 回车，值设为 1。"""

new = """   b) 菜单：命令行输入 CABLE_SUM_MENU 回车（推荐）
      它会自动找到同目录的 cable-summary.cuix 并加载，同时把菜单栏打开。

      也可以手工加载：命令行 CUILOAD → 选择 cable-summary.cuix
      注意：若 CUILOAD 只弹出命令行提问而不出现浏览窗口，说明 FILEDIA 被关掉了，
            先输入 FILEDIA 回车、填 1，再试；含空格或中文的路径在命令行里不可靠，
            这种情况下请改用 CABLE_SUM_MENU 命令。"""

n = 0
if old in s:
    s = s.replace(old, new, 1); n += 1
else:
    print("未匹配安装段，尝试关键字替换")
    s = s.replace("命令行 CUILOAD → 浏览选 cable-summary.cuix → 打开",
                  "命令行输入 CABLE_SUM_MENU 回车（推荐）；或 CUILOAD 后选择 cable-summary.cuix")
    n += 1

# 常见问题里补一条
old2 = "装了菜单但菜单栏看不到          命令行 MENUBAR 回车，设为 1"
new2 = ("装了菜单但菜单栏看不到          命令行 MENUBAR 回车，设为 1" + chr(10) +
        "CUILOAD 不弹浏览窗口            FILEDIA 被关了：输入 FILEDIA 回车填 1；" + chr(10) +
        "                                或直接用 CABLE_SUM_MENU 命令")
if old2 in s:
    s = s.replace(old2, new2, 1); n += 1

p.write_text(s, encoding="utf-8")
print("说明更新", n, "处")
