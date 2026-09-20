# -*- coding: utf-8 -*-
r"""把交付物打包成可独立分发的 zip。

默认只打 CAD 插件包：`cable-summary-plugin-<ver>.zip` = `安装说明.txt` + `CableSummary.bundle/`，
拿到的人解压后把 CableSummary.bundle 放进 %APPDATA%\Autodesk\ApplicationPlugins\ 再重启
AutoCAD 就能用（bundle 首次加载自写配置）。旧的 cable-summary-menu-plugin zip 已取消。

注意：四个交付物的内核（core/aggregate.py）**各自独立、允许各自演进**，
打包时不比对它们是否一致，只校验各交付物自身的 LISP 静态正确性。

    .venv\Scripts\python.exe tools\package.py                     # 只打插件包
    .venv\Scripts\python.exe tools\package.py --only web          # 打指定交付物

产出 dist/：
  cable-summary-plugin-<ver>.zip           ★ CAD 插件（唯一形态）：安装说明 + CableSummary.bundle
  cable-summary-web-service-<ver>.zip      网页服务：服务端跑 Python，浏览器上传
  cable-summary-skill-<ver>.zip            agent skill：装进 agent 的 skills 目录

插件包的内容就是 bundle 本身：解压 → 把 CableSummary.bundle 放进 ApplicationPlugins →
重启 AutoCAD。首次加载会自写配置，所以不需要安装脚本，也没有「解压目录」这一层。
其余三个交付物**互相解耦**、各自带一份汇总内核（由 tools/sync_core.py 同步）。
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DELIV = ROOT / "deliverables"
SKILL_SRC = Path.home() / ".dsh" / "skills" / "cad-cable-schedule"
VERSION = "1.0.0"

EXCLUDE_DIRS = {"__pycache__", ".venv", ".pytest_cache", "build", "dist", "logs", "out", ".git"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".bak"}
# 菜单版的 ini 含本机绝对路径，分发时必须由 install.bat 重新生成
EXCLUDE_NAMES = {"cable-summary.ini"}
# 注意：cable-summary.ini **要**打进包里（模板形态，runner 为空），
# 否则收件人刚解压时插件找不到配置文件，会以为插件坏了。
# 本机已配置的那份含绝对路径，由 tools/seed_ini.py 重新生成模板后再打包。


def add_tree(zf: zipfile.ZipFile, base: Path, arc_prefix: str, *, skip_ini: bool = False) -> int:
    count = 0
    for path in sorted(base.rglob("*")):
        if path.is_dir():
            continue
        # 只看**相对 base** 的路径段：否则源目录本身在 dist/ 下时（bundle 就是这种情况）
        # 会被 EXCLUDE_DIRS 里的 "dist" 整体排除掉，打出个空包。
        rel_parts = path.relative_to(base).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        if path.suffix.lower() in EXCLUDE_SUFFIX:
            continue
        if skip_ini and path.name in EXCLUDE_NAMES:
            continue
        zf.write(path, f"{arc_prefix}/{path.relative_to(base).as_posix()}")
        count += 1
    return count


def build_plugin() -> Path:
    """CAD 插件（唯一的分发形态）：官方 Autoloader bundle + 安装说明。

    包里就是「解压 → 把 CableSummary.bundle 放进 ApplicationPlugins → 重启 CAD」，
    不需要安装脚本：bundle 首次加载会自己写配置（见 LISP 的 cblsum:ensure-config）。
    以前的 cable-summary-menu-plugin zip（解压 + 双击 install.bat）不再产出。
    """
    import subprocess
    # 先按当前源码重新生成 bundle，避免拿到上一次构建的旧文件
    subprocess.run([sys.executable, str(ROOT / "tools" / "make_bundle.py")],
                   check=True, cwd=str(ROOT))
    bundle = DIST / "CableSummary.bundle"
    if not (bundle / "PackageContents.xml").exists():
        raise FileNotFoundError(f"bundle 未生成：{bundle}")
    # 防呆闸：分发的 LISP 必须是模板态（cblsum-ini nil）。曾经把烧入本机绝对路径的副本
    # 打进包里，收件人那边就会指向不存在的路径。
    lisp = bundle / "Contents" / "cable-summary-cad.lsp"
    for line in lisp.read_text(encoding="ascii").splitlines():
        if "cblsum-ini" in line and "<<" in line:
            if " nil)" not in line:
                raise ValueError("LISP 里烧入了绝对路径，拒绝打包（先跑 seed_lisp.py 重置模板）")
            break
    else:
        raise ValueError("LISP 里找不到 cblsum-ini 模板行，拒绝打包")

    guide = DELIV / "menu-plugin" / "安装说明.txt"
    out = DIST / f"cable-summary-plugin-{VERSION}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        if guide.exists():
            zf.write(guide, "安装说明.txt")        # 最外层，拿到手先看它
        add_tree(zf, bundle, "CableSummary.bundle")
    return out


def build_web() -> Path:
    src = DELIV / "web-service"
    out = DIST / f"cable-summary-web-service-{VERSION}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        add_tree(zf, src, "cable-summary-web-service")
    return out


def build_skill() -> Path:
    if not SKILL_SRC.exists():
        raise FileNotFoundError(f"找不到 skill 源目录：{SKILL_SRC}")
    out = DIST / f"cable-summary-skill-{VERSION}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        guide = ROOT / "tools" / "skill-安装说明.txt"
        if guide.exists():
            zf.write(guide, "安装说明.txt")
        add_tree(zf, SKILL_SRC, "cad-cable-schedule")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="打包交付物（默认只打插件包）")
    parser.add_argument("--only", choices=["plugin", "web", "skill"],
                        help="plugin=CAD 插件包（默认）；web/skill 为另两种交付物")
    args = parser.parse_args()

    DIST.mkdir(parents=True, exist_ok=True)
    # 打包插件前先把基础 LISP / ini 重置成模板（避免把本机绝对路径发出去），
    # 再按当前源码重建插件版 LISP，最后过三道 LISP 关卡——
    # 曾经因为少一个右括号发过一版加载报错的包，所以这里宁可慢几秒。
    import subprocess
    if args.only in (None, "plugin"):
        for name in ("seed_ini.py", "seed_lisp.py"):
            seed = ROOT / "tools" / name
            if seed.exists():
                subprocess.run([sys.executable, str(seed)], check=True, cwd=str(ROOT))
        rc = subprocess.run([sys.executable, str(ROOT / "tools" / "build_menu.py")],
                            cwd=str(ROOT)).returncode
        if rc != 0:
            print("插件 LISP 重建失败（build_menu.py），拒绝打包", file=sys.stderr)
            return 2
        lisp = DELIV / "menu-plugin" / "cad-plugin" / "cable-summary-cad.lsp"
        for tool, label in (("validate_lisp.py", "语法/括号"),
                            ("check_defun.py", "逐函数括号边界"),
                            ("check_calls.py", "调用-定义一致性")):
            rc = subprocess.run([sys.executable, str(ROOT / "tools" / tool), str(lisp)],
                                cwd=str(ROOT)).returncode
            if rc != 0:
                print(f"LISP {label} 校验未通过，拒绝打包", file=sys.stderr)
                return 2
    jobs = {"plugin": build_plugin, "web": build_web, "skill": build_skill}
    # 默认只打插件包（CAD 插件现在的唯一分发形态）；其余交付物用 --only 显式指定
    for key in ([args.only] if args.only else ["plugin"]):
        try:
            path = jobs[key]()
        except FileNotFoundError as exc:
            print(f"跳过 {key}：{exc}")
            continue
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
        print(f"{path.name}  {path.stat().st_size / 1024 / 1024:.1f} MB  {len(names)} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
