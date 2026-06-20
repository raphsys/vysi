from __future__ import annotations

from collections import Counter

from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import (
    ContainerPartCatalog,
    CoverageItem,
    FeatureCoverageReport,
    NativeDocument,
    PreservationIssue,
    PreservationReport,
)
from vysi.document_source.domain.enums import Severity


def build_quality_reports(
    native: NativeDocument,
    catalog: ContainerPartCatalog,
    ir_unit_count: int,
) -> tuple[FeatureCoverageReport, PreservationReport]:
    counts = Counter(node.kind for node in native.nodes)
    items: list[CoverageItem] = []
    for feature, count in sorted(counts.items()):
        normalized = count if feature not in {"opaque_document"} else 0
        items.append(
            CoverageItem(
                feature=feature,
                encountered_count=count,
                extracted_count=count,
                preserved_count=count,
                normalized_count=normalized,
                rendered_count=0,
                unsupported_count=count if feature == "opaque_document" else 0,
                omitted_count=0,
                severity=Severity.WARNING if feature == "opaque_document" else Severity.INFO,
            )
        )
    if not items:
        ratio = 0.0
    else:
        total = sum(item.encountered_count for item in items)
        ratio = sum(item.extracted_count for item in items) / max(1, total)
    coverage = FeatureCoverageReport(
        header=header("document_source.feature_coverage_report"),
        items=tuple(items),
        coverage_ratio=ratio,
    )

    issues: list[PreservationIssue] = []
    if native.profile.startswith("legacy_ole.partial"):
        issues.append(
            PreservationIssue(
                stage="source_to_native",
                feature="legacy_ole_structure",
                issue_kind="partial_extraction",
                severity=Severity.WARNING,
                description="Les flux OLE sont inventoriés mais leur sémantique complète n'est pas encore extraite.",
            )
        )
    if native.profile.endswith("placeholder.v1"):
        issues.append(
            PreservationIssue(
                stage="source_to_native",
                feature="legacy_v2_reader",
                issue_kind="migration_pending",
                severity=Severity.WARNING,
                description="Le lecteur v2 sera migré dans une livraison ultérieure.",
            )
        )
    if ir_unit_count < len(native.nodes):
        issues.append(
            PreservationIssue(
                stage="native_to_common_ir",
                feature="format_specific_nodes",
                issue_kind="projection_partial",
                severity=Severity.INFO,
                description="Certaines unités natives techniques ne sont pas projetées dans l'IR commune.",
            )
        )
    opaque = sum(1 for part in catalog.parts if part.opaque)
    preservation = PreservationReport(
        header=header("document_source.preservation_report"),
        issues=tuple(issues),
        opaque_parts_preserved=opaque,
        roundtrip_risk="high" if issues else "low",
    )
    return coverage, preservation
