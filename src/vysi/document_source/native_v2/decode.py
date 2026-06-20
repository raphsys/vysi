from __future__ import annotations

import re
import struct
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.contracts_v2.property_names import canonical_property_name
from vysi.document_source.execution.errors import StageFailure

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
EP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
CUSTOM_NS = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"
VT_NS = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _attr(element: ET.Element, local_name: str) -> str | None:
    for key, value in element.attrib.items():
        if _local(key) == local_name:
            return value
    return None


def _xml(payload: bytes, scope: str) -> ET.Element:
    if len(payload) > 64 * 1024 * 1024:
        raise StageFailure("DS-DEC-003", "DS08", scope, "Partie XML supérieure au quota")
    upper = payload.upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise StageFailure("DS-DEC-002", "DS08", scope, "DTD ou entité XML interdite")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise StageFailure("DS-DEC-001", "DS08", scope, "XML natif invalide", str(exc)) from exc


def _read_xml(archive: zipfile.ZipFile, name: str, required: bool = True) -> ET.Element | None:
    try:
        payload = archive.read(name)
    except KeyError:
        if required:
            raise StageFailure(
                "DS-DEC-001", "DS08", name, "Partie OOXML obligatoire absente"
            ) from None
        return None
    return _xml(payload, name)


def _typed_property(
    name: str, value: Any, source: str = "native_direct", address: str | None = None
) -> dict[str, Any]:
    if value is None:
        value_type = "null"
    elif isinstance(value, bool):
        value_type = "boolean"
    elif isinstance(value, int):
        value_type = "integer"
    elif isinstance(value, float):
        value_type = "number"
    elif isinstance(value, list):
        value_type = "array"
    else:
        value_type = "string"
        value = str(value)
    return {
        "name": canonical_property_name(name),
        "value_type": value_type,
        "value": value,
        "unit": None,
        "source": source,
        "source_address": address,
    }


def _element_properties(element: ET.Element, address: str, prefix: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for child_index, child in enumerate(element):
        name = _local(child.tag)
        value: Any = _attr(child, "val")
        if value is None:
            value = True if not child.attrib and child.text is None else (child.text or "")
        child_address = f"{address}/{name}[{child_index + 1}]"
        result.append(_typed_property(f"{prefix}.{name}", value, address=child_address))
    return result


def _zip_relationships(
    archive: zipfile.ZipFile, rels_path: str
) -> dict[str, tuple[str, str, bool]]:
    root = _read_xml(archive, rels_path, required=False)
    if root is None:
        return {}
    result: dict[str, tuple[str, str, bool]] = {}
    for rel in root.findall(f"{{{REL_NS}}}Relationship"):
        rel_id = rel.attrib.get("Id", "")
        target = rel.attrib.get("Target", "")
        rel_type = rel.attrib.get("Type", "")
        external = rel.attrib.get("TargetMode", "Internal").lower() == "external"
        result[rel_id] = (target, rel_type, external)
    return result


def _metadata_items(archive: zipfile.ZipFile, document_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path, namespace in (
        ("docProps/core.xml", "core"),
        ("docProps/app.xml", "extended"),
        ("docProps/custom.xml", "custom"),
    ):
        root = _read_xml(archive, path, required=False)
        if root is None:
            continue
        for index, element in enumerate(root):
            name = _local(element.tag)
            value_element = next(iter(element), None)
            text = (value_element.text if value_element is not None else element.text) or ""
            lower = name.lower()
            sensitivity = (
                "personal"
                if lower in {"creator", "lastmodifiedby", "company", "manager"}
                else "public"
            )
            items.append(
                {
                    "metadata_id": stable_id(
                        "metadata",
                        {"document_id": document_id, "path": path, "index": index, "name": name},
                    ),
                    "namespace": namespace,
                    "name": name,
                    "value": text,
                    "source_address": f"{path}#/{name}[{index + 1}]",
                    "sensitivity": sensitivity,
                }
            )
    return items


def _resources_from_container(
    document_id: str, container: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resources: list[dict[str, Any]] = []
    occurrences: list[dict[str, Any]] = []
    path_to_resource: dict[str, str] = {}
    for part in container["parts"]:
        path = str(part["path"])
        lower = path.lower()
        kind: str | None = None
        if "/media/" in lower or str(part.get("media_type") or "").startswith("image/"):
            kind = "image"
        elif "/embeddings/" in lower or "embedded_object" in part["security_flags"]:
            kind = "embedded_document"
        elif "vbaproject" in lower or "macro" in part["security_flags"]:
            kind = "macro_project"
        elif "/activex/" in lower or "activex" in part["security_flags"]:
            kind = "activex_control"
        elif "/fonts/" in lower or "font" in str(part.get("media_type") or "").lower():
            kind = "font"
        elif lower.startswith("theme/") or "/theme/" in lower:
            kind = "theme"
        if kind is None:
            continue
        resource_id = stable_id(
            "resource", {"document_id": document_id, "part_id": part["part_id"]}
        )
        path_to_resource[path] = resource_id
        resources.append(
            {
                "resource_id": resource_id,
                "kind": kind,
                "owner_id": document_id,
                "source_address": path,
                "media_type": part.get("media_type"),
                "size_bytes": part.get("size_bytes"),
                "sha256": part.get("sha256"),
                "stored_ref": part.get("stored_ref"),
                "active": kind in {"macro_project", "activex_control"},
                "opaque": bool(part["opaque"]),
            }
        )
    for relation in container["relationships"]:
        target = str(relation["target"])
        occurrence_resource_id = path_to_resource.get(target)
        if occurrence_resource_id is None:
            continue
        owner = relation.get("source_part_id") or document_id
        occurrences.append(
            {
                "occurrence_id": stable_id(
                    "occurrence",
                    {
                        "relationship": relation["relationship_id"],
                        "resource": occurrence_resource_id,
                    },
                ),
                "resource_id": occurrence_resource_id,
                "owner_id": owner,
                "source_address": f"relationship:{relation['relationship_id']}",
                "geometry_ref": None,
            }
        )
    return resources, occurrences


def _native_relationships(document_id: str, container: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for relation in container["relationships"]:
        rel_type = str(relation["relationship_type"])
        short_type = rel_type.rsplit("/", 1)[-1] if "/" in rel_type else rel_type
        source_id = relation.get("source_part_id") or document_id
        result.append(
            {
                "relationship_id": stable_id(
                    "native_rel",
                    {"document_id": document_id, "container_rel": relation["relationship_id"]},
                ),
                "source_id": source_id,
                "target_id": str(relation["target"]),
                "relation_type": short_type or "unknown",
                "external": bool(relation["external"]),
                "source_address": f"container_relationship:{relation['relationship_id']}",
            }
        )
    return result


@dataclass(frozen=True)
class DecodedPayload:
    document_id: str
    profile_kind: str
    profile_schema: str
    profile_body: dict[str, Any]
    root_unit_ids: tuple[str, ...]
    capabilities: tuple[str, ...]
    styles: tuple[dict[str, Any], ...]
    relationships: tuple[dict[str, Any], ...]
    resources: tuple[dict[str, Any], ...]
    occurrences: tuple[dict[str, Any], ...]
    metadata: tuple[dict[str, Any], ...]
    annotations: tuple[dict[str, Any], ...]
    opaque_part_ids: tuple[str, ...]
    decode_state: str
    reader_id: str
    warnings: tuple[str, ...] = ()


def _decode_text(path: Path, document_id: str, container: dict[str, Any]) -> DecodedPayload:
    data = path.read_bytes()
    bom: str | None = None
    offset = 0
    candidates: list[tuple[str, bytes]] = []
    if data.startswith(b"\xef\xbb\xbf"):
        bom, offset, candidates = "utf-8", 3, [("utf-8", data[3:])]
    elif data.startswith(b"\xff\xfe\x00\x00"):
        bom, offset, candidates = "utf-32le", 4, [("utf-32le", data[4:])]
    elif data.startswith(b"\x00\x00\xfe\xff"):
        bom, offset, candidates = "utf-32be", 4, [("utf-32be", data[4:])]
    elif data.startswith(b"\xff\xfe"):
        bom, offset, candidates = "utf-16le", 2, [("utf-16le", data[2:])]
    elif data.startswith(b"\xfe\xff"):
        bom, offset, candidates = "utf-16be", 2, [("utf-16be", data[2:])]
    else:
        candidates = [("utf-8", data), ("cp1252", data), ("latin-1", data)]
    text = ""
    encoding = "utf-8"
    confidence = 0.5
    for index, (candidate, payload) in enumerate(candidates):
        try:
            text = payload.decode(candidate)
            encoding = candidate
            confidence = 1.0 if index == 0 else (0.85 if candidate == "cp1252" else 0.70)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")
        encoding = "utf-8-replacement"
        confidence = 0.25
    crlf = text.count("\r\n")
    bare_lf = text.count("\n") - crlf
    bare_cr = text.count("\r") - crlf
    styles = [name for name, count in (("crlf", crlf), ("lf", bare_lf), ("cr", bare_cr)) if count]
    newline_style = styles[0] if len(styles) == 1 else ("mixed" if styles else "none")
    lines: list[dict[str, Any]] = []
    byte_cursor = offset
    split_lines = text.splitlines(keepends=True)
    if not split_lines and text == "":
        split_lines = []
    for ordinal, raw_line in enumerate(split_lines):
        line = raw_line.rstrip("\r\n")
        encoded = raw_line.encode(encoding.replace("-replacement", ""), errors="replace")
        line_bytes = line.encode(encoding.replace("-replacement", ""), errors="replace")
        unit_id = stable_id(
            "line", {"document_id": document_id, "ordinal": ordinal, "start": byte_cursor}
        )
        lines.append(
            {
                "unit_id": unit_id,
                "ordinal": ordinal,
                "byte_start": byte_cursor,
                "byte_end": byte_cursor + len(line_bytes),
                "text": line,
            }
        )
        byte_cursor += len(encoded)
    controls = sorted(
        {
            f"U+{ord(ch):04X}"
            for ch in text
            if unicodedata.category(ch) == "Cc" and ch not in "\t\n\r\f"
        }
    )
    profile = {
        "profile_kind": "plain_text",
        "profile_version": "2.0.0",
        "document_id": document_id,
        "encoding": encoding,
        "encoding_confidence": confidence,
        "bom": bom,
        "newline_style": newline_style,
        "unicode_normalization": "source_preserved",
        "lines": lines,
        "control_findings": controls,
    }
    return DecodedPayload(
        document_id,
        "plain_text",
        "profile_plain_text",
        profile,
        tuple(item["unit_id"] for item in lines),
        ("native.text", "layout.linear"),
        (),
        (),
        (),
        (),
        (),
        (),
        tuple(str(part["part_id"]) for part in container["parts"] if part["opaque"]),
        "complete",
        "vysi.native.text",
    )


def _docx_styles(
    archive: zipfile.ZipFile, document_id: str
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    root = _read_xml(archive, "word/styles.xml", required=False)
    if root is None:
        return [], {}
    raw_styles: dict[str, dict[str, Any]] = {}
    native_to_id: dict[str, str] = {}
    for ordinal, element in enumerate(root.findall(f"{{{W_NS}}}style")):
        native_id = _attr(element, "styleId") or f"anonymous-{ordinal}"
        style_id = stable_id("style", {"document_id": document_id, "native": native_id})
        native_to_id[native_id] = style_id
        name_element = element.find(f"{{{W_NS}}}name")
        based = element.find(f"{{{W_NS}}}basedOn")
        direct: list[dict[str, Any]] = []
        for child in element:
            child_name = _local(child.tag)
            if child_name in {"pPr", "rPr", "tblPr", "tcPr"}:
                direct.extend(
                    _element_properties(
                        child,
                        f"word/styles.xml#/style[{ordinal + 1}]/{child_name}",
                        child_name.lower(),
                    )
                )
        raw_styles[native_id] = {
            "style_id": style_id,
            "style_kind": _attr(element, "type") or "unknown",
            "native_name": _attr(name_element, "val") if name_element is not None else native_id,
            "parent_native": _attr(based, "val") if based is not None else None,
            "direct_properties": direct,
            "source_address": f"word/styles.xml#/styles/style[{ordinal + 1}]",
        }
    resolving: set[str] = set()

    def resolved(native_id: str) -> list[dict[str, Any]]:
        item = raw_styles[native_id]
        if native_id in resolving:
            return list(item["direct_properties"])
        resolving.add(native_id)
        merged: dict[str, dict[str, Any]] = {}
        parent = item["parent_native"]
        if isinstance(parent, str) and parent in raw_styles:
            for prop in resolved(parent):
                inherited = dict(prop)
                inherited["source"] = "native_inherited"
                merged[str(prop["name"])] = inherited
        for prop in cast(list[dict[str, Any]], item["direct_properties"]):
            merged[str(prop["name"])] = prop
        resolving.discard(native_id)
        return list(merged.values())

    styles: list[dict[str, Any]] = []
    for native_id, item in raw_styles.items():
        parent_native = item["parent_native"]
        styles.append(
            {
                "style_id": item["style_id"],
                "style_kind": item["style_kind"],
                "native_name": item["native_name"],
                "parent_style_id": native_to_id.get(parent_native)
                if isinstance(parent_native, str)
                else None,
                "direct_properties": item["direct_properties"],
                "resolved_properties": resolved(native_id),
                "source_address": item["source_address"],
            }
        )
    return styles, native_to_id


def _text_content(element: ET.Element) -> str:
    output: list[str] = []
    for node in element.iter():
        name = _local(node.tag)
        if name in {"t", "delText", "instrText"}:
            output.append(node.text or "")
        elif name == "tab":
            output.append("\t")
        elif name in {"br", "cr"}:
            output.append("\n")
    return "".join(output)


def _decode_docx(path: Path, document_id: str, container: dict[str, Any]) -> DecodedPayload:
    blocks: list[dict[str, Any]] = []
    sections: list[dict[str, Any]] = []
    revisions: list[dict[str, Any]] = []
    annotations_profile: list[dict[str, Any]] = []
    annotation_catalog: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        styles, style_map = _docx_styles(archive, document_id)
        root = cast(ET.Element, _read_xml(archive, "word/document.xml"))
        body = root.find(f"{{{W_NS}}}body")
        section_id = stable_id("section", {"document_id": document_id, "ordinal": 0})
        sections.append(
            {
                "section_id": section_id,
                "ordinal": 0,
                "source_address": "word/document.xml#/document/body",
                "properties": [],
            }
        )
        ordinal = 0
        para_map: dict[str, str] = {}

        def add_run(run: ET.Element, parent_id: str, run_ordinal: int, address: str) -> str:
            run_id = stable_id("run", {"document_id": document_id, "address": address})
            style_native: str | None = None
            rpr = run.find(f"{{{W_NS}}}rPr")
            if rpr is not None:
                rstyle = rpr.find(f"{{{W_NS}}}rStyle")
                style_native = _attr(rstyle, "val") if rstyle is not None else None
            blocks.append(
                {
                    "unit_id": run_id,
                    "kind": "run",
                    "parent_id": parent_id,
                    "ordinal": run_ordinal,
                    "source_address": address,
                    "text": _text_content(run),
                    "style_refs": [style_map[style_native]] if style_native in style_map else [],
                    "resource_refs": [],
                    "properties": _element_properties(rpr, f"{address}/rPr", "run")
                    if rpr is not None
                    else [],
                }
            )
            return run_id

        def add_paragraph(
            paragraph: ET.Element, parent_id: str, item_ordinal: int, address: str
        ) -> str:
            paragraph_id = stable_id("paragraph", {"document_id": document_id, "address": address})
            para_map[address] = paragraph_id
            ppr = paragraph.find(f"{{{W_NS}}}pPr")
            style_native: str | None = None
            if ppr is not None:
                pstyle = ppr.find(f"{{{W_NS}}}pStyle")
                style_native = _attr(pstyle, "val") if pstyle is not None else None
            blocks.append(
                {
                    "unit_id": paragraph_id,
                    "kind": "paragraph",
                    "parent_id": parent_id,
                    "ordinal": item_ordinal,
                    "source_address": address,
                    "text": _text_content(paragraph),
                    "style_refs": [style_map[style_native]] if style_native in style_map else [],
                    "resource_refs": [],
                    "properties": _element_properties(ppr, f"{address}/pPr", "paragraph")
                    if ppr is not None
                    else [],
                }
            )
            run_ordinal = 0
            for child_index, child in enumerate(paragraph):
                name = _local(child.tag)
                if name == "r":
                    add_run(child, paragraph_id, run_ordinal, f"{address}/r[{child_index + 1}]")
                    run_ordinal += 1
                elif name in {"ins", "del", "moveFrom", "moveTo"}:
                    targets: list[str] = []
                    for nested_index, run in enumerate(child.findall(f"{{{W_NS}}}r")):
                        targets.append(
                            add_run(
                                run,
                                paragraph_id,
                                run_ordinal,
                                f"{address}/{name}[{child_index + 1}]/r[{nested_index + 1}]",
                            )
                        )
                        run_ordinal += 1
                    if targets:
                        kind_map = {
                            "ins": "insert",
                            "del": "delete",
                            "moveFrom": "move_from",
                            "moveTo": "move_to",
                        }
                        revisions.append(
                            {
                                "revision_id": stable_id(
                                    "revision",
                                    {
                                        "document_id": document_id,
                                        "address": f"{address}/{name}[{child_index + 1}]",
                                    },
                                ),
                                "kind": kind_map[name],
                                "target_unit_ids": targets,
                                "author": _attr(child, "author"),
                                "date": _attr(child, "date"),
                                "source_address": f"{address}/{name}[{child_index + 1}]",
                            }
                        )
            return paragraph_id

        if body is not None:
            for child_index, child in enumerate(body):
                name = _local(child.tag)
                if name == "p":
                    add_paragraph(
                        child,
                        section_id,
                        ordinal,
                        f"word/document.xml#/document/body/p[{child_index + 1}]",
                    )
                    ordinal += 1
                elif name == "tbl":
                    table_id = stable_id(
                        "table", {"document_id": document_id, "index": child_index}
                    )
                    address = f"word/document.xml#/document/body/tbl[{child_index + 1}]"
                    blocks.append(
                        {
                            "unit_id": table_id,
                            "kind": "table",
                            "parent_id": section_id,
                            "ordinal": ordinal,
                            "source_address": address,
                            "text": None,
                            "style_refs": [],
                            "resource_refs": [],
                            "properties": [],
                        }
                    )
                    for row_index, row in enumerate(child.findall(f"{{{W_NS}}}tr")):
                        row_id = stable_id(
                            "row",
                            {"document_id": document_id, "table": table_id, "index": row_index},
                        )
                        blocks.append(
                            {
                                "unit_id": row_id,
                                "kind": "row",
                                "parent_id": table_id,
                                "ordinal": row_index,
                                "source_address": f"{address}/tr[{row_index + 1}]",
                                "text": None,
                                "style_refs": [],
                                "resource_refs": [],
                                "properties": [],
                            }
                        )
                        for cell_index, cell in enumerate(row.findall(f"{{{W_NS}}}tc")):
                            cell_id = stable_id(
                                "cell",
                                {"document_id": document_id, "row": row_id, "index": cell_index},
                            )
                            cell_address = f"{address}/tr[{row_index + 1}]/tc[{cell_index + 1}]"
                            blocks.append(
                                {
                                    "unit_id": cell_id,
                                    "kind": "cell",
                                    "parent_id": row_id,
                                    "ordinal": cell_index,
                                    "source_address": cell_address,
                                    "text": _text_content(cell),
                                    "style_refs": [],
                                    "resource_refs": [],
                                    "properties": [],
                                }
                            )
                            for p_index, paragraph in enumerate(cell.findall(f"{{{W_NS}}}p")):
                                add_paragraph(
                                    paragraph, cell_id, p_index, f"{cell_address}/p[{p_index + 1}]"
                                )
                    ordinal += 1
                elif name == "sectPr":
                    properties = _element_properties(
                        child,
                        f"word/document.xml#/document/body/sectPr[{child_index + 1}]",
                        "section",
                    )
                    sections[-1]["properties"] = properties
        for prefix, block_kind in (
            ("word/header", "header"),
            ("word/footer", "footer"),
            ("word/footnotes.xml", "footnote"),
            ("word/endnotes.xml", "endnote"),
        ):
            names = [
                name
                for name in archive.namelist()
                if name.startswith(prefix) and name.endswith(".xml")
            ]
            for _part_index, name in enumerate(sorted(names)):
                part_root = _read_xml(archive, name, required=False)
                if part_root is None:
                    continue
                parent_id = stable_id(block_kind, {"document_id": document_id, "part": name})
                blocks.append(
                    {
                        "unit_id": parent_id,
                        "kind": block_kind,
                        "parent_id": section_id,
                        "ordinal": len(blocks),
                        "source_address": name,
                        "text": _text_content(part_root),
                        "style_refs": [],
                        "resource_refs": [],
                        "properties": [],
                    }
                )
        comments_root = _read_xml(archive, "word/comments.xml", required=False)
        if comments_root is not None:
            for index, comment in enumerate(comments_root.findall(f"{{{W_NS}}}comment")):
                native_comment_id = _attr(comment, "id") or str(index)
                annotation_id = stable_id(
                    "annotation", {"document_id": document_id, "comment": native_comment_id}
                )
                target_ids: list[str] = []
                for block in blocks:
                    if block["kind"] == "paragraph":
                        target_ids = [str(block["unit_id"])]
                        break
                annotation = {
                    "annotation_id": annotation_id,
                    "kind": "comment",
                    "target_unit_ids": target_ids,
                    "text": _text_content(comment),
                    "source_address": f"word/comments.xml#/comments/comment[{index + 1}]",
                }
                annotations_profile.append(annotation)
                annotation_catalog.append(
                    {
                        "annotation_id": annotation_id,
                        "kind": "comment",
                        "owner_id": document_id,
                        "target_ids": target_ids,
                        "text": annotation["text"],
                        "author": _attr(comment, "author"),
                        "created_at_native": _attr(comment, "date"),
                        "source_address": annotation["source_address"],
                        "properties": [],
                    }
                )
        metadata = _metadata_items(archive, document_id)
    resources, occurrences = _resources_from_container(document_id, container)
    relationships = _native_relationships(document_id, container)
    profile = {
        "profile_kind": "wordprocessing",
        "profile_version": "2.0.0",
        "document_id": document_id,
        "sections": sections,
        "blocks": blocks,
        "layers": ["content"]
        + (["revision"] if revisions else [])
        + (["annotation"] if annotations_profile else []),
        "intrinsic_pagination": False,
        "revisions": revisions,
        "annotations": annotations_profile,
    }
    return DecodedPayload(
        document_id,
        "wordprocessing",
        "profile_wordprocessing",
        profile,
        tuple(item["section_id"] for item in sections),
        ("native.text", "layout.flow", "native.styles", "native.relationships"),
        tuple(styles),
        tuple(relationships),
        tuple(resources),
        tuple(occurrences),
        tuple(metadata),
        tuple(annotation_catalog),
        tuple(
            str(part["part_id"])
            for part in container["parts"]
            if part["opaque"] and not part.get("sha256")
        ),
        "complete",
        "vysi.native.docx",
    )


def _xlsx_styles(
    archive: zipfile.ZipFile, document_id: str
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    root = _read_xml(archive, "xl/styles.xml", required=False)
    if root is None:
        return [], {}
    cell_xfs = root.find(f"{{{S_NS}}}cellXfs")
    styles: list[dict[str, Any]] = []
    mapping: dict[int, str] = {}
    if cell_xfs is None:
        return styles, mapping
    for index, xf in enumerate(cell_xfs.findall(f"{{{S_NS}}}xf")):
        style_id = stable_id("style", {"document_id": document_id, "cell_xf": index})
        mapping[index] = style_id
        direct = [
            _typed_property(
                f"cell_xf.{key}",
                value,
                address=(
                    f"xl/styles.xml#/styleSheet/cellXfs/xf[{index + 1}]/@{key}"
                ),
            )
            for key, value in sorted(xf.attrib.items())
        ]
        styles.append(
            {
                "style_id": style_id,
                "style_kind": "cell_xf",
                "native_name": f"cellXf[{index}]",
                "parent_style_id": None,
                "direct_properties": direct,
                "resolved_properties": list(direct),
                "source_address": f"xl/styles.xml#/styleSheet/cellXfs/xf[{index + 1}]",
            }
        )
    return styles, mapping


def _decode_xlsx(path: Path, document_id: str, container: dict[str, Any]) -> DecodedPayload:
    worksheets: list[dict[str, Any]] = []
    cells: list[dict[str, Any]] = []
    formulas: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        workbook = cast(ET.Element, _read_xml(archive, "xl/workbook.xml"))
        rels = _zip_relationships(archive, "xl/_rels/workbook.xml.rels")
        styles, style_map = _xlsx_styles(archive, document_id)
        shared_strings: list[str] = []
        shared = _read_xml(archive, "xl/sharedStrings.xml", required=False)
        if shared is not None:
            for si in shared.findall(f"{{{S_NS}}}si"):
                shared_strings.append(
                    "".join(node.text or "" for node in si.iter() if _local(node.tag) == "t")
                )
        calc_pr = workbook.find(f"{{{S_NS}}}calcPr")
        calc_mode = _attr(calc_pr, "calcMode") if calc_pr is not None else None
        sheets_parent = workbook.find(f"{{{S_NS}}}sheets")
        if sheets_parent is not None:
            for ordinal, sheet in enumerate(sheets_parent.findall(f"{{{S_NS}}}sheet")):
                rel_id = sheet.attrib.get(f"{{{R_NS}}}id", "")
                target = rels.get(rel_id, (f"worksheets/sheet{ordinal + 1}.xml", "", False))[0]
                sheet_path = target if target.startswith("xl/") else f"xl/{target.lstrip('/')}"
                sheet_path = re.sub(r"^xl/../", "", sheet_path)
                sheet_path = str(Path(sheet_path).as_posix()).replace("xl/xl/", "xl/")
                if not sheet_path.startswith("xl/"):
                    sheet_path = f"xl/{sheet_path}"
                root = _read_xml(archive, sheet_path, required=False)
                if root is None:
                    continue
                worksheet_id = stable_id(
                    "worksheet",
                    {"document_id": document_id, "ordinal": ordinal, "path": sheet_path},
                )
                dimension = root.find(f"{{{S_NS}}}dimension")
                visibility_native = sheet.attrib.get("state", "visible")
                visibility = (
                    "very_hidden" if visibility_native == "veryHidden" else visibility_native
                )
                worksheets.append(
                    {
                        "worksheet_id": worksheet_id,
                        "name": sheet.attrib.get("name", f"Sheet{ordinal + 1}"),
                        "ordinal": ordinal,
                        "visibility": visibility
                        if visibility in {"visible", "hidden", "very_hidden"}
                        else "visible",
                        "source_address": sheet_path,
                        "used_range": dimension.attrib.get("ref")
                        if dimension is not None
                        else None,
                        "print_areas": [],
                    }
                )
                for cell_index, cell in enumerate(root.iter(f"{{{S_NS}}}c")):
                    address = cell.attrib.get("r") or f"A{cell_index + 1}"
                    type_code = cell.attrib.get("t", "n")
                    value_node = cell.find(f"{{{S_NS}}}v")
                    inline = cell.find(f"{{{S_NS}}}is")
                    formula_node = cell.find(f"{{{S_NS}}}f")
                    raw_text = value_node.text if value_node is not None else None
                    raw_value: Any = None
                    value_kind = "blank"
                    if type_code == "s" and raw_text is not None:
                        try:
                            raw_value = shared_strings[int(raw_text)]
                        except (ValueError, IndexError):
                            raw_value = raw_text
                        value_kind = "string"
                    elif type_code in {"str", "inlineStr"}:
                        raw_value = (
                            "".join(
                                node.text or "" for node in inline.iter() if _local(node.tag) == "t"
                            )
                            if inline is not None
                            else raw_text
                        )
                        value_kind = "string"
                    elif type_code == "b":
                        raw_value = raw_text == "1"
                        value_kind = "boolean"
                    elif type_code == "e":
                        raw_value = raw_text
                        value_kind = "error"
                    elif raw_text is not None:
                        try:
                            raw_value = (
                                int(raw_text)
                                if re.fullmatch(r"[-+]?\d+", raw_text)
                                else float(raw_text)
                            )
                        except ValueError:
                            raw_value = raw_text
                        value_kind = "number"
                    cell_id = stable_id(
                        "cell",
                        {"document_id": document_id, "worksheet": worksheet_id, "address": address},
                    )
                    formula_id: str | None = None
                    if formula_node is not None:
                        formula_id = stable_id(
                            "formula", {"document_id": document_id, "cell": cell_id}
                        )
                        kind_native = formula_node.attrib.get("t", "normal")
                        kind = (
                            kind_native
                            if kind_native in {"normal", "shared", "array", "data_table"}
                            else "normal"
                        )
                        source = formula_node.text or ""
                        deps = sorted(
                            set(re.findall(r"(?:'[^']+'!)?\$?[A-Z]{1,3}\$?[1-9][0-9]*", source))
                        )
                        formulas.append(
                            {
                                "formula_id": formula_id,
                                "cell_id": cell_id,
                                "source": source,
                                "kind": kind,
                                "dependency_refs": deps,
                                "volatile": bool(
                                    re.search(
                                        r"\b(?:NOW|TODAY|RAND|RANDBETWEEN|OFFSET|INDIRECT)\s*\(",
                                        source,
                                        re.I,
                                    )
                                ),
                            }
                        )
                        value_kind = "formula"
                    style_index = (
                        int(cell.attrib.get("s", "0")) if cell.attrib.get("s", "0").isdigit() else 0
                    )
                    cells.append(
                        {
                            "cell_id": cell_id,
                            "worksheet_id": worksheet_id,
                            "address": address.replace("$", ""),
                            "value_kind": value_kind,
                            "raw_value": raw_value,
                            "cached_value": raw_value if formula_id else None,
                            "formula_id": formula_id,
                            "style_refs": [style_map[style_index]]
                            if style_index in style_map
                            else [],
                            "source_address": f"{sheet_path}#/worksheet/sheetData/c[{cell_index + 1}]",
                        }
                    )
        metadata = _metadata_items(archive, document_id)
    resources, occurrences = _resources_from_container(document_id, container)
    relationships = _native_relationships(document_id, container)
    profile = {
        "profile_kind": "spreadsheet",
        "profile_version": "2.0.0",
        "document_id": document_id,
        "worksheets": worksheets,
        "cells": cells,
        "calculation_model": {
            "recalculated": False,
            "calculation_mode": calc_mode,
            "formulas": formulas,
        },
    }
    return DecodedPayload(
        document_id,
        "spreadsheet",
        "profile_spreadsheet",
        profile,
        tuple(item["worksheet_id"] for item in worksheets),
        ("native.grid", "native.formulas", "native.styles", "native.relationships"),
        tuple(styles),
        tuple(relationships),
        tuple(resources),
        tuple(occurrences),
        tuple(metadata),
        tuple(annotations),
        tuple(
            str(part["part_id"])
            for part in container["parts"]
            if part["opaque"] and not part.get("sha256")
        ),
        "complete",
        "vysi.native.xlsx",
    )


def _decode_pptx(path: Path, document_id: str, container: dict[str, Any]) -> DecodedPayload:
    slides: list[dict[str, Any]] = []
    shapes: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    animations: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        presentation = cast(ET.Element, _read_xml(archive, "ppt/presentation.xml"))
        rels = _zip_relationships(archive, "ppt/_rels/presentation.xml.rels")
        slide_list = presentation.find(f"{{{P_NS}}}sldIdLst")
        if slide_list is not None:
            for ordinal, slide_ref in enumerate(slide_list):
                rel_id = slide_ref.attrib.get(f"{{{R_NS}}}id", "")
                target = rels.get(rel_id, (f"slides/slide{ordinal + 1}.xml", "", False))[0]
                slide_path = target if target.startswith("ppt/") else f"ppt/{target.lstrip('/')}"
                slide_path = slide_path.replace("ppt/ppt/", "ppt/")
                root = _read_xml(archive, slide_path, required=False)
                if root is None:
                    continue
                slide_id = stable_id(
                    "slide", {"document_id": document_id, "ordinal": ordinal, "path": slide_path}
                )
                slide_rels_path = (
                    f"{Path(slide_path).parent.as_posix()}/_rels/{Path(slide_path).name}.rels"
                )
                slide_rels = _zip_relationships(archive, slide_rels_path)
                layout_ref: str | None = None
                master_ref: str | None = None
                notes_ref: str | None = None
                for _, (target_path, rel_type, external) in slide_rels.items():
                    if external:
                        continue
                    if rel_type.endswith("/slideLayout"):
                        layout_ref = target_path
                    elif rel_type.endswith("/slideMaster"):
                        master_ref = target_path
                    elif rel_type.endswith("/notesSlide"):
                        notes_ref = target_path
                slides.append(
                    {
                        "slide_id": slide_id,
                        "ordinal": ordinal,
                        "source_address": slide_path,
                        "layout_ref": layout_ref,
                        "master_ref": master_ref,
                        "notes_ref": notes_ref,
                        "hidden": _attr(slide_ref, "show") == "0",
                    }
                )
                sp_tree = root.find(f".//{{{P_NS}}}spTree")
                if sp_tree is not None:
                    shape_ordinal = 0
                    for element in sp_tree:
                        kind = _local(element.tag)
                        if kind not in {"sp", "pic", "graphicFrame", "grpSp", "cxnSp"}:
                            continue
                        c_nv_pr = next(
                            (node for node in element.iter() if _local(node.tag) == "cNvPr"), None
                        )
                        native_shape_id = (
                            _attr(c_nv_pr, "id") if c_nv_pr is not None else str(shape_ordinal)
                        )
                        shape_id = stable_id(
                            "shape",
                            {
                                "document_id": document_id,
                                "slide": slide_id,
                                "native": native_shape_id,
                            },
                        )
                        text = "".join(
                            node.text or "" for node in element.iter() if _local(node.tag) == "t"
                        )
                        resources_refs: list[str] = []
                        for node in element.iter():
                            embed = node.attrib.get(f"{{{R_NS}}}embed") or node.attrib.get(
                                f"{{{R_NS}}}link"
                            )
                            if embed:
                                resources_refs.append(
                                    stable_id(
                                        "resource_ref",
                                        {
                                            "document_id": document_id,
                                            "slide": slide_id,
                                            "rel": embed,
                                        },
                                    )
                                )
                        shapes.append(
                            {
                                "shape_id": shape_id,
                                "slide_id": slide_id,
                                "kind": kind,
                                "ordinal": shape_ordinal,
                                "source_address": f"{slide_path}#/sld/cSld/spTree/{kind}[{shape_ordinal + 1}]",
                                "parent_shape_id": None,
                                "text": text or None,
                                "style_refs": [],
                                "resource_refs": resources_refs,
                            }
                        )
                        shape_ordinal += 1
                transition = root.find(f"{{{P_NS}}}transition")
                if transition is not None:
                    child = next(iter(transition), None)
                    duration_native = _attr(transition, "dur")
                    transitions.append(
                        {
                            "event_id": stable_id(
                                "event",
                                {
                                    "document_id": document_id,
                                    "slide": slide_id,
                                    "kind": "transition",
                                },
                            ),
                            "kind": _local(child.tag) if child is not None else "unknown",
                            "target_shape_ids": [],
                            "trigger": "automatic" if _attr(transition, "advTm") else "on_click",
                            "ordinal": ordinal,
                            "duration_ms": int(duration_native)
                            if duration_native is not None and duration_native.isdigit()
                            else None,
                            "source_address": f"{slide_path}#/sld/transition",
                        }
                    )
                timing = root.find(f"{{{P_NS}}}timing")
                if timing is not None:
                    animations.append(
                        {
                            "event_id": stable_id(
                                "event",
                                {"document_id": document_id, "slide": slide_id, "kind": "timing"},
                            ),
                            "kind": "timing_tree",
                            "target_shape_ids": [],
                            "trigger": "unknown",
                            "ordinal": ordinal,
                            "duration_ms": None,
                            "source_address": f"{slide_path}#/sld/timing",
                        }
                    )
        metadata = _metadata_items(archive, document_id)
    resources, occurrences = _resources_from_container(document_id, container)
    relationships = _native_relationships(document_id, container)
    timing_state = "available" if animations else ("available" if transitions else "not_present")
    profile = {
        "profile_kind": "presentation",
        "profile_version": "2.0.0",
        "document_id": document_id,
        "slides": slides,
        "shapes": shapes,
        "timing_model": {
            "state": timing_state,
            "animations": animations,
            "transitions": transitions,
        },
    }
    return DecodedPayload(
        document_id,
        "presentation",
        "profile_presentation",
        profile,
        tuple(item["slide_id"] for item in slides),
        ("native.slides", "native.shapes", "native.relationships", "native.timing"),
        (),
        tuple(relationships),
        tuple(resources),
        tuple(occurrences),
        tuple(metadata),
        (),
        tuple(
            str(part["part_id"])
            for part in container["parts"]
            if part["opaque"] and not part.get("sha256")
        ),
        "complete",
        "vysi.native.pptx",
    )


def _decode_pdf(
    path: Path, document_id: str, container: dict[str, Any], encrypted: bool
) -> DecodedPayload:
    data = path.read_bytes()
    page_matches = list(re.finditer(rb"/Type\s*/Page(?!s)\b", data))
    pages: list[dict[str, Any]] = []
    for ordinal, match in enumerate(page_matches):
        window = data[max(0, match.start() - 4096) : min(len(data), match.end() + 8192)]
        media = re.search(
            rb"/MediaBox\s*\[\s*([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s+([-+0-9.]+)\s*\]", window
        )
        width = 612.0
        height = 792.0
        if media:
            try:
                x0, y0, x1, y1 = (float(value) for value in media.groups())
                width, height = abs(x1 - x0), abs(y1 - y0)
            except ValueError:
                pass
        rotate_match = re.search(rb"/Rotate\s+(-?\d+)", window)
        rotation = int(rotate_match.group(1)) % 360 if rotate_match else 0
        if rotation not in {0, 90, 180, 270}:
            rotation = 0
        pages.append(
            {
                "page_id": stable_id("page", {"document_id": document_id, "ordinal": ordinal}),
                "ordinal": ordinal,
                "width_pt": width,
                "height_pt": height,
                "rotation": rotation,
                "source_address": f"pdf:page[{ordinal}]",
                "box_refs": [],
            }
        )
    if not pages and not encrypted:
        raise StageFailure("DS-DEC-001", "DS08", document_id, "Aucune page PDF détectable")
    repaired = b"startxref" not in data[-4096:] or not data.rstrip().endswith(b"%%EOF")
    metadata: list[dict[str, Any]] = []
    for name in ("Title", "Author", "Subject", "Keywords", "Creator", "Producer"):
        info_match = re.search(rf"/{name}\s*\(([^)]*)\)".encode(), data[: 4 * 1024 * 1024])
        if info_match:
            text = info_match.group(1).decode("latin-1", errors="replace")
            metadata.append(
                {
                    "metadata_id": stable_id(
                        "metadata", {"document_id": document_id, "name": name}
                    ),
                    "namespace": "pdf.info",
                    "name": name.lower(),
                    "value": text,
                    "source_address": f"pdf:info/{name}",
                    "sensitivity": "personal" if name == "Author" else "public",
                }
            )
    annotations: list[dict[str, Any]] = []
    for index, subtype in enumerate(re.findall(rb"/Subtype\s*/([A-Za-z0-9]+)", data)):
        kind = subtype.decode("ascii", errors="replace")
        if kind in {
            "Text",
            "Link",
            "Highlight",
            "Underline",
            "StrikeOut",
            "FileAttachment",
            "Widget",
        }:
            annotations.append(
                {
                    "annotation_id": stable_id(
                        "annotation", {"document_id": document_id, "index": index, "kind": kind}
                    ),
                    "kind": kind.lower(),
                    "owner_id": document_id,
                    "target_ids": [],
                    "text": None,
                    "author": None,
                    "created_at_native": None,
                    "source_address": f"pdf:annotation[{index}]",
                    "properties": [],
                }
            )
    profile = {
        "profile_kind": "fixed_layout",
        "profile_version": "2.0.0",
        "document_id": document_id,
        "pages": pages,
        "repaired": repaired,
        "encrypted": encrypted,
    }
    return DecodedPayload(
        document_id,
        "fixed_layout",
        "profile_fixed_layout",
        profile,
        tuple(item["page_id"] for item in pages),
        ("native.pages", "layout.fixed"),
        (),
        (),
        (),
        (),
        tuple(metadata),
        tuple(annotations),
        tuple(str(part["part_id"]) for part in container["parts"] if part["opaque"]),
        "partial" if repaired else "complete",
        "vysi.native.pdf",
        ("pdf_repaired_or_truncated",) if repaired else (),
    )


def _png_info(data: bytes) -> tuple[int, int, int, list[int | None]]:
    if len(data) < 24:
        raise ValueError("PNG trop court")
    width, height = struct.unpack(">II", data[16:24])
    return width, height, 1, [None]


def _gif_info(data: bytes) -> tuple[int, int, int, list[int | None]]:
    if len(data) < 13:
        raise ValueError("GIF trop court")
    width, height = struct.unpack_from("<HH", data, 6)
    frames = data.count(b"\x2c")
    durations: list[int | None] = []
    for match in re.finditer(rb"\x21\xf9\x04(.)(..)", data, re.S):
        durations.append(struct.unpack("<H", match.group(2))[0] * 10)
    frames = max(1, frames)
    durations.extend([None] * (frames - len(durations)))
    return width, height, frames, durations[:frames]


def _jpeg_info(data: bytes) -> tuple[int, int, int, list[int | None]]:
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            break
        length = struct.unpack_from(">H", data, index)[0]
        if marker in {
            0xC0,
            0xC1,
            0xC2,
            0xC3,
            0xC5,
            0xC6,
            0xC7,
            0xC9,
            0xCA,
            0xCB,
            0xCD,
            0xCE,
            0xCF,
        } and index + 7 < len(data):
            height, width = struct.unpack_from(">HH", data, index + 3)
            return width, height, 1, [None]
        index += max(2, length)
    raise ValueError("Dimensions JPEG introuvables")


def _bmp_info(data: bytes) -> tuple[int, int, int, list[int | None]]:
    if len(data) < 26:
        raise ValueError("BMP trop court")
    width, height = struct.unpack_from("<ii", data, 18)
    return abs(width), abs(height), 1, [None]


def _webp_info(data: bytes) -> tuple[int, int, int, list[int | None]]:
    vp8x = data.find(b"VP8X")
    if vp8x >= 0 and vp8x + 18 <= len(data):
        width = 1 + int.from_bytes(data[vp8x + 12 : vp8x + 15], "little")
        height = 1 + int.from_bytes(data[vp8x + 15 : vp8x + 18], "little")
        frames = max(1, data.count(b"ANMF"))
        return width, height, frames, [None] * frames
    raise ValueError("Dimensions WebP introuvables")


def _tiff_info(data: bytes) -> tuple[int, int, int, list[int | None]]:
    if len(data) < 8:
        raise ValueError("TIFF trop court")
    order = "<" if data[:2] == b"II" else ">"
    magic = struct.unpack_from(f"{order}H", data, 2)[0]
    if magic != 42:
        raise ValueError("BigTIFF non pris en charge par le lecteur minimal")
    offset = struct.unpack_from(f"{order}I", data, 4)[0]
    visited: set[int] = set()
    frames = 0
    width = height = 0
    while offset and offset not in visited and offset + 2 <= len(data):
        visited.add(offset)
        count = struct.unpack_from(f"{order}H", data, offset)[0]
        frame_width = frame_height = 0
        for index in range(count):
            pos = offset + 2 + index * 12
            if pos + 12 > len(data):
                break
            tag, value_type, value_count, value_offset = struct.unpack_from(
                f"{order}HHII", data, pos
            )
            if value_count == 1 and value_type in {3, 4}:
                value = (
                    value_offset & 0xFFFF
                    if value_type == 3 and order == "<"
                    else (value_offset >> 16 if value_type == 3 else value_offset)
                )
                if tag == 256:
                    frame_width = value
                elif tag == 257:
                    frame_height = value
        frames += 1
        if frames == 1:
            width, height = frame_width, frame_height
        next_pos = offset + 2 + count * 12
        offset = (
            struct.unpack_from(f"{order}I", data, next_pos)[0] if next_pos + 4 <= len(data) else 0
        )
    if not width or not height:
        raise ValueError("Dimensions TIFF introuvables")
    return width, height, max(1, frames), [None] * max(1, frames)


def _jp2_info(data: bytes) -> tuple[int, int, int, list[int | None]]:
    pos = data.find(b"ihdr")
    if pos >= 4 and pos + 12 <= len(data):
        height, width = struct.unpack_from(">II", data, pos + 4)
        return width, height, 1, [None]
    raise ValueError("Dimensions JPEG 2000 introuvables")


def _decode_raster(
    path: Path, document_id: str, container: dict[str, Any], format_name: str
) -> DecodedPayload:
    data = path.read_bytes()
    parsers = {
        "png": _png_info,
        "gif": _gif_info,
        "jpeg": _jpeg_info,
        "bmp": _bmp_info,
        "webp": _webp_info,
        "tiff": _tiff_info,
        "jpeg2000": _jp2_info,
    }
    try:
        width, height, frame_count, durations = parsers[format_name](data)
    except (KeyError, ValueError, struct.error) as exc:
        raise StageFailure(
            "DS-DEC-002", "DS08", document_id, "Décodage raster minimal impossible", str(exc)
        ) from exc
    frames = [
        {
            "frame_id": stable_id("frame", {"document_id": document_id, "ordinal": ordinal}),
            "ordinal": ordinal,
            "width_px": width,
            "height_px": height,
            "duration_ms": durations[ordinal],
            "source_address": f"image:frame[{ordinal}]",
            "orientation": None,
            "icc_profile_ref": None,
        }
        for ordinal in range(frame_count)
    ]
    animated = format_name in {"gif", "webp"} and frame_count > 1
    if format_name == "tiff" and frame_count > 1:
        policy = "one_surface_per_frame"
    elif animated:
        policy = "single_surface"
    else:
        policy = "single_surface"
    artifact_part = container["parts"][0]
    resource_id = stable_id("resource", {"document_id": document_id, "kind": "native_image"})
    resources = (
        {
            "resource_id": resource_id,
            "kind": "native_image_file",
            "owner_id": document_id,
            "source_address": str(artifact_part["path"]),
            "media_type": artifact_part.get("media_type"),
            "size_bytes": artifact_part.get("size_bytes"),
            "sha256": artifact_part.get("sha256"),
            "stored_ref": artifact_part.get("stored_ref"),
            "active": False,
            "opaque": False,
        },
    )
    occurrences = tuple(
        {
            "occurrence_id": stable_id(
                "occurrence", {"document_id": document_id, "frame": ordinal}
            ),
            "resource_id": resource_id,
            "owner_id": frame["frame_id"],
            "source_address": frame["source_address"],
            "geometry_ref": None,
        }
        for ordinal, frame in enumerate(frames)
    )
    profile = {
        "profile_kind": "raster",
        "profile_version": "2.0.0",
        "document_id": document_id,
        "frames": frames,
        "document_surface_policy": policy,
        "animated": animated,
    }
    return DecodedPayload(
        document_id,
        "raster",
        "profile_raster",
        profile,
        tuple(str(frame["frame_id"]) for frame in frames),
        ("native.frames", "layout.raster"),
        (),
        (),
        resources,
        occurrences,
        (),
        (),
        (),
        "complete",
        f"vysi.native.{format_name}",
    )


def _decode_ole(document_id: str, container: dict[str, Any], format_hint: str) -> DecodedPayload:
    storages: list[dict[str, Any]] = []
    streams: list[dict[str, Any]] = []
    for part in container["parts"]:
        if part["part_kind"] in {"storage", "root_storage"}:
            storages.append(
                {
                    "storage_id": part["part_id"],
                    "path": part["path"],
                    "parent_id": part.get("parent_part_id"),
                }
            )
        elif part["part_kind"] == "stream":
            streams.append(
                {
                    "stream_id": part["part_id"],
                    "path": part["path"],
                    "size_bytes": part.get("size_bytes") or 0,
                    "sha256": part.get("sha256"),
                    "read_state": part["read_state"],
                    "source_address": part["path"],
                }
            )
    profile = {
        "profile_kind": "legacy_ole",
        "profile_version": "2.0.0",
        "document_id": document_id,
        "coverage_level": "inventory_only",
        "storages": storages,
        "streams": streams,
        "semantic_format_hint": format_hint if format_hint in {"doc", "xls", "ppt"} else None,
    }
    return DecodedPayload(
        document_id,
        "legacy_ole",
        "profile_legacy_ole",
        profile,
        tuple(item["storage_id"] for item in storages[:1]),
        ("native.container_inventory",),
        (),
        tuple(_native_relationships(document_id, container)),
        (),
        (),
        (),
        (),
        tuple(str(part["part_id"]) for part in container["parts"]),
        "partial",
        "vysi.native.ole_inventory",
        ("legacy_ole_semantic_decode_deferred",),
    )


def decode_document(
    path: Path,
    document: dict[str, Any],
    container: dict[str, Any],
    access: dict[str, Any],
) -> DecodedPayload:
    document_id = str(document["document_id"])
    access_state = str(access["access_state"])
    if access_state == "blocked":
        raise StageFailure(
            "DS-DEC-002", "DS08", document_id, "Décodage bloqué par la politique d'accès"
        )
    if access_state == "secret_required":
        raise StageFailure("DS-DEC-002", "DS08", document_id, "Décodage différé: secret requis")
    format_name = str(document["format_name"])
    if format_name == "txt":
        return _decode_text(path, document_id, container)
    if format_name in {"docx", "docm"}:
        return _decode_docx(path, document_id, container)
    if format_name in {"xlsx", "xlsm"}:
        return _decode_xlsx(path, document_id, container)
    if format_name in {"pptx", "pptm"}:
        return _decode_pptx(path, document_id, container)
    if format_name == "pdf":
        return _decode_pdf(path, document_id, container, bool(access["encryption"]["encrypted"]))
    if format_name in {"png", "jpeg", "gif", "tiff", "webp", "jpeg2000", "bmp"}:
        return _decode_raster(path, document_id, container, format_name)
    if str(document["container_kind"]) == "ole_cfb":
        extension = path.suffix.lower().lstrip(".")
        return _decode_ole(document_id, container, extension)
    raise StageFailure(
        "DS-DEC-002", "DS08", document_id, f"Aucun lecteur natif disponible pour {format_name}"
    )
