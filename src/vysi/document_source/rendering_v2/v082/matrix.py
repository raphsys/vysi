from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from ..engine import _spreadsheet_cells
from ..models import AssetOutput, GeometryOutput, SurfaceOutput
from .common import preview_outputs
from .grid import MAX_COLUMNS, MAX_ROWS, occupied_tiles
from .svg import Element, Preview, table_page


def render_matrix(
    *,
    document_id: str,
    view_id: str,
    profile: dict[str, Any],
    check: Callable[[], None],
    account: Callable[[int], None],
) -> tuple[
    list[SurfaceOutput],
    list[dict[str, Any]],
    list[GeometryOutput],
    list[AssetOutput],
    set[str],
    list[str],
]:
    surfaces: list[SurfaceOutput] = []
    spaces: list[dict[str, Any]] = []
    geometries: list[GeometryOutput] = []
    assets: list[AssetOutput] = []
    candidates: set[str] = set()
    warnings = ["spreadsheet_print_layout_is_derived_not_native"]
    ordinal = 0
    for worksheet in cast(list[dict[str, Any]], profile.get("worksheets", [])):
        check()
        worksheet_id = str(worksheet["worksheet_id"])
        candidates.add(worksheet_id)
        if str(worksheet.get("state") or "visible") != "visible":
            warnings.append("hidden_worksheet_included_in_technical_preview")
        records = _spreadsheet_cells(profile, worksheet_id)
        candidates.update(record[0] for record in records)
        buckets = occupied_tiles(records)
        for tile in sorted(buckets) or [(0, 0)]:
            check()
            row_start = tile[0] * MAX_ROWS
            column_start = tile[1] * MAX_COLUMNS
            page_cells: list[tuple[tuple[str, ...], int, int, str]] = [
                ((cell_id,), row - row_start, column - column_start, value)
                for cell_id, row, column, value in buckets.get(tile, [])
            ]
            page = table_page(
                title=(
                    f"Worksheet {worksheet.get('name', worksheet_id)} "
                    f"rows {row_start + 1}-{row_start + MAX_ROWS}, "
                    f"cols {column_start + 1}-{column_start + MAX_COLUMNS}"
                ),
                cells=page_cells,
                check=check,
                max_rows=MAX_ROWS,
                max_columns=MAX_COLUMNS,
            )
            heading = Element((worksheet_id,), 36.0, 12.0, 720.0, 30.0, "worksheet_title")
            page = Preview(
                page.payload,
                (heading, *page.elements),
                tuple(sorted(set(page.serialized) | {worksheet_id})),
                tuple(sorted(set(page.visible) | {worksheet_id})),
                page.clipped,
                page.omitted,
            )
            surface, space, geometry, asset = preview_outputs(
                document_id=document_id,
                view_id=view_id,
                ordinal=ordinal,
                kind="worksheet_print_page",
                preview=page,
                width=1123,
                height=794,
                check=check,
                account=account,
            )
            surfaces.append(surface)
            spaces.append(space)
            geometries.extend(geometry)
            assets.append(asset)
            ordinal += 1
    return surfaces, spaces, geometries, assets, candidates, warnings
