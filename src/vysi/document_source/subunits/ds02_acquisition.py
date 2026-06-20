from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, BinaryIO

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure

_CHUNK = 1024 * 1024


def _safe_component(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name).strip("._")
    return cleaned[:180] or "source.bin"


def _copy_stream(source: BinaryIO, target: Path, remaining: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    try:
        with temp.open("wb") as out:
            while True:
                chunk = source.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > remaining:
                    raise StageFailure(
                        "DS-LIM-001", "DS02", target.name, "Budget max_source_bytes dépassé"
                    )
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        temp.replace(target)
    except Exception:
        temp.unlink(missing_ok=True)
        raise
    return size, digest.hexdigest()


def _directory_files(root: Path) -> Iterator[Path]:
    for candidate in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if candidate.is_symlink():
            raise StageFailure(
                "DS-ACQ-001",
                "DS02",
                str(candidate),
                "Lien symbolique interdit dans une source répertoire",
            )
        if candidate.is_file():
            yield candidate


def execute(
    ctx: ExecutionContext,
    request: dict[str, Any],
    normalized: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    del request
    ctx.check_cancelled("DS02")
    max_bytes = int(policy["resource_budget"]["max_source_bytes"])
    max_temp_bytes = int(policy["resource_budget"]["max_temp_bytes"])
    max_parts = int(policy["resource_budget"]["max_parts"])
    total = 0
    artifacts: list[dict[str, Any]] = []
    expanded: list[tuple[dict[str, Any], Path | None, bytes | None]] = []
    for locator in normalized["normalized_sources"]:
        kind = str(locator["kind"])
        if kind in {"local_file", "archive"}:
            path = Path(str(locator["uri"]))
            if not path.is_file() or path.is_symlink():
                raise StageFailure(
                    "DS-ACQ-001",
                    "DS02",
                    str(locator["locator_id"]),
                    "Fichier local absent ou non régulier",
                )
            expanded.append((locator, path, None))
        elif kind == "directory":
            directory = Path(str(locator["uri"]))
            if not directory.is_dir() or directory.is_symlink():
                raise StageFailure(
                    "DS-ACQ-001", "DS02", str(locator["locator_id"]), "Répertoire absent ou non sûr"
                )
            for child in _directory_files(directory):
                child_locator = dict(locator)
                child_locator["display_name"] = child.relative_to(directory).as_posix()
                expanded.append((child_locator, child, None))
        elif kind in {"bytes", "stream"}:
            binding = ctx.bindings.get(str(locator["locator_id"]))
            if binding is None:
                raise StageFailure(
                    "DS-ACQ-002", "DS02", str(locator["locator_id"]), "Binding injecté absent"
                )
            expanded.append((locator, None, binding))
        elif kind == "url":
            raise StageFailure(
                "DS-ACQ-002",
                "DS02",
                str(locator["locator_id"]),
                "Acquisition réseau non implémentée dans DS02 local",
            )
        else:
            raise StageFailure(
                "DS-ACQ-002",
                "DS02",
                str(locator["locator_id"]),
                f"Type de source non pris en charge: {kind}",
            )

    if not expanded:
        raise StageFailure("DS-ACQ-001", "DS02", "bundle", "Aucun artefact acquérable")
    if len(expanded) > max_parts:
        raise StageFailure("DS-LIM-001", "DS02", "bundle", "Budget max_parts dépassé")

    for ordinal, (locator, source_path, payload) in enumerate(expanded):
        ctx.check_cancelled("DS02")
        display_name = str(
            locator.get("display_name")
            or (source_path.name if source_path else f"{locator['locator_id']}.bin")
        )
        seed = {
            "locator_id": locator["locator_id"],
            "ordinal": ordinal,
            "display_name": display_name,
        }
        artifact_id = stable_id("artifact", seed)
        target = (
            ctx.workspace
            / "native"
            / "artifacts"
            / f"{ordinal:05d}_{artifact_id}_{_safe_component(Path(display_name).name)}"
        )
        remaining = max_bytes - total
        if source_path is not None:
            with source_path.open("rb") as handle:
                size, digest = _copy_stream(handle, target, remaining)
        else:
            assert payload is not None
            from io import BytesIO

            size, digest = _copy_stream(BytesIO(payload), target, remaining)
        expected = locator.get("expected_sha256")
        if expected is not None and str(expected) != digest:
            target.unlink(missing_ok=True)
            raise StageFailure(
                "DS-ACQ-001", "DS02", artifact_id, "SHA-256 attendu différent", f"observed={digest}"
            )
        total += size
        if total > max_temp_bytes:
            target.unlink(missing_ok=True)
            raise StageFailure("DS-LIM-001", "DS02", artifact_id, "Budget max_temp_bytes dépassé")
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "source_locator_id": locator["locator_id"],
                "role": locator["role"],
                "ordinal": ordinal,
                "original_name": display_name,
                "stored_path": target.relative_to(ctx.workspace).as_posix(),
                "size_bytes": size,
                "sha256": digest,
                "acquisition_kind": locator["kind"],
                "source_uri_redacted": f"{locator['kind']}:{Path(display_name).name}",
                **(
                    {"declared_media_type": locator["declared_media_type"]}
                    if locator.get("declared_media_type")
                    else {}
                ),
            }
        )

    bundle_body = {
        "bundle_id": stable_id(
            "bundle", [(a["sha256"], a["ordinal"], a["role"]) for a in artifacts]
        ),
        "artifacts": artifacts,
        "total_size_bytes": total,
    }
    bundle = make_contract(
        "acquired_source_bundle", bundle_body, producer_version=ctx.producer_version
    )
    _, bundle_ref = validate_and_write(
        ctx.workspace,
        "manifests/acquired_source_bundle.json",
        "acquired_source_bundle",
        bundle,
        ctx.schemas,
    )
    ctx.references.append(bundle_ref)
    ctx.completed_nodes.append("DS02")
    return bundle
