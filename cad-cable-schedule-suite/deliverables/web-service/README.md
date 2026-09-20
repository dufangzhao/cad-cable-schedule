# 电缆表汇总 · 网页服务

浏览器上传 DXF / TSV，服务端汇总后返回采购用 Excel。
按 **电缆型号 / 选用芯数 / 每芯截面(mm²) 三项完全一致合并**，长度相加为总长度；任一项不同即另起一行。

本交付物**与 CAD 插件、agent skill 完全解耦**：只要一台能跑 Python 的机器，不需要 AutoCAD，
不需要 CAD 插件，也不需要装任何 agent。

## 给谁用

| 场景 | 怎么用 |
|---|---|
| 不会 CAD、不想装插件的人 | 找设计同事要一份电缆表 DXF，浏览器上传即可 |
| 采购对账 | 直接上传别人给的 TSV / DXF |
| 多人共用 | 部署在一台内网机器上，把地址发给大家 |

## 快速开始

```powershell
# 首次：装依赖
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 自检（会自动临时起服务，跑完自动关）
.\.venv\Scripts\python.exe tools\preflight.py

# 启动
.\.venv\Scripts\python.exe -m app.server --host 0.0.0.0 --port 8100
```

也可以直接双击 `自检.bat` / `启动服务.bat`（纯 ASCII，不会有编码问题）。

启动后窗口会打印两个地址：

```text
本机访问 : http://127.0.0.1:8100
同事访问 : http://192.168.1.99:8100     ← 把这个发给同事（已过滤虚拟网卡）
```

## 支持的三种上传内容

| 格式 | 来源 | 体积 | 说明 |
|---|---|---|---|
| **TSV** | CAD 插件的 CAD 插件导出的临时文件 / agent 导出 | ~85 KB | 只含选中文字，最省事最安全 |
| **DXF** | CAD 里 `WBLOCK` 选中内容，或整图 `SAVEAS → DXF` | ~11 MB | 整图也能自动找出全部电缆表，无需先选择 |
| **JSON** | agent 的 `read_drawing_structure` artifact | ~1.7 MB | 空选择/截断会失败关闭 |

## HTTP 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 上传页 |
| GET | `/api/health` | 健康检查，返回 schema 版本与大小上限 |
| POST | `/api/summarize` | 表单字段 `file`（必填）、`project`、`keep_incomplete`、`want=xlsx\|json` |
| GET | `/api/download?id=<ticket>` | 一次性取件（票据 30 分钟过期） |

## 输出

`电缆汇总表.xlsx`，五个 sheet（顺序固定）：

```text
电缆汇总   电缆型号 | 选用芯数 | 每芯截面(mm²) | 总长度(m) | 数量
           只有表头 + 各类别行，没有"合计"行；合计值在 _meta 里
备用电缆   表头同上；终点标注"备用/预留"的电缆单独成表，不计入上面的合计
明细       每一类对应的电缆号，逗号分隔，便于逐条对账
待确认     图上未填参数、空行、编号缺号、重复电缆号的提示
_meta      隐藏，schema 与元数据（含 total_quantity / total_length / spare_quantity / spare_length）
```

每列宽度按该列最长内容自动调整（中文按 2 个字符宽），保证文字能在一行内完整显示；
超过 Excel 列宽上限（255 字符）的长串自动换行，不截断。

## 生产化清单

原型已可用，正式多人使用前建议补齐：

- **并发**：DXF 解析约 4 秒/张且吃 CPU，`--workers 4` 或多开进程；相同文件可按哈希缓存结果。
- **限额**：上传大小上限默认 64 MB；按用户/IP 限流。
- **清理**：临时目录与票据已有 30 分钟 TTL，建议再加定时清扫。
- **反代**：nginx 的 `client_max_body_size` 必须大于图纸体积。
- **安全**：**只在局域网提供服务**，加 SSO 或反向代理白名单；图纸是商业资产，不要暴露公网。

## 数据边界

- 上传文件只落在系统临时目录，处理完即删；服务不写数据库、不保留历史。
- 不连接 CAD、不依赖 MCP、不访问外网。
- 汇总口径来自 `core/aggregate.py`，与 CAD 插件、agent skill 是同一份实现。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe tools\run_tests.py     # 总是启动全新服务，避免旧进程掩盖问题
```
