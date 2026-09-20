---
name: cad-cable-schedule
description: 在标准端子数据、电缆 Excel 工作簿和 CAD 电缆表之间建立固定流程。用于读取端子图或端子表.xlsx并生成按 K/AK/TK 分类的电缆表.xlsx；或对用户在 CAD 中选中的电缆表按型号/芯数/截面/长度汇总计数，输出采购用电缆汇总表.xlsx；或校验电缆 Excel、查询知识库规则、编译绘图计划并通过 cad-drawing 绘制电缆表。原始端子图语义解析复用 cad-terminal-diagram。
---

# CAD Cable Schedule

## 职责

负责把已标准化的端子连接转换为电缆记录，固定 K/AK/TK 分类、编号占位、起终点、芯数、冲突门禁和电缆表工作簿契约。所有 CAD 读写通过 `cad-drawing`；原始端子图先经 `cad-terminal-diagram` 语义化。

## 模式选择

- 输入端子 DWG/DXF 或端子 XLSX，目标为电缆 Excel：执行 `extract`。
- 输入符合契约的电缆 XLSX，目标为 CAD：执行 `render`。
- 用户在 CAD 中已选中若干电缆表，目标为按规格汇总的采购用 Excel：执行 `survey`。
- 输入混合时先统一为 `terminal-workbook`，禁止分别维护 DWG 与 Excel 两套电缆推导逻辑。

## Extract：端子数据 → 电缆 Excel

1. 确认输入图纸/工作簿、柜号范围、输出位置和电缆表用途。
2. 原始 DWG/DXF 转交 `cad-terminal-diagram extract`；端子 XLSX 使用其校验工具导入。
3. 按 `references/内置知识路由.md` 选择业务知识来源；未指定时读取本 skill 内置文档，明确指定 LLM Wiki 时记录实际页面路径。查询电缆分类、编号范围、串联关系、方向、型号和芯数规则。
4. 把知识规则物化为 `cable-derivation-rules`，运行 `scripts/从端子模型生成电缆模型.py` 生成 `cable-workbook`；保留源端子 row_id 和方向证据。
5. 运行 `scripts/电缆工作簿.py export` 生成 `电缆表.xlsx`，随后 validate 和 import 回读。
6. 向用户交付 XLSX；内部端子模型、证据和规则快照留在 `.agent`。

## Render：电缆 Excel → CAD

1. 运行 `scripts/电缆工作簿.py validate` 和 import。
2. 处理重复编号、断裂串联、方向不明、`conflict` 及 blocking issue。
3. 按 `references/内置知识路由.md` 选择业务知识来源，查询标准表块、每块容量、图层、文字、坐标和分页/分块规则，并物化为 `cable-layout-rules`。
4. 先把 `cable-workbook` 按标准块容量（31 行数据）切分为实际绘图页，再运行 `scripts/生成电缆表绘图计划.py` 编译 `cad-draw-plan`；每个 Excel sheet 必须与一个 CAD 电缆表块一一对应，不能只按 K/AK/TK 输出三张聚合表。该生成器同时写出 `cad_dispatch.json`（`cad-dispatch`）与 UTF-8 侧车：`cable-annotations` 批次**默认始终外置**为 `@file:<绝对路径>`（不看批次大小），由 MCP 主机直接读取。
5. 用 `cad-drawing/scripts/校验CAD服务契约.py --kind draw-plan` 校验计划，再交给 `cad-drawing` 服务模式执行并接收报告：执行端**只读 `cad_dispatch.json`**，按 `index` 用 `action`+`params` 调用工具，不读计划正文、不读侧车正文、不重打 payload；`block_dyn` 的 `{{handle}}` 操作保持内联，必须先绑定插块返回的真实 handle。块插入必须分为“插入并回读真实 bbox”与“绘制文字”两个门：`local_bbox/block_step` 只用于预检，不能替代真实尺寸；后续块的位置必须依据前一块回读的 xmax/ymax 加安全间隙计算。真实 bbox 发生变化或块间/块与既有实体重叠时，先按 handle 移动块及其已创建文字并复核，未通过不得继续批量填字。
6. 核对 Excel sheet 与 CAD block 的页数、逐行编号、空白行、起终点、芯数和文字落位一致，并以真实 INSERT/TEXT bbox 完成无重叠验收后交付 DWG。

## Survey：选中电缆表 → 采购汇总表

1. 只用 `cad-drawing` 读图服务，并且必须 `read_drawing_structure(scope="selected", scan_scope="modelspace")`：
   用户说“已选中/选中内容/当前选择”时不得退化为整图读取，不得用估算 bbox 代替选择集；
   空选择、`selection.count=0` 或 `scan.truncated=true` 一律失败关闭，请用户重新选中后重读。
   切换活动文档（如为查知识库打开参考图）会清空选择集，读取必须紧跟选中动作。
2. 记录返回的 `artifacts.json_path`，把它作为 `scripts/电缆汇总统计.py extract` 的 `--input`。
   选择集内容通常还包含图框和说明文字，脚本按列头识别电缆表，但用户误选的非电缆表要连同
   `metadata.candidate_tables` 一并说明。
3. 汇总口径见 `references/电缆汇总契约.md`：**电缆型号、选用芯数、每芯截面mm² 三项完全一致才合并**（长度(m) 按类相加），
   任一项不同即新增一行；`数量`等于该类电缆条数。电缆号/起点/终点/线号不参与合并，只进入`明细`表。
4. 交付 `电缆汇总表.xlsx`，并逐条说明 `待确认` 里的 warning：图上未填的截面/长度、只有电缆号没有参数的空行、
   编号缺号、重复电缆号。出现 `conflict`（同一电缆号参数不一致）时先请用户裁决，不得直接交付。
5. 数量偏小是这类任务的首要风险：读出的行数必须与图上编号行数对账，凡对不上就以 warning 明示，
   不得用“应该没问题”带过。内部提取轨迹留在 `cable-summary.json` 的 `source_rows`。
6. 用户要求“不通过 agent、给其他同事直接用”时，按 `references/部署方案.md` 选外壳。
   内核同样是 `scripts/电缆汇总统计.py`：整图 DXF 与选择集结果一致，服务侧**不需要** CAD 或 MCP。
   网页服务与 CAD 插件已是**独立交付物**（各自打包、各自分发，见 `references/部署方案.md`），
   本 skill 不再内置它们的实现；需要时按该文档取对应交付物，不要为同类需求另写汇总逻辑。

## 固定边界

- 本 skill 不直接解析 CAD 端子几何，不复制端子提取代码。
- Excel schema、状态和编号占位规则固定；电缆识别表达式、方向优先级、格式和定位参数来自知识库。
- 电缆表线号按连接记录顺序拼接，统一使用英文逗号 `,`，不得使用中文顿号 `、`。
- Excel 是用户契约；完整端子证据、推导链和 CAD handle 留在内部 JSON。
- 不把显示去重等同于删除连接或减少需用芯数。

## 按需参考

- `references/电缆表双向流程.md`：输入适配、extract/render/survey 三种模式和跨 skill 交接。
- `references/电缆工作簿契约.md`：XLSX sheets、列和编号占位。
- `references/电缆推导与门禁.md`：分类、聚合、方向、冲突和验收。
- `references/电缆推导规则契约.md`：知识库规则传给确定性脚本的 JSON 字段。
- `references/电缆表绘图规则契约.md`：表块容量、坐标字段、动态参数变量和编译门禁。
- `references/电缆汇总契约.md`：选中电缆表的型号/芯数/截面三项汇总口径、行/表识别、门禁和 XLSX 结构。
- `references/部署方案.md`：不依赖 agent 的七种外壳、取数方式、生产化清单与落地顺序。
- `references/内置知识路由.md`：内置知识默认路径、LLM Wiki 独立路径和冲突处理。

Excel 与 CAD 电缆表只做结构/视觉对照，不进行 Excel 文件到 CAD 的直接导入；实际转换必须经过知识库规则查询、模型校验和绘图计划编译。


