from __future__ import annotations

import base64
import hashlib
from typing import Any

from .canonical import canonical_payload


def stable_id(prefix: str, value: Any, length: int = 26) -> str:
    if not prefix or not prefix[0].isalpha():
        raise ValueError("prefix must start with a letter")
    digest = hashlib.sha256(canonical_payload(value)).digest()
    token = base64.b32encode(digest).decode("ascii").rstrip("=").lower()[:length]
    return f"{prefix}_{token}"
