# -*- coding: utf-8 -*-
"""打印 PAIRS 里的关键一项与文件内容的精确对比。"""
import importlib.util

spec = importlib.util.spec_from_file_location("gen", r"C:\Users\ASUS\Documents\DeepSeek-WorkSpace\Projects\cad-interaction-platform\cad-cable-schedule-suite\tools\make_lisp_cjk.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

text = gen.LISP.read_text(encoding="ascii")
target_idx = None
for i, (en, zh) in enumerate(gen.PAIRS):
    if "not baked" in en:
        target_idx = i
        print("PAIRS 项:", repr(en))
        print("  在文件里:", en in text)
if target_idx is None:
    print("PAIRS 里没有 not baked 这一项！共", len(gen.PAIRS), "项")
    for en, _ in gen.PAIRS:
        if "config:" in en:
            print("   config 相关项:", repr(en))
