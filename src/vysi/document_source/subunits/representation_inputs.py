from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.execution.verified_inputs import VerifiedInputReader
from vysi.document_source.rendering_v2 import validate_rendering_invariants
from vysi.document_source.representation_v2 import RepresentationInventory, build_inventory


@dataclass(frozen=True)
class DocumentRepresentations:
    document_id: str
    artifact_records: list[dict[str, Any]]
    container: dict[str, Any] | None
    decode_result: dict[str, Any] | None
    native: dict[str, Any]
    profile: dict[str, Any]
    styles: dict[str, Any]
    relationships: dict[str, Any]
    metadata: dict[str, Any]
    annotations: dict[str, Any]
    resources: dict[str, Any]
    ir: dict[str, Any]
    rendered: dict[str, Any] | None
    geometry: dict[str, Any] | None
    assets: dict[str, Any] | None
    inventory: RepresentationInventory
    evidence: dict[str, str]


def _optional(
    reader: VerifiedInputReader,
    path: Path,
    schema_key: str,
    document_id: str,
) -> dict[str, Any] | None:
    return reader.contract(path, schema_key, document_id=document_id) if path.is_file() else None


def _load_one_document(
    *,
    ctx: ExecutionContext,
    reader: VerifiedInputReader,
    ir_path: Path,
    artifacts: dict[str, dict[str, Any]],
    probe_documents: dict[str, dict[str, Any]],
) -> DocumentRepresentations:
    ir = reader.contract(ir_path, "technical_document_ir")
    document_id = str(ir["document_id"])
    expected_ir_path = ctx.workspace / "ir" / document_id / "technical_document_ir.json"
    if ir_path.resolve() != expected_ir_path.resolve():
        raise StageFailure(
            reader.error_code,
            reader.stage,
            document_id,
            "Chemin canonique du contrat IR incohérent",
        )

    probe_document = probe_documents.get(document_id)
    if probe_document is None:
        raise StageFailure(
            reader.error_code, reader.stage, document_id, "Document absent du rapport de détection"
        )
    artifact_ids = [str(item) for item in probe_document["artifact_ids"]]
    unknown = set(artifact_ids) - set(artifacts)
    if unknown:
        raise StageFailure(
            reader.error_code, reader.stage, document_id, f"Artefacts inconnus: {sorted(unknown)}"
        )
    artifact_records = [artifacts[identifier] for identifier in artifact_ids]
    for artifact in artifact_records:
        reader.artifact_bytes(str(artifact["stored_path"]), str(artifact["sha256"]))

    container = _optional(
        reader,
        ctx.workspace / "manifests" / "container" / f"{document_id}.json",
        "container_part_catalog",
        document_id,
    )
    decode_result = _optional(
        reader,
        ctx.workspace / "manifests" / "decode" / f"{document_id}.json",
        "native_decode_result",
        document_id,
    )

    native_dir = ctx.workspace / "native" / document_id
    native = reader.contract(
        native_dir / "native_document.json", "native_document", document_id=document_id
    )
    profile_ref = cast(dict[str, Any], native["profile_ref"])
    profile_schema_key = str(profile_ref["schema_id"]).removeprefix("document_source.")
    profile = reader.referenced_contract(profile_ref, profile_schema_key, document_id=document_id)
    expected_profile_path = f"native/{document_id}/profile.json"
    if str(profile_ref["path"]) != expected_profile_path:
        raise StageFailure(
            reader.error_code,
            reader.stage,
            document_id,
            "Chemin canonique du profil natif incohérent",
        )
    styles = reader.contract(
        native_dir / "styles.json", "native_style_catalog", document_id=document_id
    )
    relationships = reader.contract(
        native_dir / "relationships.json",
        "native_relationship_catalog",
        document_id=document_id,
    )
    metadata = reader.contract(
        native_dir / "metadata.json", "native_metadata_catalog", document_id=document_id
    )
    annotations = reader.contract(
        native_dir / "annotations.json", "native_annotation_catalog", document_id=document_id
    )
    resources = reader.contract(
        native_dir / "resources.json", "native_resource_catalog", document_id=document_id
    )
    if str(native["profile_kind"]) != str(profile["profile_kind"]):
        raise StageFailure(
            reader.error_code, reader.stage, document_id, "Type de profil natif incohérent"
        )

    rendered_dir = ctx.workspace / "rendered" / document_id
    rendered = _optional(
        reader,
        rendered_dir / "rendered_view_catalog.json",
        "rendered_view_catalog",
        document_id,
    )
    geometry = _optional(
        reader, rendered_dir / "geometry_catalog.json", "geometry_catalog", document_id
    )
    assets = _optional(
        reader,
        rendered_dir / "derived_asset_catalog.json",
        "derived_asset_catalog",
        document_id,
    )
    if (geometry is not None or assets is not None) and rendered is None:
        raise StageFailure(
            reader.error_code,
            reader.stage,
            document_id,
            "Géométrie ou asset présent sans RenderedViewCatalog",
        )
    if rendered is not None:
        if geometry is None or assets is None:
            raise StageFailure(
                reader.error_code, reader.stage, document_id,
                "Catalogues DS11 incomplets",
            )
        try:
            validate_rendering_invariants(rendered, geometry, assets)
        except ValueError as exc:
            raise StageFailure(
                reader.error_code, reader.stage, document_id,
                "Invariants DS11 invalides", str(exc),
            ) from exc
        for asset in cast(list[dict[str, Any]], assets.get("assets", [])):
            stored = cast(dict[str, Any], asset["stored_ref"])
            reader.artifact_bytes(str(stored["path"]), str(stored["sha256"]))
            asset_path = ctx.workspace / str(stored["path"])
            if asset_path.stat().st_size != int(stored["size_bytes"]):
                raise StageFailure(
                    reader.error_code, reader.stage, document_id,
                    "Taille d'asset DS11 incohérente",
                )

    evidence = {
        "bundle": "manifests/acquired_source_bundle.json",
        "probe": "manifests/format_probe_report.json",
        "container": f"manifests/container/{document_id}.json",
        "decode": f"manifests/decode/{document_id}.json",
        "native": f"native/{document_id}/native_document.json",
        "profile": f"native/{document_id}/profile.json",
        "styles": f"native/{document_id}/styles.json",
        "relationships": f"native/{document_id}/relationships.json",
        "metadata": f"native/{document_id}/metadata.json",
        "annotations": f"native/{document_id}/annotations.json",
        "resources": f"native/{document_id}/resources.json",
        "ir": f"ir/{document_id}/technical_document_ir.json",
        "rendered": f"rendered/{document_id}/rendered_view_catalog.json",
        "geometry": f"rendered/{document_id}/geometry_catalog.json",
        "assets": f"rendered/{document_id}/derived_asset_catalog.json",
    }
    inventory = build_inventory(
        artifacts=artifact_records,
        container=container,
        native=native,
        profile=profile,
        styles=styles,
        relationships=relationships,
        metadata=metadata,
        annotations=annotations,
        resources=resources,
        ir=ir,
        rendered=rendered,
        geometry=geometry,
        assets=assets,
        evidence=evidence,
    )
    return DocumentRepresentations(
        document_id,
        artifact_records,
        container,
        decode_result,
        native,
        profile,
        styles,
        relationships,
        metadata,
        annotations,
        resources,
        ir,
        rendered,
        geometry,
        assets,
        inventory,
        evidence,
    )


def load_document_representations(
    ctx: ExecutionContext,
    *,
    stage: str,
    error_code: str,
    allow_partial: bool = False,
) -> tuple[VerifiedInputReader, dict[str, Any], dict[str, Any], list[DocumentRepresentations]]:
    reader = VerifiedInputReader(ctx, stage, error_code)
    bundle = reader.contract(
        ctx.workspace / "manifests/acquired_source_bundle.json", "acquired_source_bundle"
    )
    probe = reader.contract(
        ctx.workspace / "manifests/format_probe_report.json", "format_probe_report"
    )
    artifacts = {
        str(item["artifact_id"]): cast(dict[str, Any], item) for item in bundle["artifacts"]
    }
    probe_documents = {
        str(item["document_id"]): cast(dict[str, Any], item) for item in probe["documents"]
    }

    ir_root = ctx.workspace / "ir"
    if not ir_root.is_dir():
        raise StageFailure(error_code, stage, ctx.run_id, "Répertoire IR absent")

    documents: list[DocumentRepresentations] = []
    seen_document_ids: set[str] = set()
    attempted_document_ids: set[str] = set()
    for ir_path in sorted(ir_root.glob("document_*/technical_document_ir.json")):
        ctx.check_cancelled(stage)
        scope = ir_path.parent.name
        try:
            document = _load_one_document(
                ctx=ctx,
                reader=reader,
                ir_path=ir_path,
                artifacts=artifacts,
                probe_documents=probe_documents,
            )
            attempted_document_ids.add(document.document_id)
            if document.document_id in seen_document_ids:
                raise StageFailure(error_code, stage, document.document_id, "Document IR dupliqué")
            seen_document_ids.add(document.document_id)
            documents.append(document)
        except StageFailure as caught_failure:
            attempted_document_ids.add(scope)
            if caught_failure.code in {"DS-RUN-003", "DS-LIM-001"} or not allow_partial:
                raise
            ctx.errors.append(caught_failure.to_record())
        except (KeyError, TypeError, ValueError) as exc:
            conversion_failure = StageFailure(
                error_code,
                stage,
                scope,
                "Représentations documentaires incohérentes",
                repr(exc),
            )
            if not allow_partial:
                raise conversion_failure from exc
            ctx.errors.append(conversion_failure.to_record())

    # Un document détecté mais dépourvu d'IR est un échec local explicite.
    missing_ir = set(probe_documents) - seen_document_ids
    for document_id in sorted(missing_ir):
        missing_failure = StageFailure(error_code, stage, document_id, "TechnicalDocumentIR absent")
        if not allow_partial:
            raise missing_failure
        # Évite un doublon lorsqu'un IR présent mais invalide a déjà été journalisé.
        if document_id not in attempted_document_ids:
            ctx.errors.append(missing_failure.to_record())

    if not documents:
        raise StageFailure(error_code, stage, ctx.run_id, "Aucun document IR publiable")
    return reader, bundle, probe, documents
