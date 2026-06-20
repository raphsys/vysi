from __future__ import annotations

from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import (
    ContainerPartCatalog,
    SecurityFinding,
    SecurityReport,
)
from vysi.document_source.domain.enums import FinalStatus, Severity


def assess_security(catalog: ContainerPartCatalog) -> SecurityReport:
    findings: list[SecurityFinding] = []
    for part in catalog.parts:
        for flag in part.security_flags:
            findings.append(
                SecurityFinding(
                    code=f"container.{flag}",
                    severity=Severity.WARNING if flag == "custom_xml" else Severity.ERROR,
                    description=f"Partie sensible détectée et conservée inerte: {part.path}",
                    source_ref=part.part_id,
                    inert=True,
                )
            )
    for rel in catalog.relationships:
        if rel.external:
            findings.append(
                SecurityFinding(
                    code="relationship.external",
                    severity=Severity.WARNING,
                    description=f"Relation externe non résolue: {rel.target}",
                    source_ref=rel.relationship_id,
                    inert=True,
                )
            )
    status = FinalStatus.REVIEW if findings else FinalStatus.OK
    return SecurityReport(
        header=header("document_source.security_report"),
        findings=tuple(findings),
        external_access_performed=False,
        active_content_executed=False,
        final_status=status,
    )
