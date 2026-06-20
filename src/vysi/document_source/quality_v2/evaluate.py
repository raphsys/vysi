from __future__ import annotations

from typing import Any, cast

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.representation_v2 import RepresentationInventory, group_by_kind

from .models import FeatureMeasurement, LossKind, LossRecord, PreservationTransition, Severity


class QualityError(ValueError):
    def __init__(self, message: str, code: str = "DS-PRS-001") -> None:
        super().__init__(message)
        self.code = code


_EXACTNESS_RANK = {"inferred": 0, "approximate": 1, "exact": 2}


def _portable_evidence(value: str) -> bool:
    return (
        bool(value)
        and not value.startswith("/")
        and ".." not in value.replace("\\", "/").split("/")
    )


def _mapping_source_quality(
    mapping: dict[str, Any], source_layer: str, target_layer: str
) -> dict[str, str]:
    best: dict[str, str] = {}
    for edge in cast(list[dict[str, Any]], mapping.get("mappings", [])):
        if edge["source_layer"] != source_layer or edge["target_layer"] != target_layer:
            continue
        exactness = str(edge["exactness"])
        for identifier in edge["source_ids"]:
            current = best.get(str(identifier))
            if current is None or _EXACTNESS_RANK[exactness] > _EXACTNESS_RANK[current]:
                best[str(identifier)] = exactness
    return best


def _mapping_target_ids(mapping: dict[str, Any], target_layer: str) -> frozenset[str]:
    return frozenset(
        str(identifier)
        for edge in cast(list[dict[str, Any]], mapping.get("mappings", []))
        if edge["target_layer"] == target_layer
        for identifier in edge["target_ids"]
    )


def _scan_string_refs(value: Any, keys: frozenset[str]) -> frozenset[str]:
    found: set[str] = set()

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            for key, child in item.items():
                if key in keys and isinstance(child, list):
                    found.update(str(element) for element in child if isinstance(element, str))
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    return frozenset(found)


def _measurement(
    *,
    feature: str,
    axis: str,
    basis: str,
    ids: frozenset[str],
    projected_quality: dict[str, str] | None,
    rendered_quality: dict[str, str] | None,
    preserved_ids: frozenset[str] | None = None,
    required_projection_ids: frozenset[str] | None = None,
    opaque_ids: frozenset[str] = frozenset(),
    unsupported_ids: frozenset[str] = frozenset(),
    severity: Severity = "info",
    evidence_refs: tuple[str, ...],
) -> FeatureMeasurement:
    projected_quality = projected_quality or {}
    rendered_quality = rendered_quality or {}
    preserved = ids if preserved_ids is None else ids & preserved_ids
    required = ids if required_projection_ids is None else ids & required_projection_ids
    projected_ids = ids & set(projected_quality)
    rendered_ids = ids & set(rendered_quality)
    approximated = frozenset(
        identifier
        for identifier in ids
        if projected_quality.get(identifier) in {"approximate", "inferred"}
        or rendered_quality.get(identifier) in {"approximate", "inferred"}
    )
    omitted = required - projected_ids
    return FeatureMeasurement(
        feature=feature,
        axis=cast(Any, axis),
        basis=basis,
        encountered=len(ids),
        extracted=len(ids),
        preserved=len(preserved),
        projected=len(projected_ids),
        rendered=len(rendered_ids),
        opaque=len(ids & opaque_ids),
        approximated=len(approximated),
        unsupported=len(ids & unsupported_ids),
        omitted=len(omitted),
        severity=severity,
        evidence_refs=evidence_refs,
        omitted_refs=tuple(sorted(omitted)),
        approximated_refs=tuple(sorted(approximated)),
        unsupported_refs=tuple(sorted(ids & unsupported_ids)),
    )


def _loss(
    document_id: str,
    feature: str,
    stage: str,
    severity: Severity,
    kind: LossKind,
    description: str,
    source_refs: tuple[str, ...],
) -> LossRecord:
    refs = tuple(sorted(set(source_refs)))
    seed = {
        "document_id": document_id,
        "feature": feature,
        "stage": stage,
        "severity": severity,
        "kind": kind,
        "description": description,
        "source_refs": refs,
    }
    return LossRecord(stable_id("loss", seed), feature, stage, severity, kind, description, refs)


def _losses_from_measurement(document_id: str, item: FeatureMeasurement) -> list[LossRecord]:
    losses: list[LossRecord] = []
    stage = {
        "binary": "binary_to_container",
        "structural": "native_to_technical_ir",
        "technical_semantic": "native_to_technical_ir",
        "style": "native_to_technical_ir",
        "relationship": "native_to_technical_ir",
        "visual": "native_to_rendered",
        "interactive": "native_to_technical_ir",
        "computational": "native_to_technical_ir",
        "roundtrip": "roundtrip",
    }[item.axis]
    if item.omitted:
        losses.append(
            _loss(
                document_id,
                item.feature,
                stage,
                item.severity,
                "omission",
                f"{item.omitted} occurrence(s) rencontrée(s) ne sont pas projetées",
                item.omitted_refs,
            )
        )
    if item.unsupported:
        losses.append(
            _loss(
                document_id,
                item.feature,
                stage,
                item.severity,
                "unsupported",
                f"{item.unsupported} occurrence(s) ne sont pas prises en charge",
                item.unsupported_refs,
            )
        )
    if item.approximated:
        losses.append(
            _loss(
                document_id,
                item.feature,
                stage,
                "warning" if item.severity == "info" else item.severity,
                "approximation",
                f"{item.approximated} occurrence(s) reposent sur une correspondance non exacte",
                item.approximated_refs,
            )
        )
    return losses


def _ratio(exact: int, approximate: int, total: int) -> float | None:
    if total == 0:
        return None
    return round((exact + 0.5 * approximate) / total, 6)


def _feature_score(item: FeatureMeasurement, mode: str = "projected") -> tuple[int, int, int]:
    if mode == "preserved":
        effective = item.preserved
    elif mode == "rendered":
        effective = item.rendered
    else:
        effective = item.projected
    approximate = min(item.approximated, effective)
    exact = max(0, effective - approximate)
    return exact, approximate, item.encountered


def _combine_scores(items: list[FeatureMeasurement], mode: str = "projected") -> float | None:
    exact = approximate = total = 0
    for item in items:
        item_exact, item_approximate, item_total = _feature_score(item, mode)
        exact += item_exact
        approximate += item_approximate
        total += item_total
    return _ratio(exact, approximate, total)


def _transition(
    *,
    from_layer: str,
    to_layer: str,
    relevant_edges: list[dict[str, Any]],
    producer: str,
    producer_version: str,
    method: str,
    input_refs: frozenset[str],
    output_refs: frozenset[str],
    evidence_refs: tuple[str, ...],
    loss_refs: tuple[str, ...],
    not_run: bool = False,
    failed: bool = False,
    determinism: str = "deterministic",
) -> PreservationTransition:
    if not_run:
        return PreservationTransition(
            from_layer,
            to_layer,
            "not_run",
            producer,
            producer_version,
            method,
            cast(Any, determinism),
            "not_applicable",
            None,
            tuple(sorted(input_refs)),
            tuple(sorted(output_refs)),
            evidence_refs,
            loss_refs,
        )
    if failed:
        state = "failed"
    elif loss_refs:
        state = "partial" if output_refs else "lossy_declared"
    else:
        state = "lossless"
    exactness_values = {str(edge["exactness"]) for edge in relevant_edges}
    if not exactness_values:
        exactness = "inferred" if output_refs else "not_applicable"
        confidence: float | None = 0.0 if output_refs else None
    elif exactness_values == {"exact"}:
        exactness = "exact"
        confidence = 1.0
    elif "approximate" in exactness_values:
        exactness = "approximate"
        confidence = min(float(edge["confidence"]) for edge in relevant_edges)
    else:
        exactness = "inferred"
        confidence = min(float(edge["confidence"]) for edge in relevant_edges)
    return PreservationTransition(
        from_layer,
        to_layer,
        cast(Any, state),
        producer,
        producer_version,
        method,
        cast(Any, determinism),
        cast(Any, exactness),
        confidence,
        tuple(sorted(input_refs)),
        tuple(sorted(output_refs)),
        evidence_refs,
        loss_refs,
    )


def evaluate_quality(
    *,
    document_id: str,
    producer_version: str,
    inventory: RepresentationInventory,
    artifact_records: list[dict[str, Any]],
    container: dict[str, Any] | None,
    native: dict[str, Any],
    profile: dict[str, Any],
    styles: dict[str, Any],
    relationships: dict[str, Any],
    metadata: dict[str, Any],
    annotations: dict[str, Any],
    resources: dict[str, Any],
    ir: dict[str, Any],
    mapping: dict[str, Any],
    rendered: dict[str, Any] | None,
    geometry: dict[str, Any] | None,
    assets: dict[str, Any] | None,
    decode_result: dict[str, Any] | None,
    conversion_reports: list[dict[str, Any]],
    projection_warnings: list[str],
    evidence_refs: list[str],
    policy: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    evidence = tuple(sorted(set(evidence_refs)))
    grouped = group_by_kind(inventory, "native")
    binary_ids = inventory.ids("binary")
    container_part_ids = frozenset(
        item.entity_id for item in inventory.entities_for("container") if item.kind == "part"
    )
    container_relationship_ids = frozenset(
        item.entity_id
        for item in inventory.entities_for("container")
        if item.kind == "container_relationship"
    )
    style_ids = grouped.get("style", frozenset())
    relationship_ids = grouped.get("relationship", frozenset())
    metadata_ids = grouped.get("metadata", frozenset())
    annotation_ids = grouped.get("annotation", frozenset())
    resource_ids = grouped.get("resource", frozenset())
    occurrence_ids = grouped.get("resource_occurrence", frozenset())
    formula_ids = grouped.get("formula", frozenset())
    revision_ids = grouped.get("revision", frozenset())
    event_ids = (
        grouped.get("event", frozenset())
        | grouped.get("animation", frozenset())
        | grouped.get("transition", frozenset())
    )
    opaque_native_ids = frozenset(str(item["opaque_id"]) for item in native.get("opaque_parts", []))
    special = set().union(
        style_ids,
        relationship_ids,
        metadata_ids,
        annotation_ids,
        resource_ids,
        occurrence_ids,
        formula_ids,
        revision_ids,
        event_ids,
        opaque_native_ids,
    )
    native_core_ids = inventory.ids("native") - special

    binary_to_container = _mapping_source_quality(mapping, "binary", "container")
    container_to_native = _mapping_source_quality(mapping, "container", "native")
    native_to_ir = _mapping_source_quality(mapping, "native", "technical_ir")
    native_to_rendered = _mapping_source_quality(mapping, "native", "rendered")

    required_style_ids = _scan_string_refs(profile, frozenset({"style_refs"}))
    required_resource_ids = _scan_string_refs(profile, frozenset({"resource_refs"})) | frozenset(
        str(item["resource_id"]) for item in resources.get("occurrences", [])
    )
    active_resource_ids = frozenset(
        str(item["resource_id"])
        for item in resources.get("resources", [])
        if bool(item.get("active"))
    )
    opaque_resource_ids = frozenset(
        str(item["resource_id"])
        for item in resources.get("resources", [])
        if bool(item.get("opaque"))
    )
    opaque_part_ids = frozenset(
        str(item["part_id"])
        for item in (container or {}).get("parts", [])
        if bool(item.get("opaque"))
    )
    unreadable_part_ids = frozenset(
        str(item["part_id"])
        for item in (container or {}).get("parts", [])
        if str(item.get("read_state")) in {"failed", "blocked", "not_read"}
    )

    measurements: list[FeatureMeasurement] = []
    measurements.append(
        _measurement(
            feature="binary_artifact",
            axis="binary",
            basis="Artefacts acquis, hashés et conservés sans modification",
            ids=binary_ids,
            projected_quality=binary_to_container,
            rendered_quality=None,
            required_projection_ids=binary_ids,
            severity="critical",
            evidence_refs=evidence,
        )
    )
    if container_part_ids:
        measurements.append(
            _measurement(
                feature="container_part",
                axis="structural",
                basis="Parties physiques inventoriées ; les parties opaques restent conservées dans l'original",
                ids=container_part_ids,
                projected_quality=container_to_native,
                rendered_quality=None,
                required_projection_ids=frozenset(),
                opaque_ids=opaque_part_ids,
                unsupported_ids=unreadable_part_ids,
                severity="warning" if unreadable_part_ids else "info",
                evidence_refs=evidence,
            )
        )
    if container_relationship_ids:
        measurements.append(
            _measurement(
                feature="container_relationship",
                axis="relationship",
                basis="Relations physiques du conteneur inventoriées dans leur couche d'autorité",
                ids=container_relationship_ids,
                projected_quality=None,
                rendered_quality=None,
                required_projection_ids=frozenset(),
                severity="info",
                evidence_refs=evidence,
            )
        )
    measurements.append(
        _measurement(
            feature="native_core_unit",
            axis="structural",
            basis="Unités structurelles natives attendues dans TechnicalDocumentIR",
            ids=native_core_ids,
            projected_quality=native_to_ir,
            rendered_quality=native_to_rendered,
            required_projection_ids=native_core_ids,
            severity="error",
            evidence_refs=evidence,
        )
    )
    if style_ids:
        measurements.append(
            _measurement(
                feature="native_style",
                axis="style",
                basis="Styles référencés projetés ; styles non utilisés conservés dans le catalogue natif",
                ids=style_ids,
                projected_quality=native_to_ir,
                rendered_quality=native_to_rendered,
                required_projection_ids=required_style_ids,
                severity="warning",
                evidence_refs=evidence,
            )
        )
    if relationship_ids:
        measurements.append(
            _measurement(
                feature="native_relationship",
                axis="relationship",
                basis="Relations natives projetées comme faits techniques",
                ids=relationship_ids,
                projected_quality=native_to_ir,
                rendered_quality=None,
                required_projection_ids=relationship_ids,
                severity="error",
                evidence_refs=evidence,
            )
        )
    if metadata_ids:
        measurements.append(
            _measurement(
                feature="native_metadata",
                axis="technical_semantic",
                basis="Métadonnées natives conservées et attendues dans la projection technique",
                ids=metadata_ids,
                projected_quality=native_to_ir,
                rendered_quality=None,
                required_projection_ids=metadata_ids,
                severity="warning",
                evidence_refs=evidence,
            )
        )
    if annotation_ids:
        measurements.append(
            _measurement(
                feature="native_annotation",
                axis="technical_semantic",
                basis="Annotations natives projetées avec leurs cibles",
                ids=annotation_ids,
                projected_quality=native_to_ir,
                rendered_quality=native_to_rendered,
                required_projection_ids=annotation_ids,
                severity="error",
                evidence_refs=evidence,
            )
        )
    if resource_ids:
        measurements.append(
            _measurement(
                feature="native_resource",
                axis="technical_semantic",
                basis="Ressources référencées projetées ; ressources non utilisées conservées nativement",
                ids=resource_ids,
                projected_quality=native_to_ir,
                rendered_quality=native_to_rendered,
                required_projection_ids=required_resource_ids,
                opaque_ids=opaque_resource_ids,
                severity="error",
                evidence_refs=evidence,
            )
        )
    if occurrence_ids:
        measurements.append(
            _measurement(
                feature="resource_occurrence",
                axis="structural",
                basis="Occurrences et ancrages de ressources attendus dans la projection technique",
                ids=occurrence_ids,
                projected_quality=native_to_ir,
                rendered_quality=native_to_rendered,
                required_projection_ids=occurrence_ids,
                severity="warning",
                evidence_refs=evidence,
            )
        )
    if formula_ids:
        measurements.append(
            _measurement(
                feature="formula",
                axis="computational",
                basis="Formules conservées exactement sans recalcul implicite",
                ids=formula_ids,
                projected_quality=native_to_ir,
                rendered_quality=None,
                required_projection_ids=formula_ids,
                severity="critical",
                evidence_refs=evidence,
            )
        )
    if revision_ids:
        measurements.append(
            _measurement(
                feature="revision",
                axis="technical_semantic",
                basis="Révisions natives et cibles préservées dans la projection",
                ids=revision_ids,
                projected_quality=native_to_ir,
                rendered_quality=None,
                required_projection_ids=revision_ids,
                severity="error",
                evidence_refs=evidence,
            )
        )
    interactive_ids = event_ids | active_resource_ids
    if interactive_ids:
        measurements.append(
            _measurement(
                feature="interactive_content",
                axis="interactive",
                basis="Contenu actif inventorié et préservé sans exécution",
                ids=interactive_ids,
                projected_quality=native_to_ir,
                rendered_quality=None,
                required_projection_ids=event_ids,
                opaque_ids=active_resource_ids,
                severity="warning",
                evidence_refs=evidence,
            )
        )
    opaque_ids = opaque_native_ids | opaque_resource_ids | opaque_part_ids
    if opaque_ids:
        measurements.append(
            FeatureMeasurement(
                "opaque_content",
                "roundtrip",
                "Contenu non interprété mais conservé par référence ou dans l'artefact original",
                len(opaque_ids),
                len(opaque_ids),
                len(opaque_ids),
                0,
                0,
                len(opaque_ids),
                0,
                0,
                0,
                "warning",
                evidence,
            )
        )

    surface_ids = frozenset(
        item.entity_id for item in inventory.entities_for("rendered") if item.kind == "surface"
    )
    if surface_ids:
        incoming_rendered = _mapping_target_ids(mapping, "rendered")
        surface_quality = {identifier: "exact" for identifier in surface_ids & incoming_rendered}
        measurements.append(
            _measurement(
                feature="rendered_surface",
                axis="visual",
                basis="Surfaces rendues reliées au modèle natif et à un environnement déclaré",
                ids=surface_ids,
                projected_quality=surface_quality,
                rendered_quality=surface_quality,
                required_projection_ids=surface_ids,
                severity="error",
                evidence_refs=evidence,
            )
        )
    geometry_ids = inventory.ids("geometry")
    if geometry_ids:
        geometry_mapped = _mapping_target_ids(mapping, "geometry")
        geometry_quality = {identifier: "exact" for identifier in geometry_ids & geometry_mapped}
        measurements.append(
            _measurement(
                feature="rendered_geometry",
                axis="visual",
                basis="Géométries reliées à un propriétaire et à un espace de coordonnées",
                ids=geometry_ids,
                projected_quality=geometry_quality,
                rendered_quality=geometry_quality,
                required_projection_ids=geometry_ids,
                severity="error",
                evidence_refs=evidence,
            )
        )
    asset_ids = inventory.ids("asset")
    if asset_ids:
        asset_mapped = _mapping_target_ids(mapping, "asset")
        asset_quality = {identifier: "exact" for identifier in asset_ids & asset_mapped}
        measurements.append(
            _measurement(
                feature="derived_asset",
                axis="visual",
                basis="Assets dérivés reliés à leurs entrées et conservés par référence hashée",
                ids=asset_ids,
                projected_quality=asset_quality,
                rendered_quality=asset_quality,
                required_projection_ids=asset_ids,
                severity="error",
                evidence_refs=evidence,
            )
        )

    rendering_mode = str(policy["rendering_policy"]["mode"])
    if not surface_ids and rendering_mode == "required":
        measurements.append(
            FeatureMeasurement(
                "required_source_rendering",
                "visual",
                "La politique exige un rendu source mais DS11 n'a fourni aucune surface",
                1,
                0,
                0,
                0,
                0,
                0,
                0,
                1,
                1,
                "error",
                evidence,
                omitted_refs=(document_id,),
                unsupported_refs=(document_id,),
            )
        )

    profile_kind = str(native["profile_kind"])
    if profile_kind == "legacy_ole":
        legacy_refs = binary_ids or frozenset({document_id})
        measurements.append(
            FeatureMeasurement(
                "legacy_semantic_decode",
                "technical_semantic",
                "Le conteneur OLE est inventorié mais le modèle métier historique reste inventory_only",
                1,
                0,
                1,
                0,
                0,
                1,
                0,
                1,
                0,
                "error",
                evidence,
                unsupported_refs=tuple(sorted(legacy_refs)),
            )
        )

    if projection_warnings:
        warning_refs = tuple(
            stable_id("projection_warning", {"document_id": document_id, "warning": warning})
            for warning in sorted(set(projection_warnings))
        )
        measurements.append(
            FeatureMeasurement(
                "technical_ir_projection_warning",
                "technical_semantic",
                "Avertissements explicitement publiés par DS10",
                len(warning_refs),
                len(warning_refs),
                len(warning_refs),
                0,
                0,
                0,
                len(warning_refs),
                0,
                0,
                "warning",
                evidence,
                approximated_refs=warning_refs,
            )
        )

    losses: list[LossRecord] = []
    for item in measurements:
        losses.extend(_losses_from_measurement(document_id, item))
    for warning in sorted(set(str(item) for item in (container or {}).get("warnings", []))):
        losses.append(
            _loss(
                document_id,
                "container_warning",
                "binary_to_container",
                "warning",
                "approximation",
                warning,
                tuple(sorted(container_part_ids or binary_ids)),
            )
        )
    for report in conversion_reports:
        for conversion in report.get("conversions", []):
            warnings = tuple(str(item) for item in conversion.get("warnings", []))
            kind: LossKind = "conversion"
            severity: Severity = "warning" if warnings or conversion.get("loss_refs") else "info"
            losses.append(
                _loss(
                    document_id,
                    "format_conversion",
                    "conversion",
                    severity,
                    kind,
                    f"Conversion déclarée {conversion['source_format']} → {conversion['target_format']}",
                    tuple(str(item) for item in conversion.get("input_refs", [])),
                )
            )

    # Remove exact duplicate losses while preserving stable order.
    loss_by_id = {item.loss_id: item for item in losses}
    losses = [loss_by_id[key] for key in sorted(loss_by_id)]

    by_feature = {item.feature: item for item in measurements}
    binary_score = _combine_scores([by_feature["binary_artifact"]], "preserved")
    structural_items = [
        item for item in measurements if item.feature in {"native_core_unit", "resource_occurrence"}
    ]
    structural_score = _combine_scores(structural_items)
    technical_items = [
        item
        for item in measurements
        if item.feature
        in {
            "native_core_unit",
            "native_metadata",
            "native_annotation",
            "native_resource",
            "revision",
            "technical_ir_projection_warning",
            "legacy_semantic_decode",
        }
    ]
    technical_score = _combine_scores(technical_items)
    style_score = _combine_scores([item for item in measurements if item.axis == "style"])
    relationship_score = _combine_scores(
        [item for item in measurements if item.feature == "native_relationship"]
    )
    visual_items = [item for item in measurements if item.axis == "visual"]
    visual_score = _combine_scores(visual_items, "rendered") if visual_items else None
    interactive_score = _combine_scores(
        [item for item in measurements if item.axis == "interactive"], "preserved"
    )
    computational_score = _combine_scores(
        [item for item in measurements if item.axis == "computational"]
    )

    major = sum(
        1
        for item in losses
        if item.severity in {"error", "critical"}
        and item.kind in {"loss", "omission", "unsupported"}
    )
    minor = sum(1 for item in losses if item.severity == "warning")
    if profile_kind == "legacy_ole":
        roundtrip_score = 0.25
    else:
        penalty = min(0.9, 0.2 * major + 0.05 * minor)
        roundtrip_score = round(max(0.0, 1.0 - penalty), 6)
        if profile_kind != "plain_text" and roundtrip_score == 1.0:
            roundtrip_score = 0.95
    if roundtrip_score == 1.0:
        roundtrip_risk = "none"
    elif roundtrip_score >= 0.85:
        roundtrip_risk = "low"
    elif roundtrip_score >= 0.6:
        roundtrip_risk = "medium"
    else:
        roundtrip_risk = "high"

    axis_scores = {
        "binary": binary_score,
        "structural": structural_score,
        "technical_semantic": technical_score,
        "style": style_score,
        "relationship": relationship_score,
        "visual": visual_score,
        "interactive": interactive_score,
        "computational": computational_score,
        "roundtrip": roundtrip_score,
    }

    edges = cast(list[dict[str, Any]], mapping.get("mappings", []))
    transition_specs = [
        ("binary", "container", "DS07", "container_inventory"),
        ("container", "native", "DS08-DS09", "native_decode_and_publication"),
        ("native", "technical_ir", "DS10", "technical_ir_projection"),
        ("native", "rendered", "DS11", "optional_source_rendering"),
        ("rendered", "asset", "DS11", "rendered_asset_materialization"),
    ]
    transitions: list[PreservationTransition] = []
    for from_layer, to_layer, producer, method in transition_specs:
        relevant = [
            edge
            for edge in edges
            if edge["source_layer"] == from_layer and edge["target_layer"] == to_layer
        ]
        input_ids = inventory.ids(cast(Any, from_layer))
        output_ids = inventory.ids(cast(Any, to_layer))
        stage_name = f"{from_layer}_to_{to_layer}"
        transition_loss_ids = tuple(
            item.loss_id
            for item in losses
            if item.stage == stage_name
            or (
                stage_name == "native_to_technical_ir"
                and item.stage in {"native_to_technical_ir", "container_to_native"}
            )
        )
        not_run = to_layer == "rendered" and rendered is None
        if to_layer == "asset" and assets is None:
            not_run = True
        if from_layer == "container" and container is None:
            not_run = True
        determinism = "deterministic"
        if (
            rendered is not None
            and to_layer in {"rendered", "asset"}
            and any(
                str(view.get("determinism")) == "nondeterministic"
                for view in rendered.get("views", [])
            )
        ):
            determinism = "nondeterministic"
        transitions.append(
            _transition(
                from_layer=from_layer,
                to_layer=to_layer,
                relevant_edges=relevant,
                producer=producer,
                producer_version=producer_version,
                method=method,
                input_refs=input_ids,
                output_refs=output_ids,
                evidence_refs=evidence,
                loss_refs=transition_loss_ids,
                not_run=not_run,
                failed=False,
                determinism=determinism,
            )
        )

    severities = {item.severity for item in losses}
    strictness = cast(dict[str, Any], policy["strictness_policy"])
    if "critical" in severities or "error" in severities:
        status = "rejected" if strictness["major_loss_action"] == "reject" else "review"
    elif "warning" in severities and strictness["minor_loss_action"] == "review":
        status = "review"
    else:
        status = "ok"

    coverage_body = {
        "document_id": document_id,
        "items": [item.to_dict() for item in sorted(measurements, key=lambda value: value.feature)],
        "axis_scores": axis_scores,
    }
    preservation_body = {
        "document_id": document_id,
        "transitions": [item.to_dict() for item in transitions],
        "losses": [item.to_dict() for item in losses],
        "opaque_preserved_count": len(opaque_ids),
        "roundtrip_risk": roundtrip_risk,
    }
    validate_quality_invariants(coverage_body, preservation_body)
    return coverage_body, preservation_body, status


def validate_quality_invariants(coverage: dict[str, Any], preservation: dict[str, Any]) -> None:
    if coverage.get("document_id") != preservation.get("document_id"):
        raise QualityError(
            "Les rapports de couverture et de préservation concernent des documents différents",
            "DS-COV-001",
        )
    items = cast(list[dict[str, Any]], coverage.get("items", []))
    features = [str(item["feature"]) for item in items]
    if len(features) != len(set(features)):
        raise QualityError("Fonctions de couverture dupliquées", "DS-COV-001")
    for item in items:
        if not str(item.get("basis", "")).strip():
            raise QualityError(f"Base de mesure absente: {item['feature']}", "DS-COV-001")
        evidence_refs = tuple(str(value) for value in item.get("evidence_refs", []))
        if (
            not evidence_refs
            or len(evidence_refs) != len(set(evidence_refs))
            or evidence_refs != tuple(sorted(evidence_refs))
            or not all(_portable_evidence(value) for value in evidence_refs)
        ):
            raise QualityError(f"Preuves de couverture invalides: {item['feature']}", "DS-COV-001")
        encountered = int(item["encountered"])
        for key in (
            "extracted",
            "preserved",
            "projected",
            "rendered",
            "opaque",
            "approximated",
            "unsupported",
            "omitted",
        ):
            value = int(item[key])
            if value < 0:
                raise QualityError(f"Compteur négatif: {item['feature']}.{key}", "DS-COV-001")
            if value > encountered:
                raise QualityError(
                    f"Compteur supérieur aux éléments rencontrés: {item['feature']}.{key}",
                    "DS-COV-001",
                )
        if int(item["omitted"]) and not item.get("evidence_refs"):
            raise QualityError(f"Omission sans preuve: {item['feature']}", "DS-COV-001")
    losses = cast(list[dict[str, Any]], preservation.get("losses", []))
    loss_ids = [str(item["loss_id"]) for item in losses]
    if len(loss_ids) != len(set(loss_ids)):
        raise QualityError("Identifiants de pertes dupliqués")
    for loss in losses:
        source_refs = tuple(str(value) for value in loss.get("source_refs", []))
        if not source_refs:
            raise QualityError(f"Perte sans source: {loss['loss_id']}")
        if len(source_refs) != len(set(source_refs)) or source_refs != tuple(sorted(source_refs)):
            raise QualityError(f"Sources de perte non canoniques: {loss['loss_id']}")
        expected_loss_id = stable_id(
            "loss",
            {
                "document_id": str(preservation.get("document_id", "")),
                "feature": str(loss["feature"]),
                "stage": str(loss["stage"]),
                "severity": str(loss["severity"]),
                "kind": str(loss["kind"]),
                "description": str(loss["description"]),
                "source_refs": source_refs,
            },
        )
        if str(loss["loss_id"]) != expected_loss_id:
            raise QualityError(f"Identifiant de perte non déterministe: {loss['loss_id']}")
    known_loss_ids = set(loss_ids)
    transitions = cast(list[dict[str, Any]], preservation.get("transitions", []))
    transition_pairs = [(str(item["from_layer"]), str(item["to_layer"])) for item in transitions]
    if len(transition_pairs) != len(set(transition_pairs)):
        raise QualityError("Transitions de préservation dupliquées")
    required_pairs = {
        ("binary", "container"),
        ("container", "native"),
        ("native", "technical_ir"),
        ("native", "rendered"),
        ("rendered", "asset"),
    }
    if set(transition_pairs) != required_pairs:
        raise QualityError("Chaîne de transitions de préservation incomplète")
    linked_loss_ids: set[str] = set()
    for transition in transitions:
        transition_loss_refs = tuple(str(item) for item in transition.get("loss_refs", []))
        unknown = set(transition_loss_refs) - known_loss_ids
        if unknown:
            raise QualityError(f"Transition référençant des pertes inconnues: {sorted(unknown)}")
        linked_loss_ids.update(transition_loss_refs)
        evidence_refs = tuple(str(value) for value in transition.get("evidence_refs", []))
        if (
            not evidence_refs
            or len(evidence_refs) != len(set(evidence_refs))
            or evidence_refs != tuple(sorted(evidence_refs))
            or not all(_portable_evidence(value) for value in evidence_refs)
        ):
            raise QualityError("Preuves de transition invalides")
        state = str(transition["state"])
        exactness = str(transition["exactness"])
        confidence = transition["confidence"]
        if state == "not_run":
            if confidence is not None or exactness != "not_applicable" or transition["output_refs"]:
                raise QualityError("Transition not_run avec mesure ou sortie")
        else:
            if confidence is None:
                raise QualityError("Transition exécutée sans confiance")
            if not 0.0 <= float(confidence) <= 1.0:
                raise QualityError("Confiance de transition hors limites")
            if exactness == "exact" and float(confidence) != 1.0:
                raise QualityError("Transition exacte avec confiance partielle")
            if exactness == "not_applicable":
                raise QualityError("Transition exécutée sans exactitude")
        if state == "lossless" and transition_loss_refs:
            raise QualityError("Transition lossless référençant une perte")
        if state in {"partial", "lossy_declared", "failed"} and not transition_loss_refs:
            raise QualityError("Transition dégradée sans perte déclarée")
    mandatory_linked = {
        str(item["loss_id"])
        for item in losses
        if str(item.get("stage"))
        in {
            "binary_to_container",
            "container_to_native",
            "native_to_technical_ir",
            "native_to_rendered",
            "rendered_to_asset",
        }
    }
    if mandatory_linked - linked_loss_ids:
        raise QualityError(
            f"Pertes non reliées à une transition: {sorted(mandatory_linked - linked_loss_ids)}"
        )
    axis_scores = cast(dict[str, Any], coverage.get("axis_scores", {}))
    required_axes = {
        "binary",
        "structural",
        "technical_semantic",
        "style",
        "relationship",
        "visual",
        "interactive",
        "computational",
        "roundtrip",
    }
    if set(axis_scores) != required_axes:
        raise QualityError("Axes de fidélité incomplets", "DS-COV-001")
    for score in axis_scores.values():
        if score is not None and not 0.0 <= float(score) <= 1.0:
            raise QualityError("Score de fidélité hors limites", "DS-COV-001")
