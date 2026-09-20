# -*- coding: utf-8 -*-
r"""把两个插件 LISP 转成**纯 ASCII** 版本，彻底排除编码因素。

为什么要这样：AutoCAD 2020 在中文 Windows 上按 ANSI(GBK) 读取 LISP 文件。
LISP 源里的 UTF-8 中文字节被当成 GBK 解码时，可能刚好吞掉后面的引号或括号，
导致 load 时抛"语法错误"，整个文件加载失败、命令都没定义。
把注释与提示信息改成英文后，文件变成纯 ASCII，任何代码页下都一致。

命令名 CABLE_SUM / CBLSUM 与所有函数名本来就是 ASCII，因此功能与口径完全不变；
只有命令行提示语言从中文变成英文。

    .venv\Scripts\python.exe tools\make_lisp_ascii.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "deliverables" / "offline-plugin" / "cad-plugin" / "cable-summary-cad.lsp",
    ROOT.parent / "cable-schedule-service" / "cad-plugin" / "cable-summary-cad.lsp",
]
BACKUP_SUFFIX = ".cjk.bak"


def strip_to_ascii(text: str) -> str:
    """把中文字符串替换成英文，其余原样保留。"""
    # 逐个替换含中文的字符串字面量与注释行
    out_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(";;") and any(ord(c) > 127 for c in line):
            continue                      # 整行中文注释直接丢掉
        if any(ord(c) > 127 for c in line):
            line = translate_line(line)
        out_lines.append(line)
    # 清掉连续空行
    result = []
    blank = 0
    for l in out_lines:
        if not l.strip():
            blank += 1
            if blank > 1:
                continue
        else:
            blank = 0
        result.append(l)
    return "\n".join(result) + "\n"


PAIRS = [
    ("[电缆汇总] 电缆表汇总 → 采购用 Excel（离线版）  v", "[cable-sum-schedule] Cable summary (offline)  v"),
    ("[电缆汇总] 配置: ", "[cable-sum-schedule] config: "),
    ("[电缆汇总] 未找到 cable-summary.ini，将使用默认值。",
     "[cable-sum-schedule] cable-summary.ini not found, using defaults."),
    ("[电缆汇总] 未配置 runner，已中止。",
     "[cable-sum-schedule] runner is not configured. Aborted."),
    ("请编辑 cable-summary.ini，把 runner 指向 汇总.bat 的绝对路径，例如：",
     "Edit cable-summary.ini and point runner to the absolute path of the launcher, e.g."),
    ("或直接双击运行 配置插件.bat 自动写入。",
     "Or just double-click the configure .bat to write it automatically."),
    ("[电缆汇总] 找不到启动器：", "[cable-sum-schedule] launcher not found: "),
    ("请修改 cable-summary.ini 的 runner，或双击 配置插件.bat。",
     "Fix runner in cable-summary.ini, or run the configure .bat."),
    ("[电缆汇总] 当前没有选中对象。", "[cable-sum-schedule] Nothing selected."),
    ("请先在图纸中框选电缆表（连同表头与数据文字），再运行 CABLE_SUM。",
     "Select the cable table(s) in the drawing first (including headers), then run CABLE_SUM."),
    ("[电缆汇总] 选中 ", "[cable-sum-schedule] selected "),
    (" 个对象，", " object(s), "),
    ("其中读取到 ", "collected "),
    (" 个文字对象。", " text entity(ies)."),
    ("[电缆汇总] 提示：文字对象很少，可能漏选了表格内容。",
     "[cable-sum-schedule] Note: very few text entities - you may have missed the table."),
    ("[电缆汇总] 无法写入临时文件，已中止。",
     "[cable-sum-schedule] Cannot write temp file. Aborted."),
    ("[电缆汇总] 正在本地汇总，最长等待 120 秒…",
     "[cable-sum-schedule] Running local summary, waiting up to 120s..."),
    ("[电缆汇总] 完成。", "[cable-sum-schedule] Done."),
    ("[电缆汇总] 结果文件：", "[cable-sum-schedule] Result file: "),
    ("[电缆汇总] 已用默认程序打开结果文件。",
     "[cable-sum-schedule] Opened the result file with the default application."),
    ("[电缆汇总] 启动器报告路径 ", "[cable-sum-schedule] launcher reported path "),
    ("，但文件不存在。", " but the file does not exist."),
    ("[电缆汇总] 未收到启动器响应（超时或无法启动）。",
     "[cable-sum-schedule] No response from the launcher (timeout or failed to start)."),
    ("排查顺序：1) 先跑一次 自检.bat；", "Checks: 1) run the self-test .bat first;"),
    (" 2) 确认 cable-summary.ini 的 runner 指向 汇总.bat；",
     " 2) make sure runner points to the launcher .bat;"),
    (" 3) 确认 cad-plugin 目录里存在 cable-summary.exe。",
     " 3) make sure cable-summary.exe exists in this folder."),
    ("[电缆汇总] 插件已加载 v", "[cable-sum-schedule] plugin loaded v"),
    ("[电缆汇总] 离线版：框选电缆表后输入 CABLE_SUM（短命令 CBLSUM），不联网",
     "[cable-sum-schedule] offline: select the cable table, then run CABLE_SUM (alias CBLSUM)"),
    ("[电缆汇总] 用法：先在图纸中框选电缆表，再输入命令 CABLE_SUM（短命令 CBLSUM）",
     "[cable-sum-schedule] usage: select the cable table first, then run CABLE_SUM (alias CBLSUM)"),
    ("错误：", "ERROR: "),
    ("安全取点对；组码不存在时返回 nil 而不报错。", "Safe cdr: return nil instead of erroring."),
    ("把启动器写入的字面量 \\n 还原成换行，便于命令行分多行显示。",
     "Turn the literal backslash-n written by the launcher back into newlines."),
    ("忙等。插件在文档线程内运行，轮询期间本来也无法执行其他命令，",
     "Busy wait. The plugin runs on the document thread, so nothing else can run"),
    ("所以不用 DELAY 命令（DELAY 在命令行下不可用）。",
     "anyway; DELAY is not available on the command line."),
]


def translate_line(line: str) -> str:
    for src, dst in PAIRS:
        line = line.replace(src, dst)
    # 还有残留中文：注释直接丢掉；字符串则必须报错而不是塞占位符——
    # 占位符会以"看起来正常"的英文出现在用户面前，问题反而更难发现。
    if any(ord(c) > 127 for c in line):
        if line.strip().startswith(";;") or line.strip().startswith(";"):
            return ""
        raise ValueError(f"以下行仍有中文，请在 PAIRS 里补充翻译：\n    {line.strip()}")
    return line


def main() -> int:
    rc = 0
    for path in TARGETS:
        if not path.exists():
            print(f"跳过（不存在）：{path}")
            continue
        original = path.read_text(encoding="utf-8")
        backup = path.with_suffix(path.suffix + BACKUP_SUFFIX)
        if not backup.exists():
            backup.write_text(original, encoding="utf-8")
        converted = strip_to_ascii(original)
        leftovers = [i + 1 for i, l in enumerate(converted.splitlines()) if any(ord(c) > 127 for c in l)]
        if leftovers:
            print(f"[错误] {path.name} 仍有非 ASCII 行：{leftovers[:5]}", file=sys.stderr)
            rc = 1
            continue
        backup.write_text(original, encoding="utf-8")
        path.write_text(converted, encoding="utf-8")
        print(f"已转为纯 ASCII：{path.relative_to(ROOT.parent)}  ({len(converted)} 字符, 原文件备份为 {backup.name})")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
