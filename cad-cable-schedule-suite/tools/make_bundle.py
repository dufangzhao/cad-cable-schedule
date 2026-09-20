# -*- coding: utf-8 -*-
r"""生成 AutoCAD 官方 Autoloader 插件包（ApplicationPlugins bundle）。

    .venv\Scripts\python.exe tools\make_bundle.py

产出 dist/CableSummary.bundle/：

    PackageContents.xml        官方清单：把 Contents\cable-summary-cad.lsp 声明成 AutoLISP 组件
    Contents/                  插件本体（从 deliverables/menu-plugin/cad-plugin/ 收集）
        cable-summary-cad.lsp  主 LISP（ModuleName 指向它）
        cable-summary-settings.dcl
        cable-summary.cuix     兜底菜单文件
        cable-summary.exe      汇总引擎（单文件）
        run.bat / check.bat / install.bat / uninstall.bat
        README.txt             纯 ASCII 说明（PackageContents.xml 的 HelpFile 指向它）

用户怎么用：双击 cad-plugin\install.bat（它由 setup_plugin.py --install-bundle 完成全部工作：
配置本目录 → 复制成 bundle → 在 bundle 内再配置一次 → 写 TRUSTEDPATHS → 清理旧机制残留），
重启 AutoCAD 就会自动加载——这是官方机制，不需要改 acaddoc.lsp。
本脚本生成的 dist/CableSummary.bundle 主要用于检查产物结构。

注意：PackageContents.xml 的模板在 setup_plugin.py 里有一份同样的拷贝（exe 内不能再依赖
本脚本），改这里时两处必须同步。

幂等：先删旧 bundle 再重建。
"""
from __future__ import annotations

import pathlib
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "deliverables" / "menu-plugin" / "cad-plugin"
OUT = ROOT / "dist" / "CableSummary.bundle"

BUNDLE_NAME = "CableSummary.bundle"
APP_VERSION = "1.0.0"
PRODUCT_CODE = "{7E2C1A44-5D91-4B7F-9E33-1A2B3C4D5E6F}"

# 要收进 Contents 的文件；LSP 是必需的（ModuleName 指向它），其余缺失只警告
FILES = [
    "cable-summary-cad.lsp",
    "cable-summary-settings.dcl",
    "cable-summary.cuix",
    "cable-summary.exe",
    "run.bat",
    "check.bat",
    "install.bat",
    "uninstall.bat",
]
REQUIRED = {"cable-summary-cad.lsp"}

README = (
    "Cable Summary - AutoCAD plugin bundle (official Autoloader).\n"
    "\n"
    "Copy this whole folder into %APPDATA%\\Autodesk\\ApplicationPlugins\\ and restart AutoCAD:\n"
    "PackageContents.xml declares cable-summary-cad.lsp as an AutoLISP component, so AutoCAD\n"
    "loads it by itself at every start (no acaddoc.lsp, no APPLOAD).\n"
    "\n"
    "Nothing else is needed: on the first load the plugin writes its own cable-summary.ini\n"
    "next to this file (it holds absolute paths, so it is per machine) and adds this folder\n"
    "to TRUSTEDPATHS. If your AutoCAD still asks about the unsigned file on that first\n"
    "start, choose 'Always load'.\n"
    "\n"
    "install.bat in this folder does the same and also updates TRUSTEDPATHS right away -\n"
    "run it if you prefer to configure before the first start.\n"
    "\n"
    "Uninstall: delete this folder from ApplicationPlugins, then restart AutoCAD.\n"
)


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


def main() -> int:
    if not SRC.is_dir():
        print(f"找不到插件目录：{SRC}", flush=True)
        return 2
    if OUT.exists():
        shutil.rmtree(OUT)
    contents = OUT / "Contents"
    contents.mkdir(parents=True)

    missing = []
    copied = []
    for name in FILES:
        s = SRC / name
        if s.exists():
            shutil.copy2(s, contents / name)
            copied.append((f"Contents/{name}", (contents / name).stat().st_size))
        else:
            missing.append(name)

    (OUT / "PackageContents.xml").write_text(package_contents_xml(), encoding="utf-8")
    (contents / "README.txt").write_text(README, encoding="ascii")

    print(f"已生成 {OUT.relative_to(ROOT)}")
    print(f"  {BUNDLE_NAME}/PackageContents.xml  ({len(package_contents_xml())} 字符)")
    for rel, size in copied:
        print(f"  {BUNDLE_NAME}/{rel}  {size} 字节")
    print(f"  {BUNDLE_NAME}/Contents/README.txt")
    if missing:
        print("  警告：以下文件缺失，未收进 bundle：" + ", ".join(missing))
        if REQUIRED & set(missing):
            print("  必需的 LISP 缺失，bundle 不会工作", flush=True)
            return 2
    print("  这个 bundle 就是分发形态：整包由 tools/package.py 打成")
    print("  dist/cable-summary-plugin-<ver>.zip（含安装说明.txt），")
    print("  收件人解压后把 CableSummary.bundle 放进 ApplicationPlugins 即可。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
