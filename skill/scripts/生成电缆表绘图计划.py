from __future__ import annotations

import argparse
import json
import math
import uuid
from pathlib import Path
from typing import Any


MODEL_SCHEMA = "cable-workbook"
RULES_SCHEMA = "cable-layout-rules"
PLAN_SCHEMA = "cad-draw-plan"
TYPES = ("K", "AK", "TK")
ALLOWED_FIELDS = {
    "row_id", "row_kind", "cable_type", "number", "cable_id", "start", "end",
    "spec", "required_cores", "selected_cores", "spare_cores", "core_section", "length",
    "conduit_diameter", "conduit_length", "remark", "wire_numbers", "direction_confidence", "issue",
}


def load_json(path: Path) -> dict[str, Any]:
    def reject_constant(value: str) -> None:
        raise ValueError(f"JSON 不允许 {value}")

    data = json.loads(path.read_text(encoding="utf-8-sig"), parse_constant=reject_constant)
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象")
    return data


def text(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return "" if value is None else str(value).strip()


def safe_token(value: str, field: str) -> str:
    if any(char in value for char in "|\r\n"):
        raise ValueError(f"{field} 不能包含 | 或换行")
    return value


def finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} 必须是有限数值")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是有限数值") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} 必须是有限数值")
    return number


def positive_integer(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{field} 必须是正整数")
    return value


def vector(value: Any, field: str, length: int = 3) -> list[float]:
    valid_lengths = {2, 3} if length == 3 else {length}
    if not isinstance(value, list) or len(value) not in valid_lengths:
        raise ValueError(f"{field} 必须是 {length} 维数值数组")
    result = [finite_number(item, field) for item in value]
    if length == 3 and len(result) == 2:
        result.append(0.0)
    return result


def point_add(*points: list[float]) -> list[float]:
    return [sum(items) for items in zip(*points)]


def point_scale(point: list[float], factor: int) -> list[float]:
    return [item * factor for item in point]


def point_string(point: list[float]) -> str:
    return ",".join(f"{item:.9g}" for item in point)


def validate_model(model: dict[str, Any]) -> list[dict[str, Any]]:
    if model.get("schema_version") != MODEL_SCHEMA:
        raise ValueError(f"电缆模型 schema_version 必须是 {MODEL_SCHEMA}")
    records = model.get("records")
    issues = model.get("issues", [])
    if not isinstance(records, list) or not isinstance(issues, list):
        raise ValueError("电缆模型 records 和 issues 必须是数组")
    blocking = [item for item in issues if isinstance(item, dict) and item.get("severity") == "blocking"]
    if blocking:
        raise ValueError(f"存在 {len(blocking)} 个 blocking issue，禁止绘图")
    row_ids: set[str] = set()
    numbers: dict[str, set[int]] = {kind: set() for kind in TYPES}
    clean: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"records[{index}] 必须是对象")
        row_id = text(record.get("row_id"))
        cable_type = record.get("cable_type")
        number = record.get("number")
        if not row_id or row_id in row_ids:
            raise ValueError(f"records[{index}].row_id 缺失或重复")
        if cable_type not in TYPES:
            raise ValueError(f"records[{index}].cable_type 无效")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1 or number in numbers[cable_type]:
            raise ValueError(f"{cable_type} 数字编号必须是唯一正整数：{number}")
        if record.get("status") != "confirmed":
            raise ValueError(f"records[{index}].status 必须是 confirmed")
        if record.get("row_kind") == "data" and record.get("direction_confidence", "unknown") == "unknown":
            raise ValueError(f"records[{index}] 方向置信度仍为 unknown")
        row_ids.add(row_id)
        numbers[cable_type].add(number)
        clean.append(record)
    if not clean:
        raise ValueError("电缆模型没有可绘制记录")
    for cable_type, present in numbers.items():
        if present and present != set(range(1, max(present) + 1)):
            raise ValueError(f"{cable_type} 编号不连续，缺少空行占位")
    return clean


def validate_rules(rules: dict[str, Any]) -> dict[str, Any]:
    if rules.get("schema_version") != RULES_SCHEMA:
        raise ValueError(f"规则 schema_version 必须是 {RULES_SCHEMA}")
    sources = rules.get("knowledge_sources")
    if not isinstance(sources, list) or not sources or any(not text(item) for item in sources):
        raise ValueError("knowledge_sources 必须是非空字符串数组")
    layers = rules.get("layers", [])
    if not isinstance(layers, list):
        raise ValueError("layers 必须是数组")
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict) or not safe_token(text(layer.get("name")), f"layers[{index}].name"):
            raise ValueError(f"layers[{index}].name 不能为空")
        layer["color"] = safe_token(text(layer.get("color", "white")), f"layers[{index}].color")
        layer["lineweight"] = safe_token(text(layer.get("lineweight", "25")), f"layers[{index}].lineweight")
    type_rules = rules.get("types")
    if not isinstance(type_rules, dict):
        raise ValueError("types 必须是对象")
    for cable_type, config in type_rules.items():
        if cable_type not in TYPES or not isinstance(config, dict):
            raise ValueError(f"types.{cable_type} 无效")
        if not text(config.get("source_dwg")):
            raise ValueError(f"types.{cable_type}.source_dwg 不能为空")
        config["capacity"] = positive_integer(config.get("capacity"), f"types.{cable_type}.capacity")
        for key, default in (("origin_offset", [0, 0, 0]), ("insertion_offset", [0, 0, 0])):
            config[key] = vector(config.get(key, default), f"types.{cable_type}.{key}")
        config["block_step"] = vector(config.get("block_step"), f"types.{cable_type}.block_step")
        config["local_bbox"] = vector(config.get("local_bbox"), f"types.{cable_type}.local_bbox", 4)
        if config["local_bbox"][0] >= config["local_bbox"][2] or config["local_bbox"][1] >= config["local_bbox"][3]:
            raise ValueError(f"types.{cable_type}.local_bbox 无效")
        config["scale"] = finite_number(config.get("scale", 1), f"types.{cable_type}.scale")
        config["rotation"] = finite_number(config.get("rotation", 0), f"types.{cable_type}.rotation")
        dynamic = config.get("dynamic_parameters", {})
        if not isinstance(dynamic, dict):
            raise ValueError(f"types.{cable_type}.dynamic_parameters 必须是对象")
        for key in dynamic:
            safe_token(text(key), f"types.{cable_type}.dynamic_parameters")
        layout = config.get("row_layout")
        if not isinstance(layout, dict):
            raise ValueError(f"types.{cable_type}.row_layout 必须是对象")
        layout["first_row_offset"] = vector(layout.get("first_row_offset"), f"types.{cable_type}.row_layout.first_row_offset")
        layout["row_step"] = vector(layout.get("row_step"), f"types.{cable_type}.row_layout.row_step")
        columns = layout.get("columns")
        if not isinstance(columns, list) or not columns:
            raise ValueError(f"types.{cable_type}.row_layout.columns 必须是非空数组")
        for index, column in enumerate(columns):
            if not isinstance(column, dict) or column.get("field") not in ALLOWED_FIELDS:
                raise ValueError(f"types.{cable_type}.row_layout.columns[{index}].field 无效")
            column["offset"] = vector(column.get("offset"), f"types.{cable_type}.row_layout.columns[{index}].offset")
            column["height"] = finite_number(column.get("height"), f"types.{cable_type}.row_layout.columns[{index}].height")
            column["rotation"] = finite_number(column.get("rotation", 0), f"types.{cable_type}.row_layout.columns[{index}].rotation")
            column["width_factor"] = finite_number(column.get("width_factor", 1), f"types.{cable_type}.row_layout.columns[{index}].width_factor")
            for key in ("color", "layer", "style", "alignment"):
                column[key] = safe_token(text(column.get(key)), f"types.{cable_type}.row_layout.columns[{index}].{key}")
    rules["view_margin"] = finite_number(rules.get("view_margin", 10), "view_margin")
    return rules


def bbox_at(local_bbox: list[float], point: list[float]) -> list[float]:
    return [local_bbox[0] + point[0], local_bbox[1] + point[1], local_bbox[2] + point[0], local_bbox[3] + point[1]]


def overlaps(a: list[float], b: list[float]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def text_line(point: list[float], value: str, column: dict[str, Any]) -> str:
    value = safe_token(value, f"文字字段 {column['field']}")
    return "|".join([
        "text", point_string(point), value, f"{column['height']:.9g}", column["color"] or "white",
        column["layer"] or "0", f"{column['rotation']:.9g}", column["style"],
        f"{column['width_factor']:.9g}", column["alignment"], point_string(point),
    ])


def dynamic_value(value: Any, *, row_count: int, capacity: int, cable_type: str, block_number: int) -> str:
    variables = {"$row_count": row_count, "$capacity": capacity, "$cable_type": cable_type, "$block_number": block_number}
    resolved = variables.get(value, value) if isinstance(value, str) else value
    return safe_token(text(resolved), "dynamic_parameters value")


def compile_plan(
    model: dict[str, Any], rules: dict[str, Any], source_dwg: str, save_as: str,
    origin: list[float], request_id: str,
) -> dict[str, Any]:
    records = validate_model(model)
    rules = validate_rules(rules)
    if Path(source_dwg).resolve() == Path(save_as).resolve():
        raise ValueError("save_as 不能等于 source_dwg")
    present_types = [kind for kind in TYPES if any(record["cable_type"] == kind for record in records)]
    missing_rules = [kind for kind in present_types if kind not in rules["types"]]
    if missing_rules:
        raise ValueError(f"缺少类型布局规则：{missing_rules}")

    operations: list[dict[str, Any]] = [{
        "operation_id": "prepare-working-copy", "phase": "prepare", "action": "manage_files",
        "params": {"operations": f"save|{safe_token(save_as, 'save_as')}"},
        "expected": {"saved_path": save_as, "active_document_path": save_as},
    }]
    if rules["layers"]:
        lines = [f"create|{item['name']}|{item['color']}|{item['lineweight']}" for item in rules["layers"]]
        operations.append({"operation_id": "layers-ensure", "phase": "layers", "action": "manage_layers", "params": {"operations": "\n".join(lines)}, "expected": {"succeeded": len(lines)}})

    blocks: list[dict[str, Any]] = []
    bboxes: list[dict[str, Any]] = []
    for cable_type in present_types:
        config = rules["types"][cable_type]
        selected = sorted((record for record in records if record["cable_type"] == cable_type), key=lambda record: record["number"])
        chunks = [selected[index:index + config["capacity"]] for index in range(0, len(selected), config["capacity"])]
        for chunk_index, chunk in enumerate(chunks):
            insertion = point_add(origin, config["origin_offset"], config["insertion_offset"], point_scale(config["block_step"], chunk_index))
            operation_id = f"{cable_type.lower()}-{chunk_index + 1:03d}-insert"
            operations.append({
                "operation_id": operation_id, "phase": "blocks", "action": "insert_dwg",
                "params": {"filepath": config["source_dwg"], "insertion_point": point_string(insertion), "scale": config["scale"], "rotation": config["rotation"]},
                "expected": {"handle_required": True, "entity_count": 1, "cable_type": cable_type, "block_number": chunk_index + 1},
            })
            bbox = bbox_at(config["local_bbox"], insertion)
            for previous in bboxes:
                if overlaps(bbox, previous["bbox"]):
                    raise ValueError(f"电缆表块布局重叠：{previous['cable_type']}-{previous['block_number']} 与 {cable_type}-{chunk_index + 1}")
            bboxes.append({"cable_type": cable_type, "block_number": chunk_index + 1, "bbox": bbox})
            blocks.append({"operation_id": operation_id, "cable_type": cable_type, "block_number": chunk_index + 1, "rows": chunk, "insertion": insertion, "config": config})

    for block in blocks:
        for property_index, (property_name, raw_value) in enumerate(block["config"]["dynamic_parameters"].items(), start=1):
            property_name = safe_token(text(property_name), "dynamic parameter")
            value = dynamic_value(raw_value, row_count=len(block["rows"]), capacity=block["config"]["capacity"], cable_type=block["cable_type"], block_number=block["block_number"])
            operations.append({
                "operation_id": block["operation_id"].replace("insert", f"property-{property_index:02d}"),
                "phase": "properties", "action": "block_dyn",
                "params": {"handle_ref": block["operation_id"], "operations": f"set|{{{{handle}}}}|{property_name}|{value}"},
                "expected": {"property": property_name, "value": value},
            })

    annotation_lines: list[str] = []
    entity_map: list[dict[str, Any]] = []
    for block in blocks:
        layout = block["config"]["row_layout"]
        for row_index, record in enumerate(block["rows"]):
            row_base = point_add(block["insertion"], layout["first_row_offset"], point_scale(layout["row_step"], row_index))
            for column in layout["columns"]:
                value = text(record.get(column["field"]))
                if not value:
                    continue
                point = point_add(row_base, column["offset"])
                annotation_lines.append(text_line(point, value, column))
                entity_map.append({"row_id": text(record["row_id"]), "field": column["field"], "cable_type": block["cable_type"], "block_number": block["block_number"]})
    if annotation_lines:
        operations.append({
            "operation_id": "cable-annotations", "phase": "annotations", "action": "draw_entities",
            "params": {"entities": "\n".join(annotation_lines)},
            "expected": {"handle_required": True, "entity_count": len(annotation_lines), "entity_map": entity_map},
        })

    extent = [min(item["bbox"][0] for item in bboxes), min(item["bbox"][1] for item in bboxes), max(item["bbox"][2] for item in bboxes), max(item["bbox"][3] for item in bboxes)]
    margin = rules["view_margin"]
    operations.append({
        "operation_id": "view-result", "phase": "view", "action": "execute_command",
        "params": {"command": f"_ZOOM\n_W\n{extent[0] - margin:.9g},{extent[1] - margin:.9g}\n{extent[2] + margin:.9g},{extent[3] + margin:.9g}\n"},
        "expected": {"bbox": extent},
    })
    operations.append({
        "operation_id": "save-result", "phase": "save", "action": "manage_files",
        "params": {"operations": f"save|{safe_token(save_as, 'save_as')}"},
        "expected": {"saved_path": save_as},
    })
    counts = {kind: sum(1 for record in records if record["cable_type"] == kind) for kind in TYPES}
    block_counts = {kind: sum(1 for block in blocks if block["cable_type"] == kind) for kind in TYPES}
    return {
        "schema_version": PLAN_SCHEMA,
        "request_id": request_id,
        "caller_skill": "cad-cable-schedule",
        "target": {"source_path": source_dwg, "save_as": save_as, "overwrite_source": False},
        "knowledge": {"mode": "queried", "sources": [text(item) for item in rules["knowledge_sources"]]},
        "operations": operations,
        "acceptance": {
            "checks": [
                {"name": "record_counts_by_type", "expected": counts},
                {"name": "block_counts_by_type", "expected": block_counts},
                {"name": "annotation_entities", "expected": len(annotation_lines)},
                {"name": "type_isolation", "expected": True},
                {"name": "non_overlapping_blocks", "expected": True},
            ],
            "business_summary": "K/AK/TK 类型、编号占位、起终点、芯数及线号须与获批 cable-workbook 一致",
        },
        "business_validation": {"record_row_ids": [text(record["row_id"]) for record in records], "estimated_bboxes": bboxes},
    }


def parse_origin(value: str) -> list[float]:
    return vector([part.strip() for part in value.split(",")], "origin")


def write_json_new(data: dict[str, Any], path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"拒绝覆盖现有文件：{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


#: draw_entities 批次：侧车正文与 expected 原序一一对应。
DISPATCH_ENTITY_BATCH_IDS = ("cable-annotations",)


def _cad_drawing_scripts_dir() -> Path:
    """定位兄弟技能 cad-drawing 的 scripts 目录（可移植，不内嵌机器绝对路径）。"""
    import os

    candidates: list[Path] = []
    override = os.environ.get("CAD_DRAWING_SCRIPTS")
    if override:
        candidates.append(Path(override).expanduser())
    candidates.append(Path(__file__).resolve().parents[2] / "cad-drawing" / "scripts")
    for env_name in ("CODEX_HOME", "DSH_HOME"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value).expanduser() / "skills" / "cad-drawing" / "scripts")
    candidates.append(Path.home() / ".dsh" / "skills" / "cad-drawing" / "scripts")
    for candidate in candidates:
        if (candidate / "文件分发.py").is_file():
            return candidate.resolve()
    raise ValueError(
        "找不到 cad-drawing/scripts/文件分发.py：请把 cad-drawing 作为同级技能部署，"
        "或设置环境变量 CAD_DRAWING_SCRIPTS"
    )


def write_plan_dispatch(plan: dict[str, Any], plan_path: Path, output_dir: Path) -> Path:
    """为已落盘计划生成文件分发清单（侧车 + cad_dispatch.json）。

    只新增文件、不改计划：大实体批次改用 ``@file:<绝对路径>`` 交给 MCP 自行读取，
    含 ``{{handle}}`` 的绑定操作保持内联。
    """
    import importlib.util
    import sys

    directory = _cad_drawing_scripts_dir()
    module_path = directory / "文件分发.py"
    spec = importlib.util.spec_from_file_location("cad_file_dispatch", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - 环境异常
        raise ValueError(f"无法加载文件分发器: {module_path}")
    module = importlib.util.module_from_spec(spec)
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    spec.loader.exec_module(module)
    _, manifest_path, _ = module.build_dispatch_manifest(
        plan,
        Path(output_dir),
        Path(plan_path),
        entity_batch_ids=DISPATCH_ENTITY_BATCH_IDS,
        bind_entity_ids=False,
        # 计划内按 handle_ref 绑定的动态参数/图层操作保留 {{handle}}：保持内联，
        # 并在 manifest.binding_required 中作为执行前阻断条件。
        allow_unresolved_placeholders=True,
        extra_rules=(
            "插块必须分为“插入并回读真实 bbox”与“绘制文字”两个门；"
            "local_bbox/block_step 只用于预检，后续块位置按前一块回读 xmax/ymax 加安全间隙计算",
            "含 {{handle}} 的 set_layer/set_color_bylayer/动态参数操作保持内联，必须绑定真实 handle 后执行",
        ),
    )
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 cable-workbook 与布局规则编译为 cad-draw-plan")
    parser.add_argument("--cable-model", required=True)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--source-dwg", required=True)
    parser.add_argument("--save-as", required=True)
    parser.add_argument("--origin", default="0,0,0")
    parser.add_argument("--request-id", default="")
    parser.add_argument("--output", required=True)
    parser.add_argument("--no-dispatch", action="store_true",
                        help="只输出计划，不生成文件分发清单")
    parser.add_argument("--dispatch-output", default=None,
                        help="清单/侧车输出目录；缺省为 --output 所在目录")
    args = parser.parse_args(argv)
    dispatch_path = None
    try:
        request_id = args.request_id.strip() or f"cable-render-{uuid.uuid4().hex[:12]}"
        plan = compile_plan(load_json(Path(args.cable_model)), load_json(Path(args.rules)), args.source_dwg, args.save_as, parse_origin(args.origin), request_id)
        output_path = Path(args.output)
        write_json_new(plan, output_path)
        if not args.no_dispatch:
            dispatch_dir = (Path(args.dispatch_output).expanduser().resolve()
                            if args.dispatch_output else output_path.expanduser().resolve().parent)
            dispatch_path = write_plan_dispatch(plan, output_path.expanduser().resolve(), dispatch_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    payload = {"valid": True, "schema_version": PLAN_SCHEMA, "request_id": request_id,
               "operations": len(plan["operations"]), "output": str(Path(args.output).resolve())}
    if dispatch_path is not None:
        payload["dispatch"] = str(dispatch_path)
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
