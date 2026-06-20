from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, cast


class RenderingInvariantError(ValueError):
    pass


def _portable(path: str) -> bool:
    pure = PurePosixPath(path)
    return bool(path) and not pure.is_absolute() and ".." not in pure.parts and "\\" not in path


def validate_rendering_invariants(
    rendered: dict[str, Any], geometry: dict[str, Any], assets: dict[str, Any]
) -> None:
    document_ids = {str(value.get("document_id", "")) for value in (rendered, geometry, assets)}
    if len(document_ids) != 1 or not next(iter(document_ids)):
        raise RenderingInvariantError("Catalogues DS11 rattachés à des documents divergents")

    views = cast(list[dict[str, Any]], rendered.get("views", []))
    surfaces = cast(list[dict[str, Any]], rendered.get("surfaces", []))
    asset_items = cast(list[dict[str, Any]], assets.get("assets", []))
    spaces = cast(list[dict[str, Any]], geometry.get("coordinate_spaces", []))
    geometries = cast(list[dict[str, Any]], geometry.get("geometries", []))

    view_ids = [str(item["view_id"]) for item in views]
    surface_ids = [str(item["surface_id"]) for item in surfaces]
    asset_ids = [str(item["asset_id"]) for item in asset_items]
    space_ids = [str(item["coordinate_space_id"]) for item in spaces]
    geometry_ids = [str(item["geometry_id"]) for item in geometries]
    for label, values in (
        ("view", view_ids),
        ("surface", surface_ids),
        ("asset", asset_ids),
        ("coordinate_space", space_ids),
        ("geometry", geometry_ids),
    ):
        if len(values) != len(set(values)):
            raise RenderingInvariantError(f"Identifiants {label} dupliqués")

    known_views = set(view_ids)
    known_surfaces = set(surface_ids)
    known_assets = set(asset_ids)
    known_spaces = set(space_ids)
    for surface in surfaces:
        if str(surface["view_id"]) not in known_views:
            raise RenderingInvariantError("Surface rattachée à une vue absente")
        if str(surface["coordinate_space_id"]) not in known_spaces:
            raise RenderingInvariantError("Surface rattachée à un espace absent")
        unknown_assets = set(str(item) for item in surface.get("asset_refs", [])) - known_assets
        if unknown_assets:
            raise RenderingInvariantError(f"Surface référence des assets absents: {sorted(unknown_assets)}")
        if surface.get("status") == "available" and not surface.get("asset_refs"):
            raise RenderingInvariantError("Surface disponible sans matérialisation")
        visible = set(str(item) for item in surface.get("native_unit_refs", []))
        serialized = set(str(item) for item in surface.get("serialized_native_unit_refs", []))
        clipped = set(str(item) for item in surface.get("clipped_native_unit_refs", []))
        omitted = set(str(item) for item in surface.get("omitted_native_unit_refs", []))
        if not visible <= serialized:
            raise RenderingInvariantError("Surface déclare visibles des unités non sérialisées")
        if not clipped <= visible:
            raise RenderingInvariantError("Surface déclare clippées des unités non visibles")
        if omitted & serialized:
            raise RenderingInvariantError("Surface déclare une unité à la fois omise et sérialisée")
        basis = str(surface.get("visibility_basis", "not_assessed"))
        fidelity = str(surface.get("fidelity", "not_assessed"))
        if basis == "layout_observed" and fidelity == "not_assessed":
            raise RenderingInvariantError("Surface observée sans qualification de fidélité")
        if basis in {"binary_passthrough", "native_dimensions_only"} and fidelity != "not_assessed":
            raise RenderingInvariantError(
                "Le passthrough binaire ne peut pas déclarer une fidélité visuelle mesurée"
            )

    owners = known_surfaces | known_views
    for space in spaces:
        if str(space["owner_id"]) not in owners:
            raise RenderingInvariantError("Espace de coordonnées orphelin")
    geometry_refs_by_surface: dict[str, set[str]] = {surface_id: set() for surface_id in known_surfaces}
    for item in geometries:
        if str(item["coordinate_space_id"]) not in known_spaces:
            raise RenderingInvariantError("Géométrie rattachée à un espace absent")
        owner_id = str(item["owner_id"])
        if owner_id not in owners:
            raise RenderingInvariantError("Géométrie orpheline")
        visibility = str(item.get("visibility", "not_assessed"))
        geometry_clipped = bool(item.get("clipped", False))
        if geometry_clipped and visibility != "partially_clipped":
            raise RenderingInvariantError("Géométrie clippée sans visibilité partielle")
        if visibility == "partially_clipped" and not geometry_clipped:
            raise RenderingInvariantError("Visibilité partielle sans indicateur clipped")
        refs = set(str(ref) for ref in item.get("native_unit_refs", []))
        if owner_id in geometry_refs_by_surface and visibility in {"fully_visible", "partially_clipped"}:
            geometry_refs_by_surface[owner_id].update(refs)

    for surface in surfaces:
        surface_id = str(surface["surface_id"])
        if str(surface.get("visibility_basis")) == "layout_observed":
            visible = set(str(item) for item in surface.get("native_unit_refs", []))
            missing_geometry = visible - geometry_refs_by_surface.get(surface_id, set())
            if missing_geometry:
                raise RenderingInvariantError(
                    f"Unités visibles sans géométrie observable: {sorted(missing_geometry)}"
                )

    for asset in asset_items:
        stored = cast(dict[str, Any], asset["stored_ref"])
        path = str(stored["path"])
        if not _portable(path):
            raise RenderingInvariantError(f"Chemin d'asset non portable: {path}")
        if int(stored["size_bytes"]) < 0:
            raise RenderingInvariantError("Taille d'asset négative")
        if not asset.get("input_refs"):
            raise RenderingInvariantError("Asset sans provenance")

    for view in views:
        view_id = str(view["view_id"])
        owned_surfaces = [surface for surface in surfaces if str(surface["view_id"]) == view_id]
        serialized = {str(ref) for surface in owned_surfaces for ref in surface.get("serialized_native_unit_refs", [])}
        visible = {str(ref) for surface in owned_surfaces for ref in surface.get("native_unit_refs", [])}
        clipped = {str(ref) for surface in owned_surfaces for ref in surface.get("clipped_native_unit_refs", [])}
        omitted = {str(ref) for surface in owned_surfaces for ref in surface.get("omitted_native_unit_refs", [])}
        summary = cast(dict[str, Any], view.get("visibility_summary", {}))
        expected = {
            "serialized_refs": len(serialized),
            "visible_refs": len(visible),
            "clipped_refs": len(clipped),
            "omitted_refs": len(omitted),
        }
        if any(int(summary.get(key, -1)) != value for key, value in expected.items()):
            raise RenderingInvariantError("Résumé de visibilité divergent des surfaces")
        basis = str(view.get("measurement_basis", ""))
        assessed = bool(summary.get("visual_fidelity_assessed", False))
        if basis == "technical_preview_visibility" and not assessed:
            raise RenderingInvariantError("Aperçu technique marqué comme non évalué")
        if basis in {"binary_passthrough", "unsupported"} and assessed:
            raise RenderingInvariantError("Passthrough/unsupported marqué comme fidélité visuelle évaluée")

    available_views = [item for item in views if item.get("status") in {"available", "partial"}]
    if available_views and not surfaces:
        raise RenderingInvariantError("Vue rendue disponible sans surface")
