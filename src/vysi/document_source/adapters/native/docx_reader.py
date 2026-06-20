from __future__ import annotations

import zipfile
from pathlib import Path
from typing import cast
from xml.etree import ElementTree as ET

from vysi.document_source.adapters.native.ooxml_common import (
    attr_local,
    local,
    read_xml,
    unit_id,
)
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import NativeDocument, NativeNode
from vysi.document_source.domain.enums import DocumentFamily


def _text(element: ET.Element) -> str:
    return "".join(
        node.text or "" for node in element.iter() if local(node.tag) in {"t", "tab", "br"}
    )


def read_docx(path: Path) -> NativeDocument:
    nodes: list[NativeNode] = []
    root_id = unit_id(path, "document")
    nodes.append(NativeNode(root_id, "word_document", None, 0, "word:/"))
    profile: dict[str, object] = {
        "paragraph_count": 0,
        "run_count": 0,
        "table_count": 0,
        "tracked_changes_present": False,
        "comments_present": False,
        "footnotes_present": False,
        "endnotes_present": False,
    }
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        doc = read_xml(archive, "word/document.xml")
        body = next((item for item in doc.iter() if local(item.tag) == "body"), None)
        if body is not None:
            ordinal = 0
            for child in body:
                kind = local(child.tag)
                if kind == "p":
                    pid = unit_id(path, "paragraph", ordinal)
                    p_style = None
                    for node in child.iter():
                        if local(node.tag) == "pStyle":
                            p_style = attr_local(node, "val")
                            break
                    nodes.append(
                        NativeNode(
                            pid,
                            "paragraph",
                            root_id,
                            ordinal,
                            f"word:/body/paragraph[{ordinal + 1}]",
                            text=_text(child),
                            style_refs=(p_style,) if p_style else (),
                        )
                    )
                    profile["paragraph_count"] = cast(int, profile["paragraph_count"]) + 1
                    run_ordinal = 0
                    for run in child:
                        if local(run.tag) != "r":
                            if local(run.tag) in {"ins", "del", "moveFrom", "moveTo"}:
                                profile["tracked_changes_present"] = True
                            continue
                        rid = unit_id(path, "paragraph", ordinal, "run", run_ordinal)
                        r_style = None
                        for node in run.iter():
                            if local(node.tag) == "rStyle":
                                r_style = attr_local(node, "val")
                                break
                        nodes.append(
                            NativeNode(
                                rid,
                                "run",
                                pid,
                                run_ordinal,
                                f"word:/body/paragraph[{ordinal + 1}]/run[{run_ordinal + 1}]",
                                text=_text(run),
                                style_refs=(r_style,) if r_style else (),
                            )
                        )
                        run_ordinal += 1
                        profile["run_count"] = cast(int, profile["run_count"]) + 1
                    ordinal += 1
                elif kind == "tbl":
                    table_index = cast(int, profile["table_count"])
                    tid = unit_id(path, "table", table_index)
                    nodes.append(
                        NativeNode(
                            tid,
                            "table",
                            root_id,
                            ordinal,
                            f"word:/body/table[{table_index + 1}]",
                        )
                    )
                    for row_index, row in enumerate([n for n in child if local(n.tag) == "tr"]):
                        row_id = unit_id(path, "table", table_index, "row", row_index)
                        nodes.append(
                            NativeNode(
                                row_id,
                                "table_row",
                                tid,
                                row_index,
                                f"word:/body/table[{table_index + 1}]/row[{row_index + 1}]",
                            )
                        )
                        cells = [n for n in row if local(n.tag) == "tc"]
                        for cell_index, cell in enumerate(cells):
                            cell_id = unit_id(
                                path, "table", table_index, "row", row_index, "cell", cell_index
                            )
                            nodes.append(
                                NativeNode(
                                    cell_id,
                                    "table_cell",
                                    row_id,
                                    cell_index,
                                    f"word:/body/table[{table_index + 1}]/row[{row_index + 1}]/cell[{cell_index + 1}]",
                                    text=_text(cell),
                                )
                            )
                    profile["table_count"] = table_index + 1
                    ordinal += 1
        profile["comments_present"] = "word/comments.xml" in names
        profile["footnotes_present"] = "word/footnotes.xml" in names
        profile["endnotes_present"] = "word/endnotes.xml" in names
        profile["headers"] = len(
            [name for name in names if name.startswith("word/header") and name.endswith(".xml")]
        )
        profile["footers"] = len(
            [name for name in names if name.startswith("word/footer") and name.endswith(".xml")]
        )
        profile["styles_present"] = "word/styles.xml" in names
        profile["numbering_present"] = "word/numbering.xml" in names
    return NativeDocument(
        header=header("document_source.native_document"),
        profile="wordprocessing.ooxml.v1",
        family=DocumentFamily.WORDPROCESSING,
        root_ids=(root_id,),
        nodes=tuple(nodes),
        profile_data=profile,
        capabilities=("has_flow_layout", "has_styles", "has_relationships"),
    )
