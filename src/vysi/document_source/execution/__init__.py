"""Execution primitives for DOCUMENT_SOURCE v2."""

from .coordinator import (
    PipelineResult,
    PreflightResult,
    run_ir,
    run_mapping,
    run_native,
    run_preflight,
    run_quality,
)

__all__ = [
    "PipelineResult",
    "PreflightResult",
    "run_ir",
    "run_mapping",
    "run_native",
    "run_preflight",
    "run_quality",
]
