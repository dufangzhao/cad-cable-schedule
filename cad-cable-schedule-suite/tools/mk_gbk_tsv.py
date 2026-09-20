# -*- coding: utf-8 -*-
"""用真实选择集 artifact 生成 GBK 编码的 TSV（模拟 AutoCAD 的 (open "w") 写法）。"""
import pathlib
import sys

sys.path.insert(0, r"C:\Users\ASUS\Documents\DeepSeek-WorkSpace\Projects\cad-interaction-platform\cad-cable-schedule-suite\deliverables\offline-plugin")
from core import aggregate as core

art = pathlib.Path(r"C:\Users\ASUS\AppData\Local\Temp\hermes-cad\85ba5367-c078-48e8-9955-8df81bd92352\drawing_structure.json")
out = pathlib.Path(r"C:\Users\ASUS\Documents\DeepSeek-WorkSpace\Projects\cad-interaction-platform\cad-cable-schedule-suite\build\tmp")
out.mkdir(parents=True, exist_ok=True)
texts = core.entities_from_artifact(core.load_artifact(art))
core.write_tsv(texts, out / "u.tsv")
text = (out / "u.tsv").read_text(encoding="utf-8")
(out / "g.tsv").write_bytes(text.encode("gbk"))
print(f"文字实体 {len(texts)} 个；u.tsv {(out / 'u.tsv').stat().st_size} B / g.tsv {(out / 'g.tsv').stat().st_size} B")
