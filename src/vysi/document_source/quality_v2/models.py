from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

AxisName = Literal[
    "binary",
    "structural",
    "technical_semantic",
    "style",
    "relationship",
    "visual",
    "interactive",
    "computational",
    "roundtrip",
]
Severity = Literal["info", "warning", "error", "critical"]
LossKind = Literal["loss", "approximation", "unsupported", "omission", "repair", "conversion"]
TransitionState = Literal["lossless", "lossy_declared", "partial", "failed", "not_run"]
TransitionExactness = Literal["exact", "approximate", "inferred", "not_applicable"]


@dataclass(frozen=True)
class FeatureMeasurement:
    feature: str
    axis: AxisName
    basis: str
    encountered: int
    extracted: int
    preserved: int
    projected: int
    rendered: int
    opaque: int
    approximated: int
    unsupported: int
    omitted: int
    severity: Severity
    evidence_refs: tuple[str, ...]
    omitted_refs: tuple[str, ...] = ()
    approximated_refs: tuple[str, ...] = ()
    unsupported_refs: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "axis": self.axis,
            "basis": self.basis,
            "encountered": self.encountered,
            "extracted": self.extracted,
            "preserved": self.preserved,
            "projected": self.projected,
            "rendered": self.rendered,
            "opaque": self.opaque,
            "approximated": self.approximated,
            "unsupported": self.unsupported,
            "omitted": self.omitted,
            "severity": self.severity,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class LossRecord:
    loss_id: str
    feature: str
    stage: str
    severity: Severity
    kind: LossKind
    description: str
    source_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "loss_id": self.loss_id,
            "feature": self.feature,
            "stage": self.stage,
            "severity": self.severity,
            "kind": self.kind,
            "description": self.description,
            "source_refs": list(self.source_refs),
        }


@dataclass(frozen=True)
class PreservationTransition:
    from_layer: str
    to_layer: str
    state: TransitionState
    producer: str
    producer_version: str
    method: str
    determinism: Literal["deterministic", "nondeterministic"]
    exactness: TransitionExactness
    confidence: float | None
    input_refs: tuple[str, ...]
    output_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    loss_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_layer": self.from_layer,
            "to_layer": self.to_layer,
            "state": self.state,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "method": self.method,
            "determinism": self.determinism,
            "exactness": self.exactness,
            "confidence": self.confidence,
            "input_refs": list(self.input_refs),
            "output_refs": list(self.output_refs),
            "evidence_refs": list(self.evidence_refs),
            "loss_refs": list(self.loss_refs),
        }
