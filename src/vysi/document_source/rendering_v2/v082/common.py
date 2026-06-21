from __future__ import annotations

import hashlib
import json
import locale
import os
import platform
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id

from ..engine import RenderingError
from ..models import AssetOutput, GeometryOutput, SurfaceOutput
from .svg import Element, Preview


def environment(profile: str, renderer_id: str) -> tuple[dict[str, Any], str]:
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
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return body, hashlib.sha256(encoded).hexdigest()


def asset_id(document_id: str, ordinal: int, kind: str, digest: str) -> str:
    return stable_id(
        "asset", {"document_id": document_id, "ordinal": ordinal, "kind": kind, "sha256": digest}
    )


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_artifact(records: list[dict[str, Any]], workspace: Path) -> tuple[Path, str]:
    if not records:
        raise RenderingError("Aucun artefact source disponible")
    primary = records[0]
    path = workspace / str(primary["stored_path"])
    if not path.is_file() or path.is_symlink():
        raise RenderingError("Artefact source absent ou irrégulier")
    if sha256_path(path) != str(primary["sha256"]):
        raise RenderingError("Hash de l'artefact source invalide")
    return path, str(primary["artifact_id"])


def space_bbox(
    document_id: str,
    surface_id: str,
    ordinal: int,
    width: float,
    height: float,
    unit: str,
    *,
    source: str,
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
    geometry = GeometryOutput(
        stable_id("geometry", {"surface_id": surface_id, "kind": "bbox", "ordinal": ordinal}),
        surface_id,
        space_id,
        "bbox",
        (0.0, 0.0, float(width), float(height)),
        source,
        1.0,
        method,
        (),
        "not_assessed",
        False,
        True,
        "surface",
    )
    return space, geometry


def preview_outputs(
    *,
    document_id: str,
    view_id: str,
    ordinal: int,
    kind: str,
    preview: Preview,
    width: int,
    height: int,
    check: Callable[[], None],
    account: Callable[[int], None],
) -> tuple[SurfaceOutput, dict[str, Any], list[GeometryOutput], AssetOutput]:
    check()
    payload = preview.payload
    account(len(payload))
    digest = hashlib.sha256(payload).hexdigest()
    aid = asset_id(document_id, ordinal, "technical_preview_svg", digest)
    sid = stable_id(
        "surface",
        {"document_id": document_id, "view_id": view_id, "ordinal": ordinal, "kind": kind},
    )
    relative = f"rendered/{document_id}/assets/{aid}.svg"
    provenance = preview.serialized or (document_id,)
    asset = AssetOutput(
        aid,
        relative,
        "image/svg+xml",
        digest,
        len(payload),
        tuple(sorted(set(provenance))),
        "technical_source_preview",
        "environment_bound",
        payload=payload,
        properties=(
            {
                "name": "visibility_basis",
                "value_type": "string",
                "value": "layout_observed",
                "source": "derived",
            },
            {
                "name": "serialized_ref_count",
                "value_type": "integer",
                "value": len(preview.serialized),
                "source": "derived",
            },
            {
                "name": "visible_ref_count",
                "value_type": "integer",
                "value": len(preview.visible),
                "source": "derived",
            },
            {
                "name": "clipped_ref_count",
                "value_type": "integer",
                "value": len(preview.clipped),
                "source": "derived",
            },
        ),
    )
    space, canvas = space_bbox(
        document_id,
        sid,
        ordinal,
        width,
        height,
        "px",
        source="rendered",
        method="vysi_builtin_svg_canvas",
    )
    geometries = [canvas]
    for index, element in enumerate(preview.elements):
        geometries.append(element_geometry(sid, str(space["coordinate_space_id"]), index, element))
    surface = SurfaceOutput(
        sid,
        kind,
        ordinal,
        float(width),
        float(height),
        "px",
        tuple(sorted(set(preview.visible))),
        (aid,),
        "partial",
        "approximate",
        "image/svg+xml",
        0,
        96.0,
        tuple(sorted(set(preview.serialized))),
        tuple(sorted(set(preview.clipped))),
        tuple(sorted(set(preview.omitted))),
        "layout_observed",
    )
    return surface, space, geometries, asset


def element_geometry(surface_id: str, space_id: str, ordinal: int, item: Element) -> GeometryOutput:
    gid = stable_id(
        "geometry",
        {"surface_id": surface_id, "element": ordinal, "refs": item.refs, "role": item.role},
    )
    return GeometryOutput(
        gid,
        surface_id,
        space_id,
        "bbox",
        (item.x, item.y, item.width, item.height),
        "rendered",
        1.0,
        "vysi_builtin_svg_element_bbox",
        tuple(sorted(set(item.refs))),
        "partially_clipped" if item.clipped else "fully_visible",
        item.clipped,
        True,
        item.role,
    )
