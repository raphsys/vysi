from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class RepresentationState(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    NOT_REQUESTED = "not_requested"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"
    BLOCKED_BY_POLICY = "blocked_by_policy"
    FAILED = "failed"


@dataclass(frozen=True)
class ContractHeader:
    schema_id: str
    schema_version: str
    contract_id: str
    content_hash: str
    producer: str
    producer_version: str
    created_at: str
    status: str
    revision: int
    supersedes: str | None = None


@dataclass(frozen=True)
class ContractReference:
    path: str
    sha256: str
    schema_id: str
    schema_version: str
    contract_id: str


@dataclass(frozen=True)
class RepresentationSlot:
    state: RepresentationState
    ref: ContractReference | None
    reason_codes: tuple[str, ...] = ()
    details: str | None = None

    def __post_init__(self) -> None:
        has_content = self.state in {RepresentationState.AVAILABLE, RepresentationState.PARTIAL}
        if has_content and self.ref is None:
            raise ValueError(f"{self.state.value} requires a reference")
        if not has_content and self.ref is not None:
            raise ValueError(f"{self.state.value} forbids a reference")
