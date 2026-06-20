from __future__ import annotations

from pathlib import Path
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.contracts import make_contract


def request_for(path: Path, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "request_id": stable_id("request", {"path": str(path)}),
        "sources": [
            {
                "locator_id": stable_id("locator", {"path": str(path)}),
                "kind": "local_file",
                "role": "primary",
                "uri": str(path),
                "display_name": path.name,
            }
        ],
        "selection": {"mode": "all", "selectors": []},
        "ingestion_policy": {"allow_partial": False, "resume": True, "cache": "read_write"},
        "security_policy": {
            "network": "deny",
            "active_content": "inventory_only",
            "embedded_documents": "inventory_only",
            "external_references": "inventory_only",
            "encryption": "allow_with_secret_ref",
        },
        "resource_budget": {
            "max_source_bytes": 64 * 1024 * 1024,
            "max_decompressed_bytes": 256 * 1024 * 1024,
            "max_parts": 10_000,
            "max_memory_bytes": 256 * 1024 * 1024,
            "max_cpu_seconds": 60,
            "max_wall_seconds": 120,
            "max_temp_bytes": 256 * 1024 * 1024,
            "max_child_depth": 4,
        },
        "rendering_policy": {"mode": "none", "profiles": []},
        "preservation_policy": {
            "preserve_original": True,
            "preserve_unknown_parts": True,
            "extract_native_resources": True,
        },
        "strictness_policy": {
            "mode": "balanced",
            "major_loss_action": "review",
            "minor_loss_action": "allow",
        },
        "correlation": {},
    }
    for key, value in overrides.items():
        body[key] = value
    return make_contract("source_ingestion_request", body, producer_version="0.3.0")
