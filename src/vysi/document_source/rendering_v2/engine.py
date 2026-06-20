from __future__ import annotations

import hashlib
import json
import locale
import os
import platform
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from vysi.document_source.contracts_v2.identities import stable_id

from .models import AssetOutput, GeometryOutput, RenderOutput, SurfaceOutput
from .svg import PreviewElement, PreviewItem, SvgPreview, paginate_text_preview, svg_table_page


class RenderingError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        unsupported: bool = False,
        budget_exceeded: bool = False,
    ) -> None:
        super().__init__(message)
        self.unsupported = unsupported
        self.budget_exceeded = budget_exceeded


def _environment(profile: str, renderer_id: str) -> tuple[dict[str, Any], str]:
    body = {
        "renderer_family": renderer_id,
        "profile": profile,
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.system().lower() or "unknown",
        "machine": platform.machine().lower() or "unknown",
        "locale": locale.setlocale(locale.LC_CTYPE, None) or "unknown",
        "timezone": os.environ.get("TZ", "system"),
        "network": "denied",
        "macros": "disabled",
        "field_update": "disabled",
        "formula_recalculation": "disabled",
    }
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return body, hashlib.sha256(encoded).hexdigest()


def _asset_id(document_id: str, ordinal: int, kind: str, content_sha256: str) -> str:
    return stable_id(
        "asset",
        {
            "document_id": document_id,
            "ordinal": ordinal,
            "kind": kind,
            "sha256": content_sha256,
        },
    )


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _space_and_bbox(
    document_id: str,
    surface_id: str,
    ordinal: int,
    width: float,
    height: float,
    unit: str,
    *,
    source: str,
    confidence: float,
    method: str,
) -> tuple[dict[str, Any], GeometryOutput]:
    space_id = stable_id(
        "coordspace", {"document_id": document_id, "surface_id": surface_id, "unit": unit}
    )
    space = {
        "coordinate_space_id": space_id,
        "owner_id": surface_id,
        "unit": unit,
        "origin": "top_left",
        "axis_x": "right",
        "axis_y": "down",
        "transform_to_parent": None,
    }
    geometry_id = stable_id(
        "geometry", {"surface_id": surface_id, "kind": "bbox", "ordinal": ordinal}
    )
    geometry = GeometryOutput(
        geometry_id,
        surface_id,
        space_id,
        "bbox",
        (0.0, 0.0, float(width), float(height)),
        source,
        confidence,
        method,
        (),
        "not_assessed",
        False,
        True,
        "surface",
    )
    return space, geometry


def _word_items(profile: dict[str, Any]) -> list[PreviewItem]:
    blocks = cast(list[dict[str, Any]], profile.get("blocks", []))
    selected: list[dict[str, Any]] = []
    preferred = {"paragraph", "cell", "header", "footer", "footnote", "endnote", "field"}
    for item in blocks:
        if str(item.get("text") or "") and str(item.get("kind")) in preferred:
            selected.append(item)
    selected_ids = {str(item["unit_id"]) for item in selected}
    for item in blocks:
        if (
            str(item.get("text") or "")
            and str(item.get("kind")) == "run"
            and str(item.get("parent_id") or "") not in selected_ids
        ):
            selected.append(item)
    selected.sort(key=lambda item: (int(item.get("ordinal", 0)), str(item["unit_id"])))

    items: list[PreviewItem] = []
    emitted_resources: set[tuple[str, str]] = set()
    for item in selected:
        unit_id = str(item["unit_id"])
        items.append(PreviewItem((unit_id,), str(item.get("text") or ""), str(item.get("kind") or "text")))
        for resource_id in item.get("resource_refs", []):
            key = (unit_id, str(resource_id))
            if key in emitted_resources:
                continue
            emitted_resources.add(key)
            items.append(
                PreviewItem(
                    (unit_id, str(resource_id)),
                    f"⟦embedded resource {resource_id}⟧",
                    "resource_placeholder",
                )
            )
    return items


def _spreadsheet_cells(
    profile: dict[str, Any], worksheet_id: str
) -> list[tuple[str, int, int, str]]:
    cells = [
        item
        for item in cast(list[dict[str, Any]], profile.get("cells", []))
        if str(item.get("worksheet_id")) == worksheet_id
    ]
    address_re = re.compile(r"^([A-Z]+)([0-9]+)$")
    records: list[tuple[str, int, int, str]] = []
    for item in cells:
        match = address_re.match(str(item.get("address", "")))
        if not match:
            continue
        col_name, row_text = match.groups()
        col = 0
        for char in col_name:
            col = col * 26 + ord(char) - 64
        value = item.get("raw_value")
        if value is None:
            value = item.get("cached_value")
        if value is None:
            value = item.get("formula")
        records.append(
            (str(item["cell_id"]), int(row_text) - 1, col - 1, "" if value is None else str(value))
        )
    records.sort(key=lambda item: (item[1], item[2], item[0]))
    return records


def _artifact_source(artifact_records: list[dict[str, Any]], workspace: Path) -> tuple[Path, str]:
    if not artifact_records:
        raise RenderingError("Aucun artefact source disponible")
    primary = artifact_records[0]
    path = workspace / str(primary["stored_path"])
    if not path.is_file() or path.is_symlink():
        raise RenderingError("Artefact source absent ou irrégulier")
    observed = _sha256_path(path)
    expected = str(primary["sha256"])
    if observed != expected:
        raise RenderingError("Hash de l'artefact source invalide")
    return path, str(primary["artifact_id"])


def render_document(
    *,
    document_id: str,
    profile: dict[str, Any],
    native: dict[str, Any],
    ir: dict[str, Any],
    artifact_records: list[dict[str, Any]],
    workspace: Path,
    requested_profile: str,
    producer_version: str,
    renderer_id: str = "vysi_builtin_reference_renderer",
    max_output_bytes: int | None = None,
    check_cancelled: Callable[[], None] | None = None,
) -> RenderOutput:
    del ir
    profile_kind = str(profile.get("profile_kind"))
    check = check_cancelled or (lambda: None)
    check()
    if requested_profile not in {"source_reference", "technical_preview", "native_passthrough"}:
        raise RenderingError(f"Profil de rendu inconnu: {requested_profile}", unsupported=True)
    if requested_profile == "native_passthrough" and profile_kind not in {"fixed_layout", "raster"}:
        raise RenderingError(
            f"Passthrough natif indisponible pour le profil {profile_kind}", unsupported=True
        )
    if requested_profile == "technical_preview" and profile_kind in {"fixed_layout", "raster"}:
        raise RenderingError(
            f"Aperçu technique non requis pour le profil intrinsèquement rendu {profile_kind}",
            unsupported=True,
        )
    if profile_kind == "legacy_ole":
        raise RenderingError(
            "Rendu des conteneurs OLE historiques non pris en charge", unsupported=True
        )

    environment, environment_hash = _environment(requested_profile, renderer_id)
    view_id = stable_id(
        "view",
        {
            "document_id": document_id,
            "profile_kind": profile_kind,
            "requested_profile": requested_profile,
            "renderer": renderer_id,
        },
    )
    warnings: list[str] = []
    surfaces: list[SurfaceOutput] = []
    spaces: list[dict[str, Any]] = []
    geometries: list[GeometryOutput] = []
    assets: list[AssetOutput] = []
    produced_bytes = 0

    def account_asset(size_bytes: int) -> None:
        nonlocal produced_bytes
        if size_bytes < 0:
            raise RenderingError("Taille d'asset négative")
        if max_output_bytes is not None and produced_bytes + size_bytes > max_output_bytes:
            raise RenderingError(
                "Budget max_temp_bytes dépassé pendant la production du rendu",
                budget_exceeded=True,
            )
        produced_bytes += size_bytes

    def add_svg_preview(
        *,
        ordinal: int,
        surface_kind: str,
        preview: SvgPreview,
        width: int,
        height: int,
        warning: str,
    ) -> None:
        check()
        payload = preview.payload
        account_asset(len(payload))
        content_sha256 = hashlib.sha256(payload).hexdigest()
        asset_id = _asset_id(document_id, ordinal, "technical_preview_svg", content_sha256)
        surface_id = stable_id(
            "surface",
            {
                "document_id": document_id,
                "view_id": view_id,
                "ordinal": ordinal,
                "kind": surface_kind,
            },
        )
        relative = f"rendered/{document_id}/assets/{asset_id}.svg"
        provenance = preview.serialized_refs or tuple(str(item) for item in native.get("root_unit_ids", []))
        assets.append(
            AssetOutput(
                asset_id,
                relative,
                "image/svg+xml",
                content_sha256,
                len(payload),
                tuple(sorted(set(provenance))),
                "technical_source_preview",
                "environment_bound",
                payload=payload,
                properties=(
                    {"name": "visibility_basis", "value_type": "string", "value": "layout_observed", "source": "derived"},
                    {"name": "serialized_ref_count", "value_type": "integer", "value": len(preview.serialized_refs), "source": "derived"},
                    {"name": "visible_ref_count", "value_type": "integer", "value": len(preview.visible_refs), "source": "derived"},
                    {"name": "clipped_ref_count", "value_type": "integer", "value": len(preview.clipped_refs), "source": "derived"},
                ),
            )
        )
        space, bbox = _space_and_bbox(
            document_id,
            surface_id,
            ordinal,
            float(width),
            float(height),
            "px",
            source="rendered",
            confidence=1.0,
            method="vysi_builtin_svg_canvas",
        )
        spaces.append(space)
        geometries.append(bbox)
        for element_ordinal, element in enumerate(preview.elements):
            geometry_id = stable_id(
                "geometry",
                {
                    "surface_id": surface_id,
                    "element": element_ordinal,
                    "refs": element.native_refs,
                    "role": element.role,
                },
            )
            geometries.append(
                GeometryOutput(
                    geometry_id,
                    surface_id,
                    str(space["coordinate_space_id"]),
                    "bbox",
                    (element.x, element.y, element.width, element.height),
                    "rendered",
                    1.0,
                    "vysi_builtin_svg_element_bbox",
                    tuple(sorted(set(element.native_refs))),
                    "partially_clipped" if element.clipped else "fully_visible",
                    element.clipped,
                    True,
                    element.role,
                )
            )
        surfaces.append(
            SurfaceOutput(
                surface_id,
                surface_kind,
                ordinal,
                float(width),
                float(height),
                "px",
                tuple(sorted(set(preview.visible_refs))),
                (asset_id,),
                "partial",
                "approximate",
                "image/svg+xml",
                0,
                96.0,
                tuple(sorted(set(preview.serialized_refs))),
                tuple(sorted(set(preview.clipped_refs))),
                tuple(sorted(set(preview.omitted_refs))),
                "layout_observed",
            )
        )
        if warning not in warnings:
            warnings.append(warning)

    if profile_kind == "plain_text":
        all_lines = cast(list[dict[str, Any]], profile.get("lines", []))
        text_items = [
            PreviewItem((str(item["unit_id"]),), str(item.get("text", "")), "text_line")
            for item in all_lines
        ]
        previews = paginate_text_preview(
            title="Text source technical preview",
            items=text_items,
            width=794,
            height=1123,
            footer="Vysi technical source preview — derived pagination",
        )
        for ordinal, preview in enumerate(previews):
            add_svg_preview(
                ordinal=ordinal,
                surface_kind="text_preview",
                preview=preview,
                width=794,
                height=1123,
                warning="technical_preview_layout_not_native",
            )
    elif profile_kind == "wordprocessing":
        previews = paginate_text_preview(
            title="Wordprocessing technical preview",
            items=_word_items(profile),
            width=794,
            height=1123,
            footer="Vysi technical source preview — non canonical pagination",
        )
        for ordinal, preview in enumerate(previews):
            add_svg_preview(
                ordinal=ordinal,
                surface_kind="flow_page",
                preview=preview,
                width=794,
                height=1123,
                warning="wordprocessing_pagination_is_derived_not_native",
            )
    elif profile_kind == "spreadsheet":
        worksheets = cast(list[dict[str, Any]], profile.get("worksheets", []))
        ordinal = 0
        max_rows, max_cols = 26, 12
        for worksheet in worksheets:
            check()
            worksheet_id = str(worksheet["worksheet_id"])
            records = _spreadsheet_cells(profile, worksheet_id)
            max_row = max((item[1] for item in records), default=0)
            max_col = max((item[2] for item in records), default=0)
            for row_start in range(0, max_row + 1, max_rows):
                for col_start in range(0, max_col + 1, max_cols):
                    page_cells: list[tuple[tuple[str, ...], int, int, str]] = [
                        ((cell_id,), row - row_start, col - col_start, value)
                        for cell_id, row, col, value in records
                        if row_start <= row < row_start + max_rows
                        and col_start <= col < col_start + max_cols
                    ]
                    # Une feuille vide doit rester observable et mappable.
                    if not page_cells and records:
                        continue
                    preview = svg_table_page(
                        title=(
                            f"Worksheet: {worksheet.get('name', worksheet_id)} "
                            f"rows {row_start + 1}-{row_start + max_rows}, "
                            f"cols {col_start + 1}-{col_start + max_cols}"
                        ),
                        cells=page_cells,
                        width=1123,
                        height=794,
                        max_columns=max_cols,
                        max_rows=max_rows,
                    )
                    preview = SvgPreview(
                        preview.payload,
                        (
                            PreviewElement(
                                (worksheet_id,),
                                36.0,
                                12.0,
                                720.0,
                                30.0,
                                "worksheet_title",
                                False,
                            ),
                            *preview.elements,
                        ),
                        tuple(sorted(set(preview.serialized_refs) | {worksheet_id})),
                        tuple(sorted(set(preview.visible_refs) | {worksheet_id})),
                        preview.clipped_refs,
                        preview.omitted_refs,
                    )
                    add_svg_preview(
                        ordinal=ordinal,
                        surface_kind="worksheet_print_page",
                        preview=preview,
                        width=1123,
                        height=794,
                        warning="spreadsheet_print_layout_is_derived_not_native",
                    )
                    ordinal += 1
                    if not records:
                        break
                if not records:
                    break
    elif profile_kind == "presentation":
        slides = cast(list[dict[str, Any]], profile.get("slides", []))
        shapes = cast(list[dict[str, Any]], profile.get("shapes", []))
        ordinal = 0
        for slide_index, slide in enumerate(slides):
            check()
            slide_id = str(slide["slide_id"])
            owned = sorted(
                [item for item in shapes if str(item.get("slide_id")) == slide_id],
                key=lambda item: (int(item.get("ordinal", 0)), str(item["shape_id"])),
            )
            slide_items: list[PreviewItem] = [PreviewItem((slide_id,), f"Slide {slide_index + 1}", "slide")]
            for shape in owned:
                shape_id = str(shape["shape_id"])
                text = str(shape.get("text") or "")
                kind = str(shape.get("kind") or "shape")
                slide_items.append(
                    PreviewItem(
                        (shape_id,),
                        text if text else f"⟦{kind} without textual payload⟧",
                        "shape_text" if text else "shape_placeholder",
                    )
                )
                for resource_id in shape.get("resource_refs", []):
                    slide_items.append(
                        PreviewItem(
                            (shape_id, str(resource_id)),
                            f"⟦shape resource {resource_id}⟧",
                            "resource_placeholder",
                        )
                    )
            previews = paginate_text_preview(
                title=f"Presentation slide {slide_index + 1} technical inventory",
                items=slide_items,
                width=1280,
                height=720,
                font_size=14,
                line_height=20,
                footer="Vysi technical preview — positions and styling are not native",
            )
            for preview in previews:
                add_svg_preview(
                    ordinal=ordinal,
                    surface_kind="slide",
                    preview=preview,
                    width=1280,
                    height=720,
                    warning="presentation_visual_styling_is_partial",
                )
                ordinal += 1
    elif profile_kind in {"fixed_layout", "raster"}:
        source_path, artifact_id = _artifact_source(artifact_records, workspace)
        content_sha256 = str(artifact_records[0]["sha256"])
        size_bytes = source_path.stat().st_size
        check()
        account_asset(size_bytes)
        suffix = source_path.suffix.lower().lstrip(".") or "bin"
        media_type = str(artifact_records[0].get("media_type") or "application/octet-stream")
        asset_id = _asset_id(document_id, 0, "native_passthrough", content_sha256)
        relative = f"rendered/{document_id}/assets/{asset_id}.{suffix}"
        assets.append(
            AssetOutput(
                asset_id,
                relative,
                media_type,
                content_sha256,
                size_bytes,
                (artifact_id,),
                "native_rendered_passthrough",
                "deterministic",
                source_path=source_path,
                properties=(
                    {"name": "measurement_basis", "value_type": "string", "value": "binary_passthrough", "source": "derived"},
                    {"name": "visual_fidelity_assessed", "value_type": "boolean", "value": False, "source": "derived"},
                ),
            )
        )
        if profile_kind == "fixed_layout":
            units = cast(list[dict[str, Any]], profile.get("pages", []))
            for ordinal, page_item in enumerate(units):
                check()
                width = float(page_item["width_pt"])
                height = float(page_item["height_pt"])
                page_id = str(page_item["page_id"])
                surface_id = stable_id(
                    "surface", {"document_id": document_id, "view_id": view_id, "page": page_id}
                )
                space, bbox = _space_and_bbox(
                    document_id,
                    surface_id,
                    ordinal,
                    width,
                    height,
                    "pt",
                    source="native",
                    confidence=1.0,
                    method="fixed_layout_native_page_box",
                )
                spaces.append(space)
                geometries.append(bbox)
                surfaces.append(
                    SurfaceOutput(
                        surface_id,
                        "fixed_page",
                        ordinal,
                        width,
                        height,
                        "pt",
                        (page_id,),
                        (asset_id,),
                        "available",
                        "not_assessed",
                        media_type,
                        int(page_item.get("rotation", 0)),
                        None,
                        (page_id,),
                        (),
                        (),
                        "binary_passthrough",
                    )
                )
            warnings.append("fixed_layout_binary_preserved_visual_fidelity_not_assessed")
        else:
            frames = cast(list[dict[str, Any]], profile.get("frames", []))
            for ordinal, frame in enumerate(frames):
                check()
                width = float(frame["width_px"])
                height = float(frame["height_px"])
                frame_id = str(frame["frame_id"])
                surface_id = stable_id(
                    "surface", {"document_id": document_id, "view_id": view_id, "frame": frame_id}
                )
                space, bbox = _space_and_bbox(
                    document_id,
                    surface_id,
                    ordinal,
                    width,
                    height,
                    "px",
                    source="native",
                    confidence=1.0,
                    method="raster_native_frame_dimensions",
                )
                spaces.append(space)
                geometries.append(bbox)
                multi = len(frames) > 1
                surfaces.append(
                    SurfaceOutput(
                        surface_id,
                        "raster_canvas",
                        ordinal,
                        width,
                        height,
                        "px",
                        (frame_id,),
                        (asset_id,),
                        "partial" if multi else "available",
                        "not_assessed",
                        media_type,
                        int(frame.get("orientation") or 0) if int(frame.get("orientation") or 0) in {0, 90, 180, 270} else 0,
                        None,
                        (frame_id,),
                        (),
                        (),
                        "native_dimensions_only",
                    )
                )
            warnings.append("raster_binary_preserved_pixel_decode_not_assessed")
            if len(frames) > 1:
                warnings.append("multiframe_source_preserved_as_single_container_asset")
    else:
        raise RenderingError(f"Profil natif non pris en charge: {profile_kind}", unsupported=True)

    status = "available"
    if warnings or any(item.status == "partial" for item in surfaces):
        status = "partial"
    determinism = (
        "deterministic"
        if all(item.determinism == "deterministic" for item in assets)
        else "environment_bound"
    )
    passthrough = profile_kind in {"fixed_layout", "raster"}
    serialized_refs = {ref for surface in surfaces for ref in surface.serialized_native_unit_refs}
    visible_refs = {ref for surface in surfaces for ref in surface.native_unit_refs}
    clipped_refs = {ref for surface in surfaces for ref in surface.clipped_native_unit_refs}
    omitted_refs = {ref for surface in surfaces for ref in surface.omitted_native_unit_refs}
    view = {
        "view_id": view_id,
        "view_kind": "native_passthrough" if passthrough else "technical_preview",
        "requested_profile": requested_profile,
        "renderer": renderer_id,
        "renderer_version": producer_version,
        "environment_hash": environment_hash,
        "environment": environment,
        "determinism": determinism,
        "status": status,
        "locale": str(environment["locale"]),
        "timezone": str(environment["timezone"]),
        "font_substitutions": ["document_fonts→generic_monospace"] if not passthrough else [],
        "warnings": sorted(set(warnings)),
        "measurement_basis": "binary_passthrough" if passthrough else "technical_preview_visibility",
        "visibility_summary": {
            "serialized_refs": len(serialized_refs),
            "visible_refs": len(visible_refs),
            "clipped_refs": len(clipped_refs),
            "omitted_refs": len(omitted_refs),
            "visual_fidelity_assessed": not passthrough,
        },
    }
    return RenderOutput(view, tuple(surfaces), tuple(spaces), tuple(geometries), tuple(assets))
