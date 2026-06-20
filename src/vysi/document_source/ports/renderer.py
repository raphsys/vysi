"""Port public des backends de rendu source DS11."""

from vysi.document_source.rendering_v2.backend import (
    RendererCapability,
    SourceRenderer,
)

# Alias conservé pour les imports historiques du projet. Le contrat actif est
# SourceRenderer, fondé sur les représentations DOCUMENT_SOURCE v2.
Renderer = SourceRenderer

__all__ = ["Renderer", "RendererCapability", "SourceRenderer"]
