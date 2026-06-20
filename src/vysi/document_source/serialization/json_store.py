from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from vysi.common.canonical import to_primitive
from vysi.common.hashing import sha256_file
from vysi.document_source.contracts.models import HashedReference


def write_contract(root: Path, relative: str, value: Any) -> HashedReference:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(to_primitive(value), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.replace(path)
    header = value.header
    return HashedReference(
        path=relative,
        sha256=sha256_file(path),
        schema_id=header.schema_id,
        contract_id=header.contract_id,
    )
