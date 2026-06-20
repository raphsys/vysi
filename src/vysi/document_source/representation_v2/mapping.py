from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any, cast

from vysi.document_source.contracts_v2.identities import stable_id

from .inventory import RepresentationInventory, effective_native_addresses
from .models import Exactness, LayerName, MappingEdge, cardinality


class MappingError(ValueError):
    pass


def _portable_evidence(value: str) -> bool:
    return (
        bool(value)
        and not value.startswith("/")
        and ".." not in value.replace("\\", "/").split("/")
    )


def _normalize_part_path(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.replace("\\", "/")
    if "#" in candidate:
        candidate = candidate.split("#", 1)[0]
    candidate = candidate.strip().lstrip("/")
    if not candidate or candidate.startswith("bytes:"):
        return None
    return candidate


def _mapping_identity(
    *,
    document_id: str,
    source_layer: str,
    source_ids: tuple[str, ...],
    target_layer: str,
    target_ids: tuple[str, ...],
    relation: str,
    method: str,
    producer_version: str,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "source_layer": source_layer,
        "source_ids": source_ids,
        "target_layer": target_layer,
        "target_ids": target_ids,
        "relation": relation,
        "method": method,
        "producer": "vysi.document_source.ds12",
        "producer_version": producer_version,
    }


def _edge(
    *,
    document_id: str,
    producer_version: str,
    source_layer: LayerName,
    source_ids: Iterable[str],
    target_layer: LayerName,
    target_ids: Iterable[str],
    relation: str,
    exactness: Exactness,
    confidence: float,
    method: str,
    evidence_refs: Iterable[str],
) -> MappingEdge:
    sources = tuple(sorted(set(source_ids)))
    targets = tuple(sorted(set(target_ids)))
    evidence = tuple(sorted(set(evidence_refs)))
    if not sources or not targets:
        raise MappingError("Une arête de mapping exige au moins une source et une cible")
    if not 0.0 <= confidence <= 1.0:
        raise MappingError("Confiance de mapping hors limites")
    if exactness == "exact" and confidence != 1.0:
        raise MappingError("Un mapping exact doit avoir une confiance de 1.0")
    if not evidence or not all(_portable_evidence(item) for item in evidence):
        raise MappingError("Toute arête exige des preuves portables")
    identity = _mapping_identity(
        document_id=document_id,
        source_layer=source_layer,
        source_ids=sources,
        target_layer=target_layer,
        target_ids=targets,
        relation=relation,
        method=method,
        producer_version=producer_version,
    )
    return MappingEdge(
        mapping_id=stable_id("mapping", identity),
        source_layer=source_layer,
        source_ids=sources,
        target_layer=target_layer,
        target_ids=targets,
        relation=relation,
        cardinality=cardinality(len(sources), len(targets)),
        exactness=exactness,
        confidence=confidence,
        method=method,
        producer="vysi.document_source.ds12",
        producer_version=producer_version,
        determinism="deterministic",
        evidence_refs=evidence,
    )


def _add_grouped_native_origin_edges(
    *,
    edges: list[MappingEdge],
    document_id: str,
    producer_version: str,
    inventory: RepresentationInventory,
    container: dict[str, Any] | None,
    evidence_refs: tuple[str, ...],
) -> None:
    native_addresses = effective_native_addresses(inventory)
    native_entities = inventory.entities_for("native")
    artifact_ids = inventory.ids("binary")
    part_entities = tuple(
        item for item in inventory.entities_for("container") if item.kind == "part"
    )
    part_by_path = {
        _normalize_part_path(item.source_address): item.entity_id
        for item in part_entities
        if _normalize_part_path(item.source_address)
    }
    container_relationship_ids = {
        item.entity_id
        for item in inventory.entities_for("container")
        if item.kind == "container_relationship"
    }
    grouped: dict[tuple[str, Exactness, float, str], list[str]] = defaultdict(list)
    for item in native_entities:
        address = native_addresses.get(item.entity_id)
        normalized = _normalize_part_path(address)
        matched = part_by_path.get(normalized)
        relationship_match: str | None = None
        if address and address.startswith("container_relationship:"):
            candidate = address.split(":", 1)[1]
            if candidate in container_relationship_ids:
                relationship_match = candidate
        if matched is not None:
            grouped[(matched, "exact", 1.0, "native_source_address")].append(item.entity_id)
        elif relationship_match is not None:
            grouped[(relationship_match, "exact", 1.0, "native_container_relationship_ref")].append(
                item.entity_id
            )
        elif len(part_entities) == 1:
            # A single physical part is the unambiguous authority for all native
            # objects decoded from that document, even when their source address
            # is an internal page/frame/byte address rather than the part path.
            grouped[(part_entities[0].entity_id, "exact", 1.0, "single_physical_part")].append(
                item.entity_id
            )
        elif part_entities:
            grouped[("*", "inferred", 0.5, "container_scope_fallback")].append(item.entity_id)
        elif artifact_ids:
            edges.append(
                _edge(
                    document_id=document_id,
                    producer_version=producer_version,
                    source_layer="binary",
                    source_ids=artifact_ids,
                    target_layer="native",
                    target_ids=[item.entity_id],
                    relation="decoded_as_native",
                    exactness="inferred",
                    confidence=0.5,
                    method="binary_scope_fallback",
                    evidence_refs=(*evidence_refs, item.evidence_ref),
                )
            )
        else:
            raise MappingError(f"Aucune origine disponible pour l'unité native {item.entity_id}")
    for (part_id, exactness, confidence, method), target_ids in sorted(grouped.items()):
        source_ids = [part_id] if part_id != "*" else [item.entity_id for item in part_entities]
        edges.append(
            _edge(
                document_id=document_id,
                producer_version=producer_version,
                source_layer="container",
                source_ids=source_ids,
                target_layer="native",
                target_ids=target_ids,
                relation="decodes_as_native",
                exactness=exactness,
                confidence=confidence,
                method=method,
                evidence_refs=evidence_refs,
            )
        )


def _layer_for_reference(inventory: RepresentationInventory, identifier: str) -> LayerName:
    layers = inventory.layers_for_id(identifier)
    if len(layers) != 1:
        if not layers:
            raise MappingError(f"Référence de représentation inconnue: {identifier}")
        raise MappingError(f"Référence ambiguë entre couches: {identifier} -> {layers}")
    return layers[0]


def build_mapping_catalog(
    *,
    document_id: str,
    producer_version: str,
    inventory: RepresentationInventory,
    container: dict[str, Any] | None,
    native: dict[str, Any],
    ir: dict[str, Any],
    rendered: dict[str, Any] | None,
    geometry: dict[str, Any] | None,
    assets: dict[str, Any] | None,
    evidence_refs: list[str],
) -> dict[str, Any]:
    evidence = tuple(sorted(set(evidence_refs)))
    edges: list[MappingEdge] = []
    artifact_ids = inventory.ids("binary")
    container_ids = inventory.ids("container")
    if container_ids:
        if not artifact_ids:
            raise MappingError("Un conteneur ne peut pas être cartographié sans artefact binaire")
        exactness: Exactness = "exact" if len(artifact_ids) == 1 else "inferred"
        edges.append(
            _edge(
                document_id=document_id,
                producer_version=producer_version,
                source_layer="binary",
                source_ids=artifact_ids,
                target_layer="container",
                target_ids=container_ids,
                relation="contains_container_entities",
                exactness=exactness,
                confidence=1.0 if exactness == "exact" else 0.8,
                method="container_catalog_membership",
                evidence_refs=evidence,
            )
        )

    _add_grouped_native_origin_edges(
        edges=edges,
        document_id=document_id,
        producer_version=producer_version,
        inventory=inventory,
        container=container,
        evidence_refs=evidence,
    )

    known_native = inventory.ids("native")
    ir_units = cast(list[dict[str, Any]], ir.get("units", []))
    for unit in ir_units:
        unit_id = str(unit["unit_id"])
        sources = tuple(str(item) for item in unit.get("source_native_ids", []))
        unknown = set(sources) - set(known_native)
        if unknown:
            raise MappingError(
                f"L'unité IR {unit_id} référence des unités natives inconnues: {sorted(unknown)}"
            )
        if sources:
            edges.append(
                _edge(
                    document_id=document_id,
                    producer_version=producer_version,
                    source_layer="native",
                    source_ids=sources,
                    target_layer="technical_ir",
                    target_ids=[unit_id],
                    relation="projects_to",
                    exactness="exact",
                    confidence=1.0,
                    method="technical_ir_source_native_ids",
                    evidence_refs=evidence,
                )
            )
        for style_id in sorted(set(str(item) for item in unit.get("style_refs", []))):
            if style_id not in known_native:
                raise MappingError(f"Style IR inconnu: {style_id}")
            edges.append(
                _edge(
                    document_id=document_id,
                    producer_version=producer_version,
                    source_layer="native",
                    source_ids=[style_id],
                    target_layer="technical_ir",
                    target_ids=[unit_id],
                    relation="applies_style_to",
                    exactness="exact",
                    confidence=1.0,
                    method="technical_ir_style_refs",
                    evidence_refs=evidence,
                )
            )
        for resource_id in sorted(set(str(item) for item in unit.get("resource_refs", []))):
            if resource_id not in known_native:
                raise MappingError(f"Ressource IR inconnue: {resource_id}")
            edges.append(
                _edge(
                    document_id=document_id,
                    producer_version=producer_version,
                    source_layer="native",
                    source_ids=[resource_id],
                    target_layer="technical_ir",
                    target_ids=[unit_id],
                    relation="uses_resource_in",
                    exactness="exact",
                    confidence=1.0,
                    method="technical_ir_resource_refs",
                    evidence_refs=evidence,
                )
            )

    root_native_ids = tuple(str(item) for item in native.get("root_unit_ids", []))
    synthetic_roots = tuple(
        str(item["unit_id"])
        for item in ir_units
        if item.get("parent_id") is None and item.get("origin") == "synthetic"
    )
    if synthetic_roots and root_native_ids:
        edges.append(
            _edge(
                document_id=document_id,
                producer_version=producer_version,
                source_layer="native",
                source_ids=root_native_ids,
                target_layer="technical_ir",
                target_ids=synthetic_roots,
                relation="organizes_under_synthetic_root",
                exactness="exact",
                confidence=1.0,
                method="technical_ir_root_organization",
                evidence_refs=evidence,
            )
        )

    if rendered is not None:
        for surface in cast(list[dict[str, Any]], rendered.get("surfaces", [])):
            surface_id = str(surface["surface_id"])
            sources = tuple(str(item) for item in surface.get("native_unit_refs", []))
            if sources:
                unknown = set(sources) - set(known_native)
                if unknown:
                    raise MappingError(
                        f"Surface {surface_id} référence des unités natives inconnues"
                    )
                exactness = "exact"
                confidence = 1.0
                method = "rendered_surface_native_refs"
            elif root_native_ids:
                sources = root_native_ids
                exactness = "inferred"
                confidence = 0.5
                method = "rendered_surface_root_fallback"
            else:
                raise MappingError(f"Surface rendue sans mapping minimal: {surface_id}")
            edges.append(
                _edge(
                    document_id=document_id,
                    producer_version=producer_version,
                    source_layer="native",
                    source_ids=sources,
                    target_layer="rendered",
                    target_ids=[surface_id],
                    relation="renders_on_surface",
                    exactness=exactness,
                    confidence=confidence,
                    method=method,
                    evidence_refs=evidence,
                )
            )

    if geometry is not None:
        for space in cast(list[dict[str, Any]], geometry.get("coordinate_spaces", [])):
            owner_id = str(space["owner_id"])
            source_layer = _layer_for_reference(inventory, owner_id)
            edges.append(
                _edge(
                    document_id=document_id,
                    producer_version=producer_version,
                    source_layer=source_layer,
                    source_ids=[owner_id],
                    target_layer="geometry",
                    target_ids=[str(space["coordinate_space_id"])],
                    relation="defines_coordinate_space",
                    exactness="exact",
                    confidence=1.0,
                    method="geometry_owner_reference",
                    evidence_refs=evidence,
                )
            )
        for item in cast(list[dict[str, Any]], geometry.get("geometries", [])):
            owner_id = str(item["owner_id"])
            source_layer = _layer_for_reference(inventory, owner_id)
            source = str(item.get("source", "native"))
            exactness = "inferred" if source == "inferred" else "exact"
            confidence = float(item.get("confidence", 1.0))
            if exactness == "exact":
                confidence = 1.0
            edges.append(
                _edge(
                    document_id=document_id,
                    producer_version=producer_version,
                    source_layer=source_layer,
                    source_ids=[owner_id],
                    target_layer="geometry",
                    target_ids=[str(item["geometry_id"])],
                    relation="has_geometry",
                    exactness=exactness,
                    confidence=confidence,
                    method=f"geometry_{source}",
                    evidence_refs=evidence,
                )
            )

    if assets is not None:
        surfaces = {
            str(surface["surface_id"]): set(str(item) for item in surface.get("asset_refs", []))
            for surface in cast(list[dict[str, Any]], (rendered or {}).get("surfaces", []))
        }
        for surface_id, asset_ids in sorted(surfaces.items()):
            for asset_id in sorted(asset_ids):
                if asset_id not in inventory.ids("asset"):
                    raise MappingError(f"Asset de surface inconnu: {asset_id}")
                edges.append(
                    _edge(
                        document_id=document_id,
                        producer_version=producer_version,
                        source_layer="rendered",
                        source_ids=[surface_id],
                        target_layer="asset",
                        target_ids=[asset_id],
                        relation="materializes_as_asset",
                        exactness="exact",
                        confidence=1.0,
                        method="rendered_surface_asset_refs",
                        evidence_refs=evidence,
                    )
                )
        for asset in cast(list[dict[str, Any]], assets.get("assets", [])):
            asset_id = str(asset["asset_id"])
            grouped: dict[LayerName, list[str]] = defaultdict(list)
            for source_id in sorted(set(str(item) for item in asset.get("input_refs", []))):
                layers = inventory.layers_for_id(source_id)
                if len(layers) == 1 and layers[0] != "asset":
                    grouped[layers[0]].append(source_id)
            for source_layer, source_ids in sorted(grouped.items()):
                edges.append(
                    _edge(
                        document_id=document_id,
                        producer_version=producer_version,
                        source_layer=source_layer,
                        source_ids=source_ids,
                        target_layer="asset",
                        target_ids=[asset_id],
                        relation="derives_asset",
                        exactness="exact",
                        confidence=1.0,
                        method="derived_asset_input_refs",
                        evidence_refs=evidence,
                    )
                )

    body = {
        "document_id": document_id,
        "mappings": [item.to_dict() for item in sorted(edges, key=lambda edge: edge.mapping_id)],
    }
    validate_mapping_invariants(body, inventory=inventory, producer_version=producer_version)
    return body


def validate_mapping_invariants(
    body: dict[str, Any],
    *,
    inventory: RepresentationInventory | None = None,
    layer_ids: dict[str, set[str]] | None = None,
    producer_version: str | None = None,
) -> None:
    mappings = cast(list[dict[str, Any]], body.get("mappings", []))
    identifiers = [str(item["mapping_id"]) for item in mappings]
    if len(identifiers) != len(set(identifiers)):
        raise MappingError("Identifiants de mapping dupliqués")
    seen_edges: set[tuple[Any, ...]] = set()
    available: dict[str, set[str]] = {}
    if inventory is not None:
        for layer in (
            "binary",
            "container",
            "native",
            "technical_ir",
            "rendered",
            "geometry",
            "asset",
        ):
            available[layer] = set(inventory.ids(layer))
    elif layer_ids is not None:
        available = layer_ids
    for item in mappings:
        source_ids = tuple(str(value) for value in item["source_ids"])
        target_ids = tuple(str(value) for value in item["target_ids"])
        if not source_ids or not target_ids:
            raise MappingError("Arête de mapping vide")
        if len(source_ids) != len(set(source_ids)) or len(target_ids) != len(set(target_ids)):
            raise MappingError(f"Références dupliquées dans le mapping: {item['mapping_id']}")
        if source_ids != tuple(sorted(source_ids)) or target_ids != tuple(sorted(target_ids)):
            raise MappingError(
                f"Références de mapping non canoniquement ordonnées: {item['mapping_id']}"
            )
        confidence = float(item["confidence"])
        if not 0.0 <= confidence <= 1.0:
            raise MappingError(f"Confiance hors limites: {item['mapping_id']}")
        expected_cardinality = cardinality(len(source_ids), len(target_ids))
        if item.get("cardinality", expected_cardinality) != expected_cardinality:
            raise MappingError(f"Cardinalité incohérente: {item['mapping_id']}")
        if item["exactness"] == "exact" and confidence != 1.0:
            raise MappingError(f"Mapping exact avec confiance partielle: {item['mapping_id']}")
        if item.get("determinism", "deterministic") != "deterministic":
            raise MappingError("DS12 ne produit que des mappings déterministes")
        if str(item.get("producer")) != "vysi.document_source.ds12":
            raise MappingError("Producteur de mapping incohérent")
        if producer_version is not None and str(item.get("producer_version")) != producer_version:
            raise MappingError("Version du producteur de mapping incohérente")
        evidence_refs = tuple(str(value) for value in item.get("evidence_refs", []))
        if not evidence_refs or len(evidence_refs) != len(set(evidence_refs)):
            raise MappingError("Mapping sans preuve unique")
        if evidence_refs != tuple(sorted(evidence_refs)) or not all(
            _portable_evidence(value) for value in evidence_refs
        ):
            raise MappingError("Preuves de mapping non portables ou non canoniques")
        source_layer = str(item["source_layer"])
        target_layer = str(item["target_layer"])
        effective_version = str(item.get("producer_version", ""))
        expected_id = stable_id(
            "mapping",
            _mapping_identity(
                document_id=str(body.get("document_id", "")),
                source_layer=source_layer,
                source_ids=source_ids,
                target_layer=target_layer,
                target_ids=target_ids,
                relation=str(item["relation"]),
                method=str(item["method"]),
                producer_version=effective_version,
            ),
        )
        if str(item["mapping_id"]) != expected_id:
            raise MappingError(f"Identifiant de mapping non déterministe: {item['mapping_id']}")
        if available:
            unknown_sources = set(source_ids) - available.get(source_layer, set())
            unknown_targets = set(target_ids) - available.get(target_layer, set())
            if unknown_sources:
                raise MappingError(f"Sources de mapping inconnues: {sorted(unknown_sources)}")
            if unknown_targets:
                raise MappingError(f"Cibles de mapping inconnues: {sorted(unknown_targets)}")
        semantic_key = (
            source_layer,
            tuple(sorted(set(source_ids))),
            target_layer,
            tuple(sorted(set(target_ids))),
            str(item["relation"]),
            str(item["method"]),
        )
        if semantic_key in seen_edges:
            raise MappingError("Arêtes de mapping sémantiquement dupliquées")
        seen_edges.add(semantic_key)
    if inventory is not None:
        incoming_native = {
            target
            for item in mappings
            if item["target_layer"] == "native" and item["source_layer"] in {"binary", "container"}
            for target in item["target_ids"]
        }
        missing_native = set(inventory.ids("native")) - incoming_native
        if missing_native:
            raise MappingError(
                f"Unités natives sans origine binaire/conteneur: {sorted(missing_native)}"
            )
        incoming_ir = {
            target
            for item in mappings
            if item["target_layer"] == "technical_ir"
            for target in item["target_ids"]
        }
        missing_ir = set(inventory.ids("technical_ir")) - incoming_ir
        if missing_ir:
            raise MappingError(f"Unités IR sans mapping d'origine: {sorted(missing_ir)}")
        rendered_surfaces = {
            item.entity_id for item in inventory.entities_for("rendered") if item.kind == "surface"
        }
        incoming_rendered = {
            target
            for item in mappings
            if item["target_layer"] == "rendered"
            for target in item["target_ids"]
        }
        if rendered_surfaces - incoming_rendered:
            raise MappingError("Surface rendue sans mapping minimal")
        for target_layer in ("geometry", "asset"):
            incoming = {
                target
                for item in mappings
                if item["target_layer"] == target_layer
                for target in item["target_ids"]
            }
            missing = set(inventory.ids(cast(Any, target_layer))) - incoming
            if missing:
                raise MappingError(
                    f"Représentations {target_layer} sans mapping: {sorted(missing)}"
                )
