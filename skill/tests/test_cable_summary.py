# -*- coding: utf-8 -*-
"""cable-summary（电缆表选中汇总）的行为测试。

覆盖：列头带空格、同行不同对齐 y、文字换行续行、占位符、非电缆表排除、
电缆号前缀与缺号、重复电缆号、空行处置、Excel 契约与合计。
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / "scripts" / "电缆汇总统计.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("cable_summary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


mod = _load_module()


# --------------------------------------------------------------------------- #
# 测试数据构造
# --------------------------------------------------------------------------- #
HDR_X = {
    "cable_id": 0.0, "start": 1842.6, "end": 3708.5, "wire_numbers": 9352.3,
    "required_cores": 17051.6, "spec": 19050.0, "selected_cores": 21072.0,
    "core_section": 23065.8, "length": 25082.5, "remark": 31788.8,
}
HDR_TEXT = {
    "cable_id": "电缆号", "start": "起 点", "end": "终  点", "wire_numbers": "线          号",
    "required_cores": "需用芯数", "spec": "电缆型号", "selected_cores": "选用芯数",
    "core_section": "每芯截面", "length": "长度(m)", "remark": "备     注",
}
ROW_PITCH = 700.0
CELL_TOP = -150.0   # 电缆号/线号等内容的 y 偏移
CELL_MID = -125.0   # 其余列的 y 偏移


def _t(handle, x, y, text, height=500.0, layer="C-4"):
    return {"type": "TEXT", "handle": handle, "layer": layer, "text": text,
            "insert": [x, y, 0.0], "height": height, "rotation": 0.0, "style": "HZTXT",
            "kind": "TEXT", "space": "modelspace", "coordinate_space": "model_wcs",
            "point": [x, y, 0.0]}


def make_table(ox, oy, rows, handles, *, table_title="控制电缆表"):
    """rows: list of dict(field -> str)；值为 None 表示该单元格留空。"""
    items = []
    for key, text in HDR_TEXT.items():
        items.append(_t(next(handles), ox + HDR_X[key], oy, text))
    for i, row in enumerate(rows):
        y = oy - 1275.0 - i * ROW_PITCH
        for key, value in row.items():
            if value is None:
                continue
            y_off = CELL_TOP if key in ("cable_id", "wire_numbers") else CELL_MID
            items.append(_t(next(handles), ox + HDR_X[key], y + y_off, value))
    items.append(_t(next(handles), ox - 17000.0, oy - len(rows) * ROW_PITCH - 5000.0,
                    table_title, height=350.0))
    return items


def make_load_table(ox, oy, handles):
    """非电缆表：只有电缆号/起点/终点/最大需要容量等，必须被排除。"""
    cols = {"电缆号": 0.0, "起 点": 1842.6, "终  点": 3708.5, "最大需要容量": 5907.8, "备     注": 31788.8}
    items = [_t(next(handles), ox + x, oy, text) for text, x in cols.items()]
    for i in range(2):
        y = oy - 1275.0 - i * ROW_PITCH
        items.append(_t(next(handles), ox, y, f"X{i + 1}"))
        items.append(_t(next(handles), ox + 5907.8, y, "12.5"))
    return items


def make_artifact(items, *, name="测试图.dwg"):
    return {
        "success": True,
        "read_scope": "selected",
        "document": {"name": name, "full_name": f"C:/tmp/{name}", "cad_type": "AutoCAD"},
        "selection": {"count": len(items), "handles": [i["handle"] for i in items],
                      "types": [i["type"] for i in items], "layers": sorted({i["layer"] for i in items})},
        "scan": {"total": len(items), "returned": len(items), "truncated": False,
                 "items": items, "criteria": {}, "warnings": {}},
    }


def handle_gen():
    n = 0
    while True:
        n += 1
        yield f"T{n:05X}"


def build_case():
    h = handle_gen()
    t1 = make_table(0.0, 0.0, [
        {"cable_id": "K1", "start": "1KB", "end": "1AFE", "required_cores": "3",
         "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "13"},
        {"cable_id": "K2", "start": "1KB", "end": "1INU", "required_cores": "3",
         "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "13"},
        # 数值写法等价：13.0/1.50 应与 13/1.5 合并
        {"cable_id": "K3", "start": "1KB", "end": "2INU", "required_cores": "2",
         "spec": "KVV", "selected_cores": "4", "core_section": "1.50", "length": "13.0"},
        # 备用：截面与长度是占位符，仍按型号/芯数/截面原样合并
        {"cable_id": "K4", "start": "1KB", "end": "备用", "required_cores": "2",
         "spec": "KVV", "selected_cores": "4", "core_section": "-", "length": "-"},
        {"cable_id": "K5", "start": "1KB", "end": "备用", "required_cores": "2",
         "spec": "KVV", "selected_cores": "4", "core_section": "-", "length": "-"},
        # 型号/芯数/截面三项全空：缺省不计入汇总
        {"cable_id": "K6", "start": None, "end": None, "required_cores": None,
         "spec": None, "selected_cores": None, "core_section": None, "length": None},
    ], h)
    t2 = make_table(320000.0, 0.0, [
        # UK 前缀同样有效；不同型号必须分行
        {"cable_id": "UK1", "start": "1YB", "end": "1KB", "required_cores": "2",
         "spec": "YJV-0.6/1kV", "selected_cores": "2", "core_section": "2.5", "length": "25"},
        {"cable_id": "UK2", "start": "1KB", "end": "3DB", "wire_numbers": "1K01,3DB01",
         "required_cores": "2", "spec": "YJV-0.6/1kV", "selected_cores": "2",
         "core_section": "2.5", "length": "7"},
    ], h)
    wrap_row_y = 0.0 - 1275.0 - 1 * ROW_PITCH
    t2.append(_t(next(h), HDR_X["wire_numbers"] + 320000.0, wrap_row_y - 300.0,
                   "3DB02,3DB03", height=350.0))
    t3 = make_load_table(640000.0, 0.0, h)
    return make_artifact(t1 + t2 + t3)


# --------------------------------------------------------------------------- #
# 提取与汇总
# --------------------------------------------------------------------------- #
def test_extracts_only_cable_tables_and_aggregates_by_three_fields():
    texts = mod.entities_from_artifact(build_case())
    records, candidates = mod.extract_tables(texts)
    usable = [c for c in candidates if c["usable"]]
    assert len(usable) == 2, "负荷表不得被认定为可汇总电缆表"
    assert any(not c["usable"] for c in candidates), "负荷表应登记为不可用候选"

    model = mod.build_summary(records, {"source_document": "测试图.dwg"})
    rows = {(r["spec"], r["selected_cores"], r["core_section"]): r["quantity"]
            for r in model["records"]}
    lengths = {(r["spec"], r["selected_cores"], r["core_section"]): r["total_length"]
               for r in model["records"]}

    # 三项一致即合并：K1(13) + K2(13) + K3(13.0) → 3 根、总长 39
    assert rows[("KVV", "4", "1.5")] == 3
    assert lengths[("KVV", "4", "1.5")] == "39"
    group = [r for r in model["records"] if r["spec"] == "KVV" and r["core_section"] == "1.5"][0]
    assert sorted(group["cable_ids"]) == ["K1", "K2", "K3"]
    # K4/K5 终点是「备用」→ 单独归集，不出现在正式统计里
    spare = {(r["spec"], r["selected_cores"], r["core_section"]): r for r in model["spare_records"]}
    assert spare[("KVV", "4", "-")]["quantity"] == 2
    assert spare[("KVV", "4", "-")]["total_length"] == "-"     # 长度是占位符，无法相加
    # UK1/UK2 型号与截面相同 → 合并；长度 25 + 7 = 32
    assert rows[("YJV-0.6/1kV", "2", "2.5")] == 2
    assert lengths[("YJV-0.6/1kV", "2", "2.5")] == "32"
    assert len(model["records"]) == 2                            # 正式只剩 KVV/4/1.5 与 YJV/2/2.5
    assert model["metadata"]["total_quantity"] == 5               # 备用 2 根不计入
    assert model["metadata"]["spare_quantity"] == 2
    assert model["metadata"]["total_length"] == 71                # 39 + 32


def test_blank_four_field_row_is_reported_not_silently_dropped():
    texts = mod.entities_from_artifact(build_case())
    records, _ = mod.extract_tables(texts)
    model = mod.build_summary(records, {})
    assert model["metadata"]["skipped_incomplete_rows"] == 1
    assert model["metadata"]["skipped_incomplete_cable_ids"] == ["K6"]
    assert any("工程参数全空" in i["message"] for i in model["issues"])
    kept = mod.build_summary(records, {}, keep_incomplete=True)
    # keep_incomplete 只影响"三项全空的空行"；备用仍单列，故正式为 5 + 空行 1 + ... 见下
    assert kept["metadata"]["total_quantity"] == 6


def test_wrapped_cell_text_merges_into_its_row():
    texts = mod.entities_from_artifact(build_case())
    records, _ = mod.extract_tables(texts)
    uk2 = [r for r in records if r["cable_id"] == "UK2"]
    assert len(uk2) == 1, "换行续行不得被拆成两条电缆记录"
    assert "3DB02" in uk2[0]["values"]["wire_numbers"]


def test_numbering_gap_and_duplicate_id_are_flagged():
    h = handle_gen()
    items = make_table(0.0, 0.0, [
        {"cable_id": "K1", "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "5"},
        {"cable_id": "K4", "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "5"},
    ], h)
    texts = mod.entities_from_artifact(make_artifact(items))
    records, _ = mod.extract_tables(texts)
    model = mod.build_summary(records, {})
    assert any("缺号" in i["message"] for i in model["issues"])

    # 新口径下长度不再拆分类别，所以必须用"截面不同"来制造同一电缆号的口径冲突
    h2 = handle_gen()
    items2 = make_table(0.0, 0.0, [
        {"cable_id": "K1", "spec": "KVV", "selected_cores": "4", "core_section": "1.5", "length": "5"},
        {"cable_id": "K1", "spec": "KVV", "selected_cores": "4", "core_section": "2.5", "length": "6"},
    ], h2)
    records2, _ = mod.extract_tables(mod.entities_from_artifact(make_artifact(items2)))
    model2 = mod.build_summary(records2, {})
    assert [i for i in model2["issues"] if i["severity"] == "conflict"]


def test_truncated_artifact_and_empty_selection_fail_closed(tmp_path):
    art = build_case()
    art["scan"]["truncated"] = True
    p = tmp_path / "truncated.json"
    p.write_text(json.dumps(art, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="截断"):
        mod.load_artifact(p)

    art2 = build_case()
    art2["selection"]["count"] = 0
    p2 = tmp_path / "empty.json"
    p2.write_text(json.dumps(art2, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match="选择集为空"):
        mod.load_artifact(p2)


# --------------------------------------------------------------------------- #
# Excel 契约
# --------------------------------------------------------------------------- #
def test_export_workbook_contract(tmp_path):
    records, _ = mod.extract_tables(mod.entities_from_artifact(build_case()))
    model = mod.build_summary(records, {"source_document": "测试图.dwg"})
    out = tmp_path / "电缆汇总表.xlsx"
    mod.export_summary(model, out)

    wb = load_workbook(out)
    # 备用电缆自成一个 sheet（用户要求：与正式统计彻底分开）
    assert wb.sheetnames[:4] == ["电缆汇总", "备用电缆", "明细", "待确认"]
    assert wb["_meta"].sheet_state == "hidden"
    summary = wb["电缆汇总"]
    assert [c.value for c in summary[1]] == ["电缆型号", "选用芯数", "每芯截面(mm²)", "总长度(m)", "数量"]
    rows_all = [[c.value for c in r] for r in summary.iter_rows()]
    # 「电缆汇总」不再有合计行：只有表头 + 各类别行
    assert not any(r and r[0] == "合计" for r in rows_all), "汇总表不应再有合计行"
    assert len(rows_all) == 1 + len(model["records"])
    quantities = [summary.cell(row=r, column=5).value for r in range(2, summary.max_row + 1)]
    assert all(isinstance(q, int) for q in quantities)
    # 合计数值仍在模型里（隐藏 _meta 表也记着），只是不再写进汇总表
    assert sum(quantities) == model["metadata"]["total_quantity"]
    # 备用电缆在它自己的 sheet 里，行数与模型一致，且不计入上面的合计
    spare = wb["备用电缆"]
    assert [c.value for c in spare[1]] == ["电缆型号", "选用芯数", "每芯截面(mm²)", "总长度(m)", "数量"]
    spare_rows = [[c.value for c in r] for r in spare.iter_rows(min_row=2)]
    assert len(spare_rows) == len(model["spare_records"]) > 0
    assert sum(r[4] for r in spare_rows) == model["metadata"]["spare_quantity"]
    assert not any(r and r[0] in ("合计", "备用小计") for r in spare_rows), "备用表不写小计行"

    # 列宽自适应：每列宽度要装得下该列最长内容（中文按 2 字符算），保证一行显示完整
    def display_width(value):
        return sum(2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in str(value or ""))

    for sheet in (summary, spare):
        for col in range(1, 6):
            longest = max(display_width(sheet.cell(row=r, column=col).value)
                          for r in range(1, sheet.max_row + 1))
            width = sheet.column_dimensions[get_column_letter(col)].width
            assert width >= longest, f"{sheet.title} 第 {col} 列宽 {width} 装不下最长内容 {longest}"
    detail = wb["明细"]
    assert [c.value for c in detail[1]][:6] == ["汇总行", "电缆型号", "选用芯数", "每芯截面(mm²)", "总长度(m)", "数量"]
    joined = [detail.cell(row=r, column=7).value for r in range(2, detail.max_row + 1)]
    assert all("、" not in (v or "") for v in joined), "电缆号必须用英文逗号拼接"


def test_export_refuses_to_overwrite(tmp_path):
    records, _ = mod.extract_tables(mod.entities_from_artifact(build_case()))
    model = mod.build_summary(records, {})
    out = tmp_path / "电缆汇总表.xlsx"
    mod.export_summary(model, out)
    with pytest.raises(FileExistsError):
        mod.export_summary(model, out)


# --------------------------------------------------------------------------- #
# CLI 端到端
# --------------------------------------------------------------------------- #
def test_cli_extract_render_validate_roundtrip(tmp_path):
    art = tmp_path / "artifact.json"
    art.write_text(json.dumps(build_case(), ensure_ascii=False), encoding="utf-8")
    model = tmp_path / "cable-summary.json"
    xlsx = tmp_path / "电缆汇总表.xlsx"

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "extract", "--input", str(art),
         "--output-json", str(model), "--output-xlsx", str(xlsx)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["valid"] is True and payload["total_quantity"] == 5   # 备用 2 根单列，不计入

    proc2 = subprocess.run(
        [sys.executable, str(SCRIPT), "validate", "--input-json", str(model)],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc2.returncode == 0 and json.loads(proc2.stdout)["valid"] is True

    proc3 = subprocess.run(
        [sys.executable, str(SCRIPT), "render", "--input-json", str(model),
         "--output", str(tmp_path / "再导出.xlsx")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc3.returncode == 0, proc3.stdout + proc3.stderr
    assert (tmp_path / "再导出.xlsx").exists()


def test_tsv_round_trip_matches_artifact(tmp_path):
    """CAD 插件路径：artifact → TSV → 汇总，必须与直接汇总一致（且体积远小于 DXF）。"""
    art = build_case()
    texts = mod.entities_from_artifact(art)
    tsv = tmp_path / "selection.tsv"
    mod.write_tsv(texts, tsv)

    back = mod.entities_from_tsv(tsv)
    assert len(back) == len(texts)
    direct = mod.build_summary(mod.extract_tables(texts)[0], {})
    via_tsv = mod.build_summary(mod.extract_tables(back)[0], {})
    assert [r["quantity"] for r in direct["records"]] == [r["quantity"] for r in via_tsv["records"]]
    assert direct["metadata"]["total_quantity"] == via_tsv["metadata"]["total_quantity"] == 5   # 备用 2 根单列，不计入

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "extract", "--input", str(tsv),
         "--output-json", str(tmp_path / "t.json"), "--output-xlsx", str(tmp_path / "t.xlsx")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["total_quantity"] == 5   # 备用 2 根单列，不计入


def test_tsv_written_in_ansi_codepage_is_read(tmp_path):
    """回归：AutoLISP 的 (open path "w") 写 GBK，读取端必须能认。

    真实事故：插件送来的 TSV 里中文（线号/起终点）按 GBK 编码，
    引擎按 UTF-8 读 → UnicodeDecodeError → 用户看到"读取失败"。
    """
    art = build_case()
    texts = mod.entities_from_artifact(art)
    tsv = tmp_path / "ansi.tsv"
    mod.write_tsv(texts, tsv)
    text = tsv.read_text(encoding="utf-8")
    assert any(ord(c) > 127 for c in text), "夹具本身要含中文才能覆盖这条路径"
    tsv.write_bytes(text.encode("gbk"))          # 模拟 AutoCAD 用 ANSI 写文件

    back = mod.entities_from_tsv(tsv)
    assert len(back) == len(texts)
    model = mod.build_summary(mod.extract_tables(back)[0], {})
    direct = mod.build_summary(mod.extract_tables(texts)[0], {})
    assert model["metadata"]["total_quantity"] == direct["metadata"]["total_quantity"] == 5   # 备用 2 根单列，不计入
    assert [r["quantity"] for r in model["records"]] == [r["quantity"] for r in direct["records"]]


def test_tsv_rejects_bad_header_and_rows(tmp_path):
    bad = tmp_path / "bad.tsv"
    bad.write_text("a\tb\tc\n1\t2\t3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="表头"):
        mod.entities_from_tsv(bad)
    short = tmp_path / "short.tsv"
    short.write_text("handle\tlayer\tx\ty\theight\ttext\nH1\tC-4\t1\t2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="列数不足"):
        mod.entities_from_tsv(short)


def test_dxf_input_path_matches_artifact_path(tmp_path):
    """网页/单机部署走 DXF 路径：结果必须与 artifact 路径一致（不需要 CAD 或 MCP）。"""
    ezdxf = pytest.importorskip("ezdxf")
    art = build_case()
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    for item in art["scan"]["items"]:
        x, y = item["insert"][0], item["insert"][1]
        msp.add_text(item["text"], dxfattribs={"height": item["height"], "layer": item["layer"]}
                     ).set_placement((x, y))
    dxf = tmp_path / "selection.dxf"
    doc.saveas(dxf)

    texts = mod.entities_from_dxf(dxf)
    records, _ = mod.extract_tables(texts)
    model = mod.build_summary(records, {})
    assert model["metadata"]["total_quantity"] == 5   # 备用 2 根单列，不计入
    assert model["metadata"]["summary_row_count"] == 2      # 正式 2 类（备用单列）

    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "extract", "--input", str(dxf),
         "--output-json", str(tmp_path / "m.json"), "--output-xlsx", str(tmp_path / "m.xlsx")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout)["total_quantity"] == 5   # 备用 2 根单列，不计入


REAL_ARTIFACT = Path(
    r"C:\Users\ASUS\AppData\Local\Temp\hermes-cad\b9d82655-5d1e-41d7-8805-88e4d70645b5\drawing_structure.json"
)


@pytest.mark.skipif(not REAL_ARTIFACT.exists(), reason="本机真实选择集 artifact 不存在")
def test_real_selection_artifact_regression():
    """真实图纸回归：7 张电缆表、170 行读取、145 根汇总为 49 类。"""
    data = mod.load_artifact(REAL_ARTIFACT)
    texts = mod.entities_from_artifact(data)
    records, candidates = mod.extract_tables(texts)
    usable = [c for c in candidates if c["usable"]]
    assert len(usable) == 7
    assert len(records) == 170
    model = mod.build_summary(records, {"source_document": "回归"})
    assert model["metadata"]["summary_row_count"] == 49
    assert model["metadata"]["total_quantity"] == 115   # 备用 30 根单列
    assert model["metadata"]["skipped_incomplete_rows"] == 25
    assert not [i for i in model["issues"] if i["severity"] == "conflict"]
    backup = [r for r in model["records"] if r["length"] == "-" and r["core_section"] == "-"]
    assert len(backup) == 1 and backup[0]["quantity"] == 23
