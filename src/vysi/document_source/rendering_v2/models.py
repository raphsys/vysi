from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

RenderStatus = Literal["available", "partial", "unsupported", "failed"]
Fidelity = Literal["exact", "approximate", "not_assessed"]
Determinism = Literal["deterministic", "environment_bound", "nondeterministic"]
Visibility = Literal["fully_visible", "partially_clipped", "not_visible", "not_assessed"]
VisibilityBasis = Literal[
    "layout_observed",
    "binary_passthrough",
    "native_dimensions_only",
    "not_assessed",
]


@dataclass(frozen=True)
class AssetOutput:
    asset_id: str
    relative_path: str
    media_type: str
    content_sha256: str
    size_bytes: int
    input_refs: tuple[str, ...]
    asset_kind: str
    determinism: Determinism
    payload: bytes | None = None
    source_path: Path | None = None
    properties: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if (self.payload is None) == (self.source_path is None):
            raise ValueError("Un asset doit avoir exactement une source matérielle")
        if self.size_bytes < 0:
            raise ValueError("Taille d'asset négative")


@dataclass(frozen=True)
class SurfaceOutput:
    surface_id: str
    surface_kind: str
    ordinal: int
    width: float | None
    height: float | None
    unit: str
    native_unit_refs: tuple[str, ...]
    asset_ids: tuple[str, ...]
    status: RenderStatus
    fidelity: Fidelity
    media_type: str | None
    rotation: int = 0
    dpi: float | None = None
    serialized_native_unit_refs: tuple[str, ...] = ()
    clipped_native_unit_refs: tuple[str, ...] = ()
    omitted_native_unit_refs: tuple[str, ...] = ()
    visibility_basis: VisibilityBasis = "not_assessed"


@dataclass(frozen=True)
class GeometryOutput:
    geometry_id: str
    owner_id: str
    coordinate_space_id: str
    geometry_kind: str
    values: tuple[float, ...]
    source: str
    confidence: float
    method: str
    native_unit_refs: tuple[str, ...] = ()
    visibility: Visibility = "not_assessed"
    clipped: bool = False
    serialized: bool = True
    role: str = "surface"


@dataclass(frozen=True)
class RenderOutput:
    view: dict[str, Any]
    surfaces: tuple[SurfaceOutput, ...]
    coordinate_spaces: tuple[dict[str, Any], ...]
    geometries: tuple[GeometryOutput, ...]
    assets: tuple[AssetOutput, ...]


def ensure_relative_asset_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Chemin d'asset non portable: {path}")
    return candidate
