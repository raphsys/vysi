from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id


@dataclass(frozen=True)
class ProjectionError(ValueError):
    message: str

    def __str__(self) -> str:
        return self.message


def _property(
    name: str,
    value: Any,
    *,
    source: str = "native_direct",
    address: str | None = None,
    unit: str | None = None,
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
        "name": name,
        "value_type": value_type,
        "value": value,
        "unit": unit,
        "source": source,
        "source_address": address,
    }


def _properties(
    values: Iterable[tuple[str, Any]], *, address: str | None = None
) -> list[dict[str, Any]]:
    return [_property(name, value, address=address) for name, value in values]


def _ir_id(document_id: str, native_id: str, kind: str) -> str:
    return stable_id("ir", {"document_id": document_id, "native_id": native_id, "kind": kind})


def _synthetic_id(document_id: str, purpose: str) -> str:
    return stable_id("ir", {"document_id": document_id, "synthetic": purpose})


def _unit(
    *,
    unit_id: str,
    kind: str,
    parent_id: str | None,
    ordinal: int,
    origin: str,
    source_native_ids: list[str],
    text: str | None = None,
    protected: bool = False,
    style_refs: list[str] | None = None,
    resource_refs: list[str] | None = None,
    technical_properties: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "unit_id": unit_id,
        "kind": kind,
        "parent_id": parent_id,
        "ordinal": ordinal,
        "origin": origin,
        "source_native_ids": source_native_ids,
        "text": text,
        "protected": protected,
        "style_refs": style_refs or [],
        "resource_refs": resource_refs or [],
        "technical_properties": technical_properties or [],
    }


def _root_unit(document_id: str, profile_kind: str) -> dict[str, Any]:
    return _unit(
        unit_id=_synthetic_id(document_id, "document_root"),
        kind="document",
        parent_id=None,
        ordinal=0,
        origin="synthetic",
        source_native_ids=[],
        technical_properties=[
            _property("document.profile_kind", profile_kind, source="derived"),
        ],
    )


def _native_map(units: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for unit in units:
        for native_id in unit["source_native_ids"]:
            mapping.setdefault(str(native_id), str(unit["unit_id"]))
    return mapping


def _project_plain_text(profile: dict[str, Any], root_id: str) -> list[dict[str, Any]]:
    document_id = str(profile["document_id"])
    units: list[dict[str, Any]] = []
    for line in profile["lines"]:
        native_id = str(line["unit_id"])
        address = f"bytes:{line['byte_start']}:{line['byte_end']}"
        units.append(
            _unit(
                unit_id=_ir_id(document_id, native_id, "text_line"),
                kind="text_line",
                parent_id=root_id,
                ordinal=int(line["ordinal"]),
                origin="native_projection",
                source_native_ids=[native_id],
                text=str(line["text"]),
                technical_properties=_properties(
                    [
                        ("text.byte_start", int(line["byte_start"])),
                        ("text.byte_end", int(line["byte_end"])),
                        ("text.encoding", profile["encoding"]),
                        ("text.newline_style", profile["newline_style"]),
                    ],
                    address=address,
                ),
            )
        )
    return units


_WORD_KIND_MAP = {
    "paragraph": "paragraph",
    "run": "text_span",
    "table": "table",
    "row": "table_row",
    "cell": "table_cell",
    "header": "header",
    "footer": "footer",
    "footnote": "footnote",
    "endnote": "endnote",
    "field": "field",
    "content_control": "content_control",
    "bookmark": "bookmark",
}


def _project_wordprocessing(profile: dict[str, Any], root_id: str) -> list[dict[str, Any]]:
    document_id = str(profile["document_id"])
    units: list[dict[str, Any]] = []
    native_to_ir: dict[str, str] = {}
    for section in profile["sections"]:
        native_id = str(section["section_id"])
        ir_id = _ir_id(document_id, native_id, "flow_section")
        native_to_ir[native_id] = ir_id
        units.append(
            _unit(
                unit_id=ir_id,
                kind="flow_section",
                parent_id=root_id,
                ordinal=int(section["ordinal"]),
                origin="native_projection",
                source_native_ids=[native_id],
                technical_properties=[
                    _property("source.address", section["source_address"]),
                    *list(section.get("properties", [])),
                ],
            )
        )
    for block in profile["blocks"]:
        native_id = str(block["unit_id"])
        kind = _WORD_KIND_MAP[str(block["kind"])]
        native_to_ir[native_id] = _ir_id(document_id, native_id, kind)
    for block in profile["blocks"]:
        native_id = str(block["unit_id"])
        native_parent = block.get("parent_id")
        parent_id = native_to_ir.get(str(native_parent), root_id) if native_parent else root_id
        kind = _WORD_KIND_MAP[str(block["kind"])]
        address = str(block["source_address"])
        units.append(
            _unit(
                unit_id=native_to_ir[native_id],
                kind=kind,
                parent_id=parent_id,
                ordinal=int(block["ordinal"]),
                origin="native_projection",
                source_native_ids=[native_id],
                text=block.get("text"),
                protected=kind in {"field", "content_control", "bookmark"},
                style_refs=list(block.get("style_refs", [])),
                resource_refs=list(block.get("resource_refs", [])),
                technical_properties=[
                    _property("source.address", address),
                    _property("word.native_kind", block["kind"], address=address),
                    *list(block.get("properties", [])),
                ],
            )
        )
    ordinal = len(units)
    for revision in profile["revisions"]:
        native_id = str(revision["revision_id"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, native_id, "revision"),
                kind=f"revision_{revision['kind']}",
                parent_id=root_id,
                ordinal=ordinal,
                origin="native_projection",
                source_native_ids=[native_id],
                protected=True,
                technical_properties=_properties(
                    [
                        ("revision.kind", revision["kind"]),
                        ("revision.target_unit_ids", list(revision["target_unit_ids"])),
                        ("revision.author", revision.get("author")),
                        ("revision.date", revision.get("date")),
                        ("source.address", revision["source_address"]),
                    ],
                    address=str(revision["source_address"]),
                ),
            )
        )
        ordinal += 1
    return units


def _project_spreadsheet(profile: dict[str, Any], root_id: str) -> list[dict[str, Any]]:
    document_id = str(profile["document_id"])
    units: list[dict[str, Any]] = []
    worksheet_map: dict[str, str] = {}
    cell_map: dict[str, str] = {}
    for worksheet in profile["worksheets"]:
        native_id = str(worksheet["worksheet_id"])
        ir_id = _ir_id(document_id, native_id, "worksheet")
        worksheet_map[native_id] = ir_id
        address = str(worksheet["source_address"])
        units.append(
            _unit(
                unit_id=ir_id,
                kind="worksheet",
                parent_id=root_id,
                ordinal=int(worksheet["ordinal"]),
                origin="native_projection",
                source_native_ids=[native_id],
                text=str(worksheet["name"]),
                protected=str(worksheet["visibility"]) != "visible",
                technical_properties=_properties(
                    [
                        ("sheet.name", worksheet["name"]),
                        ("sheet.visibility", worksheet["visibility"]),
                        ("sheet.used_range", worksheet.get("used_range")),
                        ("sheet.print_areas", list(worksheet.get("print_areas", []))),
                        ("source.address", address),
                    ],
                    address=address,
                ),
            )
        )
    formulas = {str(item["formula_id"]): item for item in profile["calculation_model"]["formulas"]}
    for cell in profile["cells"]:
        native_id = str(cell["cell_id"])
        cell_map[native_id] = _ir_id(document_id, native_id, "cell")
    for cell in profile["cells"]:
        native_id = str(cell["cell_id"])
        worksheet_id = str(cell["worksheet_id"])
        raw_value = cell.get("raw_value")
        value_kind = str(cell["value_kind"])
        text = (
            str(raw_value) if raw_value is not None and value_kind in {"string", "error"} else None
        )
        address = str(cell["source_address"])
        units.append(
            _unit(
                unit_id=cell_map[native_id],
                kind="cell",
                parent_id=worksheet_map.get(worksheet_id, root_id),
                ordinal=len(units),
                origin="native_projection",
                source_native_ids=[native_id],
                text=text,
                protected=value_kind == "formula",
                style_refs=list(cell.get("style_refs", [])),
                technical_properties=_properties(
                    [
                        ("cell.address", cell["address"]),
                        ("cell.value_kind", value_kind),
                        ("cell.raw_value", raw_value),
                        ("cell.cached_value", cell.get("cached_value")),
                        ("cell.formula_id", cell.get("formula_id")),
                        ("source.address", address),
                    ],
                    address=address,
                ),
            )
        )
        formula_id = cell.get("formula_id")
        if formula_id is None or str(formula_id) not in formulas:
            continue
        formula = formulas[str(formula_id)]
        formula_native_id = str(formula["formula_id"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, formula_native_id, "formula"),
                kind="formula",
                parent_id=cell_map[native_id],
                ordinal=0,
                origin="native_projection",
                source_native_ids=[formula_native_id],
                text=str(formula["source"]),
                protected=True,
                technical_properties=_properties(
                    [
                        ("formula.kind", formula["kind"]),
                        ("formula.dependency_refs", list(formula["dependency_refs"])),
                        ("formula.volatile", bool(formula.get("volatile", False))),
                        ("formula.recalculated", False),
                    ],
                    address=address,
                ),
            )
        )
    return units


def _project_presentation(profile: dict[str, Any], root_id: str) -> list[dict[str, Any]]:
    document_id = str(profile["document_id"])
    units: list[dict[str, Any]] = []
    slide_map: dict[str, str] = {}
    shape_map: dict[str, str] = {}
    slides_by_ordinal: dict[int, str] = {}
    for slide in profile["slides"]:
        native_id = str(slide["slide_id"])
        ir_id = _ir_id(document_id, native_id, "slide")
        slide_map[native_id] = ir_id
        slides_by_ordinal[int(slide["ordinal"])] = ir_id
        address = str(slide["source_address"])
        units.append(
            _unit(
                unit_id=ir_id,
                kind="slide",
                parent_id=root_id,
                ordinal=int(slide["ordinal"]),
                origin="native_projection",
                source_native_ids=[native_id],
                protected=bool(slide.get("hidden", False)),
                technical_properties=_properties(
                    [
                        ("slide.layout_ref", slide.get("layout_ref")),
                        ("slide.master_ref", slide.get("master_ref")),
                        ("slide.notes_ref", slide.get("notes_ref")),
                        ("slide.hidden", bool(slide.get("hidden", False))),
                        ("source.address", address),
                    ],
                    address=address,
                ),
            )
        )
    for shape in profile["shapes"]:
        native_id = str(shape["shape_id"])
        shape_map[native_id] = _ir_id(document_id, native_id, "shape")
    for shape in profile["shapes"]:
        native_id = str(shape["shape_id"])
        native_parent = shape.get("parent_shape_id")
        parent_id = shape_map.get(str(native_parent)) if native_parent else None
        if parent_id is None:
            parent_id = slide_map.get(str(shape["slide_id"]), root_id)
        address = str(shape["source_address"])
        text = shape.get("text")
        units.append(
            _unit(
                unit_id=shape_map[native_id],
                kind="text_shape" if text else "visual_object",
                parent_id=parent_id,
                ordinal=int(shape["ordinal"]),
                origin="native_projection",
                source_native_ids=[native_id],
                text=text,
                protected=False,
                style_refs=list(shape.get("style_refs", [])),
                resource_refs=list(shape.get("resource_refs", [])),
                technical_properties=_properties(
                    [
                        ("shape.native_kind", shape["kind"]),
                        ("source.address", address),
                    ],
                    address=address,
                ),
            )
        )
    for event_kind in ("transitions", "animations"):
        for event in profile["timing_model"][event_kind]:
            native_id = str(event["event_id"])
            ordinal = int(event["ordinal"])
            address = str(event["source_address"])
            units.append(
                _unit(
                    unit_id=_ir_id(document_id, native_id, event_kind[:-1]),
                    kind=event_kind[:-1],
                    parent_id=slides_by_ordinal.get(ordinal, root_id),
                    ordinal=ordinal,
                    origin="native_projection",
                    source_native_ids=[native_id],
                    protected=True,
                    technical_properties=_properties(
                        [
                            ("timing.kind", event["kind"]),
                            ("timing.trigger", event["trigger"]),
                            ("timing.duration_ms", event.get("duration_ms")),
                            ("timing.target_shape_ids", list(event["target_shape_ids"])),
                            ("source.address", address),
                        ],
                        address=address,
                    ),
                )
            )
    return units


def _project_fixed_layout(profile: dict[str, Any], root_id: str) -> list[dict[str, Any]]:
    document_id = str(profile["document_id"])
    units: list[dict[str, Any]] = []
    for page in profile["pages"]:
        native_id = str(page["page_id"])
        address = str(page["source_address"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, native_id, "fixed_page"),
                kind="fixed_page",
                parent_id=root_id,
                ordinal=int(page["ordinal"]),
                origin="native_projection",
                source_native_ids=[native_id],
                protected=False,
                technical_properties=[
                    _property("page.width", float(page["width_pt"]), unit="pt", address=address),
                    _property("page.height", float(page["height_pt"]), unit="pt", address=address),
                    _property(
                        "page.rotation", int(page["rotation"]), unit="degree", address=address
                    ),
                    _property("page.box_refs", list(page.get("box_refs", [])), address=address),
                    _property("source.address", address, address=address),
                ],
            )
        )
    return units


def _project_raster(profile: dict[str, Any], root_id: str) -> list[dict[str, Any]]:
    document_id = str(profile["document_id"])
    units: list[dict[str, Any]] = []
    for frame in profile["frames"]:
        native_id = str(frame["frame_id"])
        address = str(frame["source_address"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, native_id, "image_frame"),
                kind="image_frame",
                parent_id=root_id,
                ordinal=int(frame["ordinal"]),
                origin="native_projection",
                source_native_ids=[native_id],
                protected=True,
                resource_refs=[str(frame["icc_profile_ref"])]
                if frame.get("icc_profile_ref")
                else [],
                technical_properties=[
                    _property("frame.width", int(frame["width_px"]), unit="px", address=address),
                    _property("frame.height", int(frame["height_px"]), unit="px", address=address),
                    _property(
                        "frame.duration", frame.get("duration_ms"), unit="ms", address=address
                    ),
                    _property("frame.orientation", frame.get("orientation"), address=address),
                    _property(
                        "frame.surface_policy", profile["document_surface_policy"], address=address
                    ),
                    _property("source.address", address, address=address),
                ],
            )
        )
    return units


def _project_legacy_ole(profile: dict[str, Any], root_id: str) -> list[dict[str, Any]]:
    document_id = str(profile["document_id"])
    units: list[dict[str, Any]] = []
    storage_map: dict[str, str] = {}
    for storage in profile["storages"]:
        native_id = str(storage["storage_id"])
        storage_map[native_id] = _ir_id(document_id, native_id, "ole_storage")
    for ordinal, storage in enumerate(profile["storages"]):
        native_id = str(storage["storage_id"])
        parent_native = storage.get("parent_id")
        units.append(
            _unit(
                unit_id=storage_map[native_id],
                kind="ole_storage",
                parent_id=storage_map.get(str(parent_native), root_id)
                if parent_native
                else root_id,
                ordinal=ordinal,
                origin="native_projection",
                source_native_ids=[native_id],
                protected=True,
                technical_properties=_properties(
                    [
                        ("ole.path", storage["path"]),
                        ("ole.coverage_level", profile["coverage_level"]),
                    ],
                    address=str(storage["path"]),
                ),
            )
        )
    for ordinal, stream in enumerate(profile["streams"]):
        native_id = str(stream["stream_id"])
        address = str(stream["source_address"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, native_id, "ole_stream"),
                kind="ole_stream",
                parent_id=root_id,
                ordinal=ordinal,
                origin="native_projection",
                source_native_ids=[native_id],
                protected=True,
                technical_properties=_properties(
                    [
                        ("ole.path", stream["path"]),
                        ("ole.size_bytes", int(stream["size_bytes"])),
                        ("ole.sha256", stream.get("sha256")),
                        ("ole.read_state", stream["read_state"]),
                        ("source.address", address),
                    ],
                    address=address,
                ),
            )
        )
    return units


def _append_annotations(
    units: list[dict[str, Any]],
    document_id: str,
    root_id: str,
    annotations: dict[str, Any],
) -> None:
    native_to_ir = _native_map(units)
    start = len(units)
    for offset, annotation in enumerate(annotations["annotations"]):
        native_id = str(annotation["annotation_id"])
        target_ids = [str(item) for item in annotation["target_ids"]]
        parent_id = next(
            (native_to_ir[target] for target in target_ids if target in native_to_ir), root_id
        )
        address = str(annotation["source_address"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, native_id, "annotation"),
                kind=f"annotation_{annotation['kind']}",
                parent_id=parent_id,
                ordinal=start + offset,
                origin="native_projection",
                source_native_ids=[native_id],
                text=annotation.get("text"),
                protected=True,
                technical_properties=[
                    _property("annotation.owner_id", annotation["owner_id"], address=address),
                    _property("annotation.target_ids", target_ids, address=address),
                    _property("annotation.author", annotation.get("author"), address=address),
                    _property(
                        "annotation.created_at_native",
                        annotation.get("created_at_native"),
                        address=address,
                    ),
                    _property("source.address", address, address=address),
                    *list(annotation.get("properties", [])),
                ],
            )
        )


def _append_relationships(
    units: list[dict[str, Any]],
    document_id: str,
    root_id: str,
    relationships: dict[str, Any],
) -> None:
    native_to_ir = _native_map(units)
    start = len(units)
    for offset, relationship in enumerate(relationships["relationships"]):
        native_id = str(relationship["relationship_id"])
        source_id = str(relationship["source_id"])
        address = str(relationship["source_address"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, native_id, "relationship"),
                kind="external_relationship" if relationship["external"] else "relationship",
                parent_id=native_to_ir.get(source_id, root_id),
                ordinal=start + offset,
                origin="native_projection",
                source_native_ids=[native_id],
                protected=bool(relationship["external"]),
                technical_properties=_properties(
                    [
                        ("relationship.source_id", source_id),
                        ("relationship.target_id", relationship["target_id"]),
                        ("relationship.type", relationship["relation_type"]),
                        ("relationship.external", bool(relationship["external"])),
                        ("source.address", address),
                    ],
                    address=address,
                ),
            )
        )


def _append_resources(
    units: list[dict[str, Any]],
    document_id: str,
    root_id: str,
    resources: dict[str, Any],
) -> None:
    native_to_ir = _native_map(units)
    resources_by_id = {str(item["resource_id"]): item for item in resources["resources"]}
    represented: set[str] = set()
    start = len(units)
    for offset, occurrence in enumerate(resources["occurrences"]):
        resource_id = str(occurrence["resource_id"])
        resource = resources_by_id.get(resource_id)
        if resource is None:
            raise ProjectionError(
                f"Occurrence {occurrence['occurrence_id']} vers ressource absente {resource_id}"
            )
        represented.add(resource_id)
        native_id = str(occurrence["occurrence_id"])
        owner_id = str(occurrence["owner_id"])
        address = str(occurrence["source_address"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, native_id, "resource_occurrence"),
                kind=f"resource_{resource['kind']}",
                parent_id=native_to_ir.get(owner_id, root_id),
                ordinal=start + offset,
                origin="native_projection",
                source_native_ids=[native_id, resource_id],
                protected=bool(resource["active"]) or str(resource["kind"]) != "text",
                resource_refs=[resource_id],
                technical_properties=_properties(
                    [
                        ("resource.kind", resource["kind"]),
                        ("resource.media_type", resource.get("media_type")),
                        ("resource.size_bytes", resource.get("size_bytes")),
                        ("resource.sha256", resource.get("sha256")),
                        ("resource.active", bool(resource["active"])),
                        ("resource.opaque", bool(resource["opaque"])),
                        ("resource.geometry_ref", occurrence.get("geometry_ref")),
                        ("source.address", address),
                    ],
                    address=address,
                ),
            )
        )
    ordinal = len(units)
    for resource_id, resource in resources_by_id.items():
        if resource_id in represented:
            continue
        address = str(resource["source_address"])
        units.append(
            _unit(
                unit_id=_ir_id(document_id, resource_id, "resource"),
                kind=f"resource_{resource['kind']}",
                parent_id=root_id,
                ordinal=ordinal,
                origin="native_projection",
                source_native_ids=[resource_id],
                protected=bool(resource["active"]) or str(resource["kind"]) != "text",
                resource_refs=[resource_id],
                technical_properties=_properties(
                    [
                        ("resource.kind", resource["kind"]),
                        ("resource.media_type", resource.get("media_type")),
                        ("resource.size_bytes", resource.get("size_bytes")),
                        ("resource.sha256", resource.get("sha256")),
                        ("resource.active", bool(resource["active"])),
                        ("resource.opaque", bool(resource["opaque"])),
                        ("source.address", address),
                    ],
                    address=address,
                ),
            )
        )
        ordinal += 1


def validate_ir_invariants(ir_body: dict[str, Any]) -> None:
    units = list(ir_body["units"])
    ids = [str(unit["unit_id"]) for unit in units]
    if len(ids) != len(set(ids)):
        raise ProjectionError("Identifiants IR dupliqués")
    unit_ids = set(ids)
    roots = [str(item) for item in ir_body["root_unit_ids"]]
    if not roots or any(root not in unit_ids for root in roots):
        raise ProjectionError("Racine IR absente ou orpheline")
    for unit in units:
        origin = str(unit["origin"])
        source_ids = list(unit["source_native_ids"])
        if origin == "native_projection" and not source_ids:
            raise ProjectionError(f"Unité native sans source: {unit['unit_id']}")
        if origin == "synthetic" and source_ids:
            raise ProjectionError(f"Unité synthétique avec source native: {unit['unit_id']}")
        parent_id = unit.get("parent_id")
        if parent_id is not None and str(parent_id) not in unit_ids:
            raise ProjectionError(f"Parent IR orphelin: {unit['unit_id']} -> {parent_id}")
        if parent_id == unit["unit_id"]:
            raise ProjectionError(f"Auto-parent interdit: {unit['unit_id']}")
    for unit in units:
        visited: set[str] = set()
        current = unit
        while current.get("parent_id") is not None:
            current_id = str(current["unit_id"])
            if current_id in visited:
                raise ProjectionError(f"Cycle hiérarchique IR détecté depuis {unit['unit_id']}")
            visited.add(current_id)
            parent = str(current["parent_id"])
            current = units[ids.index(parent)]


def project_document(
    native_document: dict[str, Any],
    profile: dict[str, Any],
    styles: dict[str, Any],
    relationships: dict[str, Any],
    annotations: dict[str, Any],
    resources: dict[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    document_id = str(native_document["document_id"])
    if str(profile["document_id"]) != document_id:
        raise ProjectionError("Profil natif rattaché à un autre document")
    for catalog in (styles, relationships, annotations, resources):
        if str(catalog["document_id"]) != document_id:
            raise ProjectionError("Catalogue natif rattaché à un autre document")

    profile_kind = str(native_document["profile_kind"])
    root = _root_unit(document_id, profile_kind)
    root_id = str(root["unit_id"])
    units = [root]
    warnings: list[str] = []

    projector = {
        "plain_text": _project_plain_text,
        "wordprocessing": _project_wordprocessing,
        "spreadsheet": _project_spreadsheet,
        "presentation": _project_presentation,
        "fixed_layout": _project_fixed_layout,
        "raster": _project_raster,
        "legacy_ole": _project_legacy_ole,
    }.get(profile_kind)
    if projector is None:
        raise ProjectionError(f"Profil natif non projetable: {profile_kind}")
    units.extend(projector(profile, root_id))
    _append_annotations(units, document_id, root_id, annotations)
    _append_relationships(units, document_id, root_id, relationships)
    _append_resources(units, document_id, root_id, resources)

    known_style_ids = {str(item["style_id"]) for item in styles["styles"]}
    known_resource_ids = {str(item["resource_id"]) for item in resources["resources"]}
    for unit in units:
        unresolved_styles = [
            item for item in unit["style_refs"] if str(item) not in known_style_ids
        ]
        unresolved_resources = [
            item for item in unit["resource_refs"] if str(item) not in known_resource_ids
        ]
        if unresolved_styles:
            warnings.append(
                f"{unit['unit_id']}: styles non résolus: {','.join(map(str, unresolved_styles))}"
            )
            unit["technical_properties"].append(
                _property(
                    "projection.unresolved_style_refs",
                    list(map(str, unresolved_styles)),
                    source="derived",
                )
            )
        if unresolved_resources:
            warnings.append(
                f"{unit['unit_id']}: ressources non résolues: {','.join(map(str, unresolved_resources))}"
            )
            unit["technical_properties"].append(
                _property(
                    "projection.unresolved_resource_refs",
                    list(map(str, unresolved_resources)),
                    source="derived",
                )
            )

    root["technical_properties"].extend(
        [
            _property("projection.unit_count", len(units), source="derived"),
            _property("projection.warning_count", len(warnings), source="derived"),
            _property("projection.semantic_interpretation", False, source="derived"),
            _property("projection.ocr_executed", False, source="derived"),
            _property("projection.formula_recalculation", False, source="derived"),
        ]
    )
    body = {"document_id": document_id, "root_unit_ids": [root_id], "units": units}
    validate_ir_invariants(body)
    return body, tuple(sorted(set(warnings)))
