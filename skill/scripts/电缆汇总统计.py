# -*- coding: utf-8 -*-
"""从用户选中的 CAD 电缆表提取电缆记录，按型号+芯数+截面汇总为采购用电缆汇总表（长度按类相加）。

输入是 cad-drawing 服务模式的 read_drawing_structure artifact（scope=selected）
或直接给出的 DXF。输出 cable-summary 模型 JSON 与电缆汇总表.xlsx。

判定与汇总口径由 references/电缆汇总契约.md 固定；本脚本只做确定性提取、归一化和计数，
不臆造型号、截面或长度。
"""
from __future__ import annotations

import argparse
import json
import locale
import math
import re
import sys
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SCHEMA_VERSION = "cable-summary"
SHEET_SUMMARY = "电缆汇总"
SHEET_SPARE = "备用电缆"          # 备用/预留电缆单独一个 sheet，与正式统计彻底分开
SHEET_DETAIL = "明细"
SHEET_ISSUES = "待确认"
SHEET_META = "_meta"

# 汇总键：型号 + 选用芯数 + 每芯截面 三项一致即归为一类，长度按类相加。
# 长度不再是"分类依据"，而是每类的一个汇总值。
KEY_FIELDS = ("spec", "selected_cores", "core_section")
SUM_FIELD = "length"
EXCEL_HEADERS = ["电缆型号", "选用芯数", "每芯截面(mm²)", "总长度(m)", "数量"]

# 电缆表列头别名；空格在归一化阶段已去除
HEADER_ALIASES: dict[str, str] = {
    "电缆号": "cable_id", "电缆编号": "cable_id",
    "起点": "start", "始端": "start",
    "终点": "end", "末端": "end",
    "线号": "wire_numbers", "芯线号": "wire_numbers",
    "需用芯数": "required_cores", "使用芯数": "required_cores",
    "选用芯数": "selected_cores",
    "电缆型号": "spec", "型号": "spec", "型号规格": "spec",
    "每芯截面": "core_section", "截面": "core_section",
    "长度(m)": "length", "长度（m）": "length", "长度": "length",
    "钢管直径(mm)": "conduit_diameter", "钢管直径（mm）": "conduit_diameter",
    "钢管长度(m)": "conduit_length", "钢管长度（m）": "conduit_length",
    "备注": "remark",
    "数量": "quantity",
}
# 汇总表必须自带的列；缺任一列即不认定为可汇总的电缆表
REQUIRED_COLUMNS = ("cable_id",) + KEY_FIELDS

# 电缆号形态：字母前缀 + 数字（K1/AK14/TK36/UK2/…）
CABLE_ID_RE = re.compile(r"^([A-Za-z]{1,4})(\d{1,4})$")
# 缺省占位符，表示“图纸上明确未填”，与空白同义
PLACEHOLDERS = {"-", "--", "—", "－", "/", "无", "空"}


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def norm_text(value: Any) -> str:
    """归一化单元格文本：统一全角空格、去除所有空白。"""
    if value is None:
        return ""
    s = str(value)
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def compact(value: str) -> str:
    """去空白版本，用于列头匹配。"""
    return re.sub(r"\s+", "", value or "")


def is_placeholder(value: str) -> bool:
    v = compact(value)
    return v == "" or v in PLACEHOLDERS


def number_key(value: str) -> str:
    """数值归一化：13 / 13.0 / 13.00 视为同一值；非数值返回原文。"""
    v = compact(value)
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if math.isfinite(f) and f == int(f):
        return str(int(f))
    return repr(round(f, 6))


def group_key(values: dict[str, str]) -> tuple[str, ...]:
    """型号 + 选用芯数 + 每芯截面 三项一致即归为一类（截面按数值等价归一）。

    长度不参与分类：同一类的多根电缆长度相加，得到该类总长度。
    """
    spec = compact(values.get("spec", "")).upper()
    cores = number_key(values.get("selected_cores", ""))
    section = number_key(values.get("core_section", ""))
    return (spec, cores, section)


# 图纸上表示"备用/预留"的写法；这类电缆参数往往未定，不并入正式统计
SPARE_MARKERS = ("备用", "预留", "备用芯", "SPARE", "spare")


def spare_reason(values: dict[str, str]) -> str:
    """判断该行是否是备用/预留电缆；返回命中的原文（空串表示不是）。

    只看起点/终点/备注——这三处是图纸上标注"备用"的位置。
    型号列里出现"备用"不算（那是型号名的一部分）。
    """
    for field in ("end", "start", "remark"):
        text = norm_text(values.get(field, ""))
        for marker in SPARE_MARKERS:
            if marker and marker in text:
                return text
    return ""


def sum_lengths(lengths: list[str]) -> tuple[float, int]:
    """把一类的长度相加，返回 (总长度, 无法相加的条数)。

    图上写 "-" 之类的占位符表示"明确未填"，不能当成 0 —— 那样总量会偏小。
    这类条数单独返回，由调用方提示人工补齐。
    """
    total = 0.0
    bad = 0
    for raw in lengths:
        v = compact(raw)
        if is_placeholder(v):
            bad += 1
            continue
        try:
            total += float(v)
        except (TypeError, ValueError):
            bad += 1
    return total, bad


def fmt_length(total: float) -> str:
    """总长度显示：整数不带小数点，小数最多两位。"""
    if abs(total - round(total)) < 1e-9:
        return str(int(round(total)))
    return f"{total:.2f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------------------- #
# 输入读取
# --------------------------------------------------------------------------- #
def load_artifact(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("artifact 顶层必须是对象")
    if data.get("read_scope") == "selected":
        scan = data.get("scan") or {}
        if scan.get("truncated"):
            raise ValueError("选择集读取被截断（scan.truncated=true），请不加过滤条件重新读取选择集")
        if int(data.get("selection", {}).get("count", 0)) <= 0:
            raise ValueError("选择集为空，未选中任何实体")
    return data


def entity_kind_counts(data: dict[str, Any]) -> dict[str, int]:
    """统计选择集内出现的实体类型，供交付时说明哪些内容被有意忽略。"""
    scan = data.get("scan")
    items = scan.get("items") if isinstance(scan, dict) else None
    if not isinstance(items, list):
        return {}
    counts: dict[str, int] = {}
    for item in items:
        if isinstance(item, dict):
            kind = str(item.get("type") or item.get("kind") or "?")
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def entities_from_artifact(data: dict[str, Any]) -> list[dict[str, Any]]:
    """从 read_drawing_structure artifact 取出选择集内的文字实体。

    只取 TEXT/ATTRIB：电缆表数据是块外单行文字或块属性；MTEXT（图框、说明）
    不参与表识别，避免把说明文字误当电缆参数。
    """
    scan = data.get("scan")
    if isinstance(scan, dict) and isinstance(scan.get("items"), list):
        items = scan["items"]
    else:
        items = []
        for key in ("entities", "modelspace", "items"):
            node = data.get(key)
            if isinstance(node, list) and node and isinstance(node[0], dict):
                items = node
                break
    texts: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("type") or item.get("kind") or "").upper()
        if kind not in {"TEXT", "ATTRIB"}:
            continue
        point = item.get("insert") or item.get("point") or item.get("insertion_point")
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        value = item.get("text")
        if value is None:
            value = item.get("value")
        if value is None:
            value = item.get("text_string")
        texts.append({
            "handle": str(item.get("handle") or ""),
            "layer": str(item.get("layer") or ""),
            "x": float(point[0]),
            "y": float(point[1]),
            "height": float(item.get("height") or item.get("char_height") or 0.0),
            "text": norm_text(value),
            "source": kind,
        })
    return texts


TSV_HEADER = ["handle", "layer", "x", "y", "height", "text"]


def write_tsv(texts: list[dict[str, Any]], output: Path) -> None:
    """把已提取的文字实体写成 TSV，供 AutoCAD 插件等轻量客户端上传。

    只含选定范围内的单行文字（handle/图层/坐标/字高/文字），不含图框几何与块定义，
    因此比整图 DXF 小几个数量级，也不泄露图纸其余内容。
    """
    if output.exists():
        raise FileExistsError(f"拒绝覆盖现有文件：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(TSV_HEADER)]
    for t in texts:
        cells = [t["handle"], t["layer"], repr(float(t["x"])), repr(float(t["y"])),
                 repr(float(t["height"])), t["text"].replace("\t", " ").replace("\r", " ").replace("\n", " ")]
        lines.append("\t".join(cells))
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return None


def read_text_flexible(path: Path) -> str:
    """按 UTF-8 → 系统 ANSI → GBK 顺序解码文本文件。

    为什么需要：AutoLISP 的 (open path "w") 用**系统 ANSI 代码页**写文件，
    中文 Windows 上就是 GBK；而本 skill 自己写出的中间文件是 UTF-8。
    读取端两种都要认，否则插件送来的中文（线号、起终点）会直接解码失败。
    """
    raw = path.read_bytes()
    encodings = ["utf-8-sig", locale.getpreferredencoding(False), "gbk", "cp936"]
    for enc in encodings:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def entities_from_tsv(path: Path) -> list[dict[str, Any]]:
    """读取 TSV 文字实体清单；用于 CAD 插件只上传选择集文字的场景。"""
    raw = read_text_flexible(path).splitlines()
    if not raw:
        raise ValueError("TSV 为空")
    header = [c.strip() for c in raw[0].split("\t")]
    if header[: len(TSV_HEADER)] != TSV_HEADER:
        raise ValueError(f"TSV 表头必须是：{'/'.join(TSV_HEADER)}")
    index = {name: header.index(name) for name in TSV_HEADER}
    out: list[dict[str, Any]] = []
    for line_no, line in enumerate(raw[1:], start=2):
        if not line.strip():
            continue
        cells = line.split("\t")
        if len(cells) < len(TSV_HEADER):
            raise ValueError(f"TSV 第 {line_no} 行列数不足")
        try:
            out.append({
                "handle": cells[index["handle"]].strip(),
                "layer": cells[index["layer"]].strip(),
                "x": float(cells[index["x"]]),
                "y": float(cells[index["y"]]),
                "height": float(cells[index["height"]]),
                "text": norm_text(cells[index["text"]]),
                "source": "TEXT",
            })
        except ValueError as exc:
            raise ValueError(f"TSV 第 {line_no} 行坐标/字高不是数字") from exc
    return out


def entities_from_dxf(path: Path) -> list[dict[str, Any]]:
    """离线路径：直接读 DXF（与 MCP 导出的 active.dxf 等价）。"""
    try:
        import ezdxf  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ValueError("缺少 ezdxf，无法读取 DXF；请改用 artifact JSON 作为输入") from exc
    doc = ezdxf.readfile(str(path))
    out: list[dict[str, Any]] = []
    for e in doc.modelspace():
        kind = e.dxftype()
        if kind not in {"TEXT", "ATTRIB"}:
            continue
        point = e.dxf.insert
        out.append({
            "handle": str(e.dxf.get("handle", "")),
            "layer": str(e.dxf.get("layer", "")),
            "x": float(point[0]),
            "y": float(point[1]),
            "height": float(e.dxf.get("height", 0.0) or 0.0),
            "text": norm_text(e.dxf.get("text", "")),
            "source": kind,
        })
    return out


# --------------------------------------------------------------------------- #
# 表识别与行提取
# --------------------------------------------------------------------------- #
def detect_columns(band: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """从表头带内识别列。同一字段取最靠上的一处，避免数据行误当列头。"""
    cols: dict[str, dict[str, Any]] = {}
    for t in sorted(band, key=lambda z: (-z["y"], z["x"])):
        key = HEADER_ALIASES.get(compact(t["text"]))
        if key and key not in cols:
            cols[key] = t
    return cols


def column_bounds(cols: dict[str, dict[str, Any]]) -> dict[str, tuple[float, float]]:
    """列归属边界取相邻列头 x 的中点；末端外扩一个行高量级。"""
    centers = sorted(((k, v["x"]) for k, v in cols.items()), key=lambda kv: kv[1])
    span = max(centers[-1][1] - centers[0][1], 1.0)
    pad = span * 0.25
    bounds: dict[str, tuple[float, float]] = {}
    for i, (key, x) in enumerate(centers):
        lo = (centers[i - 1][1] + x) / 2 if i else x - pad
        hi = (centers[i + 1][1] + x) / 2 if i + 1 < len(centers) else x + pad
        bounds[key] = (lo, hi)
    return bounds


def cluster_rows(texts: list[dict[str, Any]], tolerance: float) -> list[list[dict[str, Any]]]:
    """按 y 聚类成行；容差取行距量级的一半，保证同行不同对齐不拆行。"""
    ordered = sorted(texts, key=lambda t: (-t["y"], t["x"]))
    clusters: list[list[dict[str, Any]]] = []
    for t in ordered:
        if clusters and abs(clusters[-1][0]["y"] - t["y"]) <= tolerance:
            clusters[-1].append(t)
        else:
            clusters.append([t])
    return clusters


def estimate_pitch(clusters: list[list[dict[str, Any]]]) -> float:
    """用相邻行 y 差的最小正众数估计行距。"""
    ys = sorted({round(c[0]["y"], 3) for c in clusters}, reverse=True)
    diffs = [round(ys[i] - ys[i + 1], 3) for i in range(len(ys) - 1)]
    diffs = [d for d in diffs if d > 0]
    if not diffs:
        return 0.0
    return Counter(diffs).most_common(1)[0][0]


def assign_cells(row: list[dict[str, Any]], bounds: dict[str, tuple[float, float]]) -> dict[str, list[str]]:
    cells: dict[str, list[str]] = {}
    for t in sorted(row, key=lambda z: z["x"]):
        if not t["text"]:
            continue
        key = None
        for k, (lo, hi) in bounds.items():
            if lo <= t["x"] <= hi:
                key = k
                break
        if key is None:
            key = min(bounds, key=lambda k: abs((bounds[k][0] + bounds[k][1]) / 2 - t["x"]))
        cells.setdefault(key, []).append(t["text"])
    return cells


def extract_tables(texts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """识别所有电缆表并提取数据行。返回 (records, candidate_tables)。"""
    anchors = sorted([t for t in texts if compact(t["text"]) == "电缆号"],
                     key=lambda t: (t["y"], t["x"]))
    records: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for order, anchor in enumerate(anchors):
        # 横向裁到"相邻表的电缆号列中点"之间：多张表并排时，若只按表头跨度取范围，
        # 右侧那张表的行会被左侧表抢走，导致整张表读不出来。
        band_lo = ((anchors[order - 1]["x"] + anchor["x"]) / 2) if order > 0 else None
        band_hi = ((anchors[order + 1]["x"] + anchor["x"]) / 2) if order + 1 < len(anchors) else None
        # 表头带：与“电缆号”同一行、位于其右侧
        band = [t for t in texts
                if abs(t["y"] - anchor["y"]) <= max(anchor["height"], 1.0) * 2.0
                and anchor["x"] - anchor["height"] * 2 <= t["x"] <= anchor["x"] + anchor["height"] * 80]
        cols = detect_columns(band)
        missing = [c for c in REQUIRED_COLUMNS if c not in cols]
        candidates.append({
            "anchor_handle": anchor["handle"], "anchor_x": round(anchor["x"], 3), "anchor_y": round(anchor["y"], 3),
            "columns": sorted(cols), "missing": missing, "usable": not missing,
        })
        if missing:
            continue
        bounds = column_bounds(cols)
        # 数据区：表头下方，横向限制在电缆号列与最右列之间
        left = min(v["x"] for v in cols.values()) - anchor["height"]
        right = max(v["x"] for v in cols.values()) + anchor["height"]
        if band_lo is not None:
            left = max(left, band_lo)
        if band_hi is not None:
            right = min(right, band_hi)
        region = [t for t in texts
                  if t["y"] < anchor["y"] - anchor["height"] * 0.4
                  and left <= t["x"] <= right
                  and anchor["y"] - t["y"] < anchor["height"] * 200]
        if not region:
            continue
        tol = max(anchor["height"] * 0.7, 1.0)
        clusters = cluster_rows(region, tol)
        # 行距按相邻行差估计；表里只有一行时无从估计，用行高做上限兜底。
        # 注意不能因此跳过整张表：单行电缆表是合法输入，跳过等于静默漏数。
        pitch = estimate_pitch(clusters) or max(anchor["height"], 1.0)
        # 续行桥接：与上一行间距远小于行距且自身无电缆号时并入上一行（文字换行）
        merged: list[list[dict[str, Any]]] = []
        for c in clusters:
            c_cells = assign_cells(c, bounds)
            c_id = " ".join(c_cells.get("cable_id", [])).strip()
            if merged:
                gap = merged[-1][0]["y"] - c[0]["y"]
                prev_cells = assign_cells(merged[-1], bounds)
                prev_id = " ".join(prev_cells.get("cable_id", [])).strip()
                if not CABLE_ID_RE.match(c_id) and prev_id and gap < pitch * 0.6:
                    merged[-1].extend(c)
                    continue
            merged.append(list(c))

        table_index = len({r["table"] for r in records}) + 1
        last_row_y: float | None = None
        for row in merged:
            cells = assign_cells(row, bounds)
            cable_id = " ".join(cells.get("cable_id", [])).strip()
            values = {k: " ".join(cells.get(k, [])).strip() for k in set(list(bounds) + list(KEY_FIELDS))}
            if not CABLE_ID_RE.match(compact(cable_id)):
                continue
            # 空行（电缆号在、型号/芯数/截面三项全空）不计入汇总，但要报出门禁
            records.append({
                "table": table_index,
                "row_y": round(row[0]["y"], 3),
                "cable_id": cable_id,
                "values": values,
                "handles": [t["handle"] for t in row if t["handle"]],
                "source_layer": row[0]["layer"],
            })
            last_row_y = row[0]["y"]
        if last_row_y is not None:
            candidates[-1]["data_rows"] = sum(1 for r in records if r["table"] == table_index)
            candidates[-1]["pitch"] = pitch
    return records, candidates


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
def build_summary(records: list[dict[str, Any]], metadata: dict[str, Any],
                  *, keep_incomplete: bool = False) -> dict[str, Any]:
    groups: "OrderedDict[tuple[str, ...], dict[str, Any]]" = OrderedDict()
    spare_groups: "OrderedDict[tuple[str, ...], dict[str, Any]]" = OrderedDict()
    issues: list[dict[str, Any]] = []
    incomplete: list[dict[str, Any]] = []
    spare_rows: list[dict[str, Any]] = []
    for rec in records:
        values = rec["values"]
        reason = spare_reason(values)
        if reason:
            # 备用电缆参数常未确定，单独归集，不并入正式类别
            key = group_key(values)
            entry = spare_groups.get(key)
            if entry is None:
                entry = {
                    "spec": norm_text(values.get("spec", "")),
                    "selected_cores": norm_text(values.get("selected_cores", "")),
                    "core_section": norm_text(values.get("core_section", "")),
                    "quantity": 0, "lengths_raw": [], "cable_ids": [], "key": list(key),
                }
                spare_groups[key] = entry
            entry["quantity"] += 1
            entry["cable_ids"].append(rec["cable_id"])
            entry["lengths_raw"].append(values.get(SUM_FIELD, ""))
            spare_rows.append(rec)
            continue
        key = group_key(values)
        if all(is_placeholder(values.get(f, "")) for f in KEY_FIELDS) and not keep_incomplete:
            incomplete.append(rec)
            continue
        entry = groups.get(key)
        if entry is None:
            entry = {
                "spec": norm_text(values.get("spec", "")),
                "selected_cores": norm_text(values.get("selected_cores", "")),
                "core_section": norm_text(values.get("core_section", "")),
                "quantity": 0,
                "lengths_raw": [],
                "cable_ids": [],
                "key": list(key),
            }
            groups[key] = entry
        entry["quantity"] += 1
        entry["cable_ids"].append(rec["cable_id"])
        entry["lengths_raw"].append(values.get(SUM_FIELD, ""))

    # 逐类把长度相加；非数值长度不能当 0，单独统计并提示人工补齐
    for bucket in (groups, spare_groups):
        for entry in bucket.values():
            total, bad = sum_lengths(entry.pop("lengths_raw"))
            entry["total_length"] = fmt_length(total) if bad == 0 else "-"
            entry["total_length_value"] = round(total, 3)
            entry["length_unknown_rows"] = bad

    if spare_groups:
        spare_count = sum(e["quantity"] for e in spare_groups.values())
        issues.append({
            "issue_id": "",
            "cable_ids": [i for e in spare_groups.values() for i in e["cable_ids"]],
            "field": "备用", "severity": "warning",
            "message": (f"{spare_count} 根是备用/预留电缆（终点标注「备用」），"
                        f"已单独归集，未计入正式汇总"),
        })

    for entry in groups.values():
        missing = [f for f in KEY_FIELDS if is_placeholder(entry.get(f, ""))]
        if missing:
            issues.append({
                "issue_id": "", "cable_ids": entry["cable_ids"], "field": ",".join(missing),
                "severity": "warning",
                "message": f"汇总键字段缺失（{','.join(missing)}），建议补齐后再采购",
            })
    unknown_len = [e for e in groups.values() if e["length_unknown_rows"]]
    if unknown_len:
        ids = [i for e in unknown_len for i in e["cable_ids"]]
        issues.append({
            "issue_id": "", "cable_ids": ids, "field": SUM_FIELD,
            "severity": "warning",
            "message": (f"{len(ids)} 根电缆的长度在图上未填（{len(unknown_len)} 类），"
                        f"无法相加，该类总长度显示为「-」；补全后可重新汇总"),
        })
    if incomplete:
        issues.append({
            "issue_id": "", "cable_ids": [r["cable_id"] for r in incomplete],
            "field": "电缆型号,选用芯数,每芯截面,长度",
            "severity": "warning",
            "message": f"{len(incomplete)} 行电缆只有电缆号、工程参数全空，未计入汇总",
        })
    dup_ids = {cid: n for cid, n in Counter(r["cable_id"] for r in records).items() if n > 1}
    if dup_ids:
        for cid, n in sorted(dup_ids.items()):
            rows = [r for r in records if r["cable_id"] == cid]
            keys = {group_key(r["values"]) for r in rows}
            issues.append({
                "issue_id": "", "cable_ids": [cid], "field": "电缆号",
                "severity": "conflict" if len(keys) > 1 else "warning",
                "message": (f"电缆号 {cid} 在选中范围内出现 {n} 次且参数不一致" if len(keys) > 1
                            else f"电缆号 {cid} 在选中范围内重复出现 {n} 次（可能重复选表或多张表重复绘制）"),
            })

    # 编号连续性门禁：同一字母前缀（K/AK/TK/UK…）范围内缺号说明有行未读出或原图缺行，
    # 会直接导致数量偏小，必须提示而不是静默通过。
    prefixes: dict[str, set[int]] = {}
    for rec in records:
        m = CABLE_ID_RE.match(compact(rec["cable_id"]))
        if m:
            prefixes.setdefault(m.group(1).upper(), set()).add(int(m.group(2)))
    for prefix, numbers in sorted(prefixes.items()):
        if len(numbers) < 2:
            continue
        missing = sorted(set(range(1, max(numbers) + 1)) - numbers)
        if missing:
            issues.append({
                "issue_id": "", "cable_ids": [f"{prefix}{n}" for n in missing], "field": "电缆号",
                "severity": "warning",
                "message": f"{prefix} 编号 1~{max(numbers)} 中缺号 {missing}，请确认原图是否存在空行或未读出",
            })

    summary_records = sorted(
        groups.values(),
        key=lambda e: (e["spec"], e["selected_cores"], e["core_section"]),
    )
    for i, entry in enumerate(summary_records, 1):
        entry["row_id"] = f"S{i}"
    # 备用电缆单独编号（B 开头），并在模型里独立成组
    spare_records = sorted(
        spare_groups.values(),
        key=lambda e: (e["spec"], e["selected_cores"], e["core_section"]),
    )
    for i, entry in enumerate(spare_records, 1):
        entry["row_id"] = f"B{i}"
    for i, issue in enumerate(issues, 1):
        issue["issue_id"] = f"I{i}"
    metadata = dict(metadata)
    # recognised_tables 由候选表派生，保证 CLI、网页、CAD 插件三条路径都能从模型里读到，
    # 而不是只存在于某个调用方的返回值里。
    candidates = metadata.get("candidate_tables")
    if isinstance(candidates, list):
        metadata.setdefault("recognised_tables", sum(1 for c in candidates if c.get("usable")))
    metadata.update({
        "source_row_count": len(records),
        "summary_row_count": len(summary_records),
        "total_quantity": sum(e["quantity"] for e in summary_records),
        "total_length": round(sum(float(e.get("total_length_value") or 0) for e in summary_records), 3),
        "classes_with_unknown_length": sum(1 for e in summary_records if e.get("length_unknown_rows")),
        "skipped_incomplete_rows": len(incomplete),
        "skipped_incomplete_cable_ids": [r["cable_id"] for r in incomplete],
        "include_incomplete_rows": bool(keep_incomplete),
        # 备用/预留电缆单列，不计入上面的正式合计
        "spare_row_count": len(spare_records),
        "spare_quantity": sum(e["quantity"] for e in spare_records),
        "spare_length": round(sum(float(e.get("total_length_value") or 0) for e in spare_records), 3),
        "spare_cable_ids": [i for e in spare_records for i in e["cable_ids"]],
    })
    return {
        "schema_version": SCHEMA_VERSION,
        "metadata": metadata,
        "records": summary_records,
        "spare_records": spare_records,
        "issues": issues,
    }


def validate_summary(model: dict[str, Any]) -> dict[str, int]:
    if model.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version 必须是 {SCHEMA_VERSION}")
    records = model.get("records")
    if not isinstance(records, list):
        raise ValueError("records 必须是数组")
    seen: set[tuple[str, ...]] = set()
    total = 0
    total_len = 0.0
    for i, r in enumerate(records):
        for field in KEY_FIELDS:
            if field not in r:
                raise ValueError(f"records[{i}].{field} 缺失")
        key = group_key({"spec": r["spec"], "selected_cores": r["selected_cores"],
                         "core_section": r["core_section"]})
        if key in seen:
            raise ValueError(f"records[{i}] 汇总键重复，未正确合并：{key}")
        seen.add(key)
        qty = r.get("quantity")
        if not isinstance(qty, int) or qty < 1:
            raise ValueError(f"records[{i}].quantity 必须为正整数")
        if "total_length" not in r:
            raise ValueError(f"records[{i}].total_length 缺失")
        total += qty
        value = r.get("total_length_value")
        if not isinstance(value, (int, float)):
            raise ValueError(f"records[{i}].total_length_value 必须是数字")
        total_len += float(value)
    meta = model.get("metadata", {})
    if total != meta.get("total_quantity", total):
        raise ValueError("total_quantity 与逐行数量之和不一致")
    if round(total_len, 3) != round(float(meta.get("total_length", total_len)), 3):
        raise ValueError("total_length 与逐行总长之和不一致")
    return {"records": len(records), "total_quantity": total,
            "total_length": round(total_len, 3), "issues": len(model.get("issues", []))}


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
THIN = Side(style="thin", color="B0B0B0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _style_header(sheet: Any, ncols: int) -> None:
    for cell in sheet[1][:ncols]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDEBF7")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    sheet.row_dimensions[1].height = 22
    sheet.freeze_panes = "A2"


def display_width(value: Any) -> int:
    """文字在 Excel 里占几个字符宽：中日韩全角算 2，其余算 1。"""
    text = "" if value is None else str(value)
    return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def autosize(sheet: Any, min_widths: dict[int, int] | None = None,
             max_widths: dict[int, int] | None = None) -> None:
    """按每列最长内容设置列宽，保证文字能在一行里完整显示。

    以前这里是写死列宽，长一点的型号/长度就被截断（用户反馈）。现在逐列扫描实际内容：
    取显示宽度最大值 + 内边距；min_widths 保证短列不至于太窄。
    Excel 自身的列宽上限是 255 个字符，超过这个宽度写了也显示不下——那种极端长文本
    （例如一类几百根电缆的电缆号拼接）由调用方对该列开自动换行兜底，保证内容不被藏起来。
    """
    mins = min_widths or {}
    maxs = max_widths or {}
    ncols = sheet.max_column or 1
    nrows = sheet.max_row or 1
    for col in range(1, ncols + 1):
        longest = 0
        for row in range(1, nrows + 1):
            value = sheet.cell(row=row, column=col).value
            width_needed = display_width(value)
            if row == 1:
                # 表头是加粗的，同一串字比默认字体宽一些；按普通字宽算会被切掉末尾。
                width_needed = int(width_needed * 1.12) + 1
            longest = max(longest, width_needed)
        width = max(longest + 2.5, float(mins.get(col, 8)))
        if col in maxs:
            width = min(width, float(maxs[col]))
        width = min(width, 255.0)        # Excel 列宽上限就是 255，再宽也显示不出来
        sheet.column_dimensions[get_column_letter(col)].width = round(width, 1)


def export_summary(model: dict[str, Any], output: Path) -> dict[str, Any]:
    validate_summary(model)
    if output.exists():
        raise FileExistsError(f"拒绝覆盖现有文件：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_SUMMARY
    ws.append(EXCEL_HEADERS)
    for r in model["records"]:
        ws.append([r["spec"], r["selected_cores"], r["core_section"],
                   r["total_length"], r["quantity"]])
    # 不写「合计」行（用户要求）：各类别行就是汇总表的全部内容。
    # 合计数值仍然保留在隐藏的 _meta 表与模型 metadata 里（total_quantity / total_length）。
    _style_header(ws, len(EXCEL_HEADERS))
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=len(EXCEL_HEADERS)):
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = BORDER
    autosize(ws, {1: 22, 2: 12, 3: 16, 4: 12, 5: 10})
    ws.auto_filter.ref = f"A1:E{max(ws.max_row, 1)}"

    # 备用/预留电缆单独一个 sheet：参数往往未定、不计入正式合计。
    # 以前靠表内一行「备用/预留电缆（不计入上方合计）」分隔，区分度不够（用户反馈），
    # 现在彻底分表，两个 sheet 结构相同、互不干扰。
    spare_ws = wb.create_sheet(SHEET_SPARE)
    spare_ws.append(EXCEL_HEADERS)
    for r in model.get("spare_records") or []:
        spare_ws.append([r["spec"], r["selected_cores"], r["core_section"],
                         r["total_length"], r["quantity"]])
    _style_header(spare_ws, len(EXCEL_HEADERS))
    for row in spare_ws.iter_rows(min_row=2, max_row=spare_ws.max_row, max_col=len(EXCEL_HEADERS)):
        for cell in row:
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = BORDER
    autosize(spare_ws, {1: 22, 2: 12, 3: 16, 4: 12, 5: 10})
    if spare_ws.max_row > 1:
        spare_ws.auto_filter.ref = f"A1:E{spare_ws.max_row}"

    detail = wb.create_sheet(SHEET_DETAIL)
    detail.append(["汇总行", "电缆型号", "选用芯数", "每芯截面(mm²)", "总长度(m)", "数量", "电缆号"])
    for r in list(model["records"]) + list(model.get("spare_records") or []):
        detail.append([r["row_id"], r["spec"], r["selected_cores"], r["core_section"],
                       r["total_length"], r["quantity"], ",".join(r["cable_ids"])])
    _style_header(detail, 7)
    for row in detail.iter_rows(min_row=2, max_row=detail.max_row, max_col=7):
        for cell in row:
            cell.alignment = Alignment(horizontal="left" if cell.column == 7 else "center", vertical="center")
            cell.border = BORDER
    autosize(detail, {1: 10, 2: 20, 3: 12, 4: 16, 5: 12, 6: 8, 7: 30})
    # 电缆号可能多到超过 Excel 的 255 列宽上限：那种情况靠自动换行把内容完整显示出来，
    # 而不是截断（列宽能装下时不换行，视觉上仍是一行）。
    for row in detail.iter_rows(min_row=1, max_row=detail.max_row, min_col=7, max_col=7):
        for cell in row:
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    issues = wb.create_sheet(SHEET_ISSUES)
    issues.append(["issue_id", "电缆号", "字段", "级别", "问题"])
    for i in model.get("issues", []):
        issues.append([i["issue_id"], ",".join(i["cable_ids"]), i["field"], i["severity"], i["message"]])
    _style_header(issues, 5)
    for row in issues.iter_rows(min_row=2, max_row=issues.max_row, max_col=5):
        for cell in row:
            cell.alignment = Alignment(horizontal="left" if cell.column in (2, 5) else "center", vertical="center")
            cell.border = BORDER
    autosize(issues, {1: 10, 2: 20, 3: 12, 4: 10, 5: 30})
    # 同上：问题描述过长时自动换行，不截断
    for row in issues.iter_rows(min_row=1, max_row=issues.max_row, min_col=5, max_col=5):
        for cell in row:
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    meta = wb.create_sheet(SHEET_META)
    meta.append(["schema_version", SCHEMA_VERSION])
    for k, v in sorted(model["metadata"].items()):
        meta.append([k, json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v])
    meta.append(["group_key", "电缆型号+选用芯数+每芯截面 三项一致即归为一类，长度(m)按类相加"])
    meta.sheet_state = "hidden"
    wb.save(output)
    return {"output": str(output.resolve()), **validate_summary(model)}


def write_json(data: dict[str, Any], output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"拒绝覆盖现有文件：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_extract(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input)
    kinds: dict[str, int] = {}
    suffix = source.suffix.lower()
    if suffix == ".dxf":
        # 离线/网页路径：直接读 DXF，不需要 CAD 或 MCP。
        texts = entities_from_dxf(source)
        doc_name = source.name
        for t in texts:
            kinds[t["source"]] = kinds.get(t["source"], 0) + 1
    elif suffix in {".tsv", ".txt"}:
        # CAD 插件路径：客户端只上传选择集文字清单，不上传图纸。
        texts = entities_from_tsv(source)
        doc_name = source.stem
        for t in texts:
            kinds[t["source"]] = kinds.get(t["source"], 0) + 1
    else:
        data = load_artifact(source)
        texts = entities_from_artifact(data)
        doc = data.get("document") or {}
        doc_name = doc.get("name") or doc.get("full_name") or source.name
        kinds = entity_kind_counts(data)
    if not texts:
        raise ValueError("输入中没有文字实体，无法提取电缆表")
    records, candidates = extract_tables(texts)
    usable = [c for c in candidates if c["usable"]]
    if not usable:
        raise ValueError("选中范围内没有识别到可汇总的电缆表（需含电缆号/电缆型号/选用芯数/每芯截面/长度列）")
    if not records:
        raise ValueError("识别到列表头但没有提取到电缆数据行")
    # 多行文字/标注不参与表识别，但要如实登记被忽略的数量，避免“选择集里有内容却没进表”无处解释。
    ignored = {k: v for k, v in kinds.items() if k in {"MTEXT", "MULTILEADER", "DIMENSION"}}
    metadata = {
        "source_document": doc_name,
        "source_input": str(source.resolve()),
        "recognised_tables": len(usable),
        "candidate_tables": candidates,
        "ignored_text_entities": ignored,
    }
    model = build_summary(records, metadata, keep_incomplete=bool(args.keep_incomplete))
    model["source_rows"] = [
        {"row_id": f"R{i}", "table": r["table"], "cable_id": r["cable_id"],
         "spec": norm_text(r["values"].get("spec", "")),
         "selected_cores": norm_text(r["values"].get("selected_cores", "")),
         "core_section": norm_text(r["values"].get("core_section", "")),
         "length": norm_text(r["values"].get("length", "")),
         "start": norm_text(r["values"].get("start", "")), "end": norm_text(r["values"].get("end", "")),
         "handles": r["handles"]}
        for i, r in enumerate(records, 1)
    ]
    write_json(model, Path(args.output_json))
    result = {"model": str(Path(args.output_json).resolve()), **validate_summary(model)}
    if args.output_xlsx:
        result |= export_summary(model, Path(args.output_xlsx))
    return result


def cmd_render(args: argparse.Namespace) -> dict[str, Any]:
    model = json.loads(Path(args.input_json).read_text(encoding="utf-8-sig"))
    return export_summary(model, Path(args.output))


def cmd_tsv(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input)
    if source.suffix.lower() == ".dxf":
        texts = entities_from_dxf(source)
    else:
        texts = entities_from_artifact(load_artifact(source))
    write_tsv(texts, Path(args.output))
    return {"output": str(Path(args.output).resolve()), "entities": len(texts)}


def cmd_validate(args: argparse.Namespace) -> dict[str, Any]:
    model = json.loads(Path(args.input_json).read_text(encoding="utf-8-sig"))
    if model.get("schema_version") == SCHEMA_VERSION:
        return validate_summary(model)
    raise ValueError(f"schema_version 必须是 {SCHEMA_VERSION}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="选中电缆表 → 型号/芯数/截面三项汇总 → 采购用 Excel")
    subs = parser.add_subparsers(dest="command", required=True)

    ex = subs.add_parser("extract", help="从选择集 artifact / DXF 提取并汇总")
    ex.add_argument("--input", required=True, help="read_drawing_structure artifact JSON 或 DXF")
    ex.add_argument("--output-json", required=True, help="cable-summary 模型输出路径")
    ex.add_argument("--output-xlsx", help="电缆汇总表.xlsx 输出路径")
    ex.add_argument("--keep-incomplete", action="store_true",
                    help="型号/芯数/截面三项全空的空行也计入汇总表（缺省只登记到待确认）")

    rd = subs.add_parser("render", help="由 cable-summary 模型生成 Excel")
    rd.add_argument("--input-json", required=True)
    rd.add_argument("--output", required=True)

    va = subs.add_parser("validate", help="校验 cable-summary 模型")
    va.add_argument("--input-json", required=True)

    tp = subs.add_parser("tsv", help="把已有 artifact 的文字实体导出为 TSV（供 CAD 插件核对格式）")
    tp.add_argument("--input", required=True, help="read_drawing_structure artifact JSON 或 DXF")
    tp.add_argument("--output", required=True, help="TSV 输出路径")

    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            result = cmd_extract(args)
        elif args.command == "render":
            result = cmd_render(args)
        elif args.command == "tsv":
            result = cmd_tsv(args)
        else:
            result = cmd_validate(args)
    except (OSError, ValueError, json.JSONDecodeError, FileExistsError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"valid": True, **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
