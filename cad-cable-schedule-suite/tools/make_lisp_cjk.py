# -*- coding: utf-8 -*-
"""把插件 LISP 里的英文提示替换成中文（以 GBK 八进制转义写入，源码仍是纯 ASCII）。

为什么不用直接写中文：AutoCAD 按系统 ANSI 代码页解析 LISP，UTF-8 中文会让文件解析失败
（我们已经踩过：一个 U+2192 就让整个文件加载报语法错误）。
改成 \\nnn 转义后，源码 100% ASCII，运行时字符串是 GBK 中文，命令行显示正常。

    .venv\\Scripts\\python.exe tools\\make_lisp_cjk.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISP = ROOT / "deliverables" / "offline-plugin" / "cad-plugin" / "cable-summary-cad.lsp"


def esc(text: str, encoding: str = "gbk") -> str:
    out = []
    for b in text.encode(encoding):
        ch = chr(b)
        if b < 128 and ch not in chr(34) + chr(92):
            out.append(ch)
        else:
            out.append(chr(92) + format(b, "03o"))
    return "".join(out)


# 英文原文 -> 中文。key 必须与 LISP 里的字符串逐字一致（不含引号）
PAIRS = [
    ("[cable-sum-schedule] Cable summary (offline)  v", "[电缆汇总] 离线版  v"),
    ("[cable-sum-schedule] config: ", "[电缆汇总] 配置文件: "),
    ("[cable-sum-schedule] config: not baked in - run configure.bat to fix that",
     "[电缆汇总] 尚未配置：请先双击 configure.bat"),
    ("[cable-sum-schedule] plugin loaded v", "[电缆汇总] 插件已加载 v"),
    ("[cable-sum-schedule] offline: select the cable table, then run CABLE_SUM (alias CBLSUM)",
     "[电缆汇总] 用法：先框选电缆表，再输入 CABLE_SUM（短命令 CBLSUM）"),
    ("[cable-sum-schedule] cable-summary.ini NOT FOUND. Looked in:",
     "[电缆汇总] 找不到 cable-summary.ini，已查找以下位置:"),
    ("[cable-sum-schedule] runner is empty, so the summary cannot start.",
     "[电缆汇总] runner 为空，无法开始汇总。"),
    ("Two possible causes:", "可能的原因有两个："),
    ("  1) cable-summary.ini was not configured yet", "  1) 还没有配置 cable-summary.ini"),
    ("     FIX: double-click configure.bat in the cad-plugin folder",
     "     处理：双击 cad-plugin 目录里的 configure.bat"),
    ("  2) you loaded this .lsp from somewhere else (e.g. copied it next to the",
     "  2) 你从别处加载了这个 .lsp（例如拷到图纸目录）"),
    ("     drawing). Then the plugin cannot see cable-summary.ini.",
     "     这样插件看不到 cable-summary.ini"),
    ("     FIX: APPLOAD the cable-summary-cad.lsp INSIDE the cad-plugin folder,",
     "     处理：APPLOAD 加载 cad-plugin 目录里的 cable-summary-cad.lsp，"),
    ("          or copy cable-summary.ini next to this .lsp file.",
     "          或把 cable-summary.ini 拷到这个 .lsp 旁边"),
    ("[cable-sum-schedule] launcher not found: ", "[电缆汇总] 找不到启动器: "),
    ("Fix runner in cable-summary.ini, or run the configure .bat.",
     "请修改 cable-summary.ini 的 runner，或运行 configure.bat"),
    ("[cable-sum-schedule] Nothing selected.", "[电缆汇总] 当前没有选中对象。"),
    ("Select the cable table(s) in the drawing first (including headers), then run CABLE_SUM.",
     "请先在图纸中框选电缆表（连同表头），再输入 CABLE_SUM。"),
    ("[cable-sum-schedule] selected ", "[电缆汇总] 选中 "),
    (" object(s), ", " 个对象，"),
    ("collected ", "读取到 "),
    (" text entity(ies).", " 个文字对象。"),
    ("[cable-sum-schedule] Note: very few text entities - you may have missed the table.",
     "[电缆汇总] 提示：文字对象很少，可能漏选了表格内容。"),
    ("[cable-sum-schedule] Cannot write temp file. Aborted.",
     "[电缆汇总] 无法写入临时文件，已中止。"),
    ("[cable-sum-schedule] Running local summary, waiting up to 120s...",
     "[电缆汇总] 正在本地汇总，最长等待 120 秒..."),
    ("[cable-sum-schedule] Done.", "[电缆汇总] 完成。"),
    ("[cable-sum-schedule] Result file: ", "[电缆汇总] 结果文件: "),
    ("[cable-sum-schedule] Opened the result file with the default application.",
     "[电缆汇总] 已用默认程序打开结果文件。"),
    ("[cable-sum-schedule] launcher reported path ", "[电缆汇总] 启动器报告路径 "),
    (" but the file does not exist.", "，但文件不存在。"),
    ("[cable-sum-schedule] No response from the launcher (timeout or failed to start).",
     "[电缆汇总] 未收到启动器响应（超时或未能启动）。"),
    ("Checks: 1) run the self-test .bat first;", "排查：1) 先跑一次 check.bat；"),
    (" 2) make sure runner points to the launcher .bat;", " 2) 确认 runner 指向 run.bat；"),
    (" 3) make sure cable-summary.exe exists in this folder.", " 3) 确认本目录有 cable-summary.exe。"),
    ("ERROR: ", "错误："),
]


def main() -> int:
    text = LISP.read_text(encoding="ascii")
    missed = []
    for en, zh in PAIRS:
        if en not in text:
            missed.append(en[:60])
            continue
        text = text.replace(en, esc(zh))
    if missed:
        print("以下英文串未在 LISP 中找到，请核对：")
        for m in missed:
            print("   ", m)
        return 1
    non_ascii = [i + 1 for i, l in enumerate(text.splitlines()) if any(ord(c) > 127 for c in l)]
    if non_ascii:
        print(f"结果仍含非 ASCII 行：{non_ascii[:5]}", flush=True)
        return 1
    LISP.write_text(text, encoding="ascii")
    print(f"已替换 {len(PAIRS)} 条提示为中文（GBK 八进制转义，源码纯 ASCII）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
