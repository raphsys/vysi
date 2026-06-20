from __future__ import annotations

import hashlib
import shutil
from typing import Any, cast

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import (
    contract_reference,
    make_contract,
    sha256_path,
    write_json,
)
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.rendering_v2 import (
    RenderingError,
    SourceRenderer,
    default_renderers,
    select_renderer,
    validate_rendering_invariants,
)

from .representation_inputs import load_document_representations


def _unsupported_view(
    *, document_id: str, requested_profile: str, producer_version: str, message: str
) -> dict[str, Any]:
    view_id = stable_id(
        "view",
        {
            "document_id": document_id,
            "requested_profile": requested_profile,
            "status": "unsupported",
            "message": message,
        },
    )
    return {
        "view_id": view_id,
        "view_kind": "unsupported",
        "requested_profile": requested_profile,
        "renderer": "vysi_no_compatible_renderer",
        "renderer_version": producer_version,
        "environment_hash": hashlib.sha256(b"vysi:unsupported-rendering").hexdigest(),
        "environment": {
            "renderer_family": "none",
            "profile": requested_profile,
            "python": "not_applicable",
            "platform": "not_applicable",
            "machine": "not_applicable",
            "locale": "not_applicable",
            "timezone": "not_applicable",
            "network": "denied",
            "macros": "disabled",
            "field_update": "disabled",
            "formula_recalculation": "disabled",
        },
        "determinism": "deterministic",
        "status": "unsupported",
        "locale": None,
        "timezone": None,
        "font_substitutions": [],
        "warnings": [message],
        "measurement_basis": "unsupported",
        "visibility_summary": {
            "serialized_refs": 0,
            "visible_refs": 0,
            "clipped_refs": 0,
            "omitted_refs": 0,
            "visual_fidelity_assessed": False,
        },
    }


def _publish_document(
    ctx: ExecutionContext,
    *,
    document: Any,
    requested_profiles: list[str],
    mode: str,
    policy: dict[str, Any],
    renderers: tuple[SourceRenderer, ...],
) -> tuple[list[dict[str, str]], bool]:
    views: list[dict[str, Any]] = []
    surfaces: list[dict[str, Any]] = []
    spaces: list[dict[str, Any]] = []
    geometries: list[dict[str, Any]] = []
    asset_items: dict[str, dict[str, Any]] = {}
    materials: dict[str, Any] = {}
    partial = False

    for requested_profile in requested_profiles:
        ctx.check_cancelled("DS11")
        try:
            backend = select_renderer(
                renderers,
                profile_kind=str(document.profile.get("profile_kind")),
                requested_profile=requested_profile,
            )
            max_temp_bytes = int(cast(dict[str, Any], policy["resource_budget"])["max_temp_bytes"])
            output = backend.render(
                document_id=document.document_id,
                profile=document.profile,
                native=document.native,
                ir=document.ir,
                artifact_records=document.artifact_records,
                workspace=ctx.workspace,
                requested_profile=requested_profile,
                max_output_bytes=max_temp_bytes,
                check_cancelled=lambda: ctx.check_cancelled("DS11"),
            )
            views.append(output.view)
            partial = partial or str(output.view["status"]) != "available"
            for item in output.surfaces:
                surfaces.append(
                    {
                        "surface_id": item.surface_id,
                        "view_id": str(output.view["view_id"]),
                        "surface_kind": item.surface_kind,
                        "ordinal": item.ordinal,
                        "width": item.width,
                        "height": item.height,
                        "unit": item.unit,
                        "rotation": item.rotation,
                        "dpi": item.dpi,
                        "status": item.status,
                        "fidelity": item.fidelity,
                        "media_type": item.media_type,
                        "coordinate_space_id": next(
                            str(space["coordinate_space_id"])
                            for space in output.coordinate_spaces
                            if str(space["owner_id"]) == item.surface_id
                        ),
                        "native_unit_refs": list(item.native_unit_refs),
                        "serialized_native_unit_refs": list(item.serialized_native_unit_refs),
                        "clipped_native_unit_refs": list(item.clipped_native_unit_refs),
                        "omitted_native_unit_refs": list(item.omitted_native_unit_refs),
                        "visibility_basis": item.visibility_basis,
                        "asset_refs": list(item.asset_ids),
                    }
                )
            spaces.extend(output.coordinate_spaces)
            geometries.extend(
                {
                    "geometry_id": item.geometry_id,
                    "owner_id": item.owner_id,
                    "coordinate_space_id": item.coordinate_space_id,
                    "geometry_kind": item.geometry_kind,
                    "values": list(item.values),
                    "source": item.source,
                    "confidence": item.confidence,
                    "method": item.method,
                    "native_unit_refs": list(item.native_unit_refs),
                    "visibility": item.visibility,
                    "clipped": item.clipped,
                    "serialized": item.serialized,
                    "role": item.role,
                }
                for item in output.geometries
            )
            for asset in output.assets:
                previous = asset_items.get(asset.asset_id)
                asset_record = {
                    "asset_id": asset.asset_id,
                    "asset_kind": asset.asset_kind,
                    "producer": "vysi.document_source.ds11",
                    "input_refs": list(asset.input_refs),
                    "stored_ref": {
                        "path": asset.relative_path,
                        "sha256": asset.content_sha256,
                        "media_type": asset.media_type,
                        "size_bytes": asset.size_bytes,
                    },
                    "determinism": asset.determinism,
                    "properties": list(asset.properties),
                }
                if previous is not None and previous != asset_record:
                    raise StageFailure(
                        "DS-RND-001",
                        "DS11",
                        document.document_id,
                        f"Asset dupliqué avec définitions divergentes: {asset.asset_id}",
                    )
                asset_items[asset.asset_id] = asset_record
                prior_material = materials.get(asset.relative_path)
                if prior_material is not None and (
                    prior_material.content_sha256 != asset.content_sha256
                    or prior_material.size_bytes != asset.size_bytes
                ):
                    raise StageFailure(
                        "DS-RND-001",
                        "DS11",
                        document.document_id,
                        f"Chemin d'asset réutilisé avec octets divergents: {asset.relative_path}",
                    )
                materials[asset.relative_path] = asset
                unique_asset_bytes = sum(item.size_bytes for item in materials.values())
                if unique_asset_bytes > max_temp_bytes:
                    raise StageFailure(
                        "DS-LIM-001",
                        "DS11",
                        document.document_id,
                        "Budget max_temp_bytes dépassé par les assets uniques de rendu",
                        f"limite={max_temp_bytes} observé={unique_asset_bytes}",
                        severity="error",
                        retryable=True,
                        recoverable=True,
                        action_taken="cancelled",
                    )
        except RenderingError as exc:
            if exc.budget_exceeded:
                raise StageFailure(
                    "DS-LIM-001",
                    "DS11",
                    document.document_id,
                    "Budget max_temp_bytes dépassé pendant le rendu",
                    str(exc),
                    severity="error",
                    retryable=True,
                    recoverable=True,
                    action_taken="cancelled",
                ) from exc
            if mode == "required":
                raise StageFailure(
                    "DS-RND-002",
                    "DS11",
                    document.document_id,
                    f"Profil de rendu exigé indisponible: {requested_profile}",
                    str(exc),
                ) from exc
            views.append(
                _unsupported_view(
                    document_id=document.document_id,
                    requested_profile=requested_profile,
                    producer_version=ctx.producer_version,
                    message=str(exc),
                )
            )
            partial = True

    # Identités et relations doivent rester uniques même avec plusieurs profils.
    for label, values in (
        ("view", [str(item["view_id"]) for item in views]),
        ("surface", [str(item["surface_id"]) for item in surfaces]),
        ("coordinate_space", [str(item["coordinate_space_id"]) for item in spaces]),
        ("geometry", [str(item["geometry_id"]) for item in geometries]),
    ):
        if len(values) != len(set(values)):
            raise StageFailure(
                "DS-RND-001",
                "DS11",
                document.document_id,
                f"Identifiants {label} dupliqués entre profils de rendu",
            )

    total_asset_bytes = sum(asset.size_bytes for asset in materials.values())
    max_temp_bytes = int(cast(dict[str, Any], policy["resource_budget"])["max_temp_bytes"])
    if total_asset_bytes > max_temp_bytes:
        raise StageFailure(
            "DS-LIM-001",
            "DS11",
            document.document_id,
            "Budget max_temp_bytes dépassé par les assets de rendu",
            f"limite={max_temp_bytes} observé={total_asset_bytes}",
            severity="error",
            retryable=True,
            recoverable=True,
            action_taken="cancelled",
        )
    ctx.check_cancelled("DS11")

    status = "review" if partial else "ok"
    rendered_body = {
        "document_id": document.document_id,
        "views": sorted(views, key=lambda item: str(item["view_id"])),
        "surfaces": sorted(surfaces, key=lambda item: str(item["surface_id"])),
    }
    geometry_body = {
        "document_id": document.document_id,
        "coordinate_spaces": sorted(spaces, key=lambda item: str(item["coordinate_space_id"])),
        "geometries": sorted(geometries, key=lambda item: str(item["geometry_id"])),
    }
    assets_body = {
        "document_id": document.document_id,
        "assets": [asset_items[key] for key in sorted(asset_items)],
    }
    rendered = make_contract(
        "rendered_view_catalog",
        rendered_body,
        status=status,
        producer_version=ctx.producer_version,
        contract_seed={
            "document_id": document.document_id,
            "views": [item["view_id"] for item in rendered_body["views"]],
            "surfaces": [item["surface_id"] for item in rendered_body["surfaces"]],
        },
    )
    geometry = make_contract(
        "geometry_catalog",
        geometry_body,
        status=status,
        producer_version=ctx.producer_version,
        contract_seed={
            "document_id": document.document_id,
            "geometries": [item["geometry_id"] for item in geometry_body["geometries"]],
        },
    )
    assets = make_contract(
        "derived_asset_catalog",
        assets_body,
        status=status,
        producer_version=ctx.producer_version,
        contract_seed={
            "document_id": document.document_id,
            "assets": [item["asset_id"] for item in assets_body["assets"]],
        },
    )
    ctx.schemas.validate("rendered_view_catalog", rendered)
    ctx.schemas.validate("geometry_catalog", geometry)
    ctx.schemas.validate("derived_asset_catalog", assets)
    validate_rendering_invariants(rendered, geometry, assets)

    final_dir = ctx.workspace / "rendered" / document.document_id
    staging_dir = ctx.workspace / "runtime" / "tmp" / f"ds11-{document.document_id}"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    for relative, material in materials.items():
        expected_prefix = f"rendered/{document.document_id}/"
        if not relative.startswith(expected_prefix):
            raise StageFailure(
                "DS-RND-001", "DS11", document.document_id, "Chemin d'asset hors zone DS11"
            )
        local = staging_dir / relative.removeprefix(expected_prefix)
        local.parent.mkdir(parents=True, exist_ok=True)
        if material.payload is not None:
            local.write_bytes(material.payload)
        else:
            assert material.source_path is not None
            if not material.source_path.is_file() or material.source_path.is_symlink():
                raise StageFailure(
                    "DS-RND-001", "DS11", relative, "Source de passthrough absente ou irrégulière"
                )
            shutil.copyfile(material.source_path, local)
    write_json(staging_dir / "rendered_view_catalog.json", rendered)
    write_json(staging_dir / "geometry_catalog.json", geometry)
    write_json(staging_dir / "derived_asset_catalog.json", assets)

    for asset_record in cast(list[dict[str, Any]], assets["assets"]):
        stored = cast(dict[str, Any], asset_record["stored_ref"])
        relative = str(stored["path"])
        local = staging_dir / relative.removeprefix(f"rendered/{document.document_id}/")
        if not local.is_file() or local.is_symlink():
            raise StageFailure("DS-RND-001", "DS11", relative, "Asset DS11 absent")
        if sha256_path(local) != str(stored["sha256"]):
            raise StageFailure("DS-RND-001", "DS11", relative, "Hash asset DS11 invalide")
        if local.stat().st_size != int(stored["size_bytes"]):
            raise StageFailure("DS-RND-001", "DS11", relative, "Taille asset DS11 invalide")

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    backup = final_dir.with_name(final_dir.name + ".before_ds11")
    if backup.exists():
        shutil.rmtree(backup)
    promoted = False
    try:
        if final_dir.exists():
            final_dir.replace(backup)
        staging_dir.replace(final_dir)
        promoted = True
        refs = [
            contract_reference(ctx.workspace, final_dir / filename, value)
            for filename, value in (
                ("rendered_view_catalog.json", rendered),
                ("geometry_catalog.json", geometry),
                ("derived_asset_catalog.json", assets),
            )
        ]
    except Exception:
        # La publication n'est considérée comme acquise qu'après la création
        # et la vérification des références de checkpoint. Une défaillance à
        # ce stade restaure l'instantané précédent au lieu de laisser un
        # répertoire DS11 partiellement promu.
        if promoted and final_dir.exists():
            shutil.rmtree(final_dir)
        if backup.exists():
            backup.replace(final_dir)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    return refs, partial


def execute(
    ctx: ExecutionContext,
    policy: dict[str, Any],
    *,
    renderers: tuple[SourceRenderer, ...] | None = None,
) -> list[dict[str, str]]:
    ctx.check_cancelled("DS11")
    rendering_policy = cast(dict[str, Any], policy["rendering_policy"])
    mode = str(rendering_policy["mode"])
    profiles = sorted(set(str(item) for item in rendering_policy.get("profiles", [])))
    if mode == "none":
        ctx.completed_nodes.append("DS11")
        return []
    requested_profiles = profiles or ["source_reference"]
    active_renderers = renderers or default_renderers(ctx.producer_version)
    allow_partial = bool(policy["ingestion_policy"]["allow_partial"])
    reader, _bundle, _probe, documents = load_document_representations(
        ctx, stage="DS11", error_code="DS-RND-001", allow_partial=allow_partial
    )
    published: list[dict[str, str]] = []
    partial_count = 0
    for document in documents:
        ctx.check_cancelled("DS11")
        try:
            refs, partial = _publish_document(
                ctx,
                document=document,
                requested_profiles=requested_profiles,
                mode=mode,
                policy=policy,
                renderers=active_renderers,
            )
            ctx.references.extend(refs)
            published.extend(refs)
            partial_count += int(partial)
        except StageFailure as exc:
            if exc.code in {"DS-RUN-003", "DS-LIM-001"} or not allow_partial or mode == "required":
                raise
            ctx.errors.append(exc.to_record())
    reader.verify_unchanged()
    if not published:
        raise StageFailure("DS-RND-002", "DS11", ctx.run_id, "Aucun rendu source publiable")
    if partial_count:
        ctx.errors.append(
            StageFailure(
                "DS-RND-003",
                "DS11",
                ctx.run_id,
                f"{partial_count} document(s) rendu(s) partiellement ou non pris en charge",
                severity="warning",
                retryable=True,
                recoverable=True,
                action_taken="review",
            ).to_record()
        )
    ctx.completed_nodes.append("DS11")
    return published
