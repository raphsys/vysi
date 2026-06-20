from __future__ import annotations

from vysi.common.ids import new_id
from vysi.common.time import utc_now
from vysi.document_source.contracts.models import ContractHeader


def header(schema_id: str, version: str = "1.0.0") -> ContractHeader:
    return ContractHeader(
        schema_id=schema_id,
        schema_version=version,
        contract_id=new_id("contract"),
        created_at=utc_now(),
    )
