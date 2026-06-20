from __future__ import annotations

import struct
import zipfile
from pathlib import Path
from typing import Any

from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.context import ExecutionContext
from vysi.document_source.execution.contracts import make_contract, validate_and_write
from vysi.document_source.execution.errors import StageFailure

OLE_MAGIC = bytes.fromhex("D0CF11E0A1B11AE1")


def _text_confidence(sample: bytes) -> tuple[float, list[str]]:
    if not sample:
        return 1.0, ["empty byte sequence accepted as plain text"]
    bom_encodings = (
        (b"\xef\xbb\xbf", "utf-8-sig"),
        (b"\xff\xfe\x00\x00", "utf-32"),
        (b"\x00\x00\xfe\xff", "utf-32"),
        (b"\xff\xfe", "utf-16"),
        (b"\xfe\xff", "utf-16"),
    )
    for bom, encoding in bom_encodings:
        if sample.startswith(bom):
            try:
                decoded = sample.decode(encoding)
            except UnicodeError:
                return 0.0, [f"invalid {encoding} byte sequence"]
            controls = sum(ord(ch) < 32 and ch not in "\t\n\r\f" for ch in decoded)
            ratio = controls / max(len(decoded), 1)
            return (0.98 if ratio <= 0.01 else 0.0), [
                f"valid {encoding}",
                f"control_ratio={ratio:.4f}",
            ]
    try:
        decoded = sample.decode("utf-8")
    except UnicodeError:
        decoded = ""
    if decoded:
        controls = sum(ord(ch) < 32 and ch not in "\t\n\r\f" for ch in decoded)
        ratio = controls / max(len(decoded), 1)
        if ratio <= 0.01:
            return 0.98, ["valid utf-8", f"control_ratio={ratio:.4f}"]
    if b"\x00" in sample:
        even_nuls = sample[0::2].count(0) / max(len(sample[0::2]), 1)
        odd_nuls = sample[1::2].count(0) / max(len(sample[1::2]), 1)
        if max(even_nuls, odd_nuls) >= 0.6 and min(even_nuls, odd_nuls) <= 0.2:
            for encoding in ("utf-16le", "utf-16be"):
                try:
                    decoded = sample.decode(encoding)
                except UnicodeError:
                    continue
                controls = sum(ord(ch) < 32 and ch not in "\t\n\r\f" for ch in decoded)
                ratio = controls / max(len(decoded), 1)
                if ratio <= 0.01:
                    return 0.85, [f"heuristic {encoding}", f"control_ratio={ratio:.4f}"]
        return 0.0, ["NUL byte pattern inconsistent with text"]
    decoded = sample.decode("latin-1")
    printable = sum(ch.isprintable() or ch in "\t\n\r\f" for ch in decoded)
    ratio = printable / max(len(decoded), 1)
    return (0.70 if ratio >= 0.95 else 0.0), [f"latin1_printable_ratio={ratio:.4f}"]


def _zip_profile(path: Path) -> tuple[str, str, str, str, list[str]]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise StageFailure(
            "DS-PRB-001", "DS03", path.name, "Conteneur ZIP invalide", str(exc)
        ) from exc
    evidence = ["ZIP signature"]
    if "[Content_Types].xml" in names:
        evidence.append("[Content_Types].xml")
    if "word/document.xml" in names:
        return (
            "docx",
            "wordprocessing",
            "flow",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            evidence + ["word/document.xml"],
        )
    if "xl/workbook.xml" in names:
        return (
            "xlsx",
            "spreadsheet",
            "grid",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            evidence + ["xl/workbook.xml"],
        )
    if "ppt/presentation.xml" in names:
        return (
            "pptx",
            "presentation",
            "slide",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            evidence + ["ppt/presentation.xml"],
        )
    return "zip", "unknown", "unknown", "application/zip", evidence


def _probe(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        sample = handle.read(256 * 1024)
    extension = path.suffix.lower().lstrip(".")
    evidence: list[str] = []
    format_version: str | None = None
    if sample.startswith(b"%PDF-"):
        format_name, family, layout, container, media = (
            "pdf",
            "fixed_layout",
            "fixed",
            "pdf",
            "application/pdf",
        )
        version = sample[5:8].decode("ascii", "replace")
        format_version = version
        evidence = [f"PDF signature {version}"]
    elif (
        sample.startswith(b"PK\x03\x04")
        or sample.startswith(b"PK\x05\x06")
        or sample.startswith(b"PK\x07\x08")
    ):
        format_name, family, layout, media, evidence = _zip_profile(path)
        container = "ooxml_zip" if format_name in {"docx", "xlsx", "pptx"} else "zip"
        format_version = "ECMA-376" if container == "ooxml_zip" else None
    elif sample.startswith(OLE_MAGIC):
        format_name, family, layout, container, media = (
            "ole",
            "legacy_ole",
            "unknown",
            "ole_cfb",
            "application/x-ole-storage",
        )
        evidence = ["OLE Compound File signature"]
    elif sample.startswith(b"\x89PNG\r\n\x1a\n"):
        format_name, family, layout, container, media = (
            "png",
            "raster",
            "raster",
            "image",
            "image/png",
        )
        evidence = ["PNG signature"]
    elif sample.startswith(b"\xff\xd8\xff"):
        format_name, family, layout, container, media = (
            "jpeg",
            "raster",
            "raster",
            "image",
            "image/jpeg",
        )
        evidence = ["JPEG signature"]
    elif sample.startswith((b"GIF87a", b"GIF89a")):
        format_name, family, layout, container, media = (
            "gif",
            "raster",
            "raster",
            "image",
            "image/gif",
        )
        evidence = ["GIF signature"]
    elif sample.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")):
        format_name, family, layout, container, media = (
            "tiff",
            "raster",
            "raster",
            "image",
            "image/tiff",
        )
        evidence = ["TIFF signature"]
    elif len(sample) >= 12 and sample[:4] == b"RIFF" and sample[8:12] == b"WEBP":
        format_name, family, layout, container, media = (
            "webp",
            "raster",
            "raster",
            "image",
            "image/webp",
        )
        evidence = ["RIFF/WEBP signature"]
    elif len(sample) >= 12 and sample[4:12] == b"jP  \r\n\x87\n":
        format_name, family, layout, container, media = (
            "jpeg2000",
            "raster",
            "raster",
            "image",
            "image/jp2",
        )
        evidence = ["JPEG 2000 signature"]
    elif sample.startswith(b"BM") and len(sample) >= 14:
        declared_size = struct.unpack_from("<I", sample, 2)[0]
        format_name, family, layout, container, media = (
            "bmp",
            "raster",
            "raster",
            "image",
            "image/bmp",
        )
        evidence = ["BMP signature", f"declared_size={declared_size}"]
    else:
        confidence, text_evidence = _text_confidence(sample)
        if confidence > 0:
            format_name, family, layout, container, media = (
                "txt",
                "plain_text",
                "linear",
                "raw_bytes",
                "text/plain",
            )
            evidence = text_evidence
        else:
            format_name, family, layout, container, media = (
                "unknown_binary",
                "unknown",
                "unknown",
                "raw_bytes",
                "application/octet-stream",
            )
            evidence = text_evidence + ["no recognized magic signature"]
    expected_extensions: dict[str, set[str]] = {
        "pdf": {"pdf"},
        "docx": {"docx", "docm"},
        "xlsx": {"xlsx", "xlsm"},
        "pptx": {"pptx", "pptm"},
        "png": {"png"},
        "jpeg": {"jpg", "jpeg", "jpe"},
        "gif": {"gif"},
        "tiff": {"tif", "tiff"},
        "webp": {"webp"},
        "jpeg2000": {"jp2", "j2k", "jpf"},
        "bmp": {"bmp"},
        "txt": {"txt", "md", "csv", "log"},
    }
    known_extensions = {item for values in expected_extensions.values() for item in values}
    extension_mismatch = bool(
        extension
        and (
            (
                format_name in expected_extensions
                and extension not in expected_extensions[format_name]
            )
            or (format_name not in expected_extensions and extension in known_extensions)
        )
    )
    capability = (
        "supported"
        if format_name
        in {
            "txt",
            "docx",
            "xlsx",
            "pptx",
            "pdf",
            "png",
            "jpeg",
            "gif",
            "tiff",
            "webp",
            "jpeg2000",
            "bmp",
        }
        else "partial"
    )
    limitations = [] if capability == "supported" else ["native decoder deferred or format unknown"]
    confidence = 1.0 if format_name != "txt" else _text_confidence(sample)[0]
    return {
        "format_name": format_name,
        "family": family,
        "layout_nature": layout,
        "container_kind": container,
        "media_type": media,
        **({"format_version": format_version} if format_version else {}),
        "confidence": confidence,
        "extension_mismatch": extension_mismatch,
        "evidence": evidence,
        "reader_candidates": [
            {
                "reader_id": f"vysi.{format_name}",
                "score": confidence,
                "capability_state": capability,
                "limitations": limitations,
            }
        ],
    }


def execute(ctx: ExecutionContext, bundle: dict[str, Any]) -> dict[str, Any]:
    ctx.check_cancelled("DS03")
    documents: list[dict[str, Any]] = []
    for artifact in bundle["artifacts"]:
        ctx.check_cancelled("DS03")
        path = ctx.workspace / artifact["stored_path"]
        probe = _probe(path)
        document_id = stable_id(
            "document", {"sha256": artifact["sha256"], "role": artifact["role"]}
        )
        documents.append(
            {"document_id": document_id, "artifact_ids": [artifact["artifact_id"]], **probe}
        )
    bundle_path = ctx.workspace / "manifests/acquired_source_bundle.json"
    bundle_ref = {
        "path": "manifests/acquired_source_bundle.json",
        "sha256": __import__("hashlib").sha256(bundle_path.read_bytes()).hexdigest(),
        "schema_id": bundle["header"]["schema_id"],
        "schema_version": bundle["header"]["schema_version"],
        "contract_id": bundle["header"]["contract_id"],
    }
    report = make_contract(
        "format_probe_report",
        {"bundle_ref": bundle_ref, "documents": documents},
        producer_version=ctx.producer_version,
    )
    _, report_ref = validate_and_write(
        ctx.workspace,
        "manifests/format_probe_report.json",
        "format_probe_report",
        report,
        ctx.schemas,
    )
    ctx.references.append(report_ref)
    ctx.completed_nodes.append("DS03")
    return report
