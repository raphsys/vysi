from __future__ import annotations

from typing import Any

from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.validation_v2 import DraftValidationError, evaluate_draft_package


def execute(ctx: ExecutionContext, policy: dict[str, Any]) -> dict[str, Any]:
    ctx.check_cancelled("DS14")
    try:
        body, validation_errors = evaluate_draft_package(ctx, policy)
    except StageFailure:
        raise
    except DraftValidationError as exc:
        raise StageFailure(
            "DS-VAL-001",
            "DS14",
            ctx.run_id,
            "Draft package impossible à valider",
            str(exc),
        ) from exc

    ctx.errors.extend(validation_errors)
    report = make_contract(
        "validation_report",
        body,
        status=str(body["package_status"]),
        producer_version=ctx.producer_version,
        contract_seed={
            "run_id": ctx.run_id,
            "snapshot": body["validated_snapshot"]["artifact_set_sha256"],
            "package_status": body["package_status"],
            "commit_eligible": body["commit_eligible"],
            "checks": [item["check_id"] for item in body["checks"]],
        },
    )
    _, ref = validate_and_write(
        ctx.workspace,
        "validation/validation_report.json",
        "validation_report",
        report,
        ctx.schemas,
    )
    ctx.references.append(ref)
    ctx.completed_nodes.append("DS14")
    return report
