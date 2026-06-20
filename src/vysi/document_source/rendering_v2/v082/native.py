from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id

from ..models import AssetOutput, GeometryOutput, SurfaceOutput
from .common import asset_id, source_artifact, space_bbox


def render_native(
    *, document_id: str, view_id: str, profile: dict[str, Any], profile_kind: str,
    artifact_records: list[dict[str, Any]], workspace: Path,
    check: Callable[[], None], account: Callable[[int], None],
) -> tuple[list[SurfaceOutput], list[dict[str, Any]], list[GeometryOutput], list[AssetOutput], set[str], list[str]]:
    source, artifact_id = source_artifact(artifact_records, workspace)
    digest = str(artifact_records[0]["sha256"])
    size = source.stat().st_size
    check()
    account(size)
    suffix = source.suffix.lower().lstrip(".") or "bin"
    media_type = str(artifact_records[0].get("media_type") or "application/octet-stream")
    aid = asset_id(document_id, 0, "native_passthrough", digest)
    asset = AssetOutput(
        aid,
        f"rendered/{document_id}/assets/{aid}.{suffix}",
        media_type,
        digest,
        size,
        (artifact_id,),
        "native_rendered_passthrough",
        "deterministic",
        source_path=source,
        properties=(
            {"name": "measurement_basis", "value_type": "string", "value": "binary_passthrough", "source": "derived"},
            {"name": "visual_fidelity_assessed", "value_type": "boolean", "value": False, "source": "derived"},
        ),
    )
    surfaces: list[SurfaceOutput] = []
    spaces: list[dict[str, Any]] = []
    geometries: list[GeometryOutput] = []
    candidates: set[str] = set()
    if profile_kind == "fixed_layout":
        units = profile.get("pages", [])
        warnings = ["fixed_layout_binary_preserved_visual_fidelity_not_assessed"]
        for ordinal, unit in enumerate(units):
            check()
            ref = str(unit["page_id"])
            candidates.add(ref)
            width = float(unit["width_pt"])
            height = float(unit["height_pt"])
            sid = stable_id("surface", {"document_id": document_id, "view_id": view_id, "page": ref})
            space, bbox = space_bbox(document_id, sid, ordinal, width, height, "pt", source="native", method="fixed_layout_native_page_box")
            spaces.append(space)
            geometries.append(bbox)
            surfaces.append(SurfaceOutput(sid, "fixed_page", ordinal, width, height, "pt", (ref,), (aid,), "available", "not_assessed", media_type, int(unit.get("rotation", 0)), None, (ref,), (), (), "binary_passthrough"))
    else:
        units = profile.get("frames", [])
        multiple = len(units) > 1
        warnings = ["raster_binary_preserved_pixel_decode_not_assessed"]
        if multiple:
            warnings.append("multiframe_source_preserved_as_single_container_asset")
        for ordinal, unit in enumerate(units):
            check()
            ref = str(unit["frame_id"])
            candidates.add(ref)
            width = float(unit["width_px"])
            height = float(unit["height_px"])
            sid = stable_id("surface", {"document_id": document_id, "view_id": view_id, "frame": ref})
            space, bbox = space_bbox(document_id, sid, ordinal, width, height, "px", source="native", method="raster_native_frame_dimensions")
            spaces.append(space)
            geometries.append(bbox)
            orientation = int(unit.get("orientation") or 0)
            surfaces.append(SurfaceOutput(sid, "raster_canvas", ordinal, width, height, "px", (ref,), (aid,), "partial" if multiple else "available", "not_assessed", media_type, orientation if orientation in {0, 90, 180, 270} else 0, None, (ref,), (), (), "native_dimensions_only"))
    return surfaces, spaces, geometries, [asset], candidates, warnings
