# -*- coding: utf-8 -*-
r"""插件配置 / 官方 Autoloader bundle 安装。

    cable-summary.exe --setup             配置本目录（写 ini + 把 ini 绝对路径烧进 LISP）
    cable-summary.exe --install-bundle    装成官方 Autoloader bundle（推荐，重启即常驻）
    cable-summary.exe --uninstall-bundle  卸载 bundle
    python tools/setup_plugin.py          开发时等价用法

为什么需要 --setup：AutoLISP 里没有任何可靠办法在运行时得知"本文件被从哪个目录加载"
（(findfile "x.lsp") 只搜支持路径），所以路径必须在配置时写死。

为什么改成 bundle：以前靠往用户支持目录的 acaddoc.lsp 追加标记块来实现"每次启动自动加载"，
属于侵入式做法。AutoCAD 官方 Autoloader 支持 %APPDATA%\Autodesk\ApplicationPlugins\ 下的
*.bundle（PackageContents.xml 里声明 AutoLISP 组件即可自动加载），对用户机器更干净：
安装 = 拷文件夹，卸载 = 删文件夹。
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
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


if getattr(sys, "frozen", False):
    PLUGIN_DIR = Path(sys.executable).resolve().parent
    HERE = PLUGIN_DIR
else:
    HERE = Path(__file__).resolve().parent
    PLUGIN_DIR = HERE.parent / "cad-plugin"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

INI = PLUGIN_DIR / "cable-summary.ini"
RUNNER = PLUGIN_DIR / "run.bat"
ENGINE = PLUGIN_DIR / "cable-summary.exe"

SENTINEL = "; <<CBLSUM-INI>>"
BS = chr(92)

# ---- 官方 Autoloader bundle 的常量（与 tools/make_bundle.py 必须保持一致）----
BUNDLE_NAME = "CableSummary.bundle"
APP_VERSION = "1.0.0"
PRODUCT_CODE = "{7E2C1A44-5D91-4B7F-9E33-1A2B3C4D5E6F}"
BUNDLE_FILES = [
    "cable-summary-cad.lsp",
    "cable-summary-settings.dcl",
    "cable-summary.cuix",
    "cable-summary.exe",
    "run.bat",
    "check.bat",
    "install.bat",
    "uninstall.bat",
]
BUNDLE_README = (
    "Cable Summary - AutoCAD plugin bundle (official Autoloader).\n"
    "\n"
    "This folder was installed into ApplicationPlugins, so AutoCAD loads\n"
    "Contents\\cable-summary-cad.lsp by itself at every start - no acaddoc.lsp,\n"
    "no APPLOAD. If the plugin reports that it is not configured, run install.bat\n"
    "in this folder once (it only re-registers the paths).\n"
    "\n"
    "Uninstall: delete this folder, then restart AutoCAD\n"
    "(or run cable-summary.exe --uninstall-bundle from the original package).\n"
)
AUTOLOAD_TAG = "cable-summary autoload"


def package_contents_xml() -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<ApplicationPackage SchemaVersion="1.0" AppVersion="{APP_VERSION}"
                    FriendlyVersion="{APP_VERSION}" ProductType="Application"
                    ProductCode="{PRODUCT_CODE}"
                    Name="Cable Summary"
                    Description="Cable schedule summary: menu, settings dialog and local engine"
                    Author="Cable Summary" HelpFile="./Contents/README.txt">
  <CompanyDetails Name="Cable Summary" Url="https://example.com/cable-summary" Email="noreply@example.com"/>
  <RuntimeRequirements OS="Win64" Platform="AutoCAD*" SeriesMin="R23.0"/>
  <Components Description="Cable summary menu plugin">
    <RuntimeRequirements OS="Win64" Platform="AutoCAD*" SeriesMin="R23.0"/>
    <ComponentEntry AppName="CableSummary" Version="{APP_VERSION}"
                    ModuleName="./Contents/cable-summary-cad.lsp"
                    AppDescription="Cable schedule summary menu plugin"
                    PerDocument="True"/>
  </Components>
</ApplicationPackage>
"""


def read_lines(ini: Path) -> list[str]:
    if ini.exists():
        # 容错解码：写入端用 mbcs（ANSI 代码页，中文 Windows = GBK），而设置对话框
        # 保存的路径/工程名可能含中文——早期这里只按 UTF-8 读，用户一旦填了中文路径
        # 就会 UnicodeDecodeError，导致 install.bat/--setup 直接崩、路径烧不进 LISP。
        raw = ini.read_bytes()
        for enc in ("utf-8-sig", "mbcs", "gbk"):
            try:
                return raw.decode(enc).splitlines()
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace").splitlines()
    # ini 也保持纯 ASCII：AutoCAD/LISP 读该文件时用 ANSI 代码页，
    # 中文注释或中文路径都可能变成新的故障点。
    return [
        "; Cable summary CAD plugin - menu edition config (ASCII only, do not add non-ASCII)",
        "; runner is written by install.bat (--install-bundle).",
    ]


def lisp_escape(value: str) -> str:
    r"""把字符串转成 LISP 字符串字面量的内容。

    非 ASCII（例如用户名是中文的 %APPDATA% 路径 C:\Users\张三\...）按 **GBK 八进制转义**
    写进去，源码因此仍是纯 ASCII——AutoCAD 在中文 Windows 上按 ANSI 代码页读文件，
    会把 \nnn 还原成原来的字节。这样插件对「路径含中文」的机器也能正常烧入配置。
    （与 tools/cblsum_i18n.py 的 esc() 同一套规则；这里自带一份，因为冻结后的 exe
      旁边没有那个模块。）
    """
    out = []
    for byte in value.encode("gbk", errors="replace"):
        ch = chr(byte)
        if byte < 128 and ch not in '"' + BS:
            out.append(ch)
        else:
            out.append(BS + format(byte, "03o"))
    return "".join(out)


def bake_lisp_path(plugin_dir: Path, ini: Path) -> str:
    """把 ini 的绝对路径写进该目录的 LISP（LISP 源码必须保持纯 ASCII）。"""
    lisp = plugin_dir / "cable-summary-cad.lsp"
    if not lisp.exists():
        return "SKIP (lsp not found)"
    raw = lisp.read_bytes()
    try:
        text = raw.decode("utf-8")            # 纯 ASCII 文件
    except UnicodeDecodeError:
        return "SKIP (lsp is not ASCII)"
    if SENTINEL not in text:
        return "WARN (sentinel not found; re-extract the package)"

    # 顺带把英文提示换成中文（GBK 八进制转义，源码保持纯 ASCII）。
    i18n_note = ""
    try:
        sys.path.insert(0, str(HERE))
        import cblsum_i18n  # type: ignore
        text, missed = cblsum_i18n.localize(text)
        i18n_note = "cn" if not missed else f"cn(未匹配{len(missed)})"
    except Exception as exc:                     # 翻译失败不影响配置写入
        i18n_note = f"skip({exc})"

    escaped = lisp_escape(str(ini))
    lines = []
    for line in text.splitlines():
        if SENTINEL in line:
            # keep the trailing ")" - this line closes the top-level (setq ...)
            lines.append(f'      cblsum-ini     "{escaped}")   {SENTINEL} absolute path written by install.bat')
        else:
            lines.append(line)
    new_text = "\n".join(lines) + "\n"
    if any(ord(c) > 127 for c in new_text):
        return "SKIP (internal: the derived text is not ASCII)"
    lisp.write_bytes(new_text.encode("ascii"))
    return f"OK ({ini}) [{i18n_note}]"


def upsert(lines: list[str], key: str, value: str) -> list[str]:
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            return lines
    lines.append(f"{key}={value}")
    return lines


# 用户设置在 ini 里的键。runner 不算设置（每台机器/每个位置都不一样，必须由安装器写）。
# output_dir / output_name 是旧版对话框留下的键，忽略即可。
SETTING_KEYS_SKIP = {"runner", "output_dir", "output_name"}


def read_settings(ini: Path) -> dict[str, str]:
    """把 ini 里的用户设置读成字典（跳过注释与 runner 之类的机器相关键）。"""
    out: dict[str, str] = {}
    if not ini.exists():
        return out
    for line in read_lines(ini):
        s = line.strip()
        if not s or s.startswith(";") or "=" not in s:
            continue
        key, _, value = s.partition("=")
        key = key.strip()
        if key and key not in SETTING_KEYS_SKIP:
            out[key] = value.strip()
    return out


def merge_settings(ini: Path, values: dict[str, str]) -> int:
    """把用户设置写回 ini：保留注释与其它键，缺的键追加到文件末尾。"""
    if not values:
        return 0
    lines = read_lines(ini)
    written = 0
    for key, value in values.items():
        lines = upsert(lines, key, value)
        written += 1
    text = "\n".join(lines) + "\n"
    try:
        ini.write_text(text, encoding="mbcs")
    except LookupError:
        ini.write_text(text, encoding="utf-8")
    return written


def configure_dir(plugin_dir: Path, project: str | None = None) -> tuple[str, str, bool]:
    """在指定目录写 cable-summary.ini（runner 指向该目录的 run.bat）并烧入 LISP。

    返回 (ini 路径, lsp 烧入结果, 引擎是否存在)。
    """
    ini = plugin_dir / "cable-summary.ini"
    engine = plugin_dir / "cable-summary.exe"
    # runner 优先直接指向 exe：exe 是「无控制台」程序，插件用 startapp 拉起它时不会弹黑窗口；
    # 早期指向 run.bat 时，cmd 会先开一个控制台窗口（用户看到的就是那个乱码窗口）。
    # 没有 exe（纯 Python 开发环境）才退回 run.bat。
    runner = engine if engine.exists() else plugin_dir / "run.bat"

    lines = read_lines(ini)
    lines = upsert(lines, "runner", str(runner))
    if project is not None:
        lines = upsert(lines, "project", project)
    if not any(l.strip().startswith("project=") for l in lines):
        lines.append("project=")
    if not any(l.strip().startswith("extra_args=") for l in lines):
        sep = chr(92)                     # 单个反斜杠即可，示例里的路径要与实际写法一致
        lines.append("; extra_args: appended to the engine command line as-is, e.g.")
        lines.append(f';             extra_args=--output "D:{sep}cable-schedule.xlsx"')
        lines.append("extra_args=")
    # ini 用系统 ANSI 代码页写出（中文 Windows = GBK），与 AutoCAD/LISP 的读法一致。
    # 不能用 ASCII：runner 路径里可能有中文，强写 ASCII 会 UnicodeEncodeError。
    text = "\n".join(lines) + "\n"
    try:
        ini.write_text(text, encoding="mbcs")        # Windows：ANSI 代码页
    except LookupError:                              # 非 Windows 兜底
        ini.write_text(text, encoding="utf-8")

    if any(ord(c) > 127 for c in str(runner)):
        print()
        print("NOTE: this folder path contains non-ASCII characters.")
        print("      AutoCAD passes the launcher path through the ANSI code page, which can")
        print("      fail on some setups. If CABLE_SUM hangs at 'Running local summary...',")
        print(f"      move this cad-plugin folder to a pure-ASCII path (e.g. D:{BS}cable-summary)")
        print("      and run install.bat again.")

    baked = bake_lisp_path(plugin_dir, ini)
    return str(ini), baked, engine.exists()


def applications_plugins() -> Path | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return Path(appdata) / "Autodesk" / "ApplicationPlugins"


def trusted_add(folder: Path) -> str:
    """把文件夹追加进 AutoCAD 的 TRUSTEDPATHS（用户配置里的受信任位置）。

    未签名的 LISP 从非受信任位置加载时，AutoCAD 会弹「安全性 - 未签名的可执行文件」，
    用户不点就不加载。直接把 bundle 目录写进受信任位置，可以免掉每次启动的询问。
    """
    try:
        import winreg
    except ImportError:
        return "skip (winreg unavailable)"
    value = str(folder) + BS
    root = winreg.HKEY_CURRENT_USER
    added, checked = 0, 0
    todo: list[str] = []
    try:
        with winreg.OpenKey(root, r"Software\Autodesk\AutoCAD") as rel:
            i = 0
            while True:
                try:
                    release = winreg.EnumKey(rel, i)
                except OSError:
                    break
                i += 1
                # 只记名字，不记句柄：句柄会在 with 退出时关闭，之后再 OpenKey 会失败
                todo.append(release)
    except OSError:
        return "skip (AutoCAD registry key not found)"

    for release in todo:
        try:
            with winreg.OpenKey(root, rf"Software\Autodesk\AutoCAD\{release}") as rk:
                j = 0
                products = []
                while True:
                    try:
                        products.append(winreg.EnumKey(rk, j))
                    except OSError:
                        break
                    j += 1
        except OSError:
            continue
        for product in products:
            profiles = rf"Software\Autodesk\AutoCAD\{release}\{product}\Profiles"
            try:
                with winreg.OpenKey(root, profiles) as pk:
                    k = 0
                    names = []
                    while True:
                        try:
                            names.append(winreg.EnumKey(pk, k))
                        except OSError:
                            break
                        k += 1
            except OSError:
                continue
            for name in names:
                general = rf"{profiles}\{name}\General"
                try:
                    with winreg.OpenKey(root, general, 0, winreg.KEY_READ | winreg.KEY_WRITE) as gk:
                        checked += 1
                        try:
                            cur, _ = winreg.QueryValueEx(gk, "TRUSTEDPATHS")
                        except OSError:
                            cur = ""
                        parts = [p for p in str(cur).split(";") if p.strip()]
                        if any(p.rstrip(BS).lower() == str(folder).rstrip(BS).lower() for p in parts):
                            continue
                        parts.append(value)
                        winreg.SetValueEx(gk, "TRUSTEDPATHS", 0, winreg.REG_SZ, ";".join(parts))
                        added += 1
                except OSError:
                    continue
    if checked == 0:
        return "skip (no AutoCAD profile found)"
    if added == 0:
        return "already trusted"
    return f"added to {added} profile(s)"


def acaddoc_files() -> list[Path]:
    """所有可能被 AutoCAD 读到的 acaddoc.lsp（旧的自启机制写的那份）。"""
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return []
    base = Path(appdata) / "Autodesk"
    if not base.is_dir():
        return []
    return sorted(base.glob("AutoCAD */R*/*/support/acaddoc.lsp")) + sorted(base.glob("AutoCAD */R*/*/Support/acaddoc.lsp"))


def strip_acaddoc_blocks() -> str:
    """删掉旧机制写进 acaddoc.lsp 的标记块（迁移到官方 Autoloader）。

    只删我们自己的块（;;; cable-summary autoload begin/end），其它内容原样保留；
    文件因此变空也保持为空文件（AutoCAD 读空文件没有问题）。
    """
    files = acaddoc_files()
    if not files:
        return "skip (no acaddoc.lsp found)"
    touched = []
    for path in files:
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        text, enc = None, "utf-8"
        for e in ("utf-8-sig", "mbcs", "gbk"):
            try:
                text = raw.decode(e)
                enc = e
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if text is None:
            continue
        out, inside, removed = [], False, 0
        for line in text.splitlines():
            if AUTOLOAD_TAG + " begin" in line:
                inside, removed = True, removed + 1
                continue
            if AUTOLOAD_TAG + " end" in line:
                inside, removed = False, removed + 1
                continue
            if inside or AUTOLOAD_TAG in line:
                removed += 1
                continue
            out.append(line)
        if not removed:
            continue
        new = "\n".join(out)
        try:
            if not new.strip():
                # 文件里原本只有我们的块：整个删掉。留一个空 acaddoc.lsp 会让 AutoCAD
                # 每次启动都弹「未签名的可执行文件」询问（实测），用户会很烦。
                path.unlink()
                touched.append("已删除空文件")
                continue
            path.write_bytes((new + "\n").encode(enc if enc != "utf-8-sig" else "utf-8"))
        except (OSError, UnicodeEncodeError):
            continue
        touched.append(f"{path.name}({removed} 行)")
    if not touched:
        return "nothing to remove"
    return "removed from " + ", ".join(touched)


def install_bundle() -> int:
    plugins = applications_plugins()
    if plugins is None:
        print("找不到 %APPDATA%，无法安装到 ApplicationPlugins。", file=sys.stderr)
        return 3
    if not (PLUGIN_DIR / "cable-summary-cad.lsp").exists():
        print(f"找不到插件文件：{PLUGIN_DIR}", file=sys.stderr)
        return 2
    if not RUNNER.exists():
        print(f"找不到启动器：{RUNNER}", file=sys.stderr)
        return 2

    print("== 装成 AutoCAD 官方 Autoloader 插件 ==")
    print(f"源目录：{PLUGIN_DIR}")

    # 1) 先配置源目录，保证它单独用也好使（拷到别处/直接 APPLOAD 都能工作）
    ini, baked, engine_ok = configure_dir(PLUGIN_DIR)
    print(f"  源目录配置：{ini}")
    print(f"  lsp 烧入  ：{baked}")

    # 2) 复制成 bundle。
    #    重装会重建整个 bundle 目录（连 ini 一起），所以先把用户设置抢救出来：
    #    优先用旧 bundle 的 ini（升级/重装场景），没有就从源目录的 ini 取（首次安装）。
    bundle = plugins / BUNDLE_NAME
    contents = bundle / "Contents"
    carried = read_settings(contents / "cable-summary.ini")
    carried_from = "旧 bundle"
    if not carried:
        carried = read_settings(PLUGIN_DIR / "cable-summary.ini")
        carried_from = "源目录"
    if carried:
        shown = ", ".join(f"{k}={v}" for k, v in sorted(carried.items()) if v)
        print(f"  保留设置：{shown if shown else '（只有空值）'}  ← 来自{carried_from}")
    # 就地增量更新，**不删整个目录**：
    #   · 目录里的 cable-summary.ini（用户设置）不在 BUNDLE_FILES 里，因此永远不会被覆盖；
    #   · 个别文件被占用（例如自检窗口还开着、引擎正在运行）时只警告，其余文件照常更新，
    #     不会像 rmtree 那样整体失败。
    contents.mkdir(parents=True, exist_ok=True)
    missing = []
    locked = []
    for name in BUNDLE_FILES:
        src = PLUGIN_DIR / name
        if not src.exists():
            missing.append(name)
            continue
        try:
            shutil.copy2(src, contents / name)
        except OSError:
            locked.append(name)
    # 清掉早期版本分发过、现在已取消的脚本（少了它们 bundle 里会留垃圾）
    for stale in ("configure.bat", "install-autoloader.bat", "uninstall-autoloader.bat"):
        old_file = contents / stale
        if old_file.exists():
            try:
                old_file.unlink()
            except OSError:
                locked.append(stale)
    (bundle / "PackageContents.xml").write_text(package_contents_xml(), encoding="utf-8")
    (contents / "README.txt").write_text(BUNDLE_README, encoding="ascii")
    print(f"  已更新到 ：{bundle}")
    if missing:
        print(f"  （源目录缺少文件：{', '.join(missing)}）")
    if locked:
        print(f"  （这些文件被占用，本次没更新：{', '.join(locked)}）")
        print("     多为自检窗口未关闭或引擎正在运行；关掉后重新双击 install.bat 即可。")

    # 3) 在 bundle 内再配置一次：ini 与 runner 都指向 bundle 自己的目录
    b_ini, b_baked, b_engine = configure_dir(contents)
    print(f"  bundle 配置：{b_ini}")
    print(f"  lsp 烧入  ：{b_baked}")

    # 3.5) 把抢救出来的用户设置写回 bundle 的 ini —— 重装不应重置用户的设置
    kept = merge_settings(contents / "cable-summary.ini", carried)
    if kept:
        print(f"  设置已恢复：{kept} 项（装在 bundle 里的那份 ini 上）")

    # 4) 受信任位置：免掉每次启动的「未签名」询问
    print(f"  TRUSTEDPATHS：{trusted_add(contents)}")

    # 5) 迁移：删掉旧机制写在 acaddoc.lsp 里的自启块（否则会重复加载两份）
    print(f"  清理旧自启块：{strip_acaddoc_blocks()}")

    print()
    print("完成。重启 AutoCAD 后菜单会自动出现（官方 Autoloader 机制）。")
    print(f"  引擎：{'已随包复制' if b_engine else 'MISSING（包内没有 cable-summary.exe）'}；源目录引擎：{'OK' if engine_ok else 'MISSING'}")
    print("  卸载：运行 从AutoCAD卸载.bat（或 cable-summary.exe --uninstall-bundle）")
    return 0


def uninstall_bundle() -> int:
    plugins = applications_plugins()
    if plugins is None:
        print("找不到 %APPDATA%。", file=sys.stderr)
        return 3
    bundle = plugins / BUNDLE_NAME
    if not bundle.exists():
        print(f"没有安装：{bundle}")
        return 0
    try:
        shutil.rmtree(bundle)
    except OSError as exc:
        print(f"删除失败：{exc}", file=sys.stderr)
        return 4
    print(f"已删除：{bundle}")
    print("重启 AutoCAD 后菜单不再出现。")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Configure the cable summary CAD plugin")
    parser.add_argument("--setup", action="store_true", help="called by cable-summary.exe")
    parser.add_argument("--install-bundle", action="store_true",
                        help="install as an official Autoloader bundle (recommended)")
    parser.add_argument("--uninstall-bundle", action="store_true", help="remove the bundle")
    parser.add_argument("--project", default=None,
                        help="optional project/drawing tag, added to the Excel file name")
    args = parser.parse_args(argv)

    _configure_stdout()
    if args.uninstall_bundle:
        return uninstall_bundle()
    if args.install_bundle:
        return install_bundle()

    if not RUNNER.exists():
        print(f"launcher not found: {RUNNER}", file=sys.stderr)
        return 2

    ini, baked, engine_ok = configure_dir(PLUGIN_DIR, args.project)
    print(f"config written: {ini}")
    print(f"  runner = {RUNNER}")
    print(f"  engine = {ENGINE.name} {'(ready)' if engine_ok else '(MISSING!)'}")
    print(f"  lsp    = {baked}")
    print()
    print("next:")
    print("  1) double-click check.bat and make sure every item is OK")
    print("  2) double-click install.bat to install the official Autoloader bundle")
    print("     (or in AutoCAD: APPLOAD -> cable-summary-cad.lsp - works too)")
    print("  3) select the cable table, then run CABLE_SUM")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
