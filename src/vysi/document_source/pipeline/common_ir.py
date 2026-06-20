from __future__ import annotations

from vysi.common.ids import stable_id
from vysi.document_source.contracts.factory import header
from vysi.document_source.contracts.models import (
    CommonDocumentIR,
    CommonUnit,
    MappingEdge,
    NativeDocument,
    RepresentationMappingCatalog,
)

TEXTUAL_KINDS = {"text_line", "paragraph", "run", "table_cell", "cell", "shape"}
STRUCTURAL_KINDS = {
    "word_document",
    "workbook",
    "presentation",
    "worksheet",
    "slide",
    "table",
    "table_row",
}


def project_common_ir(
    native: NativeDocument,
) -> tuple[CommonDocumentIR, RepresentationMappingCatalog]:
    units: list[CommonUnit] = []
    mappings: list[MappingEdge] = []
    native_to_common: dict[str, str] = {}

    for node in native.nodes:
        if node.kind in STRUCTURAL_KINDS:
            kind = {
                "word_document": "document",
                "workbook": "document",
                "presentation": "document",
                "worksheet": "section",
                "slide": "section",
                "table": "table",
                "table_row": "table_row",
            }.get(node.kind, "structure")
        elif node.kind in TEXTUAL_KINDS:
            kind = {
                "cell": "table_cell",
                "shape": "text_block" if node.text else "visual_object",
                "run": "text_span",
                "text_line": "text_block",
                "paragraph": "text_block",
            }.get(node.kind, node.kind)
        else:
            continue
        unit_id = stable_id("ir", node.unit_id)
        native_to_common[node.unit_id] = unit_id
        parent_id = native_to_common.get(node.parent_id or "")
        formula = node.properties.get("formula")
        protected = bool(formula)
        properties = dict(node.properties)
        if formula:
            properties["formula_source"] = formula
            properties["calculation_executed"] = False
        units.append(
            CommonUnit(
                unit_id=unit_id,
                kind=kind,
                source_native_ids=(node.unit_id,),
                parent_id=parent_id,
                ordinal=node.ordinal,
                text=node.text,
                protected=protected,
                properties=properties,
            )
        )
        mappings.append(
            MappingEdge(
                mapping_id=stable_id("mapping", node.unit_id, unit_id),
                source_layer="native",
                source_id=node.unit_id,
                target_layer="common_ir",
                target_id=unit_id,
                relation="projected_as",
                confidence=1.0,
                evidence=(node.address,),
            )
        )

    roots = tuple(native_to_common[root] for root in native.root_ids if root in native_to_common)
    return (
        CommonDocumentIR(
            header=header("document_source.common_document_ir"),
            root_ids=roots,
            units=tuple(units),
        ),
        RepresentationMappingCatalog(
            header=header("document_source.representation_mapping_catalog"),
            mappings=tuple(mappings),
        ),
    )
