from __future__ import annotations

from vysi.common.ids import stable_id
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import (
    ContainerPartCatalog,
    NativeResource,
    NativeResourceCatalog,
)


def build_resources(catalog: ContainerPartCatalog, document_id: str) -> NativeResourceCatalog:
    resources: list[NativeResource] = []
    for part in catalog.parts:
        path = part.path.lower()
        kind: str | None = None
        active = False
        if "/media/" in path:
            kind = "embedded_media"
        elif "/embeddings/" in path:
            kind = "embedded_object"
        elif "vbaproject" in path:
            kind = "macro_project"
            active = True
        elif "/activex/" in path:
            kind = "activex_control"
            active = True
        elif path.startswith("customxml/"):
            kind = "custom_xml"
        elif path.endswith(("styles.xml", "theme1.xml")):
            kind = "style_or_theme_part"
        if kind is None:
            continue
        resources.append(
            NativeResource(
                resource_id=stable_id("resource", part.part_id),
                kind=kind,
                owner_type="document",
                owner_id=document_id,
                native_reference=part.path,
                media_type=part.media_type,
                size_bytes=part.size_bytes,
                sha256=part.sha256,
                stored_path=None,
                active=active,
                properties={"opaque": part.opaque},
            )
        )
    return NativeResourceCatalog(
        header=header("document_source.native_resource_catalog"),
        resources=tuple(resources),
    )
