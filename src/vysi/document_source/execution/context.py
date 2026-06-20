from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vysi.document_source.contracts_v2.validation import SchemaStore
from vysi.document_source.execution.errors import StageFailure


@dataclass
class ExecutionContext:
    workspace: Path
    schemas: SchemaStore
    run_id: str
    producer_version: str
    cancel_file: Path | None = None
    bindings: dict[str, bytes] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    references: list[dict[str, str]] = field(default_factory=list)
    completed_nodes: list[str] = field(default_factory=list)
    max_wall_seconds: float | None = None
    max_cpu_seconds: float | None = None
    started_monotonic: float = field(default_factory=time.monotonic)
    started_cpu: float = field(default_factory=time.process_time)

    def configure_budget(self, resource_budget: dict[str, Any]) -> None:
        self.max_wall_seconds = float(resource_budget["max_wall_seconds"])
        self.max_cpu_seconds = float(resource_budget["max_cpu_seconds"])

    def check_cancelled(self, stage: str) -> None:
        if self.cancel_file is not None and self.cancel_file.exists():
            raise StageFailure(
                code="DS-RUN-003",
                stage=stage,
                scope=self.run_id,
                message="Annulation demandée",
                severity="warning",
                retryable=True,
                recoverable=True,
                action_taken="cancelled",
            )
        if (
            self.max_wall_seconds is not None
            and time.monotonic() - self.started_monotonic > self.max_wall_seconds
        ):
            raise StageFailure(
                "DS-LIM-001",
                stage,
                self.run_id,
                "Budget max_wall_seconds dépassé",
                severity="error",
                retryable=True,
                recoverable=True,
                action_taken="cancelled",
            )
        if (
            self.max_cpu_seconds is not None
            and time.process_time() - self.started_cpu > self.max_cpu_seconds
        ):
            raise StageFailure(
                "DS-LIM-001",
                stage,
                self.run_id,
                "Budget max_cpu_seconds dépassé",
                severity="error",
                retryable=True,
                recoverable=True,
                action_taken="cancelled",
            )
