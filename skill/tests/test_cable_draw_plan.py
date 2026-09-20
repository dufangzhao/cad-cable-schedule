from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "生成电缆表绘图计划.py"
SPEC = importlib.util.spec_from_file_location("cable_draw_plan", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

_SKILLS_ROOT = Path(__file__).resolve().parents[2]
_DRAWING_ROOT = _SKILLS_ROOT / "cad-drawing"
CONTRACT_SCRIPT = _DRAWING_ROOT / "scripts" / "校验CAD服务契约.py"
CONTRACT_SPEC = importlib.util.spec_from_file_location("cad_contract_for_cable", CONTRACT_SCRIPT)
assert CONTRACT_SPEC and CONTRACT_SPEC.loader
CONTRACT = importlib.util.module_from_spec(CONTRACT_SPEC)
CONTRACT_SPEC.loader.exec_module(CONTRACT)


def record(row_id, cable_type, number, *, status="confirmed", confidence="high"):
    return {"row_id": row_id, "row_kind": "data", "cable_type": cable_type, "number": number, "cable_id": f"{cable_type}{number}", "start": "A", "end": "B", "spec": "4x1.5", "required_cores": 2, "spare_cores": 2, "wire_numbers": ["101", "102"], "direction_confidence": confidence, "status": status, "issue": ""}


def model():
    return {"schema_version": "cable-workbook", "metadata": {}, "issues": [], "records": [record("k1", "K", 1), record("k2", "K", 2), record("k3", "K", 3), record("a1", "AK", 1)]}


def type_rule(origin):
    return {"source_dwg": "C:/blocks/cable.dwg", "capacity": 2, "origin_offset": origin, "block_step": [100, 0, 0], "local_bbox": [0, -50, 80, 0], "dynamic_parameters": {"行数": "$row_count", "类型": "$cable_type"}, "row_layout": {"first_row_offset": [10, -5, 0], "row_step": [0, -5, 0], "columns": [{"field": "number", "offset": [0, 0, 0], "height": 2.5, "layer": "CABLE", "color": "white"}, {"field": "cable_id", "offset": [15, 0, 0], "height": 2.5, "layer": "CABLE", "color": "white"}]}}


def rules():
    return {"schema_version": "cable-layout-rules", "knowledge_sources": ["wiki/cable-layout"], "layers": [{"name": "CABLE", "color": "white", "lineweight": 25}], "types": {"K": type_rule([0, 0, 0]), "AK": type_rule([0, -100, 0])}, "view_margin": 10}


def test_compiles_separate_type_blocks_and_batches_text():
    plan = MODULE.compile_plan(model(), rules(), "C:/source.dwg", "C:/out.dwg", [100, 200, 0], "req-1")
    inserts = [op for op in plan["operations"] if op["phase"] == "blocks"]
    assert [op["expected"]["cable_type"] for op in inserts] == ["K", "K", "AK"]
    assert inserts[0]["params"]["insertion_point"] == "100,200,0"
    properties = [op for op in plan["operations"] if op["phase"] == "properties"]
    assert len(properties) == 6
    assert properties[0]["params"]["handle_ref"] == "k-001-insert"
    annotations = next(op for op in plan["operations"] if op["phase"] == "annotations")
    assert annotations["expected"]["entity_count"] == 8
    assert plan["acceptance"]["checks"][1]["expected"] == {"K": 2, "AK": 1, "TK": 0}
    CONTRACT.validate_draw_plan(plan)


def test_rejects_unconfirmed_or_unknown_direction():
    candidate = model()
    candidate["records"][0]["status"] = "candidate"
    with pytest.raises(ValueError, match="confirmed"):
        MODULE.compile_plan(candidate, rules(), "C:/source.dwg", "C:/out.dwg", [0, 0, 0], "req")
    unknown = model()
    unknown["records"][0]["direction_confidence"] = "unknown"
    with pytest.raises(ValueError, match="unknown"):
        MODULE.compile_plan(unknown, rules(), "C:/source.dwg", "C:/out.dwg", [0, 0, 0], "req")


def test_rejects_missing_type_rules_and_overlapping_blocks():
    missing = rules()
    del missing["types"]["AK"]
    with pytest.raises(ValueError, match="缺少类型布局规则"):
        MODULE.compile_plan(model(), missing, "C:/source.dwg", "C:/out.dwg", [0, 0, 0], "req")
    overlap = rules()
    overlap["types"]["K"]["block_step"] = [10, 0, 0]
    with pytest.raises(ValueError, match="布局重叠"):
        MODULE.compile_plan(model(), overlap, "C:/source.dwg", "C:/out.dwg", [0, 0, 0], "req")

