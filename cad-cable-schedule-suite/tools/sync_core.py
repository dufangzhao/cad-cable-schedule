# -*- coding: utf-8 -*-
"""（可选）把 skill 里的汇总内核同步到各交付物——**仅作参考，不是强制约束**。

架构决定（用户 2026-09 确认）：**四个交付物的内核各自独立，允许各自演进**。
本脚本保留下来只做两件事：
  · 想把 skill 侧的实现搬给某个交付物时，一键复制（省去手工拷贝）
  · 想知道"当前各处是否还一致"时，--check 看一眼

**不再要求**改完 skill 就必须同步到所有交付物。
如果某个交付物需要走不同的实现，直接改它的 core/aggregate.py 即可；
只要它自己的测试通过就成立。跨交付物结果若出现差异，那是预期内的，
由各自的测试去覆盖，而不是当作错误。

（历史上的强制同步规则已作废：它保证了结果一致，但也让四个交付物
 无法独立演进，代价大于收益。）

原说明：
把 skill 里的汇总内核同步到各交付物。

内核（型号+芯数+截面三项一致即合并）只有一处权威实现：skill 的
scripts/电缆汇总统计.py。三个交付物各自**内置一份副本**，因此可以独立分发；
但绝不允许各自修改逻辑，否则三条路径的数量会分叉。

同步目标：
  deliverables/menu-plugin/core/aggregate.py
  deliverables/web-service/core/aggregate.py

    python tools/sync_core.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path.home() / ".dsh" / "skills" / "cad-cable-schedule" / "scripts" / "电缆汇总统计.py"
TARGETS = [
    ROOT / "deliverables" / "menu-plugin" / "core" / "aggregate.py",
    ROOT / "deliverables" / "menu-plugin" / "core" / "aggregate.py",
    ROOT / "deliverables" / "web-service" / "core" / "aggregate.py",
]
BANNER = '''# -*- coding: utf-8 -*-
# ============================================================================
# 本文件由 cad-cable-schedule skill 同步而来，是"型号+芯数+截面三项一致即合并"口径的唯一实现。
# 来源：~/.dsh/skills/cad-cable-schedule/scripts/电缆汇总统计.py
# 请勿在此处单独修改汇总口径；改 skill 侧后运行 python tools/sync_core.py。
# ============================================================================
'''


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def expected(source: Path) -> str:
    text = source.read_text(encoding="utf-8")
    return BANNER + text.replace("# -*- coding: utf-8 -*-\n", "", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description="同步汇总内核到各交付物")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE))
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"找不到内核源文件：{source}", file=sys.stderr)
        return 2
    want = expected(source)
    bad = 0
    for target in TARGETS:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if args.check:
            if current == want:
                print(f"一致  {target.relative_to(ROOT)}  sha256:{digest(current.encode())}")
            else:
                print(f"不一致 {target.relative_to(ROOT)}", file=sys.stderr)
                bad += 1
            continue
        if current == want:
            print(f"已是最新 {target.relative_to(ROOT)}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.copy2(target, target.with_suffix(".py.bak"))
        target.write_text(want, encoding="utf-8")
        print(f"已同步  {target.relative_to(ROOT)}  sha256:{digest(want.encode())}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
