# -*- coding: utf-8 -*-
"""菜单版交付物的构建：派生 LISP（英文纯 ASCII）→ 中文化（GBK 八进制转义）。

为什么分两步：.lsp 必须纯 ASCII（AutoCAD 按 ANSI 解析会崩），
但用户要中文提示，所以中文以 GBK 字节的八进制转义写入。
生成中文后，开发目录里的 .lsp 就是"成品"，发布前由 tools/seed_lisp.py 还原成英文模板。
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
LISP = ROOT / "deliverables" / "menu-plugin" / "cad-plugin" / "cable-summary-cad.lsp"
I18N_DIR = ROOT / "deliverables" / "menu-plugin" / "tools"


def main() -> int:
    for step in (["tools/make_menu_lisp.py"], ["tools/make_cuix.py"],
                 ["tools/make_dcl.py"], ["tools/fix_dcl_encoding.py"]):
        rc = subprocess.run([sys.executable, str(ROOT / step[0])], cwd=str(ROOT)).returncode
        if rc != 0:
            print("构建步骤失败:", step[0], file=sys.stderr)
            return rc

    # 中文化
    sys.path.insert(0, str(I18N_DIR))
    import cblsum_i18n
    text = LISP.read_text(encoding="ascii", errors="replace")
    new, missed = cblsum_i18n.localize(text)
    if any(ord(c) > 127 for c in new):
        print("中文化后仍含非 ASCII，拒绝写出", file=sys.stderr)
        return 1
    LISP.write_text(new, encoding="ascii")
    print(f"中文化完成：未匹配 {len(missed)} 条" + (f" -> {missed[:3]}" if missed else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
