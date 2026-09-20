from __future__ import annotations

import importlib.util
from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parents[2]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


TERMINAL_BOOK = load(SKILLS_ROOT / "cad-terminal-diagram" / "scripts" / "端子工作簿.py", "terminal_book_integration")
CABLE_BUILDER = load(SKILLS_ROOT / "cad-cable-schedule" / "scripts" / "从端子模型生成电缆模型.py", "cable_builder_integration")
CABLE_BOOK = load(SKILLS_ROOT / "cad-cable-schedule" / "scripts" / "电缆工作簿.py", "cable_book_integration")


def test_terminal_xlsx_can_feed_cable_xlsx_without_ad_hoc_conversion(tmp_path: Path):
    terminal_model = {
        "schema_version": "terminal-workbook",
        "metadata": {"knowledge_sources": ["wiki/terminal.md"]},
        "rows": [
            {
                "row_id": "terminal/1",
                "row_kind": "data",
                "cabinet_id": "CAB-A",
                "strip_id": "XT1",
                "terminal_no": "1",
                "local_device": "DEV-A",
                "wire_no": "W1",
                "cable_id": "K1",
                "target_cabinet": "CAB-B",
                "target_device": "DEV-B",
                "shield_state": "",
                "shorted_to": "",
                "is_spare": False,
                "status": "confirmed",
                "issue": "",
            }
        ],
        "issues": [],
    }
    terminal_xlsx = tmp_path / "terminal.xlsx"
    TERMINAL_BOOK.export_workbook(terminal_model, terminal_xlsx)
    imported_terminal = TERMINAL_BOOK.import_workbook(terminal_xlsx)
    rules = {
        "schema_version": "cable-derivation-rules",
        "cable_id_pattern": r"(?P<type>K)(?P<number>\d+)",
        "type_aliases": {"K": "K"},
        "start_priority": [r"CAB-A"],
        "max_number_by_type": {"K": 1},
        "default_spec_by_type": {},
        "spare_cores_by_type": {},
        "include_start_device_for_types": [],
    }
    cable_model = CABLE_BUILDER.build_model([(terminal_xlsx, imported_terminal)], rules, tmp_path / "rules.json")
    cable_xlsx = tmp_path / "cable.xlsx"
    CABLE_BOOK.export_workbook(cable_model, cable_xlsx)
    imported_cable = CABLE_BOOK.import_workbook(cable_xlsx)
    assert imported_cable["records"][0]["cable_id"] == "K1"
    assert imported_cable["records"][0]["source_terminal_row_ids"] == ["terminal/1"]
    assert imported_cable["records"][0]["status"] == "confirmed"
