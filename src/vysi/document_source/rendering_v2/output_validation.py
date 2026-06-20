from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .models import RenderOutput, ensure_relative_asset_path


class RenderOutputValidationError(ValueError):
    pass


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique(label: str, values: list[str]) -> None:
    if any(not value for value in values):
        raise RenderOutputValidationError(f"Identifiant {label} vide")
    if len(values) != len(set(values)):
        raise RenderOutputValidationError(f"Identifiants {label} dupliqués dans la sortie backend")


def validate_backend_output(
    output: RenderOutput,
    *,
    document_id: str,
    requested_profile: str,
    renderer_id: str,
    renderer_version: str,
    required: bool,
    max_output_bytes: int,
) -> None:
    """Validate one renderer result before it can enter the DS11 aggregate."""

    view = output.view
    view_id = str(view.get("view_id", ""))
    if str(view.get("requested_profile", "")) != requested_profile:
        raise RenderOutputValidationError("Le backend a répondu pour un profil différent")
    if str(view.get("renderer", "")) != renderer_id:
        raise RenderOutputValidationError("Le backend a falsifié son identifiant de renderer")
    if str(view.get("renderer_version", "")) != renderer_version:
        raise RenderOutputValidationError("Le backend a publié une version divergente")
    status = str(view.get("status", ""))
    if status not in {"available", "partial", "unsupported", "failed"}:
        raise RenderOutputValidationError(f"Statut de vue invalide: {status}")
    if required and status in {"unsupported", "failed"}:
        raise RenderOutputValidationError("Un profil requis n'a pas produit de vue compatible")
    if status in {"available", "partial"} and (not output.surfaces or not output.assets):
        raise RenderOutputValidationError("Vue disponible/partielle sans surface ou asset")
    if required and (not output.surfaces or not output.assets):
        raise RenderOutputValidationError("Un profil requis doit produire surface et asset")

    surface_ids = [item.surface_id for item in output.surfaces]
    space_ids = [str(item.get("coordinate_space_id", "")) for item in output.coordinate_spaces]
    geometry_ids = [item.geometry_id for item in output.geometries]
    asset_ids = [item.asset_id for item in output.assets]
    _unique("view", [view_id])
    _unique("surface", surface_ids)
    _unique("coordinate_space", space_ids)
    _unique("geometry", geometry_ids)
    _unique("asset", asset_ids)

    known_surfaces = set(surface_ids)
    known_spaces = set(space_ids)
    known_assets = set(asset_ids)
    spaces_by_owner: dict[str, list[dict[str, Any]]] = {}
    for space in output.coordinate_spaces:
        owner = str(space.get("owner_id", ""))
        spaces_by_owner.setdefault(owner, []).append(space)
        if owner not in known_surfaces and owner != view_id:
            raise RenderOutputValidationError("Espace de coordonnées orphelin dans la sortie backend")

    visible_geometry_refs: dict[str, set[str]] = {surface_id: set() for surface_id in surface_ids}
    surface_dimensions = {
        item.surface_id: (item.width, item.height, item.visibility_basis) for item in output.surfaces
    }
    for surface in output.surfaces:
        if surface.ordinal < 0:
            raise RenderOutputValidationError("Ordinal de surface négatif")
        if surface.width is not None and surface.width <= 0:
            raise RenderOutputValidationError("Largeur de surface non positive")
        if surface.height is not None and surface.height <= 0:
            raise RenderOutputValidationError("Hauteur de surface non positive")
        if len(spaces_by_owner.get(surface.surface_id, [])) != 1:
            raise RenderOutputValidationError("Une surface doit posséder exactement un espace")
        missing_assets = set(surface.asset_ids) - known_assets
        if missing_assets:
            raise RenderOutputValidationError(
                f"Surface liée à des assets inconnus: {sorted(missing_assets)}"
            )
        visible = set(surface.native_unit_refs)
        serialized = set(surface.serialized_native_unit_refs)
        clipped = set(surface.clipped_native_unit_refs)
        omitted = set(surface.omitted_native_unit_refs)
        if not visible <= serialized:
            raise RenderOutputValidationError("Référence visible non sérialisée")
        if not clipped <= visible:
            raise RenderOutputValidationError("Référence clippée non visible")
        if omitted & serialized:
            raise RenderOutputValidationError("Référence simultanément omise et sérialisée")

    for geometry in output.geometries:
        if geometry.coordinate_space_id not in known_spaces:
            raise RenderOutputValidationError("Géométrie liée à un espace inconnu")
        if geometry.owner_id not in known_surfaces and geometry.owner_id != view_id:
            raise RenderOutputValidationError("Géométrie orpheline dans la sortie backend")
        if not 0.0 <= geometry.confidence <= 1.0:
            raise RenderOutputValidationError("Confiance géométrique hors limites")
        if geometry.clipped != (geometry.visibility == "partially_clipped"):
            raise RenderOutputValidationError("Clipping et visibilité géométrique divergents")
        if geometry.owner_id in visible_geometry_refs and geometry.visibility in {
            "fully_visible",
            "partially_clipped",
        }:
            visible_geometry_refs[geometry.owner_id].update(geometry.native_unit_refs)
        if geometry.geometry_kind == "bbox" and len(geometry.values) != 4:
            raise RenderOutputValidationError("BBox backend invalide")
        if geometry.geometry_kind == "bbox" and geometry.owner_id in surface_dimensions:
            x, y, width, height = geometry.values
            surface_width, surface_height, basis = surface_dimensions[geometry.owner_id]
            if width < 0 or height < 0:
                raise RenderOutputValidationError("BBox de taille négative")
            if basis == "layout_observed" and surface_width is not None and surface_height is not None:
                epsilon = 1e-6
                if (
                    x < -epsilon
                    or y < -epsilon
                    or x + width > surface_width + epsilon
                    or y + height > surface_height + epsilon
                ):
                    raise RenderOutputValidationError("BBox visible hors de la surface")

    for surface in output.surfaces:
        if surface.visibility_basis == "layout_observed":
            missing = set(surface.native_unit_refs) - visible_geometry_refs[surface.surface_id]
            if missing:
                raise RenderOutputValidationError(
                    f"Références visibles sans géométrie backend: {sorted(missing)}"
                )

    unique_materials: dict[tuple[str, str], int] = {}
    for asset in output.assets:
        path = ensure_relative_asset_path(asset.relative_path)
        expected_prefix = Path("rendered") / document_id / "assets"
        if tuple(path.parts[:3]) != tuple(expected_prefix.parts):
            raise RenderOutputValidationError("Asset backend hors de l'espace propriétaire DS11")
        if not asset.input_refs:
            raise RenderOutputValidationError("Asset backend sans provenance")
        if asset.payload is not None:
            observed_size = len(asset.payload)
            observed_hash = hashlib.sha256(asset.payload).hexdigest()
        else:
            source = asset.source_path
            if source is None or not source.is_file() or source.is_symlink():
                raise RenderOutputValidationError("Source matérielle backend absente ou irrégulière")
            observed_size = source.stat().st_size
            observed_hash = _sha256_path(source)
        if observed_size != asset.size_bytes:
            raise RenderOutputValidationError("Taille déclarée d'asset backend divergente")
        if observed_hash != asset.content_sha256:
            raise RenderOutputValidationError("Hash déclaré d'asset backend divergent")
        unique_materials[(asset.relative_path, asset.content_sha256)] = asset.size_bytes
    if sum(unique_materials.values()) > max_output_bytes:
        raise RenderOutputValidationError("Budget de sortie dépassé par la sortie backend")
