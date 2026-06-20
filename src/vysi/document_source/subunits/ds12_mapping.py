from __future__ import annotations

from typing import Any, cast

from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.representation_v2 import MappingError, build_mapping_catalog

from .representation_inputs import load_document_representations


def execute(ctx: ExecutionContext, policy: dict[str, Any]) -> list[dict[str, str]]:
    ctx.check_cancelled("DS12")
    allow_partial = bool(policy["ingestion_policy"]["allow_partial"])
    reader, _bundle, _probe, documents = load_document_representations(
        ctx, stage="DS12", error_code="DS-MAP-001", allow_partial=allow_partial
    )
    published: list[dict[str, str]] = []
    for document in documents:
        ctx.check_cancelled("DS12")
        try:
            evidence_refs = [
                value for value in document.evidence.values() if (ctx.workspace / value).is_file()
            ]
            body = build_mapping_catalog(
                document_id=document.document_id,
                producer_version=ctx.producer_version,
                inventory=document.inventory,
                container=document.container,
                native=document.native,
                ir=document.ir,
                rendered=document.rendered,
                geometry=document.geometry,
                assets=document.assets,
                evidence_refs=evidence_refs,
            )
            inferred = any(
                str(item["exactness"]) != "exact"
                for item in cast(list[dict[str, Any]], body["mappings"])
            )
            contract = make_contract(
                "representation_mapping_catalog",
                body,
                status="review" if inferred else "ok",
                producer_version=ctx.producer_version,
                contract_seed={
                    "document_id": document.document_id,
                    "mapping_ids": [item["mapping_id"] for item in body["mappings"]],
                },
            )
            _, reference = validate_and_write(
                ctx.workspace,
                f"mapping/{document.document_id}/representation_mapping_catalog.json",
                "representation_mapping_catalog",
                contract,
                ctx.schemas,
            )
            ctx.references.append(reference)
            published.append(reference)
        except MappingError as exc:
            failure = StageFailure(
                "DS-MAP-002",
                "DS12",
                document.document_id,
                "Cartographie des représentations impossible",
                str(exc),
            )
            if not allow_partial:
                raise failure from exc
            ctx.errors.append(failure.to_record())
    reader.verify_unchanged()
    if not published:
        raise StageFailure("DS-MAP-002", "DS12", ctx.run_id, "Aucune cartographie publiable")
    ctx.completed_nodes.append("DS12")
    return published
