from __future__ import annotations

import json
import zipfile
from pathlib import Path

from helpers import CONTENT_TYPES

from vysi.document_source.services.ingest import ingest


def test_macro_is_inert_and_reported(tmp_path: Path) -> None:
    source = tmp_path / "macro.docm"
    types = CONTENT_TYPES.format(
        items="<Override PartName='/word/document.xml' ContentType='application/vnd.ms-word.document.macroEnabled.main+xml'/><Override PartName='/word/vbaProject.bin' ContentType='application/vnd.ms-office.vbaProject'/>"
    )
    doc = "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:body/></w:document>"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("[Content_Types].xml", types)
        archive.writestr("word/document.xml", doc)
        archive.writestr("word/vbaProject.bin", b"not executed")
    package = ingest(source, tmp_path / "out")
    security = json.loads((package / "contracts/security_report.json").read_text())
    assert security["active_content_executed"] is False
    assert any(item["code"] == "container.macro" for item in security["findings"])
    envelope = json.loads((package / "document_envelope.json").read_text())
    assert envelope["final_status"] == "review"


def test_every_ir_unit_maps_to_native(tmp_path: Path) -> None:
    source = tmp_path / "x.txt"
    source.write_text("a\nb", encoding="utf-8")
    package = ingest(source, tmp_path / "out")
    ir = json.loads((package / "contracts/common_document_ir.json").read_text())
    mappings = json.loads((package / "contracts/representation_mapping_catalog.json").read_text())
    mapped = {item["target_id"] for item in mappings["mappings"]}
    assert all(unit["unit_id"] in mapped for unit in ir["units"])
