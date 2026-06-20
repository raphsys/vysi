from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..models import RenderOutput
from .native import _render_target
from .native import render_document as render_legacy_route


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
    check = check_cancelled or (lambda: None)
    check()
    if str(profile.get("profile_kind")) in {"plain_text", "wordprocessing", "spreadsheet"}:
        return _render_target(
            document_id=document_id,
            profile=profile,
            requested_profile=requested_profile,
            producer_version=producer_version,
            renderer_id=renderer_id,
            max_output_bytes=max_output_bytes,
            check=check,
        )
    return render_legacy_route(
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
        check_cancelled=check,
    )


__all__ = ["render_document"]
