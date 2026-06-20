from __future__ import annotations

import mimetypes
import zipfile
from pathlib import Path

from vysi.document_source.adapters.containers.ole import OLE_SIGNATURE, inventory_ole
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import CapabilityManifest, FormatDescriptor
from vysi.document_source.domain.enums import DocumentFamily, LayoutNature


def probe(path: Path) -> tuple[FormatDescriptor, CapabilityManifest, tuple[str, ...]]:
    head = path.read_bytes()[:32]
    extension = path.suffix.lower()
    evidence: list[str] = []
    limitations: list[str] = []
    format_name = "unknown"
    family = DocumentFamily.UNKNOWN
    layout = LayoutNature.UNKNOWN
    container = "binary"
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    capabilities: list[str] = ["preserve_original"]
    ole_streams: tuple[str, ...] = ()

    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
        container = "ooxml_zip"
        evidence.append(
            "zip valide avec [Content_Types].xml" if "[Content_Types].xml" in names else "zip"
        )
        if "word/document.xml" in names:
            format_name = "docx"
            family = DocumentFamily.WORDPROCESSING
            layout = LayoutNature.FLOW
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            capabilities += [
                "has_flow_layout",
                "has_styles",
                "has_relationships",
                "supports_external_render",
            ]
        elif "xl/workbook.xml" in names:
            format_name = "xlsx"
            family = DocumentFamily.SPREADSHEET
            layout = LayoutNature.GRID
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            capabilities += [
                "has_grid_model",
                "has_formulas",
                "has_styles",
                "has_relationships",
                "supports_external_render",
            ]
        elif "ppt/presentation.xml" in names:
            format_name = "pptx"
            family = DocumentFamily.PRESENTATION
            layout = LayoutNature.SLIDE
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            capabilities += [
                "has_slides",
                "has_timing",
                "has_styles",
                "has_relationships",
                "supports_external_render",
            ]
        else:
            limitations.append("archive ZIP non reconnue comme OOXML pris en charge")
    elif head.startswith(OLE_SIGNATURE):
        container = "ole_cfb"
        catalog, ole_streams = inventory_ole(path)
        del catalog
        evidence.append("signature OLE CFB")
        lowered = {name.lower() for name in ole_streams}
        family = DocumentFamily.LEGACY_OLE
        layout = LayoutNature.UNKNOWN
        capabilities += ["has_ole_container", "supports_external_render"]
        limitations.append("extraction OLE native partielle dans 0.1.0")
        if "worddocument" in lowered:
            format_name = "doc"
            family = DocumentFamily.WORDPROCESSING
            layout = LayoutNature.FLOW
            capabilities.append("has_flow_layout")
        elif "workbook" in lowered or "book" in lowered:
            format_name = "xls"
            family = DocumentFamily.SPREADSHEET
            layout = LayoutNature.GRID
            capabilities += ["has_grid_model", "has_formulas"]
        elif "powerpoint document" in lowered:
            format_name = "ppt"
            family = DocumentFamily.PRESENTATION
            layout = LayoutNature.SLIDE
            capabilities.append("has_slides")
        media_type = "application/x-ole-storage"
    elif head.startswith(b"%PDF-"):
        format_name = "pdf"
        family = DocumentFamily.FIXED_LAYOUT
        layout = LayoutNature.FIXED
        media_type = "application/pdf"
        capabilities += ["has_native_pages", "supports_native_render"]
        limitations.append("migration du lecteur PDF v2 planifiée")
        evidence.append("signature PDF")
    elif head.startswith(b"\x89PNG\r\n\x1a\n"):
        format_name = "png"
        family = DocumentFamily.RASTER
        layout = LayoutNature.RASTER
        media_type = "image/png"
        limitations.append("migration du lecteur raster v2 planifiée")
        evidence.append("signature PNG")
    elif head.startswith(b"\xff\xd8\xff"):
        format_name = "jpeg"
        family = DocumentFamily.RASTER
        layout = LayoutNature.RASTER
        media_type = "image/jpeg"
        limitations.append("migration du lecteur raster v2 planifiée")
        evidence.append("signature JPEG")
    else:
        format_name = "txt"
        family = DocumentFamily.PLAIN_TEXT
        layout = LayoutNature.LINEAR
        media_type = "text/plain"
        capabilities += ["has_linear_text", "supports_native_parse"]
        evidence.append(f"repli texte pour extension {extension or '<none>'}")

    caps = CapabilityManifest(
        header=header("document_source.capability_manifest"),
        capabilities=tuple(sorted(set(capabilities))),
        limitations=tuple(limitations),
    )
    descriptor = FormatDescriptor(
        header=header("document_source.format_descriptor"),
        format_name=format_name,
        family=family,
        layout_nature=layout,
        container_kind=container,
        media_type=media_type,
        version=None,
        confidence=0.99 if family is not DocumentFamily.UNKNOWN else 0.5,
        evidence=tuple(evidence),
        capability_ref=None,
    )
    return descriptor, caps, ole_streams
