# -*- coding: utf-8 -*-
"""把 CABLE_SUM_MENU 命令加进菜单版 LISP 生成器（EXTRA 里）。"""
import pathlib

p = pathlib.Path(__file__).resolve().parents[1] / "tools" / "make_menu_lisp.py"
s = p.read_text(encoding="utf-8")

if "CABLE_SUM_MENU" in s:
    print("生成器里已有该命令")
    raise SystemExit(0)

BLOCK = [
    "",
    ";; ---------- menu edition: install the menu ----------",
    ";; CUILOAD typed on the command line breaks when the path contains spaces or CJK",
    ";; characters, and does nothing at all when FILEDIA is 0. Calling the same API from",
    ";; LISP passes the path as a normal string, so it cannot be mangled.",
    "(defun c:CABLE_SUM_MENU (/ cuix ok)",
    "  (cblsum:load-config)",
    "  (setvar \"FILEDIA\" 1)",
    "  (setvar \"MENUBAR\" 1)",
    "  (setq cuix (if cblsum-home",
    "               (strcat (cblsum:dir-of cblsum-home) \"cable-summary.cuix\")",
    "               (findfile \"cable-summary.cuix\")))",
    "  (cond",
    "    ((or (null cuix) (null (findfile cuix)))",
    "     (princ \"\\n[cable-sum-schedule] cable-summary.cuix not found next to the plugin.\"))",
    "    (T",
    "     (setq ok (vl-catch-all-apply 'command (list \"_.CUILOAD\" cuix)))",
    "     (if (vl-catch-all-error-p ok)",
    "       (princ (strcat \"\\n[cable-sum-schedule] cannot load the menu: \"",
    "                      (vl-catch-all-error-message ok)))",
    "       (progn",
    "         (princ (strcat \"\\n[cable-sum-schedule] menu loaded: \" cuix))",
    "         (princ \"\\n[cable-sum-schedule] if the menu bar is hidden, run MENUBAR and set it to 1.\"))))",
    "  (princ))",
    "",
]

lines = s.splitlines()
# 插到 EXTRA 的行列表里（EXTRA = r""" ... """）
start = next(i for i, l in enumerate(lines) if l.startswith("EXTRA = r"))
end = next(i for i, l in enumerate(lines[start:], start) if l.strip() == chr(34) * 3)
lines[end:end] = BLOCK
p.write_text(chr(10).join(lines) + chr(10), encoding="utf-8")
print(f"已插入 {len(BLOCK)} 行到 EXTRA（第 {end} 行前）")
