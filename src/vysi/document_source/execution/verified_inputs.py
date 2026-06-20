from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.errors import StageFailure


@dataclass
class VerifiedInputReader:
    """Load immutable, hash-checked contracts and detect input mutation."""

    ctx: ExecutionContext
    stage: str
    error_code: str
    _fingerprints: dict[Path, str] = field(default_factory=dict)

    def _failure(self, scope: str, message: str, details: str | None = None) -> StageFailure:
        return StageFailure(self.error_code, self.stage, scope, message, details or "")

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _track(self, path: Path) -> None:
        resolved = path.resolve()
        workspace = self.ctx.workspace.resolve()
        if workspace != resolved and workspace not in resolved.parents:
            raise self._failure(path.as_posix(), "Chemin d'entrée hors espace de travail")
        if path.is_symlink():
            raise self._failure(
                path.as_posix(), "Lien symbolique interdit pour un contrat d'entrée"
            )
        self._fingerprints[path] = self._sha256(path)

    def load_json(self, path: Path) -> dict[str, Any]:
        self.ctx.check_cancelled(self.stage)
        if not path.is_file():
            raise self._failure(path.as_posix(), "Fichier d'entrée absent")
        try:
            value = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError) as exc:
            raise self._failure(path.as_posix(), "JSON d'entrée illisible", str(exc)) from exc
        self._track(path)
        return value

    def contract(
        self,
        path: Path,
        schema_key: str,
        *,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        value = self.load_json(path)
        try:
            self.ctx.schemas.validate(schema_key, value)
        except Exception as exc:
            raise self._failure(
                path.as_posix(), f"Contrat {schema_key} invalide", str(exc)
            ) from exc
        header = value.get("header")
        if not isinstance(header, dict):
            raise self._failure(path.as_posix(), "En-tête contractuel absent")
        expected_schema_id = f"document_source.{schema_key}"
        if str(header.get("schema_id", "")) != expected_schema_id:
            raise self._failure(
                path.as_posix(), "schema_id incompatible", f"attendu={expected_schema_id}"
            )
        schema_version = str(header.get("schema_version", ""))
        if not schema_version.startswith("2."):
            raise self._failure(path.as_posix(), "Version majeure de contrat incompatible")
        observed = str(header.get("content_hash", ""))
        expected = content_hash(value)
        if observed != expected:
            raise self._failure(
                path.as_posix(),
                "Hash canonique invalide",
                f"attendu={expected} observé={observed}",
            )
        if document_id is not None and str(value.get("document_id", "")) != document_id:
            raise self._failure(path.as_posix(), "document_id incohérent")
        return value

    def referenced_contract(
        self,
        reference: dict[str, Any],
        schema_key: str,
        *,
        document_id: str | None = None,
    ) -> dict[str, Any]:
        relative = str(reference.get("path", ""))
        if not relative or relative.startswith("/") or ".." in Path(relative).parts:
            raise self._failure(relative or "reference", "Chemin de référence non portable")
        path = self.ctx.workspace / relative
        value = self.contract(path, schema_key, document_id=document_id)
        observed_file_hash = self._fingerprints[path]
        if observed_file_hash != str(reference.get("sha256", "")):
            raise self._failure(relative, "Hash de fichier référencé invalide")
        header = cast(dict[str, Any], value["header"])
        for key in ("schema_id", "schema_version", "contract_id"):
            if str(header.get(key, "")) != str(reference.get(key, "")):
                raise self._failure(relative, f"{key} référencé incohérent")
        return value

    def artifact_bytes(self, relative: str, expected_sha256: str) -> None:
        if not relative or relative.startswith("/") or ".." in Path(relative).parts:
            raise self._failure(relative or "artifact", "Chemin d'artefact non portable")
        path = self.ctx.workspace / relative
        self.ctx.check_cancelled(self.stage)
        if not path.is_file() or path.is_symlink():
            raise self._failure(relative, "Artefact binaire absent ou non régulier")
        observed = self._sha256(path)
        if observed != expected_sha256:
            raise self._failure(
                relative,
                "Hash SHA-256 de l'artefact invalide",
                f"attendu={expected_sha256} observé={observed}",
            )
        self._fingerprints[path] = observed

    def verify_unchanged(self) -> None:
        for path, expected in sorted(
            self._fingerprints.items(), key=lambda item: item[0].as_posix()
        ):
            if not path.is_file():
                raise self._failure(path.as_posix(), "Entrée supprimée pendant l'exécution")
            observed = self._sha256(path)
            if observed != expected:
                raise self._failure(
                    path.as_posix(),
                    "Mutation d'une entrée détectée",
                    f"avant={expected} après={observed}",
                )
