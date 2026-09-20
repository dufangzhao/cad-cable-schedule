from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import regex


RULE_SCHEMA = "cable-derivation-rules"
INPUT_SCHEMA = "terminal-workbook"
OUTPUT_SCHEMA = "cable-workbook"
TYPES = ("K", "AK", "TK")
MATCH_TIMEOUT = 0.05


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def load_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"顶层必须是对象：{path}")
    return data


def nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} 必须是非负整数")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} 必须是非负整数") from exc
    if result < 0:
        raise ValueError(f"{field} 必须是非负整数")
    return result


def compile_pattern(value: Any, field: str) -> regex.Pattern[str]:
    pattern = text(value)
    if not pattern or len(pattern) > 512:
        raise ValueError(f"{field} 必须是1至512字符的正则")
    try:
        compiled = regex.compile(pattern, regex.IGNORECASE)
    except regex.error as exc:
        raise ValueError(f"{field} 正则无效：{exc}") from exc
    return compiled


def validate_rules(rules: dict[str, Any]) -> dict[str, Any]:
    if rules.get("schema_version") != RULE_SCHEMA:
        raise ValueError(f"rules.schema_version 必须是 {RULE_SCHEMA}")
    cable_pattern = compile_pattern(rules.get("cable_id_pattern"), "cable_id_pattern")
    if not {"type", "number"}.issubset(cable_pattern.groupindex):
        raise ValueError("cable_id_pattern 必须包含 type 和 number 命名组")
    aliases = rules.get("type_aliases")
    if not isinstance(aliases, dict) or not aliases:
        raise ValueError("type_aliases 必须是非空对象")
    normalized_aliases: dict[str, str] = {}
    for raw, canonical in aliases.items():
        if canonical not in TYPES:
            raise ValueError(f"type_aliases 目标必须是 K/AK/TK：{canonical}")
        normalized_aliases[text(raw).casefold()] = canonical
    priorities = rules.get("start_priority")
    if not isinstance(priorities, list):
        raise ValueError("start_priority 必须是数组")
    priority_patterns = [compile_pattern(value, f"start_priority[{index}]") for index, value in enumerate(priorities)]
    max_numbers = rules.get("max_number_by_type", {})
    specs = rules.get("default_spec_by_type", {})
    spares = rules.get("spare_cores_by_type", {})
    include_devices = rules.get("include_start_device_for_types", [])
    for field, value in (("max_number_by_type", max_numbers), ("default_spec_by_type", specs), ("spare_cores_by_type", spares)):
        if not isinstance(value, dict):
            raise ValueError(f"{field} 必须是对象")
        if any(key not in TYPES for key in value):
            raise ValueError(f"{field} 只允许 K/AK/TK")
    if not isinstance(include_devices, list) or any(item not in TYPES for item in include_devices):
        raise ValueError("include_start_device_for_types 只允许 K/AK/TK 数组")
    return {
        "cable_pattern": cable_pattern,
        "aliases": normalized_aliases,
        "priorities": priority_patterns,
        "max_numbers": {key: nonnegative_int(value, f"max_number_by_type.{key}") for key, value in max_numbers.items()},
        "specs": {key: text(value) for key, value in specs.items()},
        "spares": {key: nonnegative_int(value, f"spare_cores_by_type.{key}") for key, value in spares.items()},
        "include_devices": set(include_devices),
    }


def parse_cable_id(cable_id: str, config: dict[str, Any]) -> tuple[str, int] | None:
    try:
        match = config["cable_pattern"].fullmatch(cable_id, timeout=MATCH_TIMEOUT)
    except TimeoutError as exc:
        raise ValueError(f"电缆号正则匹配超时：{cable_id}") from exc
    if not match:
        return None
    captured_type = text(match.group("type")).casefold()
    cable_type = config["aliases"].get(captured_type)
    if cable_type is None:
        return None
    number = nonnegative_int(match.group("number"), "电缆数字编号")
    if number < 1:
        raise ValueError(f"电缆数字编号必须从1开始：{cable_id}")
    return cable_type, number



def selected_cores(required: int | None) -> int | None:
    if required is None:
        return None
    for option in (4, 7, 10):
        if option >= required:
            return option
    return None

def choose_direction(rows: list[dict[str, Any]], config: dict[str, Any]) -> tuple[str, str, str, list[str]]:
    edges: list[tuple[str, str, dict[str, Any]]] = []
    adjacency: dict[str, set[str]] = defaultdict(set)
    issues: list[str] = []
    for row in rows:
        left = text(row.get("cabinet_id"))
        right = text(row.get("target_cabinet"))
        if not left or not right or left == right:
            issues.append(f"端子行 {text(row.get('row_id'))} 缺少有效跨柜方向")
            continue
        edges.append((left, right, row))
        adjacency[left].add(right)
        adjacency[right].add(left)
    if not edges:
        return "", "", "unknown", issues or ["没有可用于方向判断的跨柜边"]
    if any(len(neighbors) > 2 for neighbors in adjacency.values()):
        return "", "", "unknown", issues + ["连接图存在分支，不能按串联链确定起终点"]
    endpoints = sorted(node for node, neighbors in adjacency.items() if len(neighbors) == 1)
    if len(adjacency) == 2 and len(endpoints) == 2:
        pass
    elif len(endpoints) != 2:
        return "", "", "unknown", issues + ["串联链未形成唯一两个端点"]

    start = ""
    confidence = "unknown"
    for priority in config["priorities"]:
        try:
            matches = [node for node in endpoints if priority.fullmatch(node, timeout=MATCH_TIMEOUT)]
        except TimeoutError as exc:
            raise ValueError("起点优先级正则匹配超时") from exc
        if len(matches) == 1:
            start = matches[0]
            confidence = "high"
            break
        if len(matches) > 1:
            issues.append("同一优先级同时命中两个链路端点")
            break
    if not start:
        return "", "", "unknown", issues + ["没有起点规则唯一命中串联端点"]
    end = endpoints[1] if endpoints[0] == start else endpoints[0]
    return start, end, confidence, issues


def device_for_start(rows: list[dict[str, Any]], start: str) -> tuple[str, list[str]]:
    devices: list[str] = []
    for row in rows:
        if text(row.get("cabinet_id")) == start:
            device = text(row.get("local_device"))
        elif text(row.get("target_cabinet")) == start:
            device = text(row.get("target_device"))
        else:
            continue
        if device:
            devices.append(device)
    unique = list(dict.fromkeys(devices))
    if len(unique) == 1:
        return unique[0], []
    if not unique:
        return "", ["起点缺少具体设备"]
    return "", ["起点对应多个具体设备"]


def build_model(terminals: list[tuple[Path, dict[str, Any]]], rules: dict[str, Any], rules_path: Path) -> dict[str, Any]:
    config = validate_rules(rules)
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    raw_ids: dict[tuple[str, int], set[str]] = defaultdict(set)
    global_issues: list[dict[str, str]] = []
    issue_counter = 0

    def add_issue(row_id: str, field: str, severity: str, message: str) -> None:
        nonlocal issue_counter
        issue_counter += 1
        global_issues.append({"issue_id": f"ISSUE-{issue_counter:04d}", "row_id": row_id, "field": field, "severity": severity, "message": message})

    for path, model in terminals:
        if model.get("schema_version") != INPUT_SCHEMA or not isinstance(model.get("rows"), list):
            raise ValueError(f"输入不是 {INPUT_SCHEMA}：{path}")
        for row in model["rows"]:
            if not isinstance(row, dict) or row.get("row_kind") != "data":
                continue
            cable_id = text(row.get("cable_id"))
            if not cable_id:
                continue
            parsed = parse_cable_id(cable_id, config)
            if parsed is None:
                add_issue(text(row.get("row_id")), "电缆号", "blocking", f"电缆号不符合已加载分类规则：{cable_id}")
                continue
            groups[parsed].append(row)
            raw_ids[parsed].add(cable_id)

    records: list[dict[str, Any]] = []
    for (cable_type, number), rows in sorted(groups.items(), key=lambda item: (TYPES.index(item[0][0]), item[0][1])):
        row_id = f"{cable_type}/{number}"
        direction_start, direction_end, confidence, direction_issues = choose_direction(rows, config)
        status_values = {text(row.get("status")) for row in rows}
        status = "confirmed"
        record_issues: list[str] = []
        if "conflict" in status_values or len(raw_ids[(cable_type, number)]) > 1:
            status = "conflict"
        elif status_values - {"confirmed"} or not direction_start:
            status = "candidate"
        if len(raw_ids[(cable_type, number)]) > 1:
            record_issues.append("同一类型和数字编号对应多个电缆号")
        record_issues.extend(direction_issues)
        if cable_type in config["include_devices"] and direction_start:
            device, device_issues = device_for_start(rows, direction_start)
            record_issues.extend(device_issues)
            if device:
                direction_start = f"{direction_start}/{device}"
            elif device_issues:
                status = "candidate" if status != "conflict" else status
                confidence = "unknown"
        wire_numbers = list(dict.fromkeys(text(row.get("wire_no")) for row in rows if text(row.get("wire_no"))))
        cable_id = sorted(raw_ids[(cable_type, number)])[0]
        record = {
            "row_id": row_id,
            "row_kind": "data",
            "cable_type": cable_type,
            "number": number,
            "cable_id": cable_id,
            "start": direction_start,
            "end": direction_end,
            "spec": config["specs"].get(cable_type, ""),
            "required_cores": len(rows),
            "selected_cores": selected_cores(len(rows)),
            "spare_cores": (selected_cores(len(rows)) - len(rows) if selected_cores(len(rows)) is not None else None),
            "core_section": "",
            "length": "",
            "conduit_diameter": "",
            "conduit_length": "",
            "remark": "",
            "wire_numbers": wire_numbers,
            "direction_confidence": confidence,
            "status": status,
            "issue": "；".join(dict.fromkeys(record_issues)),
            "source_terminal_row_ids": [text(row.get("row_id")) for row in rows],
        }
        records.append(record)
        if status != "confirmed" or record["issue"]:
            add_issue(row_id, "电缆推导", "blocking" if status == "conflict" else "warning", record["issue"] or f"状态为 {status}")

    for cable_type in TYPES:
        actual = [record["number"] for record in records if record["cable_type"] == cable_type]
        upper = max(actual, default=0)
        upper = max(upper, config["max_numbers"].get(cable_type, 0))
        present = set(actual)
        for number in range(1, upper + 1):
            if number in present:
                continue
            records.append(
                {
                    "row_id": f"{cable_type}/{number}",
                    "row_kind": "blank",
                    "cable_type": cable_type,
                    "number": number,
                    "cable_id": "",
                    "start": "",
                    "end": "",
                    "spec": "",
                    "required_cores": None,
                    "selected_cores": None,
                    "spare_cores": None,
                    "core_section": "",
                    "length": "",
                    "conduit_diameter": "",
                    "conduit_length": "",
                    "remark": "",
                    "wire_numbers": [],
                    "direction_confidence": "unknown",
                    "status": "confirmed",
                    "issue": "",
                    "source_terminal_row_ids": [],
                }
            )
    records.sort(key=lambda record: (TYPES.index(record["cable_type"]), record["number"]))
    return {
        "schema_version": OUTPUT_SCHEMA,
        "metadata": {
            "source_terminal_models": [str(path.resolve()) for path, _ in terminals],
            "rules_path": str(rules_path.resolve()),
            "knowledge_sources": rules.get("knowledge_sources", []),
        },
        "records": records,
        "issues": global_issues,
    }


def write_new(data: dict[str, Any], output: Path) -> None:
    if output.exists():
        raise FileExistsError(f"拒绝覆盖现有文件：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="从 terminal-workbook JSON 生成 cable-workbook JSON")
    parser.add_argument("--terminal-model", action="append", required=True)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        terminal_models = [(Path(value), load_object(Path(value))) for value in args.terminal_model]
        rules_path = Path(args.rules)
        model = build_model(terminal_models, load_object(rules_path), rules_path)
        write_new(model, Path(args.output))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    counts = Counter(record["status"] for record in model["records"] if record["row_kind"] == "data")
    print(json.dumps({"success": True, "records": len(model["records"]), "issues": len(model["issues"]), "status_counts": dict(counts), "output": str(Path(args.output).resolve())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
