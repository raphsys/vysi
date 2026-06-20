from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from vysi.common.hashing import sha256_bytes
from vysi.common.ids import stable_id
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import (
    ContainerPart,
    ContainerPartCatalog,
    ContainerRelationship,
)

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"


class UnsafePackageError(ValueError):
    pass


def _normalized_target(source_path: str | None, target: str) -> str:
    base = "" if source_path is None else posixpath.dirname(source_path)
    return posixpath.normpath(posixpath.join(base, target)).lstrip("/")


def _source_part_for_rels(rels_path: str) -> str | None:
    if rels_path == "_rels/.rels":
        return None
    marker = "/_rels/"
    if marker not in rels_path or not rels_path.endswith(".rels"):
        return None
    prefix, tail = rels_path.split(marker, 1)
    return posixpath.join(prefix, tail[:-5])


def inventory_ooxml(
    path: Path,
    *,
    max_entries: int = 20_000,
    max_uncompressed_bytes: int = 2_000_000_000,
    max_ratio: float = 200.0,
) -> ContainerPartCatalog:
    parts: list[ContainerPart] = []
    relationships: list[ContainerRelationship] = []
    warnings: list[str] = []

    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > max_entries:
            raise UnsafePackageError(f"trop d'entrées ZIP: {len(infos)}")
        total_uncompressed = sum(info.file_size for info in infos)
        total_compressed = max(1, sum(info.compress_size for info in infos))
        if total_uncompressed > max_uncompressed_bytes:
            raise UnsafePackageError("taille décompressée supérieure au quota")
        if total_uncompressed / total_compressed > max_ratio:
            raise UnsafePackageError("ratio de compression suspect")

        names = {info.filename for info in infos}
        if "[Content_Types].xml" not in names:
            raise UnsafePackageError("package OOXML sans [Content_Types].xml")

        types_root = ET.fromstring(archive.read("[Content_Types].xml"))
        defaults: dict[str, str] = {}
        overrides: dict[str, str] = {}
        for item in types_root:
            if item.tag == f"{{{CT_NS}}}Default":
                defaults[item.attrib.get("Extension", "").lower()] = item.attrib.get(
                    "ContentType", "application/octet-stream"
                )
            elif item.tag == f"{{{CT_NS}}}Override":
                overrides[item.attrib.get("PartName", "").lstrip("/")] = item.attrib.get(
                    "ContentType", "application/octet-stream"
                )

        rel_by_source: dict[str | None, list[str]] = {}
        for info in infos:
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts:
                raise UnsafePackageError(f"chemin ZIP dangereux: {name}")
            if name.endswith("/"):
                continue
            if name.endswith(".rels"):
                try:
                    root = ET.fromstring(archive.read(name))
                except ET.ParseError as exc:
                    warnings.append(f"relations XML invalides: {name}: {exc}")
                    continue
                source_part = _source_part_for_rels(name)
                source_id = stable_id("part", source_part or "package-root")
                for rel in root.findall(f"{{{REL_NS}}}Relationship"):
                    rel_id = stable_id("rel", name, rel.attrib.get("Id", ""))
                    target_mode = rel.attrib.get("TargetMode", "Internal")
                    external = target_mode.lower() == "external"
                    target = rel.attrib.get("Target", "")
                    relationships.append(
                        ContainerRelationship(
                            relationship_id=rel_id,
                            source_part_id=source_id,
                            relationship_type=rel.attrib.get("Type", ""),
                            target=target if external else _normalized_target(source_part, target),
                            target_mode=target_mode,
                            external=external,
                        )
                    )
                    rel_by_source.setdefault(source_part, []).append(rel_id)

        for info in infos:
            if info.filename.endswith("/"):
                continue
            data = archive.read(info.filename)
            suffix = Path(info.filename).suffix.lower().lstrip(".")
            media_type = overrides.get(
                info.filename,
                defaults.get(suffix, "application/octet-stream"),
            )
            flags: list[str] = []
            lowered = info.filename.lower()
            if "vbaproject" in lowered or lowered.endswith(".bin") and "vba" in lowered:
                flags.append("macro")
            if "/activex/" in lowered:
                flags.append("activex")
            if "/embeddings/" in lowered:
                flags.append("embedded_object")
            if lowered.startswith("customxml/"):
                flags.append("custom_xml")
            part_id = stable_id("part", info.filename)
            source_rel_ids = tuple(rel_by_source.get(info.filename, ()))
            parts.append(
                ContainerPart(
                    part_id=part_id,
                    path=info.filename,
                    media_type=media_type,
                    size_bytes=info.file_size,
                    sha256=sha256_bytes(data),
                    compression=str(info.compress_type),
                    relationship_ids=source_rel_ids,
                    security_flags=tuple(flags),
                    opaque=not (
                        media_type.endswith("+xml") or media_type in {"application/xml", "text/xml"}
                    ),
                    properties={
                        "compressed_size": info.compress_size,
                        "crc": info.CRC,
                    },
                )
            )

    return ContainerPartCatalog(
        header=header("document_source.container_part_catalog"),
        container_kind="ooxml_zip",
        parts=tuple(parts),
        relationships=tuple(relationships),
        warnings=tuple(warnings),
    )
