# -*- coding: utf-8 -*-
"""电缆汇总引擎（本地运行、不依赖服务、不联网）

给 CAD 插件调用，也可自己手动跑：

    cable-summary.exe --input 选择集.tsv --output 电缆汇总表.xlsx
    cable-summary.exe --input 整图.dxf  --output 电缆汇总表.xlsx
    cable-summary.exe --input 选择集.json --output 电缆汇总表.xlsx   # agent 的读图 artifact
    cable-summary.exe --input 选择集.tsv --output-dir D:\结果 --output-name 电缆汇总表.xlsx
    cable-summary.exe --input 选择集.tsv --output-dir D:\结果 --timestamp

设计：插件导出选择集文字（TSV）→ 本程序本地汇总 → 直接落盘 Excel。
全程不访问网络，图纸内容不出本机。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

def _attach_console() -> bool:
    r"""无控制台进程挂到父进程的控制台；挂不上就把输出丢弃。

    打包用了 --noconsole（插件从 AutoCAD 拉起时不会弹黑窗口），所以这里要区分两种调用：
      · 从 cmd / .bat（check.bat、install.bat、uninstall.bat）里跑：
        父进程有控制台，挂上去，日志照常打印在那个窗口里（编码由 _configure_stdout 定）；
      · 从插件（AutoCAD 的 startapp）里跑：父进程没有控制台，输出丢弃——插件本来就
        只读响应文件，不依赖 stdout。
    返回 True 表示挂上了真实控制台。
    """
    if sys.stdout is not None and sys.stderr is not None:
        return True                      # 开发模式（python main.py）本来就有控制台
    try:
        import ctypes
        if not ctypes.windll.kernel32.AttachConsole(-1):
            raise OSError("no parent console")
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        return True
    except Exception:
        import io
        sys.stdout = io.StringIO()       # 没有控制台：丢弃输出，但 print 不会报错
        sys.stderr = sys.stdout
        return False


def _install_log(path_str: str | None) -> None:
    """--log FILE：把输出再写一份到文件。

    为什么要它：引擎编译成 GUI 子系统（不弹黑窗），被 bat 用 start /wait 拉起时没有可用的
    控制台，报告会丢。于是让它自己写一份 UTF-8 的日志，bat 再 type 出来显示；
    顺便这份文件也能直接发给别人排障。
    """
    if not path_str:
        return
    try:
        fh = open(resolve(path_str), "w", encoding="utf-8", errors="replace", buffering=1)
    except OSError as exc:
        print(f"cannot write the log file: {exc}", file=sys.stderr)
        return

    class _Tee:
        def __init__(self, *streams):
            self._streams = [s for s in streams if s is not None]

        def write(self, data):
            for s in self._streams:
                try:
                    s.write(data)
                except Exception:
                    pass
            return len(data)

        def flush(self):
            for s in self._streams:
                try:
                    s.flush()
                except Exception:
                    pass

        def isatty(self):
            return False

    sys.stdout = _Tee(sys.stdout, fh)
    sys.stderr = _Tee(sys.stderr, fh)


def apply_project(path: Path, project: str) -> Path:
    """把工程/图号拼进结果文件名（设置里 project 的定义就是"拼进文件名"）。

    以前只有自动命名分支用它：用户在设置里填了工号、又在「保存为」里指定了
    xxx.xlsx，工号会被整个丢掉（用户反馈"这个设置没什么作用"）。现在显式文件名也拼，
    已经拼过的不重复拼。
    """
    tag = (project or "").strip()
    if not tag:
        return path
    stem = path.stem
    if stem == tag or stem.startswith(f"{tag}_") or stem.endswith(f"_{tag}"):
        return path
    return path.with_name(f"{tag}_{path.name}")


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



# 打包成 exe 后 sys.path 里没有父目录，显式补上以便 import core
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import aggregate as core  # noqa: E402

MESSAGE_LIMIT = 60          # 写给插件的提示最多几行，避免刷屏

# 启动器 汇总.bat 会先 cd 到自己的目录，因此相对路径要按"调用者当时的工作目录"解析，
# 否则插件传来的相对 --response/--output 会落到错误位置甚至写不进去。
# 启动器通过 CBLSUM_CWD 把调用者目录带过来；没有就用进程自身的工作目录。
CALLER_CWD = Path(os.environ.get("CBLSUM_CWD") or Path.cwd())


def resolve(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (CALLER_CWD / path)


def _load_texts(path: Path) -> tuple[list[dict], str]:
    suffix = path.suffix.lower()
    if suffix == ".dxf":
        return core.entities_from_dxf(path), path.name
    if suffix in {".tsv", ".txt"}:
        return core.entities_from_tsv(path), path.stem
    artifact = json.loads(core.read_text_flexible(path))
    core.load_artifact(path)                      # 空选择/截断在此失败关闭
    document = (artifact.get("document") or {}).get("name") or path.name
    return core.entities_from_artifact(artifact), document


def _unique(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.stem}_{stamp}{path.suffix}")


def build_message(model: dict, seconds: float) -> str:
    """写给 CAD 命令行看的简报。

    原则：命令行只放"结论 + 需要你决定的事"，完整明细留在 Excel 的待确认表。
    同类问题必须合并计数，否则 11 条一模一样的 missing-field 会刷满屏幕。
    """
    meta = model["metadata"]
    unknown_cls = meta.get("classes_with_unknown_length") or 0
    total_len = meta.get("total_length")
    len_text = "总长未知" if unknown_cls and not total_len else f"总长 {total_len:g} m"
    if unknown_cls:
        len_text += f"（{unknown_cls} 类长度未填，未计入）"
    lines = [
        f"识别电缆表 {meta.get('recognised_tables', '?')} 张，"
        f"读出 {meta.get('source_row_count', '?')} 行，"
        f"汇总 {meta.get('summary_row_count', '?')} 类，"
        f"合计 {meta.get('total_quantity', '?')} 根，{len_text}（用时 {seconds:.1f} 秒）。",
    ]
    if meta.get("skipped_incomplete_rows"):
        lines.append(f"注意：{meta['skipped_incomplete_rows']} 行没有电缆参数（图上未填），未计入合计。")
    if meta.get("spare_quantity"):
        spare_len = meta.get("spare_length") or 0
        spare_txt = f"，已知总长 {spare_len:g} m" if spare_len else ""
        lines.append(f"另有 {meta['spare_quantity']} 根备用/预留电缆，已单独归集（{meta.get('spare_row_count', '?')} 类{spare_txt}），未计入上方合计。")

    # 命令行里不要出现字段名（core_section 之类），换成图纸上的列名，用户才看得懂
    field_zh = {
        "spec": "电缆型号", "selected_cores": "选用芯数",
        "core_section": "每芯截面", "length": "长度",
        "required_cores": "需用芯数", "cable_id": "电缆号",
    }

    def readable(text: str) -> str:
        for en, zh in field_zh.items():
            text = text.replace(en, zh)
        return text

    # 按 (级别, 去掉具体电缆号后的说明) 归并同类问题
    grouped: dict[tuple[str, str], list[str]] = {}
    for issue in model.get("issues", []):
        severity = str(issue.get("severity", "warning"))
        message = readable(str(issue.get("message", "")).strip())
        bucket = (severity, message)
        grouped.setdefault(bucket, []).extend(issue.get("cable_ids") or [])

    if grouped:
        lines.append(f"需要确认 {len(grouped)} 类问题（详见 Excel 的「待确认」表）：")
        for (severity, message), ids in list(grouped.items())[:MESSAGE_LIMIT]:
            mark = {"warning": "提醒", "conflict": "冲突", "blocking": "阻断"}.get(severity, severity)
            preview = ",".join(ids[:6]) + ("…" if len(ids) > 6 else "")
            lines.append(f"  [{mark}] {message}" + (f"｜涉及 {preview}" if ids else ""))
        if len(grouped) > MESSAGE_LIMIT:
            lines.append(f"  …另有 {len(grouped) - MESSAGE_LIMIT} 类，见 Excel。")
    return "\n".join(lines)


# 换行占位符：AutoLISP 逐行读响应文件，值里不能有真实换行，
# 用竖线占位、由插件还原成换行（比 backslash-n 可靠：不会被转义层数搞混）
LINE_SEP = "|"


def response_encoding() -> str:
    """响应文件必须用 **Windows ANSI 代码页** 写。

    为什么不能用 locale.getpreferredencoding()：某些 Python 环境（含打包后的
    PyInstaller）会返回 UTF-8，于是中文按 UTF-8 落盘；而 AutoLISP 的
    (open ... "r") 按系统 ANSI 代码页解码，结果就是文件名乱码、插件报
    "文件不存在"。所以这里直接取 Windows 的真实 ANSI 代码页。
    """
    try:
        import ctypes
        cp = ctypes.windll.kernel32.GetACP()
        enc = f"cp{cp}"
        "测试".encode(enc)
        return enc
    except Exception:
        return "gbk"


def write_response(path: Path | None, **fields: str) -> None:
    """写给 CAD 插件的响应文件。

    每个字段必须压缩成单行：AutoLISP 逐行读取，多行值会让后面的行看起来像新字段，
    导致提示只读到第一行。换行转义为字面量 \n，由插件显示前还原。
    """
    if not path:
        return
    out = []
    for key, value in fields.items():
        if value is None:
            continue
        flat = (str(value).replace("\r\n", "\n").replace("\r", "\n")
                .replace("\n", LINE_SEP))
        out.append(f"{key}={flat}")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(out) + "\n", encoding=response_encoding(), errors="replace")
    except OSError:
        # 写不回响应文件也要让插件看到错误（能写哪算哪），绝不静默失败
        print(f"无法写入响应文件：{path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="电缆汇总引擎（本地运行，不依赖服务）")
    parser.add_argument("--input", help="选择集 TSV / 整图 DXF / 读图 artifact JSON")
    parser.add_argument("--log", help="把输出同时写入这个文件（自检报告用）")
    parser.add_argument("--self-test", action="store_true",
                        help="跑内置自检（不需要输入文件，供 自检.bat 调用）")
    parser.add_argument("--setup", action="store_true",
                        help="写入插件配置（install.bat 会先调它；也可单独用）")
    parser.add_argument("--install-bundle", action="store_true",
                        help="装成 AutoCAD 官方 Autoloader 插件（install.bat）")
    parser.add_argument("--uninstall-bundle", action="store_true",
                        help="卸载官方 Autoloader 插件（uninstall.bat）")
    parser.add_argument("--output", help="Excel 输出完整路径（优先级最高；给了它就忽略 --output-dir 和 --output-name）")
    parser.add_argument("--output-dir", help="结果目录（插件设置里的「指定目录」；缺省时临时输入落桌面）")
    parser.add_argument("--output-name",
                        help="结果文件名（只写文件名，不含目录；缺省按命名规则自动生成，不带扩展名时按 .xlsx 处理）")
    parser.add_argument("--timestamp", action="store_true",
                        help="结果文件名加时间戳（插件设置里的「文件名加时间戳」；对 --output 也给的那份文件名同样生效）")
    parser.add_argument("--output-json", help="同时输出 cable-summary 模型 JSON")
    parser.add_argument("--response", help="写回 CAD 插件的响应文件")
    parser.add_argument("--project", default="", help="工程/图号，拼进文件名")
    parser.add_argument("--keep-incomplete", action="store_true",
                        help="型号/芯数/截面三项全为空的空行也计入汇总（缺省只登记到待确认）")
    parser.add_argument("--quiet", action="store_true", help="不打印汇总结果")
    args = parser.parse_args()

    _attach_console()
    _configure_stdout()
    _install_log(args.log)
    started = time.time()
    if args.self_test:
        # 冻结成 exe 后没有 Python 环境，自检逻辑随引擎一起打包进来
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        try:
            from preflight import main as preflight_main  # type: ignore
        except ImportError as exc:
            print(f"自检模块缺失：{exc}", file=sys.stderr)
            return 2
        return preflight_main(["--self-test"])

    if args.setup:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        try:
            from setup_plugin import main as setup_main  # type: ignore
        except ImportError as exc:
            print(f"配置模块缺失：{exc}", file=sys.stderr)
            return 2
        return setup_main(["--setup"])

    if args.install_bundle or args.uninstall_bundle:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
        try:
            from setup_plugin import main as setup_main  # type: ignore
        except ImportError as exc:
            print(f"配置模块缺失：{exc}", file=sys.stderr)
            return 2
        return setup_main(["--install-bundle"] if args.install_bundle else ["--uninstall-bundle"])

    if not args.input:
        print("缺少 --input（或使用 --self-test 跑自检）", file=sys.stderr)
        return 2
    response = resolve(args.response) if args.response else None
    source = resolve(args.input)
    if not source.exists():
        write_response(response, ERROR=f"找不到输入文件 {source}")
        print(f"找不到输入文件：{source}", file=sys.stderr)
        return 2

    try:
        texts, document = _load_texts(source)
    except Exception as exc:
        write_response(response, ERROR=f"读取失败：{exc}")
        print(f"读取失败：{exc}", file=sys.stderr)
        return 3
    if not texts:
        write_response(response, ERROR="内容里没有文字实体，无法识别电缆表")
        print("内容里没有文字实体，无法识别电缆表", file=sys.stderr)
        return 3

    records, candidates = core.extract_tables(texts)
    if not [c for c in candidates if c["usable"]]:
        write_response(response, ERROR="没有识别到可汇总的电缆表（需含 电缆号/电缆型号/选用芯数/每芯截面/长度 列）")
        print("没有识别到可汇总的电缆表。请确认框选范围包含表头。", file=sys.stderr)
        return 4
    if not records:
        write_response(response, ERROR="识别到列表头但没有提取到电缆数据行")
        print("识别到列表头但没有提取到电缆数据行", file=sys.stderr)
        return 4

    model = core.build_summary(records, {
        "source_document": document,
        "source_input": source.name,
        "candidate_tables": candidates,
    }, keep_incomplete=args.keep_incomplete)

    # 结果放桌面更好找：插件导出的 TSV 位于系统临时目录，结果落在那里很难发现
    import tempfile as _tf
    src_dir = source.parent
    in_temp = str(src_dir).lower().startswith(str(_tf.gettempdir()).lower())
    desktop = Path.home() / "Desktop"

    # 文件名：--output-name 显式给的名字优先，否则按默认命名规则
    name_arg = (args.output_name or "").strip()
    if name_arg:
        # 只给名字时目录走下面的默认启发性规则；没带扩展名就按 xlsx 处理
        file_name = name_arg if Path(name_arg).suffix else f"{name_arg}.xlsx"
        file_name = apply_project(Path(file_name), args.project).name
    else:
        tag = f"{args.project.strip()}_" if args.project.strip() else ""
        if in_temp:
            # 插件路径下 source 是系统临时目录里的随机名（cblsum001 之类），
            # 拼进结果文件名只会干扰用户，所以只留 tag + 固定名
            file_name = f"{tag}电缆汇总表.xlsx"
        else:
            file_name = f"{tag}{source.stem}_电缆汇总表.xlsx"

    explicit = resolve(args.output) if args.output else None
    if explicit:
        # --output 最优先：目录与文件名以它为准，--output-dir / --output-name 不再参与；
        # 但工程/图号仍要拼进文件名（否则设置里填了工号却看不到效果）
        out_dir = explicit.parent
        target = apply_project(explicit, args.project)
    else:
        out_dir = resolve(args.output_dir) if args.output_dir else (
            desktop if (in_temp and desktop.exists()) else src_dir)
        target = out_dir / file_name
    out_dir.mkdir(parents=True, exist_ok=True)
    if args.timestamp:
        # 时间戳插在扩展名前，显式给的文件名（--output / --output-name）同样生效
        target = target.with_name(f"{target.stem}_{time.strftime('%Y%m%d-%H%M%S')}{target.suffix}")
    target = _unique(target)
    try:
        core.export_summary(model, target)
    except Exception as exc:
        write_response(response, ERROR=f"写出 Excel 失败：{exc}")
        print(f"写出 Excel 失败：{exc}", file=sys.stderr)
        return 5

    if args.output_json:
        try:
            json_target = _unique(resolve(args.output_json))
            json_target.write_text(json.dumps(model, ensure_ascii=False, indent=2, sort_keys=True),
                                   encoding="utf-8")
        except OSError as exc:
            print(f"写出 JSON 失败（Excel 已生成）：{exc}", file=sys.stderr)

    message = build_message(model, time.time() - started)
    write_response(response, SAVE_PATH=str(target.resolve()), MESSAGE=message)
    if not args.quiet:
        print(message)
        print(f"结果文件：{target.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
