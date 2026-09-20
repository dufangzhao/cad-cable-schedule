# -*- coding: utf-8 -*-
"""把 ini 里示例路径的双反斜杠提示改成单个反斜杠（与真实写法一致）。"""
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "deliverables" / "offline-plugin" / "cad-plugin" / "cable-summary.ini"
if p.exists():
    s = p.read_text(encoding="ascii")
    before = s
    s = s.replace("D:" + chr(92) * 2 + "cable-schedule.xlsx", "D:" + chr(92) + "cable-schedule.xlsx")
    if s != before:
        p.write_text(s, encoding="ascii")
        print("已修正 ini 示例路径")
    else:
        print("无需修改")
for line in p.read_text(encoding="ascii").splitlines()[-2:]:
    print("   ", line)
