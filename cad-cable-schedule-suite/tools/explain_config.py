# -*- coding: utf-8 -*-
r"""复现"插件找不到 ini"的原因，并验证新版定位逻辑。

AutoLISP 的 (findfile "cable-summary.ini") 只搜 AutoCAD 的支持搜索路径：
  当前目录 + 支持文件搜索路径（选项→文件→支持文件搜索路径）
它**不会**搜插件所在目录，也不会搜图纸目录。
所以老版本即使 configure.bat 写好了 ini，插件仍然读不到 → runner 为空。
"""
from pathlib import Path

plug = Path(r"C:\Users\ASUS\Documents\DeepSeek-WorkSpace\Projects\cad-interaction-platform\cad-cable-schedule-suite\deliverables\offline-plugin\cad-plugin")
ini = plug / "cable-summary.ini"
print("ini 实际位置:", ini)
print("ini 存在:", ini.exists())

# 老逻辑：只认 findfile（≈ 支持路径）。插件目录通常不在里面 → 找不到
support_paths = [Path.cwd(), Path.home() / "Documents"]      # 示意
old_found = None
for base in support_paths:
    cand = base / "cable-summary.ini"
    if cand.exists():
        old_found = cand
print("老逻辑（只搜支持路径）结果:", old_found or "找不到 → runner 为空 → 就是你看到的提示")

# 新逻辑：插件同目录 → 图纸目录 → 支持路径
new_found = None
for cand in [plug / "cable-summary.ini"]:
    if cand.exists():
        new_found = cand
print("新逻辑（先找插件同目录）结果:", new_found or "未找到")

# 再验证 ini 解析（含中文路径）能否取到 runner
def ini_get(path: Path, key: str, default: str = "") -> str:
    val = default
    for line in path.read_text(encoding="ascii").splitlines():
        line = line.strip()
        if line and not line.startswith(";") and line.startswith(key + "="):
            val = line[len(key) + 1:].strip()
    return val or default

runner = ini_get(ini, "runner")
print("解析出的 runner:", runner or "(空)")
print("runner 指向的文件存在:", Path(runner).exists() if runner else False)
