from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from .engine import RenderingError, render_document
from .models import RenderOutput


@dataclass(frozen=True)
class RendererCapability:
    supported: bool
    priority: int
    reason: str | None = None


@runtime_checkable
class SourceRenderer(Protocol):
    """Backend DS11 isolé derrière un contrat de capacité explicite."""

    @property
    def renderer_id(self) -> str:
        ...

    @property
    def renderer_version(self) -> str:
        ...

    def capability(self, profile_kind: str, requested_profile: str) -> RendererCapability:
        """Déclare la capacité sans ouvrir ni modifier la source."""

    def render(
        self,
        *,
        document_id: str,
        profile: dict[str, Any],
        native: dict[str, Any],
        ir: dict[str, Any],
        artifact_records: list[dict[str, Any]],
        workspace: Path,
        requested_profile: str,
        max_output_bytes: int,
        check_cancelled: Callable[[], None],
    ) -> RenderOutput:
        """Produit des sorties matérielles non publiées et sans mutation des entrées."""


@dataclass(frozen=True)
class BuiltinReferenceRenderer:
    renderer_version: str
    renderer_id: str = "vysi_builtin_reference_renderer"

    def capability(self, profile_kind: str, requested_profile: str) -> RendererCapability:
        if requested_profile not in {
            "source_reference",
            "technical_preview",
            "native_passthrough",
        }:
            return RendererCapability(False, 0, f"Profil inconnu: {requested_profile}")
        if profile_kind == "legacy_ole":
            return RendererCapability(False, 0, "Conteneur OLE historique non pris en charge")
        if requested_profile == "native_passthrough":
            supported = profile_kind in {"fixed_layout", "raster"}
            return RendererCapability(
                supported,
                100 if supported else 0,
                None if supported else f"Passthrough indisponible pour {profile_kind}",
            )
        if requested_profile == "technical_preview":
            supported = profile_kind in {
                "plain_text",
                "wordprocessing",
                "spreadsheet",
                "presentation",
            }
            return RendererCapability(
                supported,
                50 if supported else 0,
                None
                if supported
                else f"Aperçu technique non applicable au profil {profile_kind}",
            )
        supported = profile_kind in {
            "plain_text",
            "wordprocessing",
            "spreadsheet",
            "presentation",
            "fixed_layout",
            "raster",
        }
        return RendererCapability(
            supported,
            75 if supported else 0,
            None if supported else f"Référence source indisponible pour {profile_kind}",
        )

    def render(
        self,
        *,
        document_id: str,
        profile: dict[str, Any],
        native: dict[str, Any],
        ir: dict[str, Any],
        artifact_records: list[dict[str, Any]],
        workspace: Path,
        requested_profile: str,
        max_output_bytes: int,
        check_cancelled: Callable[[], None],
    ) -> RenderOutput:
        return render_document(
            document_id=document_id,
            profile=profile,
            native=native,
            ir=ir,
            artifact_records=artifact_records,
            workspace=workspace,
            requested_profile=requested_profile,
            producer_version=self.renderer_version,
            renderer_id=self.renderer_id,
            max_output_bytes=max_output_bytes,
            check_cancelled=check_cancelled,
        )


def default_renderers(producer_version: str) -> tuple[SourceRenderer, ...]:
    renderer: SourceRenderer = BuiltinReferenceRenderer(producer_version)
    return (renderer,)


def select_renderer(
    renderers: Sequence[SourceRenderer],
    *,
    profile_kind: str,
    requested_profile: str,
) -> SourceRenderer:
    candidates: list[tuple[int, str, SourceRenderer]] = []
    reasons: list[str] = []
    for renderer in renderers:
        capability = renderer.capability(profile_kind, requested_profile)
        if capability.supported:
            candidates.append((capability.priority, renderer.renderer_id, renderer))
        elif capability.reason:
            reasons.append(f"{renderer.renderer_id}: {capability.reason}")
    if not candidates:
        detail = "; ".join(sorted(reasons)) or "aucun backend enregistré"
        raise RenderingError(
            f"Aucun backend compatible pour {profile_kind}/{requested_profile}: {detail}",
            unsupported=True,
        )
    # Priorité décroissante, puis identifiant croissant pour rester déterministe.
    candidates.sort(key=lambda item: (-item[0], item[1]))
    return candidates[0][2]
