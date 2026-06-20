from __future__ import annotations

from pathlib import Path
from typing import Any

from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.quality_v2 import QualityError, evaluate_quality
from vysi.document_source.representation_v2 import MappingError, validate_mapping_invariants

from .representation_inputs import load_document_representations


def _projection_warnings(reader: Any, workspace: Path, document_id: str) -> list[str]:
    path = workspace / "ir" / document_id / "projection_warnings.json"
    if not path.is_file():
        return []
    value = reader.load_json(path)
    if str(value.get("document_id", "")) != document_id or not isinstance(
        value.get("warnings"), list
    ):
        raise StageFailure(
            "DS-COV-001", "DS13", document_id, "Avertissements de projection incohérents"
        )
    return [str(item) for item in value["warnings"]]


def _conversion_reports(reader: Any, workspace: Path, document_id: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    root = workspace / "conversion"
    if not root.is_dir():
        return result
    for path in sorted(root.rglob("*.json")):
        value = reader.contract(path, "conversion_report_catalog")
        if str(value.get("document_id", "")) == document_id:
            result.append(value)
    return result


def execute(ctx: ExecutionContext, policy: dict[str, Any]) -> list[dict[str, str]]:
    ctx.check_cancelled("DS13")
    allow_partial = bool(policy["ingestion_policy"]["allow_partial"])
    reader, _bundle, _probe, documents = load_document_representations(
        ctx, stage="DS13", error_code="DS-COV-001", allow_partial=allow_partial
    )
    published: list[dict[str, str]] = []
    for document in documents:
        ctx.check_cancelled("DS13")
        try:
            mapping_path = (
                ctx.workspace
                / "mapping"
                / document.document_id
                / "representation_mapping_catalog.json"
            )
            mapping = reader.contract(
                mapping_path,
                "representation_mapping_catalog",
                document_id=document.document_id,
            )
            validate_mapping_invariants(
                mapping,
                inventory=document.inventory,
                producer_version=ctx.producer_version,
            )
            evidence_refs = [
                value for value in document.evidence.values() if (ctx.workspace / value).is_file()
            ]
            evidence_refs.append(
                f"mapping/{document.document_id}/representation_mapping_catalog.json"
            )
            coverage_body, preservation_body, status = evaluate_quality(
                document_id=document.document_id,
                producer_version=ctx.producer_version,
                inventory=document.inventory,
                artifact_records=document.artifact_records,
                container=document.container,
                native=document.native,
                profile=document.profile,
                styles=document.styles,
                relationships=document.relationships,
                metadata=document.metadata,
                annotations=document.annotations,
                resources=document.resources,
                ir=document.ir,
                mapping=mapping,
                rendered=document.rendered,
                geometry=document.geometry,
                assets=document.assets,
                decode_result=document.decode_result,
                conversion_reports=_conversion_reports(reader, ctx.workspace, document.document_id),
                projection_warnings=_projection_warnings(
                    reader, ctx.workspace, document.document_id
                ),
                evidence_refs=evidence_refs,
                policy=policy,
            )
            coverage = make_contract(
                "feature_coverage_report",
                coverage_body,
                status=status,
                producer_version=ctx.producer_version,
                contract_seed={
                    "document_id": document.document_id,
                    "features": [item["feature"] for item in coverage_body["items"]],
                    "axis_scores": coverage_body["axis_scores"],
                },
            )
            preservation = make_contract(
                "preservation_report",
                preservation_body,
                status=status,
                producer_version=ctx.producer_version,
                contract_seed={
                    "document_id": document.document_id,
                    "loss_ids": [item["loss_id"] for item in preservation_body["losses"]],
                    "transitions": [
                        (item["from_layer"], item["to_layer"], item["state"])
                        for item in preservation_body["transitions"]
                    ],
                },
            )
            _, coverage_ref = validate_and_write(
                ctx.workspace,
                f"quality/{document.document_id}/feature_coverage_report.json",
                "feature_coverage_report",
                coverage,
                ctx.schemas,
            )
            _, preservation_ref = validate_and_write(
                ctx.workspace,
                f"quality/{document.document_id}/preservation_report.json",
                "preservation_report",
                preservation,
                ctx.schemas,
            )
            ctx.references.extend((coverage_ref, preservation_ref))
            published.extend((coverage_ref, preservation_ref))
        except StageFailure as caught_failure:
            if caught_failure.code in {"DS-RUN-003", "DS-LIM-001"} or not allow_partial:
                raise
            ctx.errors.append(caught_failure.to_record())
        except MappingError as exc:
            mapping_failure = StageFailure(
                "DS-COV-001",
                "DS13",
                document.document_id,
                "Catalogue de mapping incohérent",
                str(exc),
            )
            if not allow_partial:
                raise mapping_failure from exc
            ctx.errors.append(mapping_failure.to_record())
        except QualityError as exc:
            quality_failure = StageFailure(
                exc.code,
                "DS13",
                document.document_id,
                "Rapports de couverture ou de préservation incohérents",
                str(exc),
            )
            if not allow_partial:
                raise quality_failure from exc
            ctx.errors.append(quality_failure.to_record())
    reader.verify_unchanged()
    if not published:
        raise StageFailure("DS-COV-002", "DS13", ctx.run_id, "Aucun rapport de qualité publiable")
    ctx.completed_nodes.append("DS13")
    return published
