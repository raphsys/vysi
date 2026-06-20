from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..engine import render_document as render_legacy
from ..models import RenderOutput


def render_document(
    *,
    document_id: str,
    profile: dict[str, Any],
    native: dict[str, Any],
    ir: dict[str, Any],
    artifact_records: list[dict[str, Any]],
    workspace: Path,
    requested_profile: str,
    producer_version: str,
    renderer_id: str = "vysi_builtin_reference_renderer",
    max_output_bytes: int | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> RenderOutput:
    return render_legacy(
        document_id=document_id,
        profile=profile,
        native=native,
        ir=ir,
        artifact_records=artifact_records,
        workspace=workspace,
        requested_profile=requested_profile,
        producer_version=producer_version,
        renderer_id=renderer_id,
        max_output_bytes=max_output_bytes,
        check_cancelled=check_cancelled,
    )
