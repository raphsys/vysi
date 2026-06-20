from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CheckStatus = Literal["pass", "warning", "fail", "not_applicable"]
CheckKind = Literal[
    "schema",
    "hash",
    "reference",
    "invariant",
    "security",
    "format",
    "policy",
    "storage",
    "identity",
    "completeness",
    "execution",
    "determinism",
]
Severity = Literal["info", "warning", "error", "critical"]
PackageStatus = Literal["ok", "review", "rejected", "error", "cancelled"]


@dataclass(frozen=True)
class ValidationCheck:
    check_id: str
    code: str
    kind: CheckKind
    scope: str
    status: CheckStatus
    severity: Severity
    blocking: bool
    message: str
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "code": self.code,
            "kind": self.kind,
            "scope": self.scope,
            "status": self.status,
            "severity": self.severity,
            "blocking": self.blocking,
            "message": self.message,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class DocumentValidationResult:
    document_id: str
    status: PackageStatus
    commit_eligible: bool
    check_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    error_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status": self.status,
            "commit_eligible": self.commit_eligible,
            "check_refs": list(self.check_refs),
            "evidence_refs": list(self.evidence_refs),
            "error_refs": list(self.error_refs),
        }
