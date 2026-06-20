from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from vysi.document_source.contracts.factory import header


def test_contract_header_is_immutable() -> None:
    value = header("test")
    with pytest.raises(FrozenInstanceError):
        value.schema_id = "changed"  # type: ignore[misc]
