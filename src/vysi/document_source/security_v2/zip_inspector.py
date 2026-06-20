from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class ZipInspection:
    entries: int
    decompressed_bytes: int
    compressed_bytes: int
    unsafe_paths: tuple[str, ...]
    duplicate_paths: tuple[str, ...]
    active_parts: tuple[str, ...]
    external_parts: tuple[str, ...]
    embedded_parts: tuple[str, ...]
    encrypted_entries: tuple[str, ...]


def inspect_zip(path: Path) -> ZipInspection:
    seen: set[str] = set()
    duplicates: list[str] = []
    unsafe: list[str] = []
    active: list[str] = []
    external: list[str] = []
    embedded: list[str] = []
    encrypted: list[str] = []
    decompressed = 0
    compressed = 0
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        for info in infos:
            name = info.filename.replace("\\", "/")
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                unsafe.append(info.filename)
            normalized = pure.as_posix().lower()
            if normalized in seen:
                duplicates.append(info.filename)
            seen.add(normalized)
            decompressed += info.file_size
            compressed += info.compress_size
            if any(
                token in normalized for token in ("vbaproject", "activex", "macrosheet", "customui")
            ):
                active.append(info.filename)
            if normalized.endswith(".rels") and info.file_size <= 4 * 1024 * 1024:
                with archive.open(info) as handle:
                    relation_bytes = handle.read(4 * 1024 * 1024 + 1)
                if (
                    b'TargetMode="External"' in relation_bytes
                    or b"TargetMode='External'" in relation_bytes
                ):
                    external.append(info.filename)
            if any(token in normalized for token in ("/embeddings/", "oleobject")):
                embedded.append(info.filename)
            if info.flag_bits & 0x1:
                encrypted.append(info.filename)
    return ZipInspection(
        entries=len(infos),
        decompressed_bytes=decompressed,
        compressed_bytes=compressed,
        unsafe_paths=tuple(unsafe),
        duplicate_paths=tuple(duplicates),
        active_parts=tuple(active),
        external_parts=tuple(external),
        embedded_parts=tuple(embedded),
        encrypted_entries=tuple(encrypted),
    )
