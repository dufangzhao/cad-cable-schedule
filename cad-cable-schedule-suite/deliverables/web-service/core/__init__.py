"""电缆汇总内核：表识别、行聚类、型号/芯数/截面三项汇总、Excel 生成。"""
from .aggregate import (  # noqa: F401
    EXCEL_HEADERS, KEY_FIELDS, SCHEMA_VERSION,
    build_summary, entities_from_artifact, entities_from_dxf, entities_from_tsv,
    export_summary, extract_tables, load_artifact, norm_text, validate_summary, write_tsv,
)

__all__ = [
    "SCHEMA_VERSION", "KEY_FIELDS", "EXCEL_HEADERS",
    "build_summary", "export_summary", "extract_tables", "validate_summary",
    "entities_from_artifact", "entities_from_dxf", "entities_from_tsv", "write_tsv",
    "load_artifact", "norm_text",
]
