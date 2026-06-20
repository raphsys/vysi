from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure
from vysi.document_source.technical_ir_v2 import ProjectionError, project_document

_REQUIRED_NATIVE_FILES = {
    "native": ("native_document.json", "native_document"),
    "profile": ("profile.json", None),
    "styles": ("styles.json", "native_style_catalog"),
    "relationships": ("relationships.json", "native_relationship_catalog"),
    "metadata": ("metadata.json", "native_metadata_catalog"),
    "annotations": ("annotations.json", "native_annotation_catalog"),
    "resources": ("resources.json", "native_resource_catalog"),
}


def _load(path: Path) -> dict[str, Any]:
    try:
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise StageFailure(
            "DS-IR-001", "DS10", path.as_posix(), "Contrat natif illisible", str(exc)
        ) from exc


def _verify_content_hash(value: dict[str, Any], scope: str) -> None:
    header = value.get("header")
    if not isinstance(header, dict):
        raise StageFailure("DS-IR-001", "DS10", scope, "En-tête contractuel absent")
    observed = str(header.get("content_hash", ""))
    expected = content_hash(value)
    if observed != expected:
        raise StageFailure(
            "DS-IR-001",
            "DS10",
            scope,
            "Hash canonique du contrat natif invalide",
            f"attendu={expected} observé={observed}",
        )


def _verify_reference(
    ctx: ExecutionContext, reference: dict[str, Any], scope: str
) -> dict[str, Any]:
    relative = str(reference["path"])
    path = ctx.workspace / relative
    if not path.is_file():
        raise StageFailure("DS-IR-001", "DS10", scope, f"Référence absente: {relative}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != str(reference["sha256"]):
        raise StageFailure(
            "DS-IR-001",
            "DS10",
            scope,
            "Hash de fichier référencé invalide",
            f"{relative}: attendu={reference['sha256']} observé={digest}",
        )
    value = _load(path)
    if str(value.get("header", {}).get("contract_id", "")) != str(reference["contract_id"]):
        raise StageFailure("DS-IR-001", "DS10", scope, "contract_id référencé incohérent")
    if str(value.get("header", {}).get("schema_id", "")) != str(reference["schema_id"]):
        raise StageFailure("DS-IR-001", "DS10", scope, "schema_id référencé incohérent")
    _verify_content_hash(value, relative)
    return value


def _load_native_set(ctx: ExecutionContext, directory: Path) -> dict[str, dict[str, Any]]:
    loaded: dict[str, dict[str, Any]] = {}
    for key, (filename, schema_key) in _REQUIRED_NATIVE_FILES.items():
        path = directory / filename
        if not path.is_file():
            raise StageFailure(
                "DS-IR-001", "DS10", directory.name, f"Contrat natif obligatoire absent: {filename}"
            )
        value = _load(path)
        if schema_key is not None:
            ctx.schemas.validate(schema_key, value)
        _verify_content_hash(value, path.relative_to(ctx.workspace).as_posix())
        loaded[key] = value
    native = loaded["native"]
    profile_ref = cast(dict[str, Any], native["profile_ref"])
    referenced_profile = _verify_reference(ctx, profile_ref, directory.name)
    if referenced_profile != loaded["profile"]:
        raise StageFailure(
            "DS-IR-001", "DS10", directory.name, "Le profil publié diffère du profil référencé"
        )
    profile_schema_key = str(profile_ref["schema_id"]).removeprefix("document_source.")
    ctx.schemas.validate(profile_schema_key, loaded["profile"])
    document_id = str(native["document_id"])
    for key, value in loaded.items():
        if key == "native":
            continue
        if str(value.get("document_id", "")) != document_id:
            raise StageFailure(
                "DS-IR-001", "DS10", directory.name, f"Document incohérent dans {key}"
            )
    return loaded


def execute(ctx: ExecutionContext, policy: dict[str, Any]) -> list[dict[str, str]]:
    ctx.check_cancelled("DS10")
    native_root = ctx.workspace / "native"
    if not native_root.is_dir():
        raise StageFailure("DS-IR-001", "DS10", ctx.run_id, "Répertoire natif absent")
    document_directories = sorted(
        path
        for path in native_root.iterdir()
        if path.is_dir() and path.name.startswith("document_")
    )
    if not document_directories:
        raise StageFailure("DS-IR-001", "DS10", ctx.run_id, "Aucun document natif publié")

    allow_partial = bool(policy["ingestion_policy"]["allow_partial"])
    published: list[dict[str, str]] = []
    for directory in document_directories:
        ctx.check_cancelled("DS10")
        try:
            native_set = _load_native_set(ctx, directory)
            native = native_set["native"]
            document_id = str(native["document_id"])
            body, warnings = project_document(
                native,
                native_set["profile"],
                native_set["styles"],
                native_set["relationships"],
                native_set["metadata"],
                native_set["annotations"],
                native_set["resources"],
            )
            status = "review" if warnings or str(native["header"]["status"]) != "ok" else "ok"
            ir = make_contract(
                "technical_document_ir",
                body,
                status=status,
                producer_version=ctx.producer_version,
                contract_seed={
                    "document_id": document_id,
                    "profile_contract_id": native_set["profile"]["header"]["contract_id"],
                    "units": [unit["unit_id"] for unit in body["units"]],
                },
            )
            _, ref = validate_and_write(
                ctx.workspace,
                f"ir/{document_id}/technical_document_ir.json",
                "technical_document_ir",
                ir,
                ctx.schemas,
            )
            ctx.references.append(ref)
            published.append(ref)
            if warnings:
                warning_path = ctx.workspace / f"ir/{document_id}/projection_warnings.json"
                warning_path.write_text(
                    json.dumps(
                        {"document_id": document_id, "warnings": list(warnings)},
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                    + "\n",
                    encoding="utf-8",
                )
        except ProjectionError as exc:
            failure = StageFailure(
                "DS-IR-002", "DS10", directory.name, "Projection IR impossible", str(exc)
            )
            if not allow_partial:
                raise failure from exc
            ctx.errors.append(failure.to_record())
    if not published:
        raise StageFailure("DS-IR-002", "DS10", ctx.run_id, "Aucune projection IR publiable")
    ctx.completed_nodes.append("DS10")
    return published
