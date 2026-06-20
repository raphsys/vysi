from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.contracts_v2.validation import SchemaStore
from vysi.document_source.execution.time import utc_now

PRODUCER = "vysi.document_source"
SCHEMA_VERSION = "2.0.0"
SCHEMA_VERSIONS = {
    "normalized_source_request": "2.1.0",
    "acquired_source_bundle": "2.1.0",
    "profile_plain_text": "2.2.0",
    "profile_wordprocessing": "2.2.0",
    "profile_spreadsheet": "2.2.0",
    "profile_presentation": "2.2.0",
    "profile_fixed_layout": "2.2.0",
    "profile_raster": "2.2.0",
    "profile_legacy_ole": "2.2.0",
    "representation_mapping_catalog": "2.8.0",
    "feature_coverage_report": "2.8.0",
    "preservation_report": "2.8.0",
    "rendered_view_catalog": "2.8.0",
    "geometry_catalog": "2.8.0",
    "derived_asset_catalog": "2.8.0",
    "validation_report": "2.8.0",
}


def schema_id(schema_key: str) -> str:
    return f"document_source.{schema_key}"


def make_contract(
    schema_key: str,
    body: dict[str, Any],
    *,
    status: str = "ok",
    producer_version: str = "0.8.1",
    contract_seed: Any | None = None,
) -> dict[str, Any]:
    seed = body if contract_seed is None else contract_seed
    contract_id = stable_id(schema_key[:20], seed)
    contract: dict[str, Any] = {
        "header": {
            "schema_id": schema_id(schema_key),
            "schema_version": SCHEMA_VERSIONS.get(schema_key, SCHEMA_VERSION),
            "contract_id": contract_id,
            "content_hash": "0" * 64,
            "producer": PRODUCER,
            "producer_version": producer_version,
            "created_at": utc_now(),
            "status": status,
            "revision": 1,
            "supersedes": None,
            "extensions": {},
        },
        **body,
    }
    contract["header"]["content_hash"] = content_hash(contract)
    return contract


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def contract_reference(root: Path, path: Path, value: dict[str, Any]) -> dict[str, str]:
    return {
        "path": path.relative_to(root).as_posix(),
        "sha256": sha256_path(path),
        "schema_id": str(value["header"]["schema_id"]),
        "schema_version": str(value["header"]["schema_version"]),
        "contract_id": str(value["header"]["contract_id"]),
    }


def validate_and_write(
    root: Path,
    relative: str,
    schema_key: str,
    value: dict[str, Any],
    schemas: SchemaStore,
) -> tuple[Path, dict[str, str]]:
    schemas.validate(schema_key, value)
    path = root / relative
    write_json(path, value)
    return path, contract_reference(root, path, value)
