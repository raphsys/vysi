from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, cast

from .models import LayerEntity, LayerName


@dataclass(frozen=True)
class RepresentationInventory:
    entities: tuple[LayerEntity, ...]

    def ids(self, layer: LayerName) -> frozenset[str]:
        return frozenset(item.entity_id for item in self.entities if item.layer == layer)

    def entities_for(self, layer: LayerName) -> tuple[LayerEntity, ...]:
        return tuple(item for item in self.entities if item.layer == layer)

    def layers_for_id(self, entity_id: str) -> tuple[LayerName, ...]:
        return tuple(sorted({item.layer for item in self.entities if item.entity_id == entity_id}))

    def entity(self, layer: LayerName, entity_id: str) -> LayerEntity | None:
        return next(
            (item for item in self.entities if item.layer == layer and item.entity_id == entity_id),
            None,
        )


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _entity(
    identifier: Any,
    kind: str,
    evidence_ref: str,
    *,
    source_address: Any = None,
    owner_id: Any = None,
) -> LayerEntity:
    if not isinstance(identifier, str) or not identifier:
        raise ValueError(f"Identifiant natif invalide pour {kind}")
    return LayerEntity(
        "native",
        identifier,
        kind,
        _string(source_address),
        _string(owner_id),
        evidence_ref,
    )


def _profile_entities(profile: dict[str, Any], evidence_ref: str) -> list[LayerEntity]:
    """Inventorie uniquement les objets définis par le profil.

    Les clés étrangères (`worksheet_id` dans une cellule, `slide_id` dans une
    forme, etc.) ne créent jamais une seconde entité. Cette distinction entre
    identité d'objet et référence est indispensable pour éviter de fabriquer
    des représentations contradictoires.
    """

    kind = str(profile.get("profile_kind"))
    result: list[LayerEntity] = []

    if kind == "plain_text":
        for line in cast(list[dict[str, Any]], profile.get("lines", [])):
            start = int(line["byte_start"])
            end = int(line["byte_end"])
            result.append(
                _entity(
                    line["unit_id"],
                    "line",
                    evidence_ref,
                    source_address=f"bytes:{start}-{end}",
                )
            )

    elif kind == "wordprocessing":
        for section in cast(list[dict[str, Any]], profile.get("sections", [])):
            result.append(
                _entity(
                    section["section_id"],
                    "section",
                    evidence_ref,
                    source_address=section.get("source_address"),
                )
            )
        for block in cast(list[dict[str, Any]], profile.get("blocks", [])):
            result.append(
                _entity(
                    block["unit_id"],
                    str(block.get("kind") or "wordprocessing_unit"),
                    evidence_ref,
                    source_address=block.get("source_address"),
                    owner_id=block.get("parent_id"),
                )
            )
        for revision in cast(list[dict[str, Any]], profile.get("revisions", [])):
            result.append(
                _entity(
                    revision["revision_id"],
                    "revision",
                    evidence_ref,
                    source_address=revision.get("source_address"),
                )
            )
        for annotation in cast(list[dict[str, Any]], profile.get("annotations", [])):
            result.append(
                _entity(
                    annotation["annotation_id"],
                    "annotation",
                    evidence_ref,
                    source_address=annotation.get("source_address"),
                )
            )

    elif kind == "spreadsheet":
        cells = cast(list[dict[str, Any]], profile.get("cells", []))
        cells_by_id = {str(item["cell_id"]): item for item in cells}
        for worksheet in cast(list[dict[str, Any]], profile.get("worksheets", [])):
            result.append(
                _entity(
                    worksheet["worksheet_id"],
                    "worksheet",
                    evidence_ref,
                    source_address=worksheet.get("source_address"),
                )
            )
        for cell in cells:
            result.append(
                _entity(
                    cell["cell_id"],
                    "cell",
                    evidence_ref,
                    source_address=cell.get("source_address"),
                    owner_id=cell.get("worksheet_id"),
                )
            )
        calculation = cast(dict[str, Any], profile.get("calculation_model", {}))
        for formula in cast(list[dict[str, Any]], calculation.get("formulas", [])):
            cell = cells_by_id.get(str(formula.get("cell_id")), {})
            result.append(
                _entity(
                    formula["formula_id"],
                    "formula",
                    evidence_ref,
                    source_address=cell.get("source_address"),
                    owner_id=formula.get("cell_id"),
                )
            )

    elif kind == "presentation":
        for slide in cast(list[dict[str, Any]], profile.get("slides", [])):
            result.append(
                _entity(
                    slide["slide_id"],
                    "slide",
                    evidence_ref,
                    source_address=slide.get("source_address"),
                )
            )
        for shape in cast(list[dict[str, Any]], profile.get("shapes", [])):
            owner = shape.get("parent_shape_id") or shape.get("slide_id")
            result.append(
                _entity(
                    shape["shape_id"],
                    "shape",
                    evidence_ref,
                    source_address=shape.get("source_address"),
                    owner_id=owner,
                )
            )
        timing = cast(dict[str, Any], profile.get("timing_model", {}))
        for collection in ("animations", "transitions"):
            for event in cast(list[dict[str, Any]], timing.get(collection, [])):
                targets = cast(list[str], event.get("target_shape_ids", []))
                result.append(
                    _entity(
                        event["event_id"],
                        "animation" if collection == "animations" else "transition",
                        evidence_ref,
                        source_address=event.get("source_address"),
                        owner_id=targets[0] if len(targets) == 1 else None,
                    )
                )

    elif kind == "fixed_layout":
        for page in cast(list[dict[str, Any]], profile.get("pages", [])):
            result.append(
                _entity(
                    page["page_id"],
                    "page",
                    evidence_ref,
                    source_address=page.get("source_address"),
                )
            )

    elif kind == "raster":
        for frame in cast(list[dict[str, Any]], profile.get("frames", [])):
            result.append(
                _entity(
                    frame["frame_id"],
                    "frame",
                    evidence_ref,
                    source_address=frame.get("source_address"),
                )
            )

    elif kind == "legacy_ole":
        for storage in cast(list[dict[str, Any]], profile.get("storages", [])):
            result.append(
                _entity(
                    storage["storage_id"],
                    "storage",
                    evidence_ref,
                    source_address=storage.get("path"),
                    owner_id=storage.get("parent_id"),
                )
            )
        for stream in cast(list[dict[str, Any]], profile.get("streams", [])):
            result.append(
                _entity(
                    stream["stream_id"],
                    "stream",
                    evidence_ref,
                    source_address=stream.get("source_address") or stream.get("path"),
                )
            )
    else:
        raise ValueError(f"Profil natif non inventoriable: {kind}")

    return result


def _catalog_entities(
    values: list[dict[str, Any]],
    *,
    id_key: str,
    kind: str,
    evidence_ref: str,
) -> list[LayerEntity]:
    result: list[LayerEntity] = []
    for value in values:
        identifier = str(value[id_key])
        result.append(
            LayerEntity(
                "native",
                identifier,
                kind,
                _string(value.get("source_address")),
                _string(value.get("owner_id")),
                evidence_ref,
            )
        )
    return result


def _merge_entities(entities: list[LayerEntity]) -> tuple[LayerEntity, ...]:
    unique: dict[tuple[LayerName, str], LayerEntity] = {}
    for entity in entities:
        key = (entity.layer, entity.entity_id)
        previous = unique.get(key)
        if previous is None:
            unique[key] = entity
            continue
        if previous.kind != entity.kind:
            raise ValueError(
                f"Identifiant dupliqué avec types divergents: {entity.layer}:{entity.entity_id}"
            )
        addresses = {value for value in (previous.source_address, entity.source_address) if value}
        owners = {value for value in (previous.owner_id, entity.owner_id) if value}
        if len(addresses) > 1 or len(owners) > 1:
            raise ValueError(
                f"Identifiant dupliqué avec définitions divergentes: {entity.layer}:{entity.entity_id}"
            )
        unique[key] = LayerEntity(
            entity.layer,
            entity.entity_id,
            entity.kind,
            next(iter(addresses), None),
            next(iter(owners), None),
            min(previous.evidence_ref, entity.evidence_ref),
        )
    return tuple(sorted(unique.values()))


def build_inventory(
    *,
    artifacts: list[dict[str, Any]],
    container: dict[str, Any] | None,
    native: dict[str, Any],
    profile: dict[str, Any],
    styles: dict[str, Any],
    relationships: dict[str, Any],
    metadata: dict[str, Any],
    annotations: dict[str, Any],
    resources: dict[str, Any],
    ir: dict[str, Any],
    rendered: dict[str, Any] | None,
    geometry: dict[str, Any] | None,
    assets: dict[str, Any] | None,
    evidence: dict[str, str],
) -> RepresentationInventory:
    entities: list[LayerEntity] = []
    for item in artifacts:
        entities.append(
            LayerEntity(
                "binary",
                str(item["artifact_id"]),
                "artifact",
                str(item["stored_path"]),
                None,
                evidence["bundle"],
            )
        )
    if container is not None:
        for item in container.get("parts", []):
            entities.append(
                LayerEntity(
                    "container",
                    str(item["part_id"]),
                    "part",
                    str(item["path"]),
                    str(item["parent_part_id"]) if item.get("parent_part_id") else None,
                    evidence["container"],
                )
            )
        for item in container.get("relationships", []):
            entities.append(
                LayerEntity(
                    "container",
                    str(item["relationship_id"]),
                    "container_relationship",
                    None,
                    str(item["source_part_id"]),
                    evidence["container"],
                )
            )

    entities.extend(_profile_entities(profile, evidence["profile"]))
    entities.extend(
        _catalog_entities(
            cast(list[dict[str, Any]], styles.get("styles", [])),
            id_key="style_id",
            kind="style",
            evidence_ref=evidence["styles"],
        )
    )
    entities.extend(
        _catalog_entities(
            cast(list[dict[str, Any]], relationships.get("relationships", [])),
            id_key="relationship_id",
            kind="relationship",
            evidence_ref=evidence["relationships"],
        )
    )
    entities.extend(
        _catalog_entities(
            cast(list[dict[str, Any]], metadata.get("items", [])),
            id_key="metadata_id",
            kind="metadata",
            evidence_ref=evidence["metadata"],
        )
    )
    entities.extend(
        _catalog_entities(
            cast(list[dict[str, Any]], annotations.get("annotations", [])),
            id_key="annotation_id",
            kind="annotation",
            evidence_ref=evidence["annotations"],
        )
    )
    entities.extend(
        _catalog_entities(
            cast(list[dict[str, Any]], resources.get("resources", [])),
            id_key="resource_id",
            kind="resource",
            evidence_ref=evidence["resources"],
        )
    )
    entities.extend(
        _catalog_entities(
            cast(list[dict[str, Any]], resources.get("occurrences", [])),
            id_key="occurrence_id",
            kind="resource_occurrence",
            evidence_ref=evidence["resources"],
        )
    )

    # `opaque_parts` décrit un état de préservation et non une nouvelle nature
    # d'objet. On ne crée une entité opaque que si le profil ne définit pas déjà
    # le même identifiant (cas des storages/streams OLE).
    existing_native_ids = {item.entity_id for item in entities if item.layer == "native"}
    for item in native.get("opaque_parts", []):
        identifier = str(item["opaque_id"])
        if identifier in existing_native_ids:
            continue
        entities.append(
            LayerEntity(
                "native",
                identifier,
                "opaque_part",
                str(item["source_address"]),
                None,
                evidence["native"],
            )
        )
        existing_native_ids.add(identifier)

    for item in ir.get("units", []):
        entities.append(
            LayerEntity(
                "technical_ir",
                str(item["unit_id"]),
                str(item["kind"]),
                None,
                str(item["parent_id"]) if item.get("parent_id") else None,
                evidence["ir"],
            )
        )

    if rendered is not None:
        for item in rendered.get("views", []):
            entities.append(
                LayerEntity(
                    "rendered", str(item["view_id"]), "view", None, None, evidence["rendered"]
                )
            )
        for item in rendered.get("surfaces", []):
            entities.append(
                LayerEntity(
                    "rendered",
                    str(item["surface_id"]),
                    "surface",
                    None,
                    str(item["view_id"]),
                    evidence["rendered"],
                )
            )

    if geometry is not None:
        for item in geometry.get("coordinate_spaces", []):
            entities.append(
                LayerEntity(
                    "geometry",
                    str(item["coordinate_space_id"]),
                    "coordinate_space",
                    None,
                    str(item["owner_id"]),
                    evidence["geometry"],
                )
            )
        for item in geometry.get("geometries", []):
            entities.append(
                LayerEntity(
                    "geometry",
                    str(item["geometry_id"]),
                    "geometry",
                    None,
                    str(item["owner_id"]),
                    evidence["geometry"],
                )
            )

    if assets is not None:
        for item in assets.get("assets", []):
            entities.append(
                LayerEntity("asset", str(item["asset_id"]), "asset", None, None, evidence["assets"])
            )

    return RepresentationInventory(_merge_entities(entities))


def effective_native_addresses(inventory: RepresentationInventory) -> dict[str, str | None]:
    native = {item.entity_id: item for item in inventory.entities_for("native")}
    resolved: dict[str, str | None] = {}

    def resolve(identifier: str, stack: frozenset[str]) -> str | None:
        if identifier in resolved:
            return resolved[identifier]
        if identifier in stack:
            return None
        item = native[identifier]
        if item.source_address:
            resolved[identifier] = item.source_address
            return item.source_address
        if item.owner_id and item.owner_id in native:
            address = resolve(item.owner_id, stack | {identifier})
            resolved[identifier] = address
            return address
        resolved[identifier] = None
        return None

    for identifier in native:
        resolve(identifier, frozenset())
    return resolved


def group_by_kind(
    inventory: RepresentationInventory, layer: LayerName
) -> dict[str, frozenset[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for item in inventory.entities_for(layer):
        grouped[item.kind].add(item.entity_id)
    return {key: frozenset(value) for key, value in grouped.items()}
