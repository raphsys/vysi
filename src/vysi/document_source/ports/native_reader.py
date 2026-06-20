from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from vysi.document_source.contracts.models import FormatDescriptor, NativeDocument


@runtime_checkable
class NativeReader(Protocol):
    """Port d'un lecteur natif fortement typé."""

    reader_id: str
    reader_version: str

    def supports(self, descriptor: FormatDescriptor) -> bool:
        """Indique si le lecteur sait traiter le format détecté."""

    def read(self, source: Path, descriptor: FormatDescriptor) -> NativeDocument:
        """Produit le modèle natif sans exécuter de contenu actif."""
