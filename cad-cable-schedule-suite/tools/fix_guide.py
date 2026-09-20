# -*- coding: utf-8 -*-
"""把使用说明里"方案乙 = C 盘固定目录"改成"方案乙 = 双击 configure.bat"。"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / "deliverables" / "offline-plugin" / "使用说明.txt"
s = p.read_text(encoding="utf-8")
start = s.find("---------------- 方式乙")
end = s.find("---------------- 如果两种都没做")
assert start > 0 and end > start, "找不到方式乙段落"
BS = chr(92)
block = [
    "---------------- 方式乙：双击一次 configure.bat（放哪都行）----------------",
    "",
    "适合：不想改 AutoCAD 设置，或插件目录要放在别的盘。",
    "",
    "  1) 把 cad-plugin 目录放到任意位置，例如 D:" + BS + "cable-summary" + BS + "cad-plugin",
    "",
    "  2) 双击该目录里的 configure.bat（只需一次）",
    "     它会打印三行，确认 runner / engine / lsp 都有值：",
    "         runner = D:" + BS + "cable-summary" + BS + "cad-plugin" + BS + "run.bat",
    "         engine = cable-summary.exe (ready)",
    "         lsp    = OK (...cable-summary.ini)",
    "     它做的是：把绝对路径写进 cable-summary.ini 与 .lsp，顺便把提示切成中文。",
    "",
    "  3) 命令行输入 APPLOAD，加载该目录的 cable-summary-cad.lsp，选始终加载",
    "",
    "  完成。",
    "",
    "  注意：目录一旦移动，需要重新双击一次 configure.bat。",
    "",
    "",
    "",
]
s = s[:start] + chr(10).join(block) + s[end:]
p.write_text(s, encoding="utf-8")
print("使用说明已更新")
