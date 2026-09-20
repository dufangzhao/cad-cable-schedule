from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILDER = load_script("从端子模型生成电缆模型.py")
WORKBOOK = load_script("电缆工作簿.py")


def terminal_row(row_id: str, cable: str, cabinet: str, remote: str, local_device: str, target_device: str):
    return {
        "row_id": row_id,
        "row_kind": "data",
        "cabinet_id": cabinet,
        "strip_id": "XT1",
        "terminal_no": row_id.rsplit("/", 1)[-1],
        "local_device": local_device,
        "wire_no": f"W-{row_id}",
        "cable_id": cable,
        "target_cabinet": remote,
        "target_device": target_device,
        "shield_state": "",
        "shorted_to": "",
        "is_spare": False,
        "status": "confirmed",
        "issue": "",
    }


def rules():
    return {
        "schema_version": BUILDER.RULE_SCHEMA,
        "cable_id_pattern": r"(?:.*/)?(?P<type>AK|TK|K)(?P<number>\d+)",
        "type_aliases": {"K": "K", "AK": "AK", "TK": "TK"},
        "start_priority": [r"CAB-A", r"CAB-KB"],
        "max_number_by_type": {"K": 3},
        "default_spec_by_type": {"K": "SPEC-K", "TK": "SPEC-TK"},
        "spare_cores_by_type": {"K": 1, "TK": 2},
        "include_start_device_for_types": ["TK"],
        "knowledge_sources": ["wiki/cable-rules.md"],
    }


def test_builder_generates_gap_rows_and_counts_source_connections(tmp_path: Path):
    source_path = tmp_path / "terminal.json"
    rules_path = tmp_path / "rules.json"
    terminal = {
        "schema_version": BUILDER.INPUT_SCHEMA,
        "rows": [
            terminal_row("t/1", "K1", "CAB-A", "CAB-B", "A1", "B1"),
            terminal_row("t/2", "K1", "CAB-A", "CAB-B", "A2", "B2"),
            terminal_row("t/3", "K3", "CAB-A", "CAB-C", "A3", "C3"),
        ],
    }
    model = BUILDER.build_model([(source_path, terminal)], rules(), rules_path)
    WORKBOOK.validate_model(model)
    k_rows = [row for row in model["records"] if row["cable_type"] == "K"]
    assert [row["number"] for row in k_rows] == [1, 2, 3]
    assert k_rows[1]["row_kind"] == "blank"
    assert k_rows[0]["required_cores"] == 2
    assert k_rows[0]["start"] == "CAB-A"
    assert k_rows[0]["end"] == "CAB-B"


def test_builder_adds_start_device_for_configured_type(tmp_path: Path):
    source_path = tmp_path / "terminal.json"
    rules_path = tmp_path / "rules.json"
    terminal = {
        "schema_version": BUILDER.INPUT_SCHEMA,
        "rows": [terminal_row("t/1", "TK1", "CAB-KB", "CAB-D", "PLC-1", "REMOTE-1")],
    }
    model = BUILDER.build_model([(source_path, terminal)], rules(), rules_path)
    record = next(row for row in model["records"] if row["cable_type"] == "TK")
    assert record["start"] == "CAB-KB/PLC-1"
    assert record["status"] == "confirmed"


def test_builder_fails_closed_when_direction_rule_does_not_match(tmp_path: Path):
    source_path = tmp_path / "terminal.json"
    rules_path = tmp_path / "rules.json"
    terminal = {
        "schema_version": BUILDER.INPUT_SCHEMA,
        "rows": [terminal_row("t/1", "AK1", "CAB-X", "CAB-Y", "X1", "Y1")],
    }
    model = BUILDER.build_model([(source_path, terminal)], rules(), rules_path)
    record = next(row for row in model["records"] if row["cable_type"] == "AK")
    assert record["status"] == "candidate"
    assert record["start"] == record["end"] == ""
    assert model["issues"][0]["severity"] == "warning"
