# -*- coding: utf-8 -*-
r"""生成菜单版交付物的 AutoCAD 菜单文件 cable-summary.cuix。

.cuix 就是一个 zip，里面是若干 XML 部件。本脚本按 AutoCAD 2020（R23.1）的
局部自定义文件（partial customization file）结构生成最小可用的菜单：

    Header.cui                 文件标识
    MenuGroup.cui              命令宏（MenuMacro）与菜单组
    PopMenuRoot.cui            弹出菜单（菜单项）
    Menu_Package_Info.xml      部件清单
    [Content_Types].xml        zip 内容类型
    _rels/.rels                关系

菜单宏统一用 _ 前缀 + ^C^C^C（先取消当前命令），这样中英文版 AutoCAD 都能识别。
生成后需要用户在 AutoCAD 里加载一次（MENU 或 CUILOAD）。

    .venv\Scripts\python.exe tools\make_cuix.py
"""
from __future__ import annotations

import pathlib
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "deliverables" / "menu-plugin" / "cad-plugin" / "cable-summary.cuix"

GROUP = "CABLESUM"

# 菜单项：(显示名, 宏, 帮助文字)
MENU_ITEMS = [
    ("统计选中电缆表", "^C^C^C_CABLE_SUM ", "统计已选中的电缆表，输出 Excel"),
    ("-", "", ""),
    ("统计设置…", "^C^C^C_CABLE_SUM_SETTINGS ", "打开设置对话框"),
    ("打开结果目录", "^C^C^C_CABLE_SUM_OPEN ", "用资源管理器打开结果所在目录"),
    ("-", "", ""),
    ("自检", "^C^C^C_CABLE_SUM_CHECK ", "检查插件配置与引擎是否就绪"),
    ("关于", "^C^C^C_CABLE_SUM_ABOUT ", "版本与配置位置"),
]

HEADER = """<?xml version="1.0" encoding="utf-8"?>
<CUI xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <Header>
    <Version MajorVersion="23" MinorVersion="1" UserVersion="0"/>
    <FileVersion MajorVersion="23" MinorVersion="1" UserVersion="0"/>
    <ProductName>AutoCAD</ProductName>
    <ProductVersion>2020</ProductVersion>
  </Header>
</CUI>
"""

CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="cui" ContentType="application/vnd.autodesk.autocad.cui+xml"/>
  <Default Extension="xml" ContentType="application/vnd.autodesk.autocad.menu+xml"/>
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="utf-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.autodesk.com/autocad/2006/relationships/menupackage" Target="Menu_Package_Info.xml"/>
</Relationships>
"""


def menu_group_xml() -> str:
    """命令宏 + 菜单组。菜单组里用 Menus 段把弹出菜单挂上菜单栏。"""
    macros = []
    for i, (name, macro, help_text) in enumerate(MENU_ITEMS, 1):
        if macro == "":
            continue
        uid = f"MM_{i:04d}"
        macros.append(f"""    <MenuMacro UID="{uid}">
      <Macro type="Any">
        <Revision MajorVersion="23" MinorVersion="1" UserVersion="0"/>
        <Name xlate="true" UID="XLS_{i:04d}">{name}</Name>
        <Command>{macro}</Command>
        <HelpString xlate="true" UID="XLS_H{i:04d}">{help_text}</HelpString>
      </Macro>
    </MenuMacro>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<MenuGroup xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" Name="{GROUP}" DisplayName="电缆统计">
  <MacroGroup Name="{GROUP}Macros" Citizen="A">
{chr(10).join(macros)}
  </MacroGroup>
  <Menus>
    <Menu UID="MENU_CABLESUM">
      <Name xlate="true" UID="XLS_MENU">电缆统计</Name>
      <PopMenuRef pUID="PM_CABLESUM" UID="PMR_CABLESUM"/>
    </Menu>
  </Menus>
</MenuGroup>
"""


def pop_menu_xml() -> str:
    """弹出菜单：菜单项引用上面的命令宏。"""
    items = []
    for i, (name, macro, help_text) in enumerate(MENU_ITEMS, 1):
        if macro == "":
            items.append(f"""    <PopMenuItem IsSeparator="true" UID="PMI_{i:04d}">
      <ModifiedRev MajorVersion="23" MinorVersion="1" UserVersion="0"/>
    </PopMenuItem>""")
            continue
        items.append(f"""    <PopMenuItem IsSeparator="false" UID="PMI_{i:04d}">
      <ModifiedRev MajorVersion="23" MinorVersion="1" UserVersion="0"/>
      <MenuMacroID UID="MM_{i:04d}"/>
      <Name xlate="true" UID="XLS_{i:04d}">{name}</Name>
    </PopMenuItem>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<PopMenuRoot xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <PopMenu hasDiesel="false" UID="PM_CABLESUM">
    <ModifiedRev MajorVersion="23" MinorVersion="1" UserVersion="0"/>
    <Name xlate="true" UID="XLS_PM">电缆统计</Name>
{chr(10).join(items)}
  </PopMenu>
</PopMenuRoot>
"""


def package_info_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8"?>
<MenuPackageParts>
  <PartData PartData_Name="/Header.cui"/>
  <PartData PartData_Name="/MenuGroup.cui"/>
  <PartData PartData_Name="/PopMenuRoot.cui"/>
</MenuPackageParts>
"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    parts = {
        "Header.cui": HEADER,
        "MenuGroup.cui": menu_group_xml(),
        "PopMenuRoot.cui": pop_menu_xml(),
        "Menu_Package_Info.xml": package_info_xml(),
        "[Content_Types].xml": CONTENT_TYPES,
        "_rels/.rels": RELS,
    }
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in parts.items():
            z.writestr(name, text)
    print(f"已生成 {OUT.relative_to(ROOT)}  ({OUT.stat().st_size} 字节)")
    print("  菜单组:", GROUP, "| 菜单项:", len([m for m in MENU_ITEMS if m[1]]), "个命令",
          "+", len([m for m in MENU_ITEMS if not m[1]]), "个分隔线")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
