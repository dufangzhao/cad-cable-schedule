# 电缆表汇总套件

把 CAD 图纸里的电缆表，按 **电缆型号 / 选用芯数 / 每芯截面(mm²) 三项合并**
（同类多根电缆的**长度相加**）汇总成采购用 Excel。

## 四个交付物，彼此独立

| 交付物 | 目录 | 给谁用 | 要装什么 | 产物 |
|---|---|---|---|---|
| **CAD 插件（正式分发）** | `deliverables/menu-plugin`（源码）→ bundle | CAD 设计师 | 只要 AutoCAD 2020+ | `cable-summary-plugin-1.0.0.zip`（= 安装说明.txt + CableSummary.bundle） |
| **网页服务** | `deliverables/web-service` | 不会 CAD 的同事、采购 | 服务端一台 Python 机器 | `cable-summary-web-service-1.0.0.zip` |
| **agent skill** | `~/.dsh/skills/cad-cable-schedule/`（`tools/skill-安装说明.txt` 是它的打包说明） | 用 agent 的人 | DSH / 其他 agent | `cable-summary-skill-1.0.0.zip` |

插件**只发一个包** `cable-summary-plugin-1.0.0.zip`：解压后把 `CableSummary.bundle` 放进
`%APPDATA%\Autodesk\ApplicationPlugins\`、重启 AutoCAD 即可（bundle 首次加载自写配置）。
以前的 `cable-summary-menu-plugin` zip（解压 + 双击 install.bat）已取消。
`deliverables/menu-plugin/` 就是**插件唯一源码**（引擎入口 `main.py` + 内核 `core/` + 打包材料 `tools/` +
生成物 `cad-plugin/`），不再有第二份副本；LISP 的**基座模板**在 `tools/templates/cable-summary-base.lsp`
（构建输入，不是交付物），插件 LISP 由 `tools/make_menu_lisp.py` 从模板 + 菜单扩展生成。
免菜单版方案已下线。

四个交付物**各自打包、各自分发**，可以只给某一个人其中一份。

## 汇总口径

- 按 **电缆型号 + 选用芯数 + 每芯截面(mm²)** 三项合并分类（不是四项：长度不参与分类）
- 同一类的多根电缆**长度相加**，得到该类总长度
- Sheet 顺序：**电缆汇总** / **备用电缆** / 明细 / 待确认 / `_meta`（隐藏）
- 「电缆汇总」只有表头 + 各类别行，**不再有「合计」行**；列：`电缆型号 | 选用芯数 | 每芯截面(mm²) | 总长度(m) | 数量(根)`
- 合计数值记在隐藏 sheet `_meta` 的 metadata（JSON 类型 `bid-wisdom-pro`）里：`total_quantity` / `total_length`
- 终点标注「备用」的电缆**单独成一个「备用电缆」sheet**（表头与「电缆汇总」相同），不再排在汇总表下方，也不写「备用小计」行；备用电缆本来就不计入正式合计
- 列宽按内容**自动调整**（中文按 2 个字符宽计算），保证单元格文字能在一行里完整显示、不被截断
- 「明细」表：汇总行（`S1`、`S2`… 与备用 `B1`、`B2`…）/ 电缆型号 / 选用芯数 / 每芯截面(mm²) / 总长度(m) / 电缆号（英文逗号拼接）；「待确认」表照旧
- 图上**未填长度**的类别，总长度显示 `-`，并在「待确认」表里提示

旧口径「四项完全一致才合并」已废弃（见交接文档第 7 节的基准数据）。

## 架构：内核各自独立

**架构决定：内核不需要共用独一份**，各方案可以自行参考、各自演进。

每个交付物自带一份内核：

| 交付物 | 内核位置 |
|---|---|
| 插件 | `deliverables/menu-plugin/core/aggregate.py` |
| 菜单版 | `deliverables/menu-plugin/core/aggregate.py` |
| 网页服务 | `deliverables/web-service/core/aggregate.py` |
| skill | `~/.dsh/skills/cad-cable-schedule/scripts/电缆汇总统计.py` |

改了哪个就测哪个。`tools/sync_core.py` 只作**可选参考**（想搬实现或看一眼差异时用）：

    python tools/sync_core.py           # 把 skill 侧实现搬到某个交付物
    python tools/sync_core.py --check   # 只检查一致性

老规则（改一处必须同步全部）**已作废**——它保证结果一致，但让四个交付物无法独立演进。
跨交付物一致性由 `tests/test_consistency.py` 兜底，分叉属于**预期内**。

## 三种取数方式（都实测过）

| 方式 | 操作 | 体积 | 适用 |
|---|---|---|---|
| 插件导出 TSV | 插件自动完成 | **85 KB** | 离线/菜单插件默认路径，只含选中文字 |
| 整图 DXF | CAD 里 `SAVEAS → DXF` | 11.4 MB | 网页上传；**整图也能自动找出全部电缆表，无需先选择** |
| 读图 artifact | agent 的 `read_drawing_structure` | 1.7 MB | skill 路径，空选择/截断会失败关闭 |

## 菜单版设置对话框

菜单：电缆统计 → 统计设置…（对话框布局由 `tools/make_dcl.py` 生成，不要手改 DCL）

| 字段 | 说明 |
|---|---|
| **保存为** | 结果**完整路径（含文件名）**。留空 = 保存到桌面并**自动命名**（`工程图号_电缆汇总表.xlsx`）；以 `.xlsx` 结尾 = 就用这个文件保存；其他内容 = 当作目录，文件名自动命名 |
| **浏览…** | 弹出保存对话框（**默认位置是桌面**，默认文件名 `电缆汇总表.xlsx`，可改成任意文件名）；点「取消」不会改动已填内容，也不报错 |
| **用图纸目录** | 一键填成当前图纸所在目录 + `电缆汇总表.xlsx` |
| **工程/图号** | 拼在结果文件名最前面（工程图号_xxx.xlsx）；「保存为」填目录或完整文件名都生效，已含则不重复拼 |
| **文件名加时间戳** | 默认**关**；即使重名，引擎也不会覆盖已有文件 |
| **统计完成后自动打开 Excel** | 勾上则统计完直接打开（需装 Excel 或 WPS） |

设置保存在 `cad-plugin\cable-summary.ini`，**随插件目录一起拷贝**（默认不写注册表、不写用户目录，卸载就是删文件夹；加载时的「开机常驻」只写 TRUSTEDPATHS 与 acaddoc.lsp 两处，点菜单里的「卸载菜单」即可撤销）。
设置**自动保存且长期有效**：写在插件的 `cable-summary.ini` 里，重开 AutoCAD 不用重设；
**重装 / 升级插件也不会重置**（安装器先读旧设置、装完再写回）；改完立即生效，无需重启 CAD。

## 开机常驻：AutoCAD 官方 Autoloader

插件装成 ApplicationPlugins bundle（AutoCAD 官方插件自动加载机制），装一次，之后每次开 CAD
自动加载并显示菜单——不需要 APPLOAD，也不改用户的 acaddoc.lsp。

安装（一次性）：

    双击 cad-plugin\install.bat      （等价：cable-summary.exe --install-bundle）

它做四件事：

1. 把插件复制到 `%APPDATA%\Autodesk\ApplicationPlugins\CableSummary.bundle\`
2. 写 `PackageContents.xml`：把 `Contents\cable-summary-cad.lsp` 声明为 AutoLISP 组件
   （官方文档明确支持 lsp，组件类型按扩展名推断），并用 SeriesMin="R23.1" 限定版本范围
3. 在 bundle 内写 `cable-summary.ini`（runner 指向 bundle 自己的 run.bat），
   并把该 ini 的绝对路径烧进 bundle 内那份 LISP
4. 把 bundle 目录加进 `TRUSTEDPATHS`（受信任位置），免掉未签名 LISP 的启动询问；
   同时清掉旧机制留在 `acaddoc.lsp` 里的自启标记块（否则插件会被加载两次）

重启 AutoCAD 后菜单自动出现在菜单栏最右边。

卸载：

- 双击 `cad-plugin\uninstall.bat`（等价 --uninstall-bundle）：删掉 bundle 文件夹，重启即消失
- 菜单 电缆统计 → 卸载菜单：只对当前会话生效；若插件走的是旧 acaddoc 方式，会连同自启标记块一起删掉

回退路径：不装 bundle、直接 APPLOAD 加载 LISP 也能用，但只在当前会话有效，重启后要重新加载。
旧版本用过的 acaddoc.lsp 标记块机制已彻底移除；安装 bundle 时安装器仍会顺手清理用户机器上
可能残留的旧标记块（以及被清空后会引起启动询问的空 acaddoc.lsp）。

生成 bundle 供检查：`.venv\Scripts\python.exe tools\make_bundle.py` → `dist\CableSummary.bundle\`。

**只想发给别人？把 `dist\CableSummary.bundle` 整个文件夹（10 个文件、约 24 MB）打包发过去就够了**：
对方解压到 `%APPDATA%\Autodesk\ApplicationPlugins\` 下、重启 AutoCAD 即可——
bundle 里不带 `cable-summary.ini`（里面有绝对路径，必须每台机器自己生成），
插件**首次被加载时会自己在同目录写一份**（runner 指向自己的引擎）并把该目录加进
`TRUSTEDPATHS`；那一次启动若仍弹"未签名的可执行文件"，选「始终加载」即可。
文件夹名保持 `CableSummary.bundle` 最稳（改名了插件也会在 ApplicationPlugins 里按
`*.bundle` 找一遍我们自己）。

**装好之后解压目录可以删**：AutoCAD 加载的是 `%APPDATA%\Autodesk\ApplicationPlugins\CableSummary.bundle\`
里那份**完整副本**（LISP / 对话框 / CUIX / 引擎 / 配置全在），`PackageContents.xml` 只是告诉
AutoCAD「要加载哪个文件」的清单，运行时不读解压目录。设置也存在副本的 `cable-summary.ini` 里，
删掉解压目录既不丢设置也不影响卸载/自检（副本里带 `uninstall.bat` / `check.bat`）。
升级时用新压缩包再解压、双击新的 `install.bat` 即可，设置会保留。
（已实测：把解压目录里 9 个文件全部改名移走后，插件自检 12 项仍然全过。）

## 引擎 CLI

`cable-summary.exe`（PyInstaller 单文件绿色版，约 24 MB，内核打包了 Python 运行时 + openpyxl + ezdxf + VCRUNTIME）：

| 参数 | 作用 |
|---|---|
| `--input` | 选择集 TSV / 整图 DXF / 读图 artifact JSON |
| `--output-dir` | 结果目录（CLI 用；插件设置走 `--output`；缺省落桌面） |
| `--output-name` | 结果文件名（只写文件名不含目录；缺省按命名规则自动生成；不带扩展名按 `.xlsx`） |
| `--timestamp` | 文件名加时间戳（默认**关**） |
| `--project` | 工程/图号，拼进文件名 |
| `--output` | 完整路径（优先级最高，给了它 `--output-dir`/`--output-name` 都不参与） |
| `--response` | 写回 CAD 插件的响应文件 |

**默认命名不再带临时随机串**：插件路径下输入是系统临时目录里的随机名（`cblsum001` 之类），
拼进结果文件名只会干扰用户，现在只留 `工程图号_电缆汇总表.xlsx`。

## 目录

```text
cad-cable-schedule-suite/
├─ deliverables/
│  ├─ menu-plugin/     CAD 插件唯一源码（main.py + core/ + tools/ + cad-plugin/ 生成物 + 安装说明）
│  ├─ menu-plugin/        CAD 插件菜单版（cad-plugin/ + core/ + main.py + 使用说明.txt）
│  ├─ web-service/        网页服务（app/ + core/ + tools/ + tests/）
│  └─ skill/              安装说明.txt（skill 本体在 ~/.dsh/skills/cad-cable-schedule/）
├─ tools/
│  ├─ sync_core.py        可选：把 skill 侧内核搬到某个交付物（只作参考）
│  ├─ make_bats.py        生成 .bat（纯 ASCII + CRLF + 无 BOM）
│  ├─ build_engine.py     PyInstaller 打插件引擎单文件 exe（随插件包分发）
│  ├─ build_menu.py       重建菜单版：派生 LISP → 中文化 → 生成 dcl/cuix
│  ├─ make_menu_lisp.py   菜单版 LISP 生成器（菜单 + 设置对话框逻辑在 EXTRA 里）
│  ├─ make_dcl.py         设置对话框 DCL 生成器（GBK 由 fix_dcl_encoding.py 转）
│  ├─ make_cuix.py        兜底菜单文件 cable-summary.cuix 生成器
│  ├─ validate_lisp.py    LISP 语法/括号/裸 token 校验
│  ├─ check_defun.py      逐函数括号边界（判据最硬）
│  ├─ check_calls.py      调用-定义一致性
│  ├─ seed_ini.py         重新生成 ini 模板（打包前去掉本机绝对路径）
│  ├─ seed_lisp.py        把 .lsp 还原成英文模板（发布前）
│  ├─ fix_dcl_encoding.py UTF-8 → GBK
│  └─ package.py          打发布 zip 到 dist/（默认只打插件包）
├─ tests/                 跨交付物测试（数量一致性、exe+服务端结果对比）
└─ dist/                  发布产物（dist/<交付物名>/ 是解压出来的工作副本，package.py 不管它）
```

## 常用命令

```powershell
# 首次
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 内核（可选，只想搬实现时用）
.\.venv\Scripts\python.exe tools\sync_core.py
.\.venv\Scripts\python.exe tools\sync_core.py --check

# 重新生成一键脚本 / 重建 exe / 重建菜单版 / 重新打包
.\.venv\Scripts\python.exe tools\make_bats.py
.\.venv\Scripts\python.exe tools\build_engine.py
.\.venv\Scripts\python.exe tools\build_menu.py    # 内部按序调 make_menu_lisp / make_cuix / make_dcl / fix_dcl_encoding
.\.venv\Scripts\python.exe tools\make_dcl.py       # 只改对话框时单独跑
.\.venv\Scripts\python.exe tools\package.py
.\.venv\Scripts\python.exe tools\package.py --only web    # 只打某一个（默认只打插件包）
```

### 打包关卡（三道，全过才允许打包）

`package.py` 打包前自动跑：`validate_lisp.py` → `check_defun.py` → `check_calls.py`，
任一不过就拒绝打包。**这是为了防止再发出语法错误的包**（历史上发过两版）。

### 测试

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q      # 跨交付物一致性
```

## 编码边界与 AutoLISP 规则

细节全部写在项目根的 **`../交接文档.md`**（README 不重复），至少包括：

- 各文件 ↔ AutoCAD 的编码边界表（`.bat` 纯 ASCII、`.lsp` 纯 ASCII + GBK 八进制转义、`.dcl` GBK、`.ini` 系统 ANSI）
- AutoLISP 的真实规则：**没有 `let`**，反斜杠转义与括号的实测结论
- 菜单宏必须用 **ESC 字符**（`(strcat (chr 27) (chr 27) "_CMD ")`），`^C^C^C` 在 COM 路径不生效
- **DCL 对话框打开期间绝不要驱动命令行**（会让对话框变孤儿，只能重启 CAD）

改 LISP 请改**基座模板** `tools/templates/cable-summary-base.lsp`（基础部分）或 `tools/make_menu_lisp.py` 的 EXTRA（菜单部分），
再跑 `build_menu.py` 生成 `deliverables/menu-plugin/cad-plugin/cable-summary-cad.lsp`——**不要直接改生成出来的 `.lsp`**。

## 两条容易踩的坑（已固化进工具）

1. **.bat / .lsp 里绝不能出现非 ASCII 字符。** cmd.exe 按控制台代码页解析批处理文件，编码不对会吃掉中文后面的
   ASCII（`if not exist` 变成 `xist`），某些环境下还会让首行 `@echo off` 失效、整屏回显命令。
   AutoLISP 同理会崩。所有 .bat 由 `tools/make_bats.py` 生成，纯 ASCII + CRLF + 无 BOM；
   中文一律交给 Python/exe 输出，或写成 GBK 字节的八进制转义。
2. **子进程一律用绝对路径。** 启动器会 `cd` 到自己的目录，相对路径会解析到错误位置。
   启动器通过 `CBLSUM_CWD` 把调用者目录传给引擎，因此相对路径也能用。

主要文件：`tools/sync_core.py`、`tools/make_bats.py`、`tools/build_engine.py`、`tools/build_menu.py`、
`tools/make_dcl.py`、`tools/package.py`、`deliverables/menu-plugin/使用说明.txt`。
