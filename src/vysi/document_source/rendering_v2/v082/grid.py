from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any

from ..models import AssetOutput, GeometryOutput, RenderOutput, SurfaceOutput

MAX_ROWS = 26
MAX_COLUMNS = 12
GridCell = tuple[str, int, int, str]
RenderParts = tuple[
    list[SurfaceOutput],
    list[dict[str, Any]],
    list[GeometryOutput],
    list[AssetOutput],
    set[str],
    list[str],
]


def occupied_tiles(records: list[GridCell]) -> dict[tuple[int, int], list[GridCell]]:
    buckets: dict[tuple[int, int], list[GridCell]] = defaultdict(list)
    for cell_id, row, column, value in records:
        key = (row // MAX_ROWS, column // MAX_COLUMNS)
        buckets[key].append((cell_id, row, column, value))
    return dict(sorted(buckets.items()))


def prepare_output(output: RenderParts) -> RenderParts:
    surfaces, spaces, geometries, assets, candidates, warnings = output
    serialized = {ref for surface in surfaces for ref in surface.serialized_native_unit_refs}
    omitted = tuple(sorted(candidates - serialized))
    if omitted and surfaces:
        surfaces[0] = replace(
            surfaces[0],
            omitted_native_unit_refs=tuple(
                sorted(set(surfaces[0].omitted_native_unit_refs) | set(omitted))
            ),
        )
        warnings.append("renderable_native_candidates_omitted")
    return surfaces, spaces, geometries, assets, candidates, warnings


def finalize_output(
    *,
    output: RenderParts,
    view_id: str,
    requested_profile: str,
    renderer_id: str,
    producer_version: str,
    environment: dict[str, Any],
    environment_hash: str,
) -> RenderOutput:
    surfaces, spaces, geometries, assets, _candidates, warnings = prepare_output(output)
    serialized = {ref for surface in surfaces for ref in surface.serialized_native_unit_refs}
    visible = {ref for surface in surfaces for ref in surface.native_unit_refs}
    clipped = {ref for surface in surfaces for ref in surface.clipped_native_unit_refs}
    omitted = {ref for surface in surfaces for ref in surface.omitted_native_unit_refs}
    view = {
        "view_id": view_id,
        "view_kind": "technical_preview",
        "requested_profile": requested_profile,
        "renderer": renderer_id,
        "renderer_version": producer_version,
        "environment_hash": environment_hash,
        "environment": environment,
        "determinism": "environment_bound",
        "status": "partial",
        "locale": str(environment["locale"]),
        "timezone": str(environment["timezone"]),
        "font_substitutions": ["document_fonts->generic_monospace"],
        "warnings": sorted(set(warnings)),
        "measurement_basis": "technical_preview_visibility",
        "visibility_summary": {
            "serialized_refs": len(serialized),
            "visible_refs": len(visible),
            "clipped_refs": len(clipped),
            "omitted_refs": len(omitted),
            "visual_fidelity_assessed": True,
        },
    }
    return RenderOutput(view, tuple(surfaces), tuple(spaces), tuple(geometries), tuple(assets))
