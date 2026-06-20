from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id


@dataclass
class StageFailure(Exception):
    code: str
    stage: str
    scope: str
    message: str
    technical_details: str = ""
    severity: str = "error"
    retryable: bool = False
    recoverable: bool = False
    action_taken: str = "aborted_stage"

    def __str__(self) -> str:
        return f"{self.code} {self.stage}: {self.message}"

    def to_record(self) -> dict[str, Any]:
        identity = {
            "code": self.code,
            "stage": self.stage,
            "scope": self.scope,
            "message": self.message,
            "technical_details": self.technical_details,
        }
        return {
            "error_id": stable_id("error", identity),
            "code": self.code,
            "stage": self.stage,
            "scope": self.scope,
            "severity": self.severity,
            "message": self.message,
            "technical_details": self.technical_details[:16000],
            "cause_error_id": None,
            "retryable": self.retryable,
            "recoverable": self.recoverable,
            "action_taken": self.action_taken,
            "evidence_refs": [],
        }
