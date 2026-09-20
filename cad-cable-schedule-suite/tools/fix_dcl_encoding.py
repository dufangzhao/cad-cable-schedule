# -*- coding: utf-8 -*-
r"""把 DCL 文件转成 GBK——AutoCAD 按 ANSI 代码页读对话框定义，UTF-8 会乱码。

幂等：已经是 GBK 的文件再跑一次也不会出错。
"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / "deliverables" / "menu-plugin" / "cad-plugin" / "cable-summary-settings.dcl"
raw = p.read_bytes()
try:
    text = raw.decode("utf-8")
    note = "由 UTF-8 转 GBK"
    p.write_bytes(text.encode("gbk"))
except UnicodeDecodeError:
    text = raw.decode("gbk")          # 已经是 GBK
    note = "已是 GBK，跳过"
print(f"DCL {note}：{p.name}  {p.stat().st_size} 字节")
print("  首行:", text.splitlines()[0][:60])
