from __future__ import annotations

import struct
from pathlib import Path

from vysi.common.ids import stable_id
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import ContainerPart, ContainerPartCatalog

OLE_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
FREESECT = 0xFFFFFFFF
ENDOFCHAIN = 0xFFFFFFFE


def _sector(data: bytes, sector_size: int, sector_id: int) -> bytes:
    start = (sector_id + 1) * sector_size
    return data[start : start + sector_size]


def inventory_ole(path: Path) -> tuple[ContainerPartCatalog, tuple[str, ...]]:
    data = path.read_bytes()
    if len(data) < 512 or data[:8] != OLE_SIGNATURE:
        raise ValueError("signature OLE invalide")
    byte_order = struct.unpack_from("<H", data, 0x1C)[0]
    if byte_order != 0xFFFE:
        raise ValueError("ordre des octets OLE non pris en charge")
    sector_shift = struct.unpack_from("<H", data, 0x1E)[0]
    sector_size = 1 << sector_shift
    first_dir_sector = struct.unpack_from("<I", data, 0x30)[0]
    fat_sector_count = struct.unpack_from("<I", data, 0x2C)[0]
    difat = list(struct.unpack_from("<109I", data, 0x4C))
    fat_sector_ids = [sid for sid in difat if sid not in {FREESECT, ENDOFCHAIN}]
    fat_sector_ids = fat_sector_ids[:fat_sector_count]
    fat: list[int] = []
    for sid in fat_sector_ids:
        chunk = _sector(data, sector_size, sid)
        fat.extend(struct.unpack(f"<{len(chunk) // 4}I", chunk))

    def chain(start: int, limit: int = 100_000) -> list[int]:
        result: list[int] = []
        current = start
        visited: set[int] = set()
        while current not in {FREESECT, ENDOFCHAIN} and current < len(fat):
            if current in visited or len(result) >= limit:
                break
            visited.add(current)
            result.append(current)
            current = fat[current]
        return result

    dir_bytes = b"".join(_sector(data, sector_size, sid) for sid in chain(first_dir_sector))
    parts: list[ContainerPart] = []
    stream_names: list[str] = []
    for offset in range(0, len(dir_bytes), 128):
        entry = dir_bytes[offset : offset + 128]
        if len(entry) < 128:
            continue
        name_len = struct.unpack_from("<H", entry, 64)[0]
        obj_type = entry[66]
        if name_len < 2 or obj_type not in {1, 2, 5}:
            continue
        raw_name = entry[: max(0, name_len - 2)]
        name = raw_name.decode("utf-16le", errors="replace")
        size = struct.unpack_from("<Q", entry, 120)[0]
        if obj_type == 2:
            stream_names.append(name)
        parts.append(
            ContainerPart(
                part_id=stable_id("ole-part", offset, name),
                path=name,
                media_type="application/octet-stream",
                size_bytes=int(size),
                sha256=None,
                compression=None,
                opaque=True,
                properties={"ole_object_type": int(obj_type), "directory_offset": offset},
            )
        )

    catalog = ContainerPartCatalog(
        header=header("document_source.container_part_catalog"),
        container_kind="ole_cfb",
        parts=tuple(parts),
        relationships=(),
        warnings=("les flux mini-FAT sont inventoriés mais non extraits dans 0.1.0",),
    )
    return catalog, tuple(stream_names)
