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
