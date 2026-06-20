from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from vysi.document_source.contracts.models import NativeDocument, RenderedViewCatalog


@runtime_checkable
class Renderer(Protocol):
    """Port de rendu dérivé et traçable."""

    renderer_id: str
    renderer_version: str

    def render(self, source: Path, native: NativeDocument) -> RenderedViewCatalog:
        """Produit une vue dérivée sans remplacer la structure native."""
