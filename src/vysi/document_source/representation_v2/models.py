from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

LayerName = Literal[
    "binary",
    "container",
    "native",
    "technical_ir",
    "rendered",
    "geometry",
    "asset",
]
Exactness = Literal["exact", "approximate", "inferred"]
Determinism = Literal["deterministic", "nondeterministic"]
Cardinality = Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"]


@dataclass(frozen=True, order=True)
class LayerEntity:
    layer: LayerName
    entity_id: str
    kind: str
    source_address: str | None
    owner_id: str | None
    evidence_ref: str


@dataclass(frozen=True)
class MappingEdge:
    mapping_id: str
    source_layer: LayerName
    source_ids: tuple[str, ...]
    target_layer: LayerName
    target_ids: tuple[str, ...]
    relation: str
    cardinality: Cardinality
    exactness: Exactness
    confidence: float
    method: str
    producer: str
    producer_version: str
    determinism: Determinism
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "source_layer": self.source_layer,
            "source_ids": list(self.source_ids),
            "target_layer": self.target_layer,
            "target_ids": list(self.target_ids),
            "relation": self.relation,
            "cardinality": self.cardinality,
            "exactness": self.exactness,
            "confidence": self.confidence,
            "method": self.method,
            "producer": self.producer,
            "producer_version": self.producer_version,
            "determinism": self.determinism,
            "evidence_refs": list(self.evidence_refs),
        }


def cardinality(source_count: int, target_count: int) -> Cardinality:
    if source_count == 1 and target_count == 1:
        return "one_to_one"
    if source_count == 1:
        return "one_to_many"
    if target_count == 1:
        return "many_to_one"
    return "many_to_many"
