from __future__ import annotations

from pathlib import Path

from vysi.common.ids import stable_id
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import NativeDocument, NativeNode
from vysi.document_source.domain.enums import DocumentFamily


def read_opaque(path: Path, family: DocumentFamily, profile: str, reason: str) -> NativeDocument:
    root_id = stable_id("native", path.name, "opaque-root")
    return NativeDocument(
        header=header("document_source.native_document"),
        profile=profile,
        family=family,
        root_ids=(root_id,),
        nodes=(
            NativeNode(
                root_id,
                "opaque_document",
                None,
                0,
                "opaque:/",
                properties={"reason": reason},
            ),
        ),
        profile_data={"native_coverage": "partial", "reason": reason},
        capabilities=("preserve_original",),
    )
