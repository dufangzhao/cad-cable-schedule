# -*- coding: utf-8 -*-
"""为离线插件包生成一个模板 cable-summary.ini（纯 ASCII）。

runner 留空，由目标机器上的 install.bat 写入本机绝对路径；
包里带一份模板的好处是收件人打开就能看清配置项长什么样。
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "deliverables" / "menu-plugin" / "cad-plugin" / "cable-summary.ini"
template = "\n".join([
    "; Cable summary CAD plugin - offline config",
    "; ASCII only: do not add non-ASCII characters (AutoCAD reads this with the ANSI code page).",
    ";",
    "; runner      : absolute path of run.bat (written automatically by install.bat)",
    "; project     : optional project/drawing tag, added to the Excel file name",
    "; extra_args  : appended to the engine command line as-is, e.g.",
    ';               extra_args=--output "D:\\cable-schedule.xlsx"',
    "runner=",
    "project=",
    "extra_args=",
]) + "\n"
target.write_text(template, encoding="ascii")
print(f"已写入模板：{target.name}（{len(template)} 字符, 纯 ASCII）")
