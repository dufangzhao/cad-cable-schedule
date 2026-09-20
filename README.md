# 电缆表汇总插件（CAD Cable Schedule Suite）

> 在 AutoCAD 里**框选电缆表，一键汇总成采购用的 Excel**：按「电缆型号 + 选用芯数 + 每芯截面」
> 合并同类、长度相加，备用/预留电缆单独成表，图上没填的参数进「待确认」。
> 全过程在本机完成——图纸不出机器，目标机器不需要联网、不需要 Python、不需要管理员权限。

## 特性

- **一键汇总**：框选图纸里的电缆表 → 菜单「统计选中电缆表」→ 自动生成 Excel 并打开
- **识别稳健**：以「电缆号」列头为锚点自动识别表格；图框、说明文字、负荷表等干扰会被排除并说明
- **口径明确**：型号/芯数/截面三项一致即归为一类，`长度(m)` 按类相加；备用/预留电缆单独成表、不计入合计
- **可追溯**：另附「明细」（每一类对应哪些电缆号）与「待确认」（未填参数、只有编号的空行、缺号、重复号）
- **免安装**：官方 Autoloader 插件包（`ApplicationPlugins` bundle），放进目录重启 CAD 即用；
  不改用户任何配置（不写 acaddoc.lsp、不动支持路径），卸载 = 删文件夹
- **零依赖引擎**：单文件 exe 自带 Python 运行库与 openpyxl，在没有 Python 的机器上照常运行
- **干净的 Excel**：无合计行、列宽按内容自适应、中文不乱码

## 安装（三步，只需一次）

1. 取得 `cable-summary-plugin-1.0.0.zip`（见本仓库 Releases；或按下面「从源码构建」自行打包）
2. 解压，把其中的 **`CableSummary.bundle` 整个文件夹**放进：
   ```text
   %APPDATA%\Autodesk\ApplicationPlugins\
   ```
   路径必须正好是 `...\ApplicationPlugins\CableSummary.bundle\PackageContents.xml`（不多不少一层）
3. 重启 AutoCAD → 菜单栏最右侧出现「电缆统计」

首次启动若弹「安全性 - 未签名的可执行文件」，选**始终加载**（插件会把自己目录加进受信任位置，之后不再询问）。
插件首次加载会在自己目录里生成配置文件（自举），**不需要任何安装脚本**。

> 插件包里的 `安装说明.txt` 是面向最终用户的中文图文步骤；
> 目标机器只需 Windows 版 AutoCAD **2020 或更高**（不支持 AutoCAD LT）。

## 使用

1. 在图纸里框选电缆表（连表头一起框；可以把图框一起框进去）
2. 点菜单 **电缆统计 → 统计选中电缆表**（命令行等价命令：`CABLE_SUM` / `CBLSUM`）
3. 命令行打印进度，完成后自动打开 Excel

结果默认存到桌面；保存位置、工程/图号（会拼在文件名最前）、时间戳、是否自动打开，都在
**电缆统计 → 统计设置…** 里改。设置保存一次长期有效，重装/升级插件也不会被重置。

### 输出结构（`电缆汇总表.xlsx`）

| sheet | 内容 |
|---|---|
| 电缆汇总 | 采购口径：电缆型号 / 选用芯数 / 每芯截面(mm²) / 总长度(m) / 数量（**无合计行**） |
| 备用电缆 | 终点标注「备用/预留」的电缆，单独成表、不计入上面的合计 |
| 明细 | 汇总行（S1/S2…、备用 B1/B2…）+ 该类的电缆号（英文逗号拼接），逐条对账用 |
| 待确认 | 图上未填的截面/长度、只有编号没有参数的空行、编号缺号、重复编号等提示 |
| _meta | 隐藏；schema 与元数据（含 `total_quantity` / `total_length` / `spare_*` 合计值） |

总长度显示 `-` 表示该类在图上没填长度（不是 0），并会在「待确认」里列出。

## 仓库结构

```text
cad-cable-schedule-suite/
├── deliverables/
│   ├── menu-plugin/       CAD 插件（唯一源码）：引擎入口 main.py + core/ 内核 + tools/ +
│   │                      cad-plugin/（LISP/DCL 生成物、bat、ini 模板）+ 安装说明.txt
│   └── web-service/       网页服务（FastAPI：上传 DXF/TSV → 下载 Excel）
├── tools/                 构建、校验、打包脚本；templates/ 下有 LISP 基座模板
└── tests/                 跨交付物一致性 + CLI 命名回归测试
skill/                     agent skill（脚本 + 契约文档 + 测试，可单独分发）
```

## 从源码构建

```powershell
python -m venv .venv
.venv\Scripts\pip install -r cad-cable-schedule-suite\requirements-dev.txt
cd cad-cable-schedule-suite
.venv\Scripts\python.exe tools\build_engine.py   # PyInstaller 打引擎 exe（约 24 MB）
.venv\Scripts\python.exe tools\build_menu.py     # 生成插件 LISP（含中文化）/ CUIx / DCL
.venv\Scripts\python.exe tools\package.py        # 打出 dist\cable-summary-plugin-1.0.0.zip
```

提交前建议跑的三道 LISP 关卡与测试（CI 上也可以照搬）：

```powershell
$lsp = "deliverables\menu-plugin\cad-plugin\cable-summary-cad.lsp"
.venv\Scripts\python.exe tools\validate_lisp.py $lsp   # 括号配平/字符串闭合/无裸 token
.venv\Scripts\python.exe tools\check_defun.py  $lsp   # 逐函数括号边界
.venv\Scripts\python.exe tools\check_calls.py  $lsp   # 调用-定义一致性
.venv\Scripts\python.exe -m pytest tests -q            # 一致性 + CLI 命名
.venv\Scripts\python.exe deliverables\web-service\tools\run_tests.py
```

> 仓库里**不含**构建产物（引擎 exe、打包 zip、CUIx，以及 GBK 编码的 DCL 对话框文件——它们都由
> `tools/` 下的脚本生成，已在 `.gitignore` 中排除）：按上面命令自行构建，或直接下载 Release。

## 工作原理（简述）

```text
AutoLISP 前端（菜单/选择集→TSV/设置对话框）
        │ startapp（无控制台窗口）
Python 引擎（单文件 exe：识别表格 → 按三项合并 → 写 Excel → 回写响应文件）
        │ 同一份内核 core/aggregate.py
网页服务（FastAPI）/ agent skill（脚本）
```

- 常驻方式用 AutoCAD **官方 Autoloader**：`PackageContents.xml` 声明把 LISP 当 AutoLISP 组件加载，
  AutoCAD 每次启动自动加载；会话内的菜单由 COM(ActiveX) 现场创建（不依赖菜单文件）。
- 引擎编译为 GUI 子系统（不弹黑色控制台窗口），被脚本调用时会挂接到父控制台输出；
  自检报告通过 `--log` 落盘再由 bat 显示，避免「拿不到输出端」导致报告丢失。
- 更详细的设计说明与踩坑记录见 `cad-cable-schedule-suite/README.md`。

## 测试与自检

| 项目 | 覆盖 | 现状 |
|---|---|---|
| `pytest tests`（套件） | 跨交付物一致性（引擎/网页/skill 结果逐类一致）+ CLI 命名回归 | 11 项通过 |
| 插件自检 `check.bat` | 12 项：配置、引擎、跑通汇总、响应格式、Excel 结构、干扰表排除 | 全过 |
| 网页服务 `run_tests.py` | 起真实服务 → 上传 TSV → 下载 Excel 全链路 | 5 项通过 |
| skill 侧 pytest | 表识别、合并口径、备用、待确认、Excel 契约（含列宽断言） | 28 项通过 |

## 兼容性与已知限制

- **Windows + AutoCAD 2020 或更高**（bundle 清单声明 `SeriesMin=R23.0`）；**不支持 AutoCAD LT**（不能跑 AutoLISP）。
- 插件无代码签名：首次启动可能弹一次询问，选「始终加载」即可。
- 只识别**带列头**的电缆表（要求 电缆号/型号/芯数/截面/长度 列头齐全）；表头被炸开的表识别不到。
- 图上没填的数值**不臆造**：该类总长度显示 `-` 并进「待确认」，需人工补图后重跑。
- 建议把插件目录放在纯英文路径下（中文用户名已支持，但路径越简单越稳）。

## 许可

MIT License，见 [LICENSE](LICENSE)。

本项目与 Autodesk 无关联；AutoCAD 是 Autodesk, Inc. 的商标。

---

## English summary

A menu plugin for AutoCAD (Windows, 2020+) that turns the cable schedules you select on a drawing
into a procurement-ready Excel summary. It merges rows by **cable type + cores + core section**,
sums the lengths, keeps **spare/reserved cables in their own sheet**, and lists anything that needs
human confirmation (missing values, blank rows, gaps or duplicates in cable numbers).

- Ships as an official **Autoloader bundle** (`%APPDATA%\Autodesk\ApplicationPlugins\CableSummary.bundle`):
  drop the folder in, restart AutoCAD, done — no config changes, no install script.
- The engine is a self-contained single-file executable (PyInstaller); target machines need **no Python**
  and no network access. The same Python core also backs a small FastAPI web service and an agent skill.
- Excel output: five sheets (summary / spares / details / to-confirm / hidden meta), no total row,
  auto-fitted column widths, CJK-safe.

Build: `tools/build_engine.py` → `tools/build_menu.py` → `tools/package.py` (see above).
MIT licensed. Not affiliated with Autodesk.
