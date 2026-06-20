from __future__ import annotations

import json
from pathlib import Path

from helpers import make_docx, make_pptx, make_xlsx

from vysi.document_source.services.ingest import ingest


def _load(package: Path, name: str) -> dict:
    return json.loads((package / name).read_text(encoding="utf-8"))


def test_docx_native_structure(tmp_path: Path) -> None:
    source = tmp_path / "sample.docx"
    make_docx(source)
    package = ingest(source, tmp_path / "out")
    native = _load(package, "contracts/native_document.json")
    kinds = {node["kind"] for node in native["nodes"]}
    assert native["profile"] == "wordprocessing.ooxml.v1"
    assert {"paragraph", "run", "table", "table_cell"} <= kinds


def test_xlsx_formula_is_preserved_not_executed(tmp_path: Path) -> None:
    source = tmp_path / "sample.xlsx"
    make_xlsx(source)
    package = ingest(source, tmp_path / "out")
    native = _load(package, "contracts/native_document.json")
    assert native["profile_data"]["formula_count"] == 1
    assert native["profile_data"]["calculation_executed"] is False
    ir = _load(package, "contracts/common_document_ir.json")
    formula_units = [unit for unit in ir["units"] if unit["properties"].get("formula_source")]
    assert len(formula_units) == 1
    assert formula_units[0]["protected"] is True


def test_pptx_slide_and_shape(tmp_path: Path) -> None:
    source = tmp_path / "sample.pptx"
    make_pptx(source)
    package = ingest(source, tmp_path / "out")
    native = _load(package, "contracts/native_document.json")
    assert native["profile_data"]["slide_count"] == 1
    assert any(node["kind"] == "shape" and node["text"] == "Titre" for node in native["nodes"])
