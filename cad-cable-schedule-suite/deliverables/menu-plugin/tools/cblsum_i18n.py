# -*- coding: utf-8 -*-
"""插件提示的中英文对照表 + GBK 八进制转义。

AutoCAD 按系统 ANSI 代码页解析 LISP，UTF-8 中文会让文件解析失败。
所以中文以 GBK 字节的八进制转义写进 .lsp：源码 100% ASCII，运行时显示中文。
"""


def esc(text: str, encoding: str = "gbk") -> str:
    out = []
    for b in text.encode(encoding):
        ch = chr(b)
        if b < 128 and ch not in chr(34) + chr(92):
            out.append(ch)
        else:
            out.append(chr(92) + format(b, "03o"))
    return "".join(out)


PAIRS = [
    ("[cable-sum-schedule] Cable summary (offline)  v", "[电缆汇总] 离线版  v"),
    ("[cable-sum-schedule] first run: wrote cable-summary.ini next to the plugin.",
     "[电缆汇总] 首次运行：已在插件目录里生成 cable-summary.ini。"),
    ("[cable-sum-schedule] plugin folder added to TRUSTEDPATHS (no startup prompt).",
     "[电缆汇总] 插件目录已加入受信任位置（以后启动不再询问）。"),
    ("[cable-sum-schedule] config: not baked in - run install.bat to fix that",
     "[电缆汇总] 尚未配置：请先双击 install.bat"),
    ("[cable-sum-schedule] config: ", "[电缆汇总] 配置文件: "),
    ("[cable-sum-schedule] plugin loaded v", "[电缆汇总] 插件已加载 v"),
    ("[cable-sum-schedule] offline: select the cable table, then run CABLE_SUM (alias CBLSUM)",
     "[电缆汇总] 用法：先框选电缆表，再输入 CABLE_SUM（短命令 CBLSUM）"),
    ("[cable-sum-schedule] cable-summary.ini NOT FOUND. Looked in:",
     "[电缆汇总] 找不到 cable-summary.ini，已查找以下位置:"),
    ("[cable-sum-schedule] locating the engine (first run only)...",
     "[电缆汇总] 正在定位引擎（仅首次需要）..."),
    ("[cable-sum-schedule] engine not found in the usual places.",
     "[电缆汇总] 在支持路径和 C:\\cable-summary 都没有找到引擎。"),
    ("[cable-sum-schedule] Cannot find cable-summary.exe. Pick one of these two:",
     "[电缆汇总] 找不到 cable-summary.exe，两种解决办法："),
    ("  A) add the cad-plugin folder to AutoCAD's support search path (no setup needed):",
     "  甲）把 cad-plugin 目录加入 AutoCAD 的支持文件搜索路径："),
    ("     OPTIONS - Files - Support File Search Path - Add - pick the cad-plugin folder",
     "     选项 → 文件 → 支持文件搜索路径 → 添加 → 选中 cad-plugin 目录"),
    ("  B) or just double-click install.bat once in the cad-plugin folder;",
     "     只需在本目录双击一次 install.bat；"),
    ("     it writes the absolute paths into the config, so the folder can live anywhere.",
     "      它会把绝对路径写进配置，因此插件目录可以放在任意位置。"),
    ("[cable-sum-schedule] launcher not found: ", "[电缆汇总] 找不到启动器: "),
    ("Please re-extract the package, or run install.bat once.",
     "请重新解压安装包，或运行一次 install.bat。"),
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
    ("[cable-sum-schedule] settings saved",
     "[电缆汇总] 设置已保存"),
    ("cable-sum-schedule] settings dialog needs the file: ",
     "[电缆汇总] 设置对话框需要文件: "),
    ("[cable-sum-schedule] cannot load dialog: ",
     "[电缆汇总] 无法加载对话框: "),
    ("[cable-sum-schedule] result folder: ",
     "[电缆汇总] 结果目录: "),
    ("[cable-sum-schedule] no result folder yet - nothing to open.",
     "[电缆汇总] 还没有结果目录，暂无可打开的位置。"),
    ("[cable-sum-schedule] version ",
     "[电缆汇总] 版本 "),
    ("config file: ",
     "配置文件: "),
    ("engine     : ",
     "引擎      : "),
    ("[cable-sum-schedule] building the menu with COM, no menu file needed...",
     "[电缆汇总] 正在用 COM 创建菜单，不需要菜单文件..."),
    ("[cable-sum-schedule] COM is not available in this AutoCAD.",
     "[电缆汇总] 当前 AutoCAD 不支持 COM 接口。"),
    ("[cable-sum-schedule] cannot read the menu groups of this AutoCAD.",
     "[电缆汇总] 无法读取 AutoCAD 的菜单组。"),
    ("[cable-sum-schedule] existing menu group reused: ",
     "[电缆汇总] 沿用已有的菜单组: "),
    ("[cable-sum-schedule] menu group created: ",
     "[电缆汇总] 已创建菜单组: "),
    ("[cable-sum-schedule] cannot create the menu group ",
     "[电缆汇总] 无法创建菜单组 "),
    ("[cable-sum-schedule] using the base menu group instead.",
     "[电缆汇总] 改用基本菜单组。"),
    ("[cable-sum-schedule] this menu lasts for this AutoCAD session only.",
     "[电缆汇总] 该菜单仅在本次 AutoCAD 会话中有效。"),
    ("[cable-sum-schedule] no menu group is available for the menu.",
     "[电缆汇总] 没有可用的菜单组，无法创建菜单。"),
    ("[cable-sum-schedule] existing popup menu reused: ",
     "[电缆汇总] 沿用已有的弹出菜单: "),
    ("[cable-sum-schedule] popup menu created: ",
     "[电缆汇总] 已创建弹出菜单: "),
    ("[cable-sum-schedule] cannot create the popup menu: ",
     "[电缆汇总] 无法创建弹出菜单: "),
    ("[cable-sum-schedule] menu item added: ",
     "[电缆汇总] 已添加菜单项: "),
    ("[cable-sum-schedule] cannot add the menu item ",
     "[电缆汇总] 无法添加菜单项 "),
    ("[cable-sum-schedule] separator added.",
     "[电缆汇总] 已添加分隔线。"),
    ("[cable-sum-schedule] cannot add the separator: ",
     "[电缆汇总] 无法添加分隔线: "),
    ("[cable-sum-schedule] the menu is already on the menu bar.",
     "[电缆汇总] 菜单栏上已有该菜单，不再重复添加。"),
    ("[cable-sum-schedule] cannot insert the menu into the menu bar: ",
     "[电缆汇总] 无法把菜单加到菜单栏: "),
    ("[cable-sum-schedule] menu added to the menu bar (look at the right end).",
     "[电缆汇总] 菜单已加到菜单栏（请看最右边）。"),
    ("[cable-sum-schedule] cannot read the menu bar of this drawing.",
     "[电缆汇总] 无法读取当前图纸的菜单栏。"),
    ("[cable-sum-schedule] the COM route did not finish - trying the menu file.",
     "[电缆汇总] COM 方式未完成，改用菜单文件重试。"),
    ("[cable-sum-schedule] no menu was created.",
     "[电缆汇总] 未能创建菜单。"),
    ("[cable-sum-schedule] cannot switch the menu bar on.",
     "[电缆汇总] 无法打开菜单栏显示。"),
    ("[cable-sum-schedule] menu bar display is on (MENUBAR=1).",
     "[电缆汇总] 菜单栏显示已打开（MENUBAR=1）。"),
    ("[cable-sum-schedule] popup menu found in the CABLESUM menu group.",
     "[电缆汇总] 在 CABLESUM 菜单组里找到了弹出菜单。"),
    ("[cable-sum-schedule] popup menu found in the base menu group (ACAD).",
     "[电缆汇总] 在基本菜单组（ACAD）里找到了弹出菜单。"),
    ("[cable-sum-schedule] no cable summary menu is loaded.",
     "[电缆汇总] 当前没有加载电缆统计菜单。"),
    ("[cable-sum-schedule] the menu is not on the menu bar, so there is nothing to take off.",
     "[电缆汇总] 菜单不在菜单栏上，无需移除。"),
    ("[cable-sum-schedule] menu taken off the menu bar.",
     "[电缆汇总] 已把菜单从菜单栏移除。"),
    ("Choose where the result file is saved",
     "选择结果保存的位置与文件名"),
    ("[cable-sum-schedule] auto-open is off - open it when you need it.",
     "[电缆汇总] 已关闭自动打开，需要时请自行打开结果文件。"),
    ("[cable-sum-schedule] the dialog was terminated by another command.",
     "[电缆汇总] 对话框被其他命令中断了。"),
    ("[cable-sum-schedule] the CABLESUM menu group is not loaded, so there is nothing to unload.",
     "[电缆汇总] CABLESUM 菜单组未加载，无需卸载。"),
    ("[cable-sum-schedule] the base menu group cannot be unloaded - the menu stays there and is reused next time.",
     "[电缆汇总] 基本菜单组不能卸载——菜单留在其中，下次可直接复用。"),
    ("[cable-sum-schedule] cable-summary.cuix not found next to the plugin.",
     "[电缆汇总] 插件目录下找不到 cable-summary.cuix。"),
    ("[cable-sum-schedule] menu file: ",
     "[电缆汇总] 菜单文件: "),
    ("[cable-sum-schedule] menu group already loaded: ",
     "[电缆汇总] 菜单组已经加载: "),
    ("[cable-sum-schedule] menu group loaded: ",
     "[电缆汇总] 菜单组已加载: "),
    ("[cable-sum-schedule] cannot load the menu file: ",
     "[电缆汇总] 无法加载菜单文件: "),
    ("[cable-sum-schedule] the loaded menu file has no menu named: ",
     "[电缆汇总] 加载的菜单文件里没有这个菜单: "),
    ("[cable-sum-schedule] MENUUNLOAD failed: ",
     "[电缆汇总] MENUUNLOAD 失败: "),
    ("[cable-sum-schedule] MENUUNLOAD done.",
     "[电缆汇总] 菜单组已卸载。"),
    ("[cable-sum-schedule] cannot take the menu off the menu bar: ",
     "[电缆汇总] 无法把菜单从菜单栏移除: "),
    ("[cable-sum-schedule] unloading the menu group CABLESUM...",
     "[电缆汇总] 正在卸载菜单组 CABLESUM..."),
    ("Cable Summary",
     "电缆统计"),
    ("Count Selected Cables",
     "统计选中电缆表"),
    ("Settings...",
     "统计设置…"),
    ("Open Result Folder",
     "打开结果目录"),
    ("Self Check",
     "自检"),
    ("About",
     "关于"),
    ("Unload Menu",
     "卸载菜单"),
    ("[cable-sum-schedule] running the self check - read the window that just opened.",
     "[电缆汇总] 正在运行自检——请看刚弹出的窗口里的结果。"),
    ("[cable-sum-schedule] cannot find check.bat - run it from the cad-plugin folder.",
     "[电缆汇总] 找不到 check.bat，请在 cad-plugin 目录里手动运行它。"),
    # --- 结果文件名（设置对话框的「文件名」框）---
    # 生成器（make_menu_lisp.py）拒绝非 ASCII，所以英文模板里只能放占位符，
    # 由这张表换成真正的中文默认文件名（和引擎不带 --output-name 时的默认名一致）
    ("cblsum-default-output-name.xlsx",
     "电缆汇总表.xlsx"),
    # --- 开机自启（TRUSTEDPATHS + acaddoc.lsp 标记块；首次加载自动安装）---
    # --- 设置对话框：单个「保存为」框 + 浏览对话框标题 ---
    ("Choose where the result file is saved",
     "选择结果保存的位置与文件名"),
    # --- 首次加载时自动常驻（以后每次启动自动加载插件并建菜单） ---
    # 注意：本表的替换是"子串替换、按表顺序执行"，句子里不能包含表里已有的其他词条
    # （例如产品名 Cable Summary、菜单项名），否则会被先替换掉而导致整句匹配失败。
    ("[cable-sum-schedule] to remove the plugin completely, run uninstall.bat in the plugin folder.",
     "[电缆汇总] 要彻底移除插件，请运行插件目录里的 uninstall.bat。"),
]


def _flexible_pattern(en: str) -> str:
    """把对照表里的英文串编译成正则，连续反斜杠按"一个或多个"匹配。

    为什么：LISP 源码里的路径是全字面量（例如 C:\\cable-summary\\），
    与 Python 三层转义后写出的对照表差一个反斜杠就会整条失配。
    与其逐条对齐转义层数，不如让匹配对反斜杠数量容错。
    """
    import re
    parts = [re.escape(p) for p in en.split(chr(92))]
    return chr(92) + "+".join(parts)


# 特殊规则：含有 Windows 路径的提示，反斜杠在源码里是全字面量，
# 与对照表无论如何都对不齐转义层数。这里按 ASCII 前缀整体替换，不再比较路径部分。
SPECIAL = [
    ("B) or move the whole cad-plugin folder to ",
     "乙）或把整个 cad-plugin 目录放到 C:" + chr(92) * 2 + "cable-summary" + chr(92) * 2 + " 再试一次"),
]


def localize(text: str) -> tuple[str, list[str]]:
    """把英文提示换成中文转义；返回 (新文本, 未匹配到的英文串列表)。"""
    missed = []
    for en, zh in PAIRS:
        if en in text:
            text = text.replace(en, esc(zh))
        elif esc(zh) not in text:
            # 路径类提示里的反斜杠与对照表对不齐转义层数，交给 SPECIAL 规则处理
            if not any(en.startswith(pref) for pref, _ in SPECIAL):
                missed.append(en)
    return text, missed
