from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _copy_contract(
    ctx: ExecutionContext,
    source_ref: dict[str, Any],
    target_relative: str,
    schema_key: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    source_path = ctx.workspace / str(source_ref["path"])
    if not source_path.is_file():
        raise StageFailure(
            "DS-NAT-001", "DS09", str(source_ref["path"]), "Contrat de décodage absent"
        )
    value = _load(source_path)
    ctx.schemas.validate(schema_key, value)
    _, ref = validate_and_write(
        ctx.workspace,
        target_relative,
        schema_key,
        value,
        ctx.schemas,
    )
    ctx.references.append(ref)
    return value, ref


def execute(ctx: ExecutionContext, decode_results: list[dict[str, Any]]) -> list[dict[str, str]]:
    ctx.check_cancelled("DS09")
    published: list[dict[str, str]] = []
    for result in decode_results:
        ctx.check_cancelled("DS09")
        document_id = str(result["document_id"])
        if result["decode_state"] not in {"complete", "partial"}:
            continue
        slots = result["output_slots"]
        required = ("native", "styles", "relationships", "metadata", "annotations", "resources")
        if any(slots[name]["state"] not in {"available", "partial"} for name in required):
            raise StageFailure("DS-NAT-001", "DS09", document_id, "Slots de décodage incomplets")
        staging_native = _load(ctx.workspace / str(slots["native"]["ref"]["path"]))
        profile_ref = staging_native["profile_ref"]
        profile_schema_key = str(profile_ref["schema_id"]).removeprefix("document_source.")
        _, canonical_profile_ref = _copy_contract(
            ctx,
            profile_ref,
            f"native/{document_id}/profile.json",
            profile_schema_key,
        )
        native = make_contract(
            "native_document",
            {
                "document_id": document_id,
                "profile_kind": staging_native["profile_kind"],
                "profile_version": staging_native["profile_version"],
                "profile_ref": canonical_profile_ref,
                "root_unit_ids": staging_native["root_unit_ids"],
                "opaque_parts": staging_native["opaque_parts"],
                "capabilities": staging_native.get("capabilities", []),
            },
            status=str(staging_native["header"]["status"]),
            producer_version=ctx.producer_version,
        )
        _, native_ref = validate_and_write(
            ctx.workspace,
            f"native/{document_id}/native_document.json",
            "native_document",
            native,
            ctx.schemas,
        )
        ctx.references.append(native_ref)
        published.append(native_ref)
        for slot_name, schema_key, filename in (
            ("styles", "native_style_catalog", "styles.json"),
            ("relationships", "native_relationship_catalog", "relationships.json"),
            ("metadata", "native_metadata_catalog", "metadata.json"),
            ("annotations", "native_annotation_catalog", "annotations.json"),
            ("resources", "native_resource_catalog", "resources.json"),
        ):
            _, ref = _copy_contract(
                ctx,
                slots[slot_name]["ref"],
                f"native/{document_id}/{filename}",
                schema_key,
            )
            published.append(ref)
    ctx.completed_nodes.append("DS09")
    return published
