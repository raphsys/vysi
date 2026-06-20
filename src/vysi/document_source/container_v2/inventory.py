from __future__ import annotations

import hashlib
import posixpath
import struct
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, Any
from urllib.parse import quote
from xml.etree import ElementTree as ET

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.errors import StageFailure

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE
FATSECT = 0xFFFFFFFD
DIFSECT = 0xFFFFFFFC
MAXREGSECT = 0xFFFFFFFA
_CHUNK = 1024 * 1024


def _sha_stream(handle: IO[bytes], limit: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = handle.read(_CHUNK)
        if not chunk:
            break
        size += len(chunk)
        if size > limit:
            raise StageFailure(
                "DS-CNT-003", "DS07", "stream", "Budget de lecture de partie dépassé"
            )
        digest.update(chunk)
    return digest.hexdigest(), size


def _portable_component(value: str) -> str:
    cleaned = value.replace("\\", "/")
    return quote(cleaned, safe="._-()/[]{}@!$&',;=+~") or "unnamed"


def _portable_path(value: str) -> str:
    parts = [part for part in value.replace("\\", "/").split("/") if part not in {"", ".", ".."}]
    return "/".join(_portable_component(part) for part in parts) or "root"


def _xml_root(payload: bytes, scope: str) -> ET.Element:
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise StageFailure("DS-CNT-002", "DS07", scope, "DTD ou entité XML interdite")
    try:
        return ET.fromstring(payload)
    except ET.ParseError as exc:
        raise StageFailure(
            "DS-CNT-001", "DS07", scope, "XML de conteneur invalide", str(exc)
        ) from exc


def _source_part_for_rels(rels_path: str) -> str | None:
    if rels_path == "_rels/.rels":
        return None
    marker = "/_rels/"
    if marker not in rels_path or not rels_path.endswith(".rels"):
        return None
    prefix, tail = rels_path.split(marker, 1)
    return posixpath.join(prefix, tail[:-5])


def _normalized_target(source_path: str | None, target: str) -> str:
    base = "" if source_path is None else posixpath.dirname(source_path)
    return posixpath.normpath(posixpath.join(base, target)).lstrip("/")


def _part_kind(path: str, media_type: str) -> str:
    lower = path.lower()
    if lower == "[content_types].xml":
        return "content_types"
    if lower.endswith(".rels"):
        return "relationships"
    if (
        media_type.endswith("+xml")
        or media_type in {"application/xml", "text/xml"}
        or lower.endswith(".xml")
    ):
        return "xml"
    if any(
        token in lower
        for token in ("/media/", "/embeddings/", "vbaproject", "/activex/", "/fonts/")
    ):
        return "resource"
    return "binary"


def _security_flags(path: str, media_type: str, encrypted: bool) -> list[str]:
    lower = path.lower()
    flags: list[str] = []
    if encrypted:
        flags.append("encrypted_entry")
    if "vbaproject" in lower or "vbaProject" in media_type:
        flags.append("macro")
    if "/activex/" in lower or "activeX" in media_type:
        flags.append("activex")
    if "/embeddings/" in lower or "oleObject" in media_type:
        flags.append("embedded_object")
    if lower.startswith("customxml/"):
        flags.append("custom_xml")
    if "/externallinks/" in lower:
        flags.append("external_link_part")
    if lower.startswith("_xmlsignatures/"):
        flags.append("digital_signature")
    return sorted(set(flags))


def _zip_compression_name(value: int) -> str:
    names = {
        zipfile.ZIP_STORED: "stored",
        zipfile.ZIP_DEFLATED: "deflate",
        zipfile.ZIP_BZIP2: "bzip2",
        zipfile.ZIP_LZMA: "lzma",
    }
    return names.get(value, f"method_{value}")


def inventory_zip(
    path: Path,
    document_id: str,
    container_kind: str,
    bundle_ref: dict[str, str],
    max_parts: int,
    max_decompressed_bytes: int,
) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    warnings: list[str] = []
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise StageFailure(
            "DS-CNT-001", "DS07", document_id, "Conteneur ZIP invalide", str(exc)
        ) from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > max_parts:
            raise StageFailure("DS-CNT-003", "DS07", document_id, "Budget max_parts dépassé")
        total = sum(info.file_size for info in infos)
        if total > max_decompressed_bytes:
            raise StageFailure(
                "DS-CNT-003", "DS07", document_id, "Budget max_decompressed_bytes dépassé"
            )
        names_seen: set[str] = set()
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                raise StageFailure("DS-CNT-001", "DS07", info.filename, "Chemin ZIP non portable")
            if info.filename in names_seen:
                warnings.append(f"duplicate_zip_entry:{info.filename}")
            names_seen.add(info.filename)

        defaults: dict[str, str] = {}
        overrides: dict[str, str] = {}
        if "[Content_Types].xml" in names_seen:
            payload = archive.read("[Content_Types].xml")
            if len(payload) > 16 * 1024 * 1024:
                raise StageFailure(
                    "DS-CNT-003", "DS07", document_id, "[Content_Types].xml trop volumineux"
                )
            root = _xml_root(payload, "[Content_Types].xml")
            for child in root:
                if child.tag == f"{{{CT_NS}}}Default":
                    defaults[child.attrib.get("Extension", "").lower()] = child.attrib.get(
                        "ContentType", "application/octet-stream"
                    )
                elif child.tag == f"{{{CT_NS}}}Override":
                    overrides[child.attrib.get("PartName", "").lstrip("/")] = child.attrib.get(
                        "ContentType", "application/octet-stream"
                    )
        elif container_kind == "ooxml_zip":
            warnings.append("missing_content_types")

        rel_source_ids: dict[str | None, str] = {}
        for info in infos:
            if info.is_dir() or not info.filename.endswith(".rels"):
                continue
            payload = archive.read(info.filename)
            if len(payload) > 16 * 1024 * 1024:
                warnings.append(f"relations_too_large:{info.filename}")
                continue
            try:
                root = _xml_root(payload, info.filename)
            except StageFailure:
                warnings.append(f"invalid_relationship_xml:{info.filename}")
                continue
            source_path = _source_part_for_rels(info.filename)
            source_id = stable_id(
                "part", {"document_id": document_id, "path": source_path or "package-root"}
            )
            rel_source_ids[source_path] = source_id
            for rel in root.findall(f"{{{REL_NS}}}Relationship"):
                rel_native_id = rel.attrib.get("Id", "")
                target_mode = rel.attrib.get("TargetMode", "Internal")
                external = target_mode.lower() == "external"
                target = rel.attrib.get("Target", "")
                normalized = target if external else _normalized_target(source_path, target)
                relationships.append(
                    {
                        "relationship_id": stable_id(
                            "relationship",
                            {
                                "document_id": document_id,
                                "rels": info.filename,
                                "id": rel_native_id,
                            },
                        ),
                        "source_part_id": source_id,
                        "relationship_type": rel.attrib.get("Type", "unknown"),
                        "target": normalized,
                        "target_mode": "external" if external else "internal",
                        "external": external,
                    }
                )

        for info in infos:
            if info.is_dir():
                continue
            suffix = PurePosixPath(info.filename).suffix.lower().lstrip(".")
            media_type = overrides.get(
                info.filename, defaults.get(suffix, "application/octet-stream")
            )
            with archive.open(info, "r") as handle:
                digest, observed = _sha_stream(handle, max_decompressed_bytes)
            if observed != info.file_size:
                warnings.append(f"zip_size_mismatch:{info.filename}")
            kind = _part_kind(info.filename, media_type)
            opaque = kind not in {"xml", "relationships", "content_types"}
            parts.append(
                {
                    "part_id": stable_id(
                        "part",
                        {"document_id": document_id, "path": info.filename, "sha256": digest},
                    ),
                    "path": _portable_path(info.filename),
                    "part_kind": kind,
                    "media_type": media_type,
                    "compressed_size": info.compress_size,
                    "size_bytes": info.file_size,
                    "sha256": digest,
                    "compression": _zip_compression_name(info.compress_type),
                    "parent_part_id": None,
                    "read_state": "preserved" if opaque else "hashed",
                    "opaque": opaque,
                    "security_flags": _security_flags(
                        info.filename, media_type, bool(info.flag_bits & 0x1)
                    ),
                    "stored_ref": bundle_ref if opaque else None,
                }
            )
    return {
        "document_id": document_id,
        "container_kind": container_kind,
        "parts": parts,
        "relationships": relationships,
        "warnings": sorted(set(warnings)),
    }


@dataclass(frozen=True)
class _CfbEntry:
    index: int
    name: str
    object_type: int
    left: int
    right: int
    child: int
    start_sector: int
    size: int


class _CfbReader:
    def __init__(self, path: Path, max_parts: int, max_bytes: int) -> None:
        self.path = path
        self.data = path.read_bytes()
        self.max_parts = max_parts
        self.max_bytes = max_bytes
        if len(self.data) < 512 or self.data[:8] != OLE_MAGIC:
            raise StageFailure("DS-CNT-001", "DS07", path.name, "Signature OLE invalide")
        if struct.unpack_from("<H", self.data, 0x1C)[0] != 0xFFFE:
            raise StageFailure(
                "DS-CNT-002", "DS07", path.name, "Ordre des octets OLE non pris en charge"
            )
        self.sector_size = 1 << struct.unpack_from("<H", self.data, 0x1E)[0]
        self.mini_sector_size = 1 << struct.unpack_from("<H", self.data, 0x20)[0]
        if self.sector_size not in {512, 4096} or self.mini_sector_size != 64:
            raise StageFailure(
                "DS-CNT-002", "DS07", path.name, "Tailles de secteurs OLE non prises en charge"
            )
        self.fat_sector_count = struct.unpack_from("<I", self.data, 0x2C)[0]
        self.first_dir_sector = struct.unpack_from("<I", self.data, 0x30)[0]
        self.mini_cutoff = struct.unpack_from("<I", self.data, 0x38)[0]
        self.first_mini_fat = struct.unpack_from("<I", self.data, 0x3C)[0]
        self.mini_fat_count = struct.unpack_from("<I", self.data, 0x40)[0]
        self.first_difat = struct.unpack_from("<I", self.data, 0x44)[0]
        self.difat_count = struct.unpack_from("<I", self.data, 0x48)[0]
        self.fat = self._load_fat()
        self.entries = self._load_directory()
        self.root = next((entry for entry in self.entries if entry.object_type == 5), None)
        self.mini_fat = self._load_mini_fat()
        self.mini_stream = (
            self._read_regular_stream(self.root.start_sector, self.root.size) if self.root else b""
        )

    def _sector(self, sector_id: int) -> bytes:
        sector_count = max(0, len(self.data) // self.sector_size - 1)
        if sector_id < 0 or sector_id >= sector_count:
            raise StageFailure(
                "DS-CNT-001", "DS07", self.path.name, f"Secteur OLE hors limites: {sector_id}"
            )
        start = (sector_id + 1) * self.sector_size
        sector = self.data[start : start + self.sector_size]
        if len(sector) != self.sector_size:
            raise StageFailure(
                "DS-CNT-001", "DS07", self.path.name, f"Secteur OLE tronqué: {sector_id}"
            )
        return sector

    def _chain(self, start: int, table: list[int], limit: int | None = None) -> list[int]:
        result: list[int] = []
        visited: set[int] = set()
        current = start
        effective_limit = limit or max(1, len(table) + 1)
        while current not in {FREESECT, ENDOFCHAIN}:
            if current in visited or current >= len(table) or current > MAXREGSECT:
                raise StageFailure(
                    "DS-CNT-001", "DS07", self.path.name, "Chaîne OLE invalide ou cyclique"
                )
            visited.add(current)
            result.append(current)
            if len(result) > effective_limit:
                raise StageFailure(
                    "DS-CNT-003", "DS07", self.path.name, "Chaîne OLE supérieure au quota"
                )
            current = table[current]
        return result

    def _load_fat(self) -> list[int]:
        difat = [sid for sid in struct.unpack_from("<109I", self.data, 0x4C) if sid <= MAXREGSECT]
        current = self.first_difat
        seen: set[int] = set()
        for _ in range(self.difat_count):
            if current in seen or current > MAXREGSECT:
                raise StageFailure("DS-CNT-001", "DS07", self.path.name, "Chaîne DIFAT invalide")
            seen.add(current)
            sector = self._sector(current)
            count = self.sector_size // 4
            values = list(struct.unpack(f"<{count}I", sector))
            difat.extend(sid for sid in values[:-1] if sid <= MAXREGSECT)
            current = values[-1]
        fat_sector_ids = difat[: self.fat_sector_count]
        if len(fat_sector_ids) < self.fat_sector_count:
            raise StageFailure("DS-CNT-001", "DS07", self.path.name, "FAT OLE incomplète")
        fat: list[int] = []
        for sid in fat_sector_ids:
            sector = self._sector(sid)
            fat.extend(struct.unpack(f"<{self.sector_size // 4}I", sector))
        return fat

    def _load_mini_fat(self) -> list[int]:
        if self.mini_fat_count == 0 or self.first_mini_fat in {FREESECT, ENDOFCHAIN}:
            return []
        sectors = self._chain(self.first_mini_fat, self.fat, self.mini_fat_count + 1)
        payload = b"".join(self._sector(sid) for sid in sectors[: self.mini_fat_count])
        return list(struct.unpack(f"<{len(payload) // 4}I", payload))

    def _read_regular_stream(self, start: int, size: int) -> bytes:
        if size == 0:
            return b""
        sectors = self._chain(start, self.fat)
        payload = b"".join(self._sector(sid) for sid in sectors)
        return payload[:size]

    def _read_mini_stream(self, start: int, size: int) -> bytes:
        if size == 0:
            return b""
        if not self.mini_fat:
            raise StageFailure("DS-CNT-001", "DS07", self.path.name, "mini-FAT absente")
        sectors = self._chain(start, self.mini_fat)
        pieces: list[bytes] = []
        for sid in sectors:
            offset = sid * self.mini_sector_size
            pieces.append(self.mini_stream[offset : offset + self.mini_sector_size])
        return b"".join(pieces)[:size]

    def _load_directory(self) -> list[_CfbEntry]:
        sectors = self._chain(self.first_dir_sector, self.fat)
        payload = b"".join(self._sector(sid) for sid in sectors)
        entries: list[_CfbEntry] = []
        for index, offset in enumerate(range(0, len(payload), 128)):
            raw = payload[offset : offset + 128]
            if len(raw) < 128:
                break
            name_len = struct.unpack_from("<H", raw, 64)[0]
            obj_type = raw[66]
            if obj_type not in {0, 1, 2, 5}:
                raise StageFailure(
                    "DS-CNT-001",
                    "DS07",
                    self.path.name,
                    f"Type d'entrée OLE invalide à l'index {index}: {obj_type}",
                )
            name = ""
            if 2 <= name_len <= 64:
                name = raw[: name_len - 2].decode("utf-16le", errors="replace")
            entries.append(
                _CfbEntry(
                    index=index,
                    name=name,
                    object_type=obj_type,
                    left=struct.unpack_from("<I", raw, 68)[0],
                    right=struct.unpack_from("<I", raw, 72)[0],
                    child=struct.unpack_from("<I", raw, 76)[0],
                    start_sector=struct.unpack_from("<I", raw, 116)[0],
                    size=struct.unpack_from("<Q", raw, 120)[0],
                )
            )
            if len(entries) > self.max_parts:
                raise StageFailure("DS-CNT-003", "DS07", self.path.name, "Budget max_parts dépassé")
        return entries

    def _tree_indices(self, root_index: int) -> Iterable[int]:
        visited: set[int] = set()

        def walk(index: int) -> Iterable[int]:
            if (
                index in {FREESECT, ENDOFCHAIN, 0xFFFFFFFF}
                or index >= len(self.entries)
                or index in visited
            ):
                return ()
            visited.add(index)
            entry = self.entries[index]
            return (*walk(entry.left), index, *walk(entry.right))

        return walk(root_index)

    def paths(self) -> dict[int, tuple[str, int | None]]:
        result: dict[int, tuple[str, int | None]] = {}
        root = self.root
        if root is None:
            return result
        result[root.index] = (_portable_component(root.name or "Root Entry"), None)

        def descend(parent: _CfbEntry, parent_path: str) -> None:
            for index in self._tree_indices(parent.child):
                entry = self.entries[index]
                name = _portable_component(entry.name or f"entry_{index}")
                path = f"{parent_path}/{name}"
                result[index] = (path, parent.index)
                if entry.object_type in {1, 5}:
                    descend(entry, path)

        descend(root, result[root.index][0])
        for entry in self.entries:
            result.setdefault(
                entry.index, (f"orphan/{entry.index}_{_portable_component(entry.name)}", None)
            )
        return result

    def stream_bytes(self, entry: _CfbEntry) -> bytes:
        if entry.size > self.max_bytes:
            raise StageFailure("DS-CNT-003", "DS07", entry.name, "Flux OLE supérieur au quota")
        if entry.size < self.mini_cutoff and entry.object_type == 2:
            return self._read_mini_stream(entry.start_sector, entry.size)
        return self._read_regular_stream(entry.start_sector, entry.size)


def inventory_ole(
    path: Path,
    document_id: str,
    bundle_ref: dict[str, str],
    max_parts: int,
    max_decompressed_bytes: int,
) -> dict[str, Any]:
    reader = _CfbReader(path, max_parts, max_decompressed_bytes)
    paths = reader.paths()
    parts: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []
    index_to_id: dict[int, str] = {}
    for entry in reader.entries:
        if entry.object_type == 0:
            continue
        path_value, _ = paths[entry.index]
        part_id = stable_id(
            "part", {"document_id": document_id, "ole_index": entry.index, "path": path_value}
        )
        index_to_id[entry.index] = part_id
    for entry in reader.entries:
        if entry.object_type == 0:
            continue
        path_value, parent_index = paths[entry.index]
        parent_id = index_to_id.get(parent_index) if parent_index is not None else None
        kind = {1: "storage", 2: "stream", 5: "root_storage"}.get(entry.object_type, "unknown")
        digest: str | None = None
        size = int(entry.size)
        read_state = "metadata_only"
        flags: list[str] = []
        lower = entry.name.lower()
        if any(token in lower for token in ("vba", "macros", "_vba_project")):
            flags.append("macro")
        if any(token in lower for token in ("objectpool", "ole10native", "package")):
            flags.append("embedded_object")
        if any(token in lower for token in ("encryptedpackage", "encryptioninfo")):
            flags.append("encrypted_content")
        if entry.object_type == 2:
            try:
                payload = reader.stream_bytes(entry)
                digest = hashlib.sha256(payload).hexdigest()
                read_state = "preserved"
            except StageFailure:
                read_state = "failed"
        parts.append(
            {
                "part_id": index_to_id[entry.index],
                "path": path_value,
                "part_kind": kind,
                "media_type": "application/octet-stream" if entry.object_type == 2 else None,
                "compressed_size": None,
                "size_bytes": size,
                "sha256": digest,
                "compression": None,
                "parent_part_id": parent_id,
                "read_state": read_state,
                "opaque": True,
                "security_flags": sorted(set(flags)),
                "stored_ref": bundle_ref,
            }
        )
        if parent_id is not None:
            relationships.append(
                {
                    "relationship_id": stable_id(
                        "relationship",
                        {
                            "document_id": document_id,
                            "source": parent_id,
                            "target": index_to_id[entry.index],
                        },
                    ),
                    "source_part_id": parent_id,
                    "relationship_type": "contains",
                    "target": index_to_id[entry.index],
                    "target_mode": "internal",
                    "external": False,
                }
            )
    return {
        "document_id": document_id,
        "container_kind": "ole_cfb",
        "parts": parts,
        "relationships": relationships,
        "warnings": ["legacy_ole_semantic_decode_deferred"],
    }


def inventory_single(
    artifact: dict[str, Any],
    document: dict[str, Any],
    bundle_ref: dict[str, str],
) -> dict[str, Any]:
    format_name = str(document["format_name"])
    if format_name == "txt":
        kind = "text"
    elif str(document["family"]) == "raster":
        kind = "image"
    elif format_name == "pdf":
        kind = "fixed_layout_document"
    else:
        kind = "binary"
    path = _portable_path(f"artifact/{artifact['original_name']}")
    part = {
        "part_id": stable_id(
            "part", {"document_id": document["document_id"], "artifact": artifact["artifact_id"]}
        ),
        "path": path,
        "part_kind": kind,
        "media_type": document.get("media_type"),
        "compressed_size": None,
        "size_bytes": artifact["size_bytes"],
        "sha256": artifact["sha256"],
        "compression": None,
        "parent_part_id": None,
        "read_state": "preserved",
        "opaque": format_name == "unknown_binary",
        "security_flags": [],
        "stored_ref": bundle_ref,
    }
    return {
        "document_id": document["document_id"],
        "container_kind": document["container_kind"],
        "parts": [part],
        "relationships": [],
        "warnings": [],
    }


def inventory_document(
    path: Path,
    artifact: dict[str, Any],
    document: dict[str, Any],
    bundle_ref: dict[str, str],
    max_parts: int,
    max_decompressed_bytes: int,
) -> dict[str, Any]:
    kind = str(document["container_kind"])
    if kind in {"ooxml_zip", "zip"}:
        return inventory_zip(
            path, str(document["document_id"]), kind, bundle_ref, max_parts, max_decompressed_bytes
        )
    if kind == "ole_cfb":
        return inventory_ole(
            path, str(document["document_id"]), bundle_ref, max_parts, max_decompressed_bytes
        )
    return inventory_single(artifact, document, bundle_ref)
