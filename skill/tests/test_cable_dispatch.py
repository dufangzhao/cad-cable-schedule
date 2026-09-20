"""电缆表绘图计划的文件分发交接（纯文件，不连接 CAD）。

覆盖：生成器默认产出 cad_dispatch.json 与 UTF-8 侧车；计划文件与验收数据不被改写；
draw_entities 批次（cable-annotations）内容逐字一致、行数与 expected 对应；
execute_command（ZOOM）与 {{handle}} 绑定操作保持内联；``--no-dispatch`` 只出计划。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

PLAN_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "生成电缆表绘图计划.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PLAN = _load(PLAN_SCRIPT, "cable_draw_plan_dispatch")


def record(row_id, cable_type, number, *, status="confirmed", confidence="high"):
    return {"row_id": row_id, "row_kind": "data", "cable_type": cable_type, "number": number,
            "cable_id": f"{cable_type}{number}", "start": "A", "end": "B", "spec": "4x1.5",
            "required_cores": 2, "spare_cores": 2, "wire_numbers": ["101", "102"],
            "direction_confidence": confidence, "status": status, "issue": ""}


def model():
    return {"schema_version": "cable-workbook", "metadata": {}, "issues": [],
            "records": [record("k1", "K", 1), record("k2", "K", 2), record("k3", "K", 3),
                        record("a1", "AK", 1)]}


def type_rule(origin):
    return {"source_dwg": "C:/blocks/cable.dwg", "capacity": 2, "origin_offset": origin,
            "block_step": [100, 0, 0], "local_bbox": [0, -50, 80, 0],
            "dynamic_parameters": {"行数": "$row_count", "类型": "$cable_type"},
            "row_layout": {"first_row_offset": [10, -5, 0], "row_step": [0, -5, 0],
                           "columns": [{"field": "number", "offset": [0, 0, 0], "height": 2.5,
                                        "layer": "CABLE", "color": "white"},
                                       {"field": "cable_id", "offset": [15, 0, 0], "height": 2.5,
                                        "layer": "CABLE", "color": "white"}]}}


def rules():
    return {"schema_version": "cable-layout-rules", "knowledge_sources": ["wiki/cable-layout"],
            "layers": [{"name": "CABLE", "color": "white", "lineweight": 25}],
            "types": {"K": type_rule([0, 0, 0]), "AK": type_rule([0, -100, 0])}, "view_margin": 10}


def compile_and_write(tmp_path, *, dispatch=True, dispatch_dir=None):
    model_path = tmp_path / "model.json"
    rules_path = tmp_path / "rules.json"
    model_path.write_text(json.dumps(model(), ensure_ascii=False), encoding="utf-8")
    rules_path.write_text(json.dumps(rules(), ensure_ascii=False), encoding="utf-8")
    plan_path = tmp_path / "plan.json"
    argv = ["--cable-model", str(model_path), "--rules", str(rules_path),
            "--source-dwg", "C:/source.dwg", "--save-as", "C:/out.dwg",
            "--request-id", "req-cable-dispatch", "--output", str(plan_path)]
    if dispatch_dir is not None:
        argv += ["--dispatch-output", str(dispatch_dir)]
    if not dispatch:
        argv.append("--no-dispatch")
    assert PLAN.main(argv) == 0
    return plan_path, json.loads(plan_path.read_text(encoding="utf-8"))


def test_cable_generator_writes_dispatch_without_touching_plan(tmp_path):
    plan_path, plan = compile_and_write(tmp_path)
    before = plan_path.read_bytes()
    dispatch_path = tmp_path / "cad_dispatch.json"
    assert dispatch_path.is_file(), "独立生成器默认必须产出文件分发清单"
    dispatch = json.loads(dispatch_path.read_text(encoding="utf-8"))

    assert dispatch["schema_version"] == "cad-dispatch"
    assert dispatch["caller_skill"] == "cad-cable-schedule"
    assert dispatch["plan_sha256"]
    assert plan_path.read_bytes() == before, "dispatch 生成不得改写计划文件"
    assert [e["operation_id"] for e in dispatch["operations"]] == [
        o["operation_id"] for o in plan["operations"]
    ]
    assert [e["action"] for e in dispatch["operations"]] == [
        o["action"] for o in plan["operations"]
    ]


def test_cable_annotations_batch_is_byte_exact_and_ordered(tmp_path):
    plan_path, plan = compile_and_write(tmp_path, dispatch=False)
    dispatch_path = PLAN.write_plan_dispatch(plan, plan_path, tmp_path / "out")
    dispatch = json.loads(dispatch_path.read_text(encoding="utf-8"))

    annotations = [e for e in dispatch["operations"] if e["operation_id"] == "cable-annotations"]
    assert annotations, "计划必须包含 cable-annotations 批次"
    entry = annotations[0]
    original = next(o for o in plan["operations"] if o["operation_id"] == "cable-annotations")
    marker = entry["params"]["entities"]
    if marker.startswith("@file:"):
        assert Path(marker[len("@file:"):]).read_text(encoding="utf-8") == original["params"]["entities"]
    else:
        assert marker == original["params"]["entities"]
    # expected 的 entity_map 逐条保留（顺序即行序）
    assert entry["expected"]["entity_map"] == original["expected"]["entity_map"]
    assert entry["expected"]["entity_count"] == original["expected"]["entity_count"]


def test_cable_zoom_and_placeholder_ops_stay_inline(tmp_path):
    _, plan = compile_and_write(tmp_path, dispatch=False)
    dispatch_path = PLAN.write_plan_dispatch(plan, tmp_path / "plan.json", tmp_path / "out")
    dispatch = json.loads(dispatch_path.read_text(encoding="utf-8"))

    dynamic_ids = [op["operation_id"] for op in plan["operations"] if op["action"] == "block_dyn"]
    assert dynamic_ids, "电缆计划必须含按 handle_ref 绑定的动态参数操作"
    assert [e["operation_id"] for e in dispatch["operations"]] == [
        o["operation_id"] for o in plan["operations"]
    ]
    for entry, original in zip(dispatch["operations"], plan["operations"]):
        if original["action"] == "execute_command":
            # 原生命令串不是实体批次：MCP 不解析 @file:，必须原样内联
            assert entry["params"]["command"] == original["params"]["command"]
            assert not entry["params"]["command"].startswith("@file:")
        if original["action"] == "block_dyn":
            # handle 占位符必须内联，并登记为执行前阻断条件
            assert entry["params"]["operations"] == original["params"]["operations"]
            assert "{{handle}}" in entry["params"]["operations"]
    blocked = {item["operation_id"] for item in dispatch.get("binding_required", [])}
    assert set(dynamic_ids) <= blocked
    assert dispatch["execution_blockers"]


def test_cable_no_dispatch_flag_writes_only_plan(tmp_path):
    plan_path, _ = compile_and_write(tmp_path, dispatch=False, dispatch_dir=tmp_path / "nested")
    assert plan_path.is_file()
    assert not (tmp_path / "cad_dispatch.json").exists()
    assert not (tmp_path / "nested").exists()
    assert list(tmp_path.glob("payload_*.txt")) == []
