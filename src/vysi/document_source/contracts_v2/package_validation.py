from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .validation import ContractValidationError, SchemaStore


@dataclass(frozen=True)
class PackageFinding:
    code: str
    message: str
    path: str | None = None


def validate_portable_path(path: str) -> bool:
    pure = PurePosixPath(path)
    return bool(path) and not pure.is_absolute() and ".." not in pure.parts and "\\" not in path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _references(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        keys = {"path", "sha256", "schema_id", "schema_version", "contract_id"}
        if keys.issubset(value):
            yield value
        for child in value.values():
            yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def _schema_key(schema_id: str) -> str | None:
    prefix = "document_source."
    return schema_id[len(prefix) :] if schema_id.startswith(prefix) else None


def validate_package(root: Path, schemas: SchemaStore) -> tuple[PackageFinding, ...]:
    findings: list[PackageFinding] = []
    manifest_path = root / "package_manifest.json"
    if not manifest_path.is_file():
        return (PackageFinding("DS-VAL-001", "package_manifest.json missing"),)
    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
        schemas.validate("package_manifest", manifest)
    except (OSError, json.JSONDecodeError, ContractValidationError) as exc:
        return (PackageFinding("DS-VAL-001", str(exc), "package_manifest.json"),)

    declared_paths: set[str] = set()
    for entry in manifest["files"]:
        relative = str(entry["path"])
        declared_paths.add(relative)
        if not validate_portable_path(relative):
            findings.append(PackageFinding("DS-PST-001", "non-portable path", relative))
            continue
        target = root / relative
        if not target.is_file():
            findings.append(PackageFinding("DS-VAL-001", "manifest file missing", relative))
            continue
        if target.stat().st_size != int(entry["size_bytes"]):
            findings.append(PackageFinding("DS-VAL-001", "size mismatch", relative))
        if sha256_file(target) != str(entry["sha256"]):
            findings.append(PackageFinding("DS-VAL-001", "hash mismatch", relative))
        if target.suffix == ".json":
            try:
                value = json.loads(target.read_text(encoding="utf-8"))
                schema_id = (
                    value.get("header", {}).get("schema_id") if isinstance(value, dict) else None
                )
                key = _schema_key(str(schema_id)) if schema_id else None
                if key and key in schemas.schema_keys:
                    schemas.validate(key, value)
                for reference in _references(value):
                    ref_path = str(reference["path"])
                    if not validate_portable_path(ref_path):
                        findings.append(
                            PackageFinding("DS-VAL-001", "invalid reference path", relative)
                        )
                        continue
                    ref_target = root / ref_path
                    if not ref_target.is_file():
                        findings.append(
                            PackageFinding("DS-VAL-001", f"orphan reference: {ref_path}", relative)
                        )
                        continue
                    if sha256_file(ref_target) != str(reference["sha256"]):
                        findings.append(
                            PackageFinding(
                                "DS-VAL-001", f"reference hash mismatch: {ref_path}", relative
                            )
                        )
            except (OSError, json.JSONDecodeError, ContractValidationError) as exc:
                findings.append(PackageFinding("DS-VAL-001", str(exc), relative))

    for candidate in root.rglob("*"):
        if candidate.is_file():
            rel = candidate.relative_to(root).as_posix()
            if rel not in declared_paths and rel not in {"package_manifest.json", "COMMITTED"}:
                findings.append(PackageFinding("DS-PST-001", "undeclared package file", rel))
    if not (root / "COMMITTED").is_file():
        findings.append(PackageFinding("DS-PST-002", "COMMITTED marker missing"))
    return tuple(findings)
