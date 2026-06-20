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


def read_pptx(path: Path) -> NativeDocument:
    root_id = unit_id(path, "presentation")
    nodes: list[NativeNode] = [NativeNode(root_id, "presentation", None, 0, "pptx:/")]
    profile: dict[str, object] = {
        "slide_count": 0,
        "shape_count": 0,
        "paragraph_count": 0,
        "timing_present": False,
        "transition_count": 0,
    }
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        presentation = read_xml(archive, "ppt/presentation.xml")
        rels = relationship_map(archive, "ppt/presentation.xml")
        slide_ids = [node for node in presentation.iter() if local(node.tag) == "sldId"]
        for slide_index, slide_ref in enumerate(slide_ids):
            rid = attr_ns(slide_ref, R_NS, "id")
            target = rels.get(rid or "")
            sid = unit_id(path, "slide", slide_index)
            nodes.append(
                NativeNode(
                    sid,
                    "slide",
                    root_id,
                    slide_index,
                    f"pptx:/slide[{slide_index + 1}]",
                    properties={"relationship_id": rid, "part": target},
                )
            )
            profile["slide_count"] = cast(int, profile["slide_count"]) + 1
            if not target or target not in names:
                continue
            slide = read_xml(archive, target)
            if any(local(node.tag) == "timing" for node in slide.iter()):
                profile["timing_present"] = True
            profile["transition_count"] = cast(int, profile["transition_count"]) + sum(
                1 for node in slide.iter() if local(node.tag) == "transition"
            )
            shape_ordinal = 0
            for shape in slide.iter():
                if local(shape.tag) not in {"sp", "pic", "graphicFrame", "cxnSp", "grpSp"}:
                    continue
                shape_id = unit_id(path, "slide", slide_index, "shape", shape_ordinal)
                text = "".join(node.text or "" for node in shape.iter() if local(node.tag) == "t")
                nodes.append(
                    NativeNode(
                        shape_id,
                        "shape",
                        sid,
                        shape_ordinal,
                        f"pptx:/slide[{slide_index + 1}]/shape[{shape_ordinal + 1}]",
                        text=text or None,
                        properties={"shape_xml_kind": local(shape.tag)},
                    )
                )
                shape_ordinal += 1
                profile["shape_count"] = cast(int, profile["shape_count"]) + 1
                profile["paragraph_count"] = cast(int, profile["paragraph_count"]) + sum(
                    1 for node in shape.iter() if local(node.tag) == "p"
                )
        profile["master_count"] = len(
            [
                name
                for name in names
                if name.startswith("ppt/slideMasters/slideMaster") and name.endswith(".xml")
            ]
        )
        profile["layout_count"] = len(
            [
                name
                for name in names
                if name.startswith("ppt/slideLayouts/slideLayout") and name.endswith(".xml")
            ]
        )
        profile["notes_count"] = len(
            [
                name
                for name in names
                if name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")
            ]
        )
    return NativeDocument(
        header=header("document_source.native_document"),
        profile="presentation.ooxml.v1",
        family=DocumentFamily.PRESENTATION,
        root_ids=(root_id,),
        nodes=tuple(nodes),
        profile_data=profile,
        capabilities=("has_slides", "has_timing", "has_styles", "has_relationships"),
    )
