from __future__ import annotations

import hashlib
import json
from typing import Any

_EPHEMERAL_HEADER_FIELDS = {"content_hash", "created_at"}


def canonical_payload(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for contract content identity."""
    normalized = _normalize(value)
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_payload(value)).hexdigest()


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            if key == "header" and isinstance(value[key], dict):
                result[key] = {
                    k: _normalize(v)
                    for k, v in sorted(value[key].items())
                    if k not in _EPHEMERAL_HEADER_FIELDS
                }
            else:
                result[key] = _normalize(value[key])
        return result
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, float):
        if not (value == value and abs(value) != float("inf")):
            raise ValueError("non-finite floats are forbidden")
        return value
    return value
