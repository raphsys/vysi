from __future__ import annotations

import zipfile
from pathlib import Path
from typing import cast

from vysi.document_source.adapters.native.ooxml_common import (
    attr_ns,
    local,
    read_xml,
    relationship_map,
    unit_id,
)
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import NativeDocument, NativeNode
from vysi.document_source.domain.enums import DocumentFamily

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = read_xml(archive, "xl/sharedStrings.xml")
    values: list[str] = []
    for item in root:
        if local(item.tag) != "si":
            continue
        values.append("".join(node.text or "" for node in item.iter() if local(node.tag) == "t"))
    return values


def read_xlsx(path: Path) -> NativeDocument:
    root_id = unit_id(path, "workbook")
    nodes: list[NativeNode] = [NativeNode(root_id, "workbook", None, 0, "xlsx:/")]
    profile: dict[str, object] = {
        "sheet_count": 0,
        "cell_count": 0,
        "formula_count": 0,
        "merged_range_count": 0,
        "calculation_executed": False,
    }
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        workbook = read_xml(archive, "xl/workbook.xml")
        rels = relationship_map(archive, "xl/workbook.xml")
        shared = _shared_strings(archive)
        sheets = [node for node in workbook.iter() if local(node.tag) == "sheet"]
        for sheet_index, sheet in enumerate(sheets):
            name = sheet.attrib.get("name", f"Sheet{sheet_index + 1}")
            rid = attr_ns(sheet, R_NS, "id")
            target = rels.get(rid or "")
            sid = unit_id(path, "sheet", sheet_index, name)
            nodes.append(
                NativeNode(
                    sid,
                    "worksheet",
                    root_id,
                    sheet_index,
                    f"xlsx:/sheet[{name}]",
                    properties={"name": name, "relationship_id": rid, "part": target},
                )
            )
            profile["sheet_count"] = cast(int, profile["sheet_count"]) + 1
            if not target or target not in names:
                continue
            sheet_root = read_xml(archive, target)
            for cell_index, cell in enumerate(
                node for node in sheet_root.iter() if local(node.tag) == "c"
            ):
                address = cell.attrib.get("r", f"cell-{cell_index}")
                cell_type = cell.attrib.get("t")
                style_index = cell.attrib.get("s")
                formula = next((node.text or "" for node in cell if local(node.tag) == "f"), None)
                raw_value = next((node.text or "" for node in cell if local(node.tag) == "v"), None)
                inline = next((node for node in cell if local(node.tag) == "is"), None)
                value: str | None = raw_value
                if cell_type == "s" and raw_value is not None:
                    try:
                        value = shared[int(raw_value)]
                    except (ValueError, IndexError):
                        value = raw_value
                elif inline is not None:
                    value = "".join(
                        node.text or "" for node in inline.iter() if local(node.tag) == "t"
                    )
                cid = unit_id(path, "sheet", sheet_index, "cell", address)
                nodes.append(
                    NativeNode(
                        cid,
                        "cell",
                        sid,
                        cell_index,
                        f"xlsx:/sheet[{name}]/cell[{address}]",
                        text=value,
                        style_refs=(style_index,) if style_index else (),
                        properties={
                            "address": address,
                            "cell_type": cell_type,
                            "formula": formula,
                            "cached_value": raw_value,
                        },
                    )
                )
                profile["cell_count"] = cast(int, profile["cell_count"]) + 1
                if formula is not None:
                    profile["formula_count"] = cast(int, profile["formula_count"]) + 1
            merged = [node for node in sheet_root.iter() if local(node.tag) == "mergeCell"]
            profile["merged_range_count"] = cast(int, profile["merged_range_count"]) + len(merged)
        profile["styles_present"] = "xl/styles.xml" in names
        profile["shared_strings_count"] = len(shared)
        profile["external_links"] = len(
            [
                name
                for name in names
                if name.startswith("xl/externalLinks/") and name.endswith(".xml")
            ]
        )
    return NativeDocument(
        header=header("document_source.native_document"),
        profile="spreadsheet.ooxml.v1",
        family=DocumentFamily.SPREADSHEET,
        root_ids=(root_id,),
        nodes=tuple(nodes),
        profile_data=profile,
        capabilities=("has_grid_model", "has_formulas", "has_styles", "has_relationships"),
    )
