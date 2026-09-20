# -*- coding: utf-8 -*-
"""离线插件自检：不需要 AutoCAD、不需要服务，用内置小电缆表跑通本地汇总链路。

    cable-summary.exe --self-test        （打包后）
    python tools/preflight.py            （开发时）

逐项检查：启动器/引擎是否存在、配置是否可用、能否读出并汇总出预期结果、响应文件协议是否正确。
"""
from __future__ import annotations

import argparse
import json
import locale
import subprocess
import sys
import tempfile
from pathlib import Path

def _configure_stdout() -> None:
    """让 stdout/stderr 跟随 Windows 控制台代码页。"""
    enc = "utf-8"
    try:
        import ctypes
        cp = ctypes.windll.kernel32.GetConsoleOutputCP()
        if cp:
            enc = "utf-8" if cp == 65001 else f"cp{cp}"
    except Exception:
        pass
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding=enc, errors="replace")
            except Exception:
                pass



# 打包成 exe 后 __file__ 指向解包目录，必须回到 exe 所在位置找插件文件
if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).resolve().parent
    PLUGIN_DIR = HERE
else:
    HERE = Path(__file__).resolve().parent
    PLUGIN_DIR = HERE.parent / "cad-plugin"

# 中文输出统一 UTF-8：exe 里若跟随控制台 GBK，中文会乱码；配合 .bat 的 chcp 65001
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

INI = PLUGIN_DIR / "cable-summary.ini"
LISP = PLUGIN_DIR / "cable-summary-cad.lsp"
RUNNER = PLUGIN_DIR / "run.bat"
ENGINE = PLUGIN_DIR / "cable-summary.exe"
MAIN = HERE.parent / "main.py"

HDR = {"cable_id": "电缆号", "start": "起 点", "end": "终  点", "wire_numbers": "线          号",
       "required_cores": "需用芯数", "spec": "电缆型号", "selected_cores": "选用芯数",
       "core_section": "每芯截面", "length": "长度(m)", "remark": "备     注"}
X = {"cable_id": 0.0, "start": 1842.6, "end": 3708.5, "wire_numbers": 9352.3,
     "required_cores": 17051.6, "spec": 19050.0, "selected_cores": 21072.0,
     "core_section": 23065.8, "length": 25082.5, "remark": 31788.8}


def build_fixture() -> str:
    """内置最小电缆表：两行合并、单行表、以及必须被排除的负荷表。"""
    lines = ["handle\tlayer\tx\ty\theight\ttext"]
    n = 0

    def add(x, y, text):
        nonlocal n
        n += 1
        lines.append(f"T{n:05X}\tC-4\t{x}\t{y}\t500.0\t{text}")

    def table(ox, rows):
        for key, label in HDR.items():
            add(ox + X[key], 0.0, label)
        for i, row in enumerate(rows):
            y = -1275.0 - i * 700.0
            for key, value in row.items():
                add(ox + X[key], y + (-150.0 if key in ("cable_id", "wire_numbers") else -125.0), value)

    table(0.0, [
        {"cable_id": "K1", "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "13"},
        {"cable_id": "K2", "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "13"},
    ])
    table(320000.0, [   # 单行表：早期版本会因估不出行距而整张丢掉
        {"cable_id": "UK1", "spec": "YJV-0.6/1kV", "selected_cores": "2", "core_section": "2.5", "length": "25"},
    ])
    for label, x in [("电缆号", 0.0), ("起 点", 1842.6), ("终  点", 3708.5), ("最大需要容量", 5907.8)]:
        add(640000.0 + x, 0.0, label)
    add(640000.0, -1275.0, "X1")
    return "\n".join(lines) + "\n"


def read_ini() -> dict[str, str]:
    """读插件配置。

    install.bat 用系统 ANSI 代码页写这个文件（与 AutoCAD/LISP 的读法一致），
    里面可能有中文路径；所以要按"UTF-8 → 系统 ANSI"的顺序尝试，不能假定 UTF-8。
    """
    if not INI.exists():
        return {}
    raw = INI.read_bytes()
    for enc in ("utf-8-sig", locale.getpreferredencoding(False), "gbk", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith(";") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def diagnose() -> None:
    """打印配置诊断：文件在哪、用什么编码、runner 的原始字节。

    这一步是为了让"插件说 runner 是空的"这类问题一次定位到位，
    而不是靠猜（我们已经在编码问题上猜错两次了）。
    """
    print()
    print("---- 配置诊断 ----")
    print(f"  插件目录      : {PLUGIN_DIR}")
    print(f"  期望的 ini    : {INI}")
    print(f"  ini 是否存在  : {INI.exists()}")
    if INI.exists():
        raw = INI.read_bytes()
        print(f"  ini 字节数    : {len(raw)}")
        for enc in ("utf-8-sig", locale.getpreferredencoding(False), "gbk"):
            try:
                text = raw.decode(enc)
                print(f"  可解码为      : {enc}")
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            text = raw.decode("utf-8", errors="replace")
            print("  可解码为      : 未知（已用 replace）")
        for line in text.splitlines():
            if line.strip().startswith("runner="):
                value = line.strip()[len("runner="):]
                print(f"  runner 原文   : {value!r}")
                print(f"  runner 长度   : {len(value)}")
                print(f"  runner 目标存在: {Path(value).exists() if value else False}")
                if value and not Path(value).exists():
                    print("  → runner 有值但文件不存在：多半是目录被移动过，重跑 install.bat")
                if not value:
                    print("  → runner 为空：install.bat 没写成功（看它自己的输出有没有报错）")
                break
        else:
            print("  runner 行     : 文件里没有 runner= 这一行")
    # 有没有别处的同名 ini 在干扰
    import glob
    others = []
    for pattern in (PLUGIN_DIR.parent / "**" / "cable-summary.ini",
                    Path.cwd() / "cable-summary.ini"):
        others.extend(str(p) for p in glob.glob(str(pattern), recursive=True))
    others = [p for p in dict.fromkeys(others) if Path(p) != INI]
    if others:
        print("  其他同名 ini  :")
        for p in others[:5]:
            print(f"      {p}")
    else:
        print("  其他同名 ini  : 无")
    print("-------------------")


def engine_command() -> list[str] | None:
    """决定用哪个引擎跑：优先冻结的 exe，其次本机 Python + main.py。"""
    if ENGINE.exists():
        return [str(ENGINE)]
    if MAIN.exists():
        return [sys.executable, str(MAIN)]
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="离线插件自检")
    parser.add_argument("--self-test", action="store_true",
                        help="由 cable-summary.exe 调用：直接跑内置夹具")
    args = parser.parse_args(argv)

    _configure_stdout()
    results: list[tuple[bool, str, str]] = []

    def check(ok: bool, name: str, hint: str = "") -> bool:
        results.append((ok, name, hint))
        return ok

    print("=" * 66)
    print("电缆汇总 · 离线插件自检")
    print("=" * 66)

    cmd = engine_command()
    check(LISP.exists(), "插件文件存在", f"缺少 {LISP}")
    check(RUNNER.exists(), "启动器 run.bat 存在", f"缺少 {RUNNER}（CAD 插件靠它调用引擎）")
    check(cmd is not None, "汇总引擎可用",
          "cad-plugin 下缺少 cable-summary.exe；开发环境请确认存在 main.py")
    cfg = read_ini()
    diagnose()
    check(bool(cfg), "配置文件可读", f"缺少 {INI}")
    runner = cfg.get("runner", "")
    check(bool(runner) and Path(runner).exists(),
          f"配置的 runner 可用（{runner or '未配置'}）",
          "双击 install.bat 自动写入，或手工把 runner 指向 run.bat 的绝对路径")

    if cmd:
        tmp = Path(tempfile.mkdtemp())
        tsv = tmp / "preflight.tsv"
        tsv.write_text(build_fixture(), encoding="utf-8")
        resp = tmp / "resp.txt"
        proc = subprocess.run(cmd + ["--input", str(tsv), "--output", str(tmp / "r.xlsx"),
                                     "--response", str(resp), "--quiet"],
                              capture_output=True, text=True, errors="replace",
                               encoding=locale.getpreferredencoding(False) or "utf-8",
                               timeout=300)
        check(proc.returncode == 0, "本地汇总跑通",
              (proc.stdout + proc.stderr).strip()[-200:] or f"返回码 {proc.returncode}")

        fields: dict[str, str] = {}
        if resp.exists():
            # 响应文件按系统 ANSI 代码页写（AutoCAD 的读法），不能假定 UTF-8
            raw = resp.read_bytes()
            for enc in ("utf-8-sig", locale.getpreferredencoding(False), "gbk", "latin-1"):
                try:
                    decoded = raw.decode(enc)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                decoded = raw.decode("utf-8", errors="replace")
            lines = [l for l in decoded.splitlines() if l]
            check(all("=" in l for l in lines), "响应文件每个字段占一行",
                  "多行值会让 CAD 插件只读到第一行")
            fields = dict(l.split("=", 1) for l in lines)
        saved = Path(fields.get("SAVE_PATH", "")) if fields.get("SAVE_PATH") else None
        check(bool(saved and saved.exists()), "结果 Excel 已生成", "见上一步输出")
        if saved and saved.exists():
            try:
                from openpyxl import load_workbook
                wb = load_workbook(saved)
                sh = wb["电缆汇总"]
                # 汇总表自 2026-09 起不再有「合计」行，所以数量要把各类别行相加，
                # 不能再读最后一行（那是旧版式的合计行位置，会误读成最后一条数据的数量）。
                rows = [sh.cell(row=r, column=5).value for r in range(2, sh.max_row + 1)]
                total = sum(v for v in rows if isinstance(v, int))
                check(total == 3, f"汇总数量正确（各类相加={total}）", "预期 3：K1/K2 合并 2 + UK1 1")
                check(not any(sh.cell(row=r, column=1).value == "合计" for r in range(1, sh.max_row + 1)),
                      "汇总表没有合计行", "新表结构：汇总表只应有表头 + 类别行")
                check("备用电缆" in wb.sheetnames, "备用电缆单独成表", "新表结构：备用电缆应独立成 sheet")
            except Exception as exc:
                check(False, "结果 Excel 可解析", str(exc)[:90])
        msg = fields.get("MESSAGE", "")
        check("识别电缆表 2 张" in msg, "负荷表未被当成电缆表", f"引擎提示：{msg[:70]}")

    print()
    failed = 0
    for ok, name, hint in results:
        print(f"  [{'OK  ' if ok else '失败'}] {name}")
        if not ok:
            failed += 1
            if hint:
                print(f"         → {hint}")
    print()
    if failed == 0:
        print("全部通过。接下来：")
        print("  1) 若还没装过：双击 cad-plugin\\install.bat（装成官方 Autoloader 插件），然后重启 AutoCAD")
        print("  2) 重启后菜单栏右侧会出现「电缆统计」；框选电缆表 → 点菜单里的「统计选中电缆表」")
        print("  （不装也行：在 AutoCAD 里 APPLOAD 本目录的 cable-summary-cad.lsp，只对本次会话有效）")
    else:
        print(f"有 {failed} 项未通过，请按 → 提示处理后重跑自检。")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
