from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any, cast

from ..models import AssetOutput, GeometryOutput, SurfaceOutput
from .common import preview_outputs
from .svg import Item, text_pages


def word_items(profile: dict[str, Any]) -> tuple[list[Item], set[str]]:
    blocks = cast(list[dict[str, Any]], profile.get("blocks", []))
    children: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for block in blocks:
        parent = block.get("parent_id")
        if parent is not None:
            children[str(parent)].append(block)
    preferred = {
        "paragraph", "cell", "header", "footer", "footnote", "endnote",
        "field", "content_control", "bookmark",
    }
    selected: list[dict[str, Any]] = []
    for block in blocks:
        text = str(block.get("text") or "")
        kind = str(block.get("kind") or "")
        if not text or kind not in preferred:
            continue
        if kind == "cell" and any(
            str(child.get("kind")) == "paragraph" and str(child.get("text") or "")
            for child in children.get(str(block["unit_id"]), [])
        ):
            continue
        selected.append(block)
    selected_ids = {str(block["unit_id"]) for block in selected}
    for block in blocks:
        if (
            str(block.get("text") or "")
            and str(block.get("kind")) == "run"
            and str(block.get("parent_id") or "") not in selected_ids
        ):
            selected.append(block)
    source_order = {str(block["unit_id"]): index for index, block in enumerate(blocks)}
    selected.sort(key=lambda block: source_order.get(str(block["unit_id"]), len(blocks)))
    items: list[Item] = []
    refs: set[str] = set()
    resources: set[tuple[str, str]] = set()
    for block in selected:
        uid = str(block["unit_id"])
        refs.add(uid)
        items.append(Item((uid,), str(block.get("text") or ""), str(block.get("kind") or "text")))
        for resource_id in block.get("resource_refs", []):
            resource = str(resource_id)
            key = (uid, resource)
            if key in resources:
                continue
            resources.add(key)
            refs.add(resource)
            items.append(Item((uid, resource), f"[embedded resource {resource}]", "resource_placeholder"))
    return items, refs


def render_text(
    *, document_id: str, view_id: str, profile: dict[str, Any],
    profile_kind: str, check: Callable[[], None], account: Callable[[int], None],
) -> tuple[list[SurfaceOutput], list[dict[str, Any]], list[GeometryOutput], list[AssetOutput], set[str], list[str]]:
    if profile_kind == "plain_text":
        lines = cast(list[dict[str, Any]], profile.get("lines", []))
        items = [Item((str(line["unit_id"]),), str(line.get("text") or ""), "text_line") for line in lines]
        candidates = {str(line["unit_id"]) for line in lines}
        title = "Text source technical preview"
        kind = "text_preview"
        footer = "Vysi technical source preview - derived pagination"
        warning = "technical_preview_layout_not_native"
    else:
        items, candidates = word_items(profile)
        title = "Wordprocessing technical preview"
        kind = "flow_page"
        footer = "Vysi technical source preview - non canonical pagination"
        warning = "wordprocessing_pagination_is_derived_not_native"
    previews = text_pages(title=title, items=items, width=794, height=1123, footer=footer, check=check)
    surfaces: list[SurfaceOutput] = []
    spaces: list[dict[str, Any]] = []
    geometries: list[GeometryOutput] = []
    assets: list[AssetOutput] = []
    for ordinal, preview in enumerate(previews):
        surface, space, geo, asset = preview_outputs(
            document_id=document_id, view_id=view_id, ordinal=ordinal, kind=kind,
            preview=preview, width=794, height=1123, check=check, account=account,
        )
        surfaces.append(surface)
        spaces.append(space)
        geometries.extend(geo)
        assets.append(asset)
    return surfaces, spaces, geometries, assets, candidates, [warning]
