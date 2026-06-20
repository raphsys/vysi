from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vysi.document_source.domain.enums import (
    DocumentFamily,
    FinalStatus,
    LayoutNature,
    Severity,
)


@dataclass(frozen=True)
class ContractHeader:
    schema_id: str
    schema_version: str
    contract_id: str
    created_at: str
    producer: str = "vysi.document_source"


@dataclass(frozen=True)
class HashedReference:
    path: str
    sha256: str
    schema_id: str
    contract_id: str


@dataclass(frozen=True)
class SourceArtifact:
    header: ContractHeader
    artifact_id: str
    original_name: str
    stored_path: str
    size_bytes: int
    sha256: str
    media_type: str
    declared_extension: str


@dataclass(frozen=True)
class CapabilityManifest:
    header: ContractHeader
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class FormatDescriptor:
    header: ContractHeader
    format_name: str
    family: DocumentFamily
    layout_nature: LayoutNature
    container_kind: str
    media_type: str
    version: str | None
    confidence: float
    evidence: tuple[str, ...]
    capability_ref: HashedReference | None = None


@dataclass(frozen=True)
class ContainerPart:
    part_id: str
    path: str
    media_type: str
    size_bytes: int
    sha256: str | None
    compression: str | None
    relationship_ids: tuple[str, ...] = ()
    security_flags: tuple[str, ...] = ()
    opaque: bool = False
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ContainerRelationship:
    relationship_id: str
    source_part_id: str | None
    relationship_type: str
    target: str
    target_mode: str
    external: bool


@dataclass(frozen=True)
class ContainerPartCatalog:
    header: ContractHeader
    container_kind: str
    parts: tuple[ContainerPart, ...]
    relationships: tuple[ContainerRelationship, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class NativeNode:
    unit_id: str
    kind: str
    parent_id: str | None
    ordinal: int
    address: str
    layer: str = "content"
    text: str | None = None
    style_refs: tuple[str, ...] = ()
    resource_refs: tuple[str, ...] = ()
    relationship_refs: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeDocument:
    header: ContractHeader
    profile: str
    family: DocumentFamily
    root_ids: tuple[str, ...]
    nodes: tuple[NativeNode, ...]
    profile_data: dict[str, Any]
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class CommonUnit:
    unit_id: str
    kind: str
    source_native_ids: tuple[str, ...]
    parent_id: str | None
    ordinal: int
    text: str | None = None
    protected: bool = False
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommonDocumentIR:
    header: ContractHeader
    root_ids: tuple[str, ...]
    units: tuple[CommonUnit, ...]


@dataclass(frozen=True)
class MappingEdge:
    mapping_id: str
    source_layer: str
    source_id: str
    target_layer: str
    target_id: str
    relation: str
    confidence: float
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True)
class RepresentationMappingCatalog:
    header: ContractHeader
    mappings: tuple[MappingEdge, ...]


@dataclass(frozen=True)
class RenderedSurface:
    surface_id: str
    view_id: str
    surface_kind: str
    ordinal: int
    width: float | None
    height: float | None
    native_unit_refs: tuple[str, ...]
    asset_refs: tuple[str, ...] = ()
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderedViewCatalog:
    header: ContractHeader
    requested: bool
    renderer: str | None
    renderer_version: str | None
    views: tuple[dict[str, Any], ...]
    surfaces: tuple[RenderedSurface, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class NativeResource:
    resource_id: str
    kind: str
    owner_type: str
    owner_id: str
    native_reference: str
    media_type: str | None
    size_bytes: int | None
    sha256: str | None
    stored_path: str | None
    active: bool = False
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NativeResourceCatalog:
    header: ContractHeader
    resources: tuple[NativeResource, ...]


@dataclass(frozen=True)
class CoverageItem:
    feature: str
    encountered_count: int
    extracted_count: int
    preserved_count: int
    normalized_count: int
    rendered_count: int
    unsupported_count: int
    omitted_count: int
    severity: Severity
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeatureCoverageReport:
    header: ContractHeader
    items: tuple[CoverageItem, ...]
    coverage_ratio: float


@dataclass(frozen=True)
class PreservationIssue:
    stage: str
    feature: str
    issue_kind: str
    severity: Severity
    description: str
    source_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreservationReport:
    header: ContractHeader
    issues: tuple[PreservationIssue, ...]
    opaque_parts_preserved: int
    roundtrip_risk: str


@dataclass(frozen=True)
class SecurityFinding:
    code: str
    severity: Severity
    description: str
    source_ref: str
    inert: bool


@dataclass(frozen=True)
class SecurityReport:
    header: ContractHeader
    findings: tuple[SecurityFinding, ...]
    external_access_performed: bool
    active_content_executed: bool
    final_status: FinalStatus


@dataclass(frozen=True)
class DocumentEnvelope:
    header: ContractHeader
    document_id: str
    source_artifact_ref: HashedReference
    format_descriptor_ref: HashedReference
    capability_manifest_ref: HashedReference
    container_catalog_ref: HashedReference
    native_document_ref: HashedReference
    common_ir_ref: HashedReference
    rendered_views_ref: HashedReference
    representation_mapping_ref: HashedReference
    native_resources_ref: HashedReference
    feature_coverage_ref: HashedReference
    preservation_report_ref: HashedReference
    security_report_ref: HashedReference
    final_status: FinalStatus
    warnings: tuple[str, ...] = ()
