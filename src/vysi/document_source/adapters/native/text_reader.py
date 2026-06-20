from __future__ import annotations

from pathlib import Path

from vysi.common.ids import stable_id
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import NativeDocument, NativeNode
from vysi.document_source.domain.enums import DocumentFamily


def _decode(data: bytes) -> tuple[str, str, str | None]:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8"), "utf-8", "utf-8-sig"
    if data.startswith(b"\xff\xfe"):
        return data[2:].decode("utf-16le"), "utf-16le", "utf-16le-bom"
    if data.startswith(b"\xfe\xff"):
        return data[2:].decode("utf-16be"), "utf-16be", "utf-16be-bom"
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding), encoding, None
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replacement", None


def read_text(path: Path) -> NativeDocument:
    data = path.read_bytes()
    text, encoding, bom = _decode(data)
    newline = "mixed"
    if "\r\n" in text and text.count("\r\n") == text.count("\n"):
        newline = "crlf"
    elif "\r" in text and "\n" not in text:
        newline = "cr"
    elif "\n" in text:
        newline = "lf"
    root_id = stable_id("native", path.name, "root")
    nodes: list[NativeNode] = [
        NativeNode(
            unit_id=root_id,
            kind="text_document",
            parent_id=None,
            ordinal=0,
            address="text:/",
            properties={"encoding": encoding, "bom": bom, "newline": newline},
        )
    ]
    for index, line in enumerate(text.splitlines(keepends=True)):
        clean = line.rstrip("\r\n")
        nodes.append(
            NativeNode(
                unit_id=stable_id("native", path.name, "line", index),
                kind="text_line",
                parent_id=root_id,
                ordinal=index,
                address=f"text:/line[{index + 1}]",
                text=clean,
                properties={"terminator": line[len(clean) :]},
            )
        )
    return NativeDocument(
        header=header("document_source.native_document"),
        profile="plain_text.v1",
        family=DocumentFamily.PLAIN_TEXT,
        root_ids=(root_id,),
        nodes=tuple(nodes),
        profile_data={
            "encoding": encoding,
            "bom": bom,
            "newline": newline,
            "character_count": len(text),
            "line_count": max(0, len(nodes) - 1),
        },
        capabilities=("has_linear_text",),
    )
