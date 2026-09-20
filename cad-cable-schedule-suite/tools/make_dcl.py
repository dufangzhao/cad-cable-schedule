# -*- coding: utf-8 -*-
r"""生成菜单版的设置对话框 cable-summary-settings.dcl。

DCL 控件里的中文由 AutoCAD 按 ANSI 代码页读取，所以最终文件必须是 GBK：
本脚本先写 UTF-8，紧接着由 tools/fix_dcl_encoding.py 转成 GBK（build_menu.py 会按序调用）。

布局说明（用户反馈后重排，2026-09-18）：
  · 结果目录只有一处输入：目录框 + 「浏览…」+「用图纸目录」。
    旧版还有一对单选「保存到桌面 / 保存到指定目录」，和目录框表达同一件事，
    用户明确指出重复，已删除；改成在框下写明「留空 = 保存到桌面」。
  · 「浏览…」取消必须无副作用（回调里的错误会连带关闭整个对话框，历史 bug）。
  · 2026-09-18 v3 新增「文件名」框：插件路径下引擎拿到的输入是系统临时目录里的
    随机 TSV 名（cblsum001 之类），旧版结果文件名会带上那个随机串，用户看不懂。
    现在文件名由这里指定（或留空走引擎的默认命名规则），「浏览…」一次性同时设定
    目录和文件名（getfiled 挑文件模式）。
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables" / "menu-plugin" / "cad-plugin" / "cable-summary-settings.dcl"

DCL = r'''// 电缆统计 · 设置对话框
// AutoCAD 的 DCL 对话框定义。配合 LISP 里的 CABLE_SUM_SETTINGS 命令使用。
//
// 注意：DCL 控件里的中文按 ANSI 代码页读取，本文件必须是 GBK 或纯 ASCII。
// 本文件由 tools/make_dcl.py 生成，不要手改；改模板请改生成脚本。

cable_summary_settings : dialog {
  label = "电缆统计 · 设置";

  : boxed_column {
    label = "结果文件";

    : row {
      : edit_box { key = "out_dir"; label = "保存为："; edit_width = 40; }
      : button { key = "browse"; label = "浏览…"; width = 10; }
      : button { key = "use_dwg_dir"; label = "用图纸目录"; width = 14; }
    }

    : edit_box { key = "project"; label = "工程/图号："; edit_width = 24; }

    : toggle { key = "timestamp"; label = "文件名加时间戳（避免覆盖同名文件）"; }
  }

  : boxed_column {
    label = "行为";

    : toggle { key = "auto_open"; label = "统计完成后自动打开 Excel"; }
  }

  : text {
    key = "hint";
    label = "设置保存在 cad-plugin\\cable-summary.ini，随插件目录一起拷贝。";
  }

  : row {
    : spacer { width = 1; }
    : button { key = "accept"; label = "保存"; is_default = true; }
    : button { key = "cancel"; label = "取消"; is_cancel = true; }
  }
}
'''


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(DCL, encoding="utf-8")
    lines = DCL.count(chr(10))
    print(f"已生成 {OUT.name}（UTF-8 中间态，{lines} 行）——随后由 fix_dcl_encoding.py 转 GBK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
