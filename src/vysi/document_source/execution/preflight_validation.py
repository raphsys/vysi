from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.contracts_v2.validation import ContractValidationError, SchemaStore


@dataclass(frozen=True)
class PreflightFinding:
    code: str
    message: str
    path: str | None = None


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _portable(path: str) -> bool:
    pure = PurePosixPath(path)
    return bool(path) and not pure.is_absolute() and ".." not in pure.parts and "\\" not in path


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _references(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        required = {"path", "sha256", "schema_id", "schema_version", "contract_id"}
        if required.issubset(value):
            yield cast(dict[str, Any], value)
        for child in value.values():
            yield from _references(child)
    elif isinstance(value, list):
        for child in value:
            yield from _references(child)


def validate_preflight(
    root: Path, schemas: SchemaStore | None = None
) -> tuple[PreflightFinding, ...]:
    active_schemas = schemas or SchemaStore(Path(__file__).resolve().parents[1] / "schemas" / "v2")
    findings: list[PreflightFinding] = []
    if (root / "COMMITTED").exists():
        findings.append(
            PreflightFinding("DS-PST-001", "COMMITTED interdit avant DS15", "COMMITTED")
        )
    checkpoint_path = root / "execution/checkpoint_manifest.json"
    if not checkpoint_path.is_file():
        return (
            PreflightFinding(
                "DS-VAL-001", "Checkpoint absent", "execution/checkpoint_manifest.json"
            ),
        )
    try:
        checkpoint = _load(checkpoint_path)
        active_schemas.validate("checkpoint_manifest", checkpoint)
        if checkpoint["header"]["content_hash"] != content_hash(checkpoint):
            findings.append(
                PreflightFinding(
                    "DS-VAL-001",
                    "Hash canonique du checkpoint invalide",
                    "execution/checkpoint_manifest.json",
                )
            )
    except (OSError, json.JSONDecodeError, ContractValidationError) as exc:
        return (PreflightFinding("DS-VAL-001", str(exc), "execution/checkpoint_manifest.json"),)

    for reference in checkpoint["artifacts"]:
        relative = str(reference["path"])
        if not _portable(relative):
            findings.append(PreflightFinding("DS-PST-001", "Chemin non portable", relative))
            continue
        target = root / relative
        if not target.is_file():
            findings.append(PreflightFinding("DS-VAL-001", "Référence absente", relative))
            continue
        if _sha(target) != reference["sha256"]:
            findings.append(
                PreflightFinding("DS-VAL-001", "SHA-256 de référence invalide", relative)
            )
            continue
        if target.suffix != ".json":
            continue
        try:
            value = _load(target)
            schema_id = str(value.get("header", {}).get("schema_id", ""))
            schema_key = schema_id.removeprefix("document_source.")
            if schema_key not in active_schemas.schema_keys:
                findings.append(
                    PreflightFinding("DS-VAL-001", f"Schéma inconnu: {schema_id}", relative)
                )
                continue
            active_schemas.validate(schema_key, value)
            if value["header"]["content_hash"] != content_hash(value):
                findings.append(
                    PreflightFinding("DS-VAL-001", "Hash canonique du contrat invalide", relative)
                )
            if value["header"]["contract_id"] != reference["contract_id"]:
                findings.append(
                    PreflightFinding("DS-VAL-001", "contract_id de référence incohérent", relative)
                )
            for nested in _references(value):
                nested_path = str(nested["path"])
                if not _portable(nested_path):
                    findings.append(
                        PreflightFinding(
                            "DS-PST-001", "Chemin de référence imbriquée non portable", relative
                        )
                    )
                    continue
                nested_target = root / nested_path
                if not nested_target.is_file():
                    findings.append(
                        PreflightFinding(
                            "DS-VAL-001", f"Référence imbriquée absente: {nested_path}", relative
                        )
                    )
                elif _sha(nested_target) != nested["sha256"]:
                    findings.append(
                        PreflightFinding(
                            "DS-VAL-001",
                            f"Hash de référence imbriquée invalide: {nested_path}",
                            relative,
                        )
                    )
        except (OSError, json.JSONDecodeError, ContractValidationError, KeyError) as exc:
            findings.append(PreflightFinding("DS-VAL-001", str(exc), relative))

    bundle_path = root / "manifests/acquired_source_bundle.json"
    if bundle_path.is_file():
        try:
            bundle = _load(bundle_path)
            for artifact in bundle["artifacts"]:
                relative = str(artifact["stored_path"])
                if not _portable(relative):
                    findings.append(
                        PreflightFinding("DS-PST-001", "Chemin artefact non portable", relative)
                    )
                    continue
                target = root / relative
                if not target.is_file():
                    findings.append(
                        PreflightFinding("DS-VAL-001", "Artefact acquis absent", relative)
                    )
                elif _sha(target) != artifact["sha256"]:
                    findings.append(
                        PreflightFinding(
                            "DS-VAL-001", "Hash de l'artefact acquis invalide", relative
                        )
                    )
                elif target.stat().st_size != artifact["size_bytes"]:
                    findings.append(
                        PreflightFinding(
                            "DS-VAL-001", "Taille de l'artefact acquise invalide", relative
                        )
                    )
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            findings.append(
                PreflightFinding("DS-VAL-001", str(exc), "manifests/acquired_source_bundle.json")
            )

    declared = {str(item["path"]) for item in checkpoint["artifacts"]}
    for directory in (
        "request",
        "manifests",
        "execution",
        "native",
        "ir",
        "mapping",
        "quality",
        "rendered",
    ):
        base = root / directory
        if not base.exists():
            continue
        for candidate in base.rglob("*.json"):
            relative = candidate.relative_to(root).as_posix()
            if relative == "execution/checkpoint_manifest.json":
                continue
            try:
                candidate_value = _load(candidate)
            except (OSError, json.JSONDecodeError):
                continue
            if "header" in candidate_value and relative not in declared:
                findings.append(
                    PreflightFinding(
                        "DS-VAL-001", "Contrat JSON non déclaré dans le checkpoint", relative
                    )
                )

    if (root / "PREFLIGHT_COMPLETE").is_file():
        required = {"DS00", "DS01", "DS02", "DS03", "DS04", "DS05", "DS06"}
        if not required.issubset(set(checkpoint["completed_nodes"])):
            findings.append(
                PreflightFinding(
                    "DS-VAL-001", "Marqueur complet avec étapes incomplètes", "PREFLIGHT_COMPLETE"
                )
            )
    if (root / "NATIVE_COMPLETE").is_file():
        required_native = {f"DS{index:02d}" for index in range(10)}
        if not required_native.issubset(set(checkpoint["completed_nodes"])):
            findings.append(
                PreflightFinding(
                    "DS-VAL-001", "Marqueur natif avec étapes incomplètes", "NATIVE_COMPLETE"
                )
            )
    if (root / "IR_COMPLETE").is_file():
        required_ir = {f"DS{index:02d}" for index in range(11)}
        if not required_ir.issubset(set(checkpoint["completed_nodes"])):
            findings.append(
                PreflightFinding("DS-VAL-001", "Marqueur IR avec étapes incomplètes", "IR_COMPLETE")
            )
    if (root / "RENDERING_COMPLETE").is_file():
        required_rendering = {f"DS{index:02d}" for index in range(12)}
        if not required_rendering.issubset(set(checkpoint["completed_nodes"])):
            findings.append(
                PreflightFinding(
                    "DS-VAL-001",
                    "Marqueur rendu avec étapes incomplètes",
                    "RENDERING_COMPLETE",
                )
            )
    if (root / "MAPPING_COMPLETE").is_file():
        required_mapping = {f"DS{index:02d}" for index in range(13)}
        if not required_mapping.issubset(set(checkpoint["completed_nodes"])):
            findings.append(
                PreflightFinding(
                    "DS-VAL-001", "Marqueur mapping avec étapes incomplètes", "MAPPING_COMPLETE"
                )
            )
    if (root / "QUALITY_COMPLETE").is_file():
        required_quality = {f"DS{index:02d}" for index in range(14)}
        if not required_quality.issubset(set(checkpoint["completed_nodes"])):
            findings.append(
                PreflightFinding(
                    "DS-VAL-001", "Marqueur qualité avec étapes incomplètes", "QUALITY_COMPLETE"
                )
            )
    if (root / "VALIDATION_COMPLETE").is_file():
        required_validation = {f"DS{index:02d}" for index in range(15)}
        if not required_validation.issubset(set(checkpoint["completed_nodes"])):
            findings.append(
                PreflightFinding(
                    "DS-VAL-001",
                    "Marqueur validation avec étapes incomplètes",
                    "VALIDATION_COMPLETE",
                )
            )
        validation_path = root / "validation/validation_report.json"
        if not validation_path.is_file():
            findings.append(
                PreflightFinding(
                    "DS-VAL-001",
                    "ValidationReport absent malgré VALIDATION_COMPLETE",
                    "validation/validation_report.json",
                )
            )
    return tuple(findings)
