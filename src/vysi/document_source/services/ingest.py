from __future__ import annotations

import os
import shutil
from pathlib import Path

from vysi.common.hashing import sha256_file
from vysi.common.ids import new_id, safe_name
from vysi.document_source.adapters.containers.ole import inventory_ole
from vysi.document_source.adapters.containers.ooxml import inventory_ooxml
from vysi.document_source.adapters.native.docx_reader import read_docx
from vysi.document_source.adapters.native.opaque_reader import read_opaque
from vysi.document_source.adapters.native.pptx_reader import read_pptx
from vysi.document_source.adapters.native.text_reader import read_text
from vysi.document_source.adapters.native.xlsx_reader import read_xlsx
from vysi.document_source.adapters.probe import probe
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import (
    ContainerPartCatalog,
    DocumentEnvelope,
    RenderedViewCatalog,
    SourceArtifact,
)
from vysi.document_source.domain.enums import DocumentFamily, FinalStatus
from vysi.document_source.pipeline.common_ir import project_common_ir
from vysi.document_source.pipeline.quality import build_quality_reports
from vysi.document_source.pipeline.resources import build_resources
from vysi.document_source.pipeline.security import assess_security
from vysi.document_source.serialization.json_store import write_contract


def _empty_catalog(kind: str) -> ContainerPartCatalog:
    return ContainerPartCatalog(
        header=header("document_source.container_part_catalog"),
        container_kind=kind,
        parts=(),
        relationships=(),
    )


def ingest(source: Path, output_root: Path) -> Path:
    source = source.resolve(strict=True)
    output_root.mkdir(parents=True, exist_ok=True)
    run_id = new_id("run")
    temp_root = output_root / f".{run_id}.tmp"
    final_root = output_root / run_id
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True)
    try:
        original_dir = temp_root / "original"
        original_dir.mkdir()
        original_name = safe_name(source.name)
        stored = original_dir / original_name
        shutil.copy2(source, stored)
        document_id = new_id("document")
        artifact = SourceArtifact(
            header=header("document_source.source_artifact"),
            artifact_id=new_id("artifact"),
            original_name=source.name,
            stored_path=f"original/{original_name}",
            size_bytes=stored.stat().st_size,
            sha256=sha256_file(stored),
            media_type="application/octet-stream",
            declared_extension=source.suffix.lower(),
        )
        artifact_ref = write_contract(temp_root, "contracts/source_artifact.json", artifact)

        descriptor, capabilities, _ = probe(stored)
        capability_ref = write_contract(
            temp_root, "contracts/capability_manifest.json", capabilities
        )
        descriptor = descriptor.__class__(
            **{**descriptor.__dict__, "capability_ref": capability_ref}
        )
        format_ref = write_contract(temp_root, "contracts/format_descriptor.json", descriptor)

        if descriptor.container_kind == "ooxml_zip":
            container = inventory_ooxml(stored)
        elif descriptor.container_kind == "ole_cfb":
            container, _ = inventory_ole(stored)
        else:
            container = _empty_catalog(descriptor.container_kind)
        container_ref = write_contract(
            temp_root, "contracts/container_part_catalog.json", container
        )

        if descriptor.format_name == "txt":
            native = read_text(stored)
        elif descriptor.format_name == "docx":
            native = read_docx(stored)
        elif descriptor.format_name == "xlsx":
            native = read_xlsx(stored)
        elif descriptor.format_name == "pptx":
            native = read_pptx(stored)
        elif descriptor.format_name in {"doc", "xls", "ppt"}:
            native = read_opaque(
                stored,
                descriptor.family,
                "legacy_ole.partial.v1",
                "structure binaire OLE conservée, décodage sémantique partiel",
            )
        elif descriptor.family == DocumentFamily.FIXED_LAYOUT:
            native = read_opaque(
                stored,
                descriptor.family,
                "fixed_layout.placeholder.v1",
                "migration contrôlée PDF depuis docs_parser_v2 en attente",
            )
        elif descriptor.family == DocumentFamily.RASTER:
            native = read_opaque(
                stored,
                descriptor.family,
                "raster.placeholder.v1",
                "migration contrôlée images depuis docs_parser_v2 en attente",
            )
        else:
            native = read_opaque(
                stored, descriptor.family, "unknown.placeholder.v1", "format non pris en charge"
            )
        native_ref = write_contract(temp_root, "contracts/native_document.json", native)

        common_ir, mapping = project_common_ir(native)
        common_ref = write_contract(temp_root, "contracts/common_document_ir.json", common_ir)
        mapping_ref = write_contract(
            temp_root, "contracts/representation_mapping_catalog.json", mapping
        )

        resources = build_resources(container, document_id)
        resources_ref = write_contract(
            temp_root, "contracts/native_resource_catalog.json", resources
        )

        rendered = RenderedViewCatalog(
            header=header("document_source.rendered_view_catalog"),
            requested=False,
            renderer=None,
            renderer_version=None,
            views=(),
            surfaces=(),
            warnings=("aucun rendu demandé; la structure native reste canonique",),
        )
        rendered_ref = write_contract(temp_root, "contracts/rendered_view_catalog.json", rendered)

        security = assess_security(container)
        security_ref = write_contract(temp_root, "contracts/security_report.json", security)
        coverage, preservation = build_quality_reports(native, container, len(common_ir.units))
        coverage_ref = write_contract(temp_root, "contracts/feature_coverage_report.json", coverage)
        preservation_ref = write_contract(
            temp_root, "contracts/preservation_report.json", preservation
        )

        warnings = tuple(capabilities.limitations) + tuple(
            issue.description
            for issue in preservation.issues
            if issue.severity.value in {"warning", "error", "critical"}
        )
        status = (
            FinalStatus.REVIEW
            if warnings or security.final_status == FinalStatus.REVIEW
            else FinalStatus.OK
        )
        envelope = DocumentEnvelope(
            header=header("document_source.document_envelope", "2.0.0"),
            document_id=document_id,
            source_artifact_ref=artifact_ref,
            format_descriptor_ref=format_ref,
            capability_manifest_ref=capability_ref,
            container_catalog_ref=container_ref,
            native_document_ref=native_ref,
            common_ir_ref=common_ref,
            rendered_views_ref=rendered_ref,
            representation_mapping_ref=mapping_ref,
            native_resources_ref=resources_ref,
            feature_coverage_ref=coverage_ref,
            preservation_report_ref=preservation_ref,
            security_report_ref=security_ref,
            final_status=status,
            warnings=warnings,
        )
        write_contract(temp_root, "document_envelope.json", envelope)
        _validate_package(temp_root)
        (temp_root / "COMMITTED").write_text(f"{run_id}\n", encoding="utf-8")
        os.replace(temp_root, final_root)
        return final_root
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise


def _validate_package(root: Path) -> None:
    required = [
        "document_envelope.json",
        "contracts/source_artifact.json",
        "contracts/format_descriptor.json",
        "contracts/capability_manifest.json",
        "contracts/container_part_catalog.json",
        "contracts/native_document.json",
        "contracts/common_document_ir.json",
        "contracts/rendered_view_catalog.json",
        "contracts/representation_mapping_catalog.json",
        "contracts/native_resource_catalog.json",
        "contracts/feature_coverage_report.json",
        "contracts/preservation_report.json",
        "contracts/security_report.json",
    ]
    missing = [relative for relative in required if not (root / relative).is_file()]
    if missing:
        raise RuntimeError(f"package incomplet: {missing}")
