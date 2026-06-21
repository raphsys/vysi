from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id

from ..engine import RenderingError
from ..engine import render_document as render_legacy
from ..models import RenderOutput
from .common import environment
from .grid import finalize_output
from .matrix import render_matrix
from .text import render_text


def _render_target(
    *,
    document_id: str,
    profile: dict[str, Any],
    requested_profile: str,
    producer_version: str,
    renderer_id: str,
    max_output_bytes: int | None,
    check: Callable[[], None],
) -> RenderOutput:
    profile_kind = str(profile.get("profile_kind"))
    if requested_profile not in {"source_reference", "technical_preview"}:
        raise RenderingError(f"Profil de rendu indisponible: {requested_profile}", unsupported=True)
    environment_data, environment_hash = environment(requested_profile, renderer_id)
    view_id = stable_id(
        "view",
        {
            "document_id": document_id,
            "profile_kind": profile_kind,
            "requested_profile": requested_profile,
            "renderer": renderer_id,
        },
    )
    produced = 0

    def account(size: int) -> None:
        nonlocal produced
        if size < 0:
            raise RenderingError("Taille d'asset négative")
        if max_output_bytes is not None and produced + size > max_output_bytes:
            raise RenderingError("Budget max_temp_bytes dépassé", budget_exceeded=True)
        produced += size

    if profile_kind in {"plain_text", "wordprocessing"}:
        output = render_text(
            document_id=document_id,
            view_id=view_id,
            profile=profile,
            profile_kind=profile_kind,
            check=check,
            account=account,
        )
    else:
        output = render_matrix(
            document_id=document_id,
            view_id=view_id,
            profile=profile,
            check=check,
            account=account,
        )
    return finalize_output(
        output=output,
        view_id=view_id,
        requested_profile=requested_profile,
        renderer_id=renderer_id,
        producer_version=producer_version,
        environment=environment_data,
        environment_hash=environment_hash,
    )


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
