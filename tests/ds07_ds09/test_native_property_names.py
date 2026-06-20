from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from ds00_ds06.helpers import request_for

from vysi.document_source.contracts_v2.property_names import canonical_property_name
from vysi.document_source.execution.coordinator import run_mapping, run_quality

PROPERTY_NAME_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,200}$")


def _make_realistic_docx(path: Path) -> None:
    content_types = """<?xml version='1.0' encoding='UTF-8'?>
<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>
  <Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/>
  <Override PartName='/word/styles.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml'/>
  <Override PartName='/word/header1.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml'/>
  <Override PartName='/docProps/core.xml' ContentType='application/vnd.openxmlformats-package.core-properties+xml'/>
</Types>"""
    document = """<w:document
 xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
 xmlns:r='http://schemas.openxmlformats.org/officeDocument/2006/relationships'>
 <w:body>
  <w:p>
   <w:pPr>
    <w:keepNext/><w:keepLines/><w:pageBreakBefore/><w:widowControl/>
    <w:wordWrap/><w:overflowPunct/><w:topLinePunct/><w:autoSpaceDE/>
    <w:autoSpaceDN/><w:adjustRightInd/><w:snapToGrid/>
    <w:textAlignment w:val='center'/><w:rPr/>
   </w:pPr>
   <w:r>
    <w:rPr><w:rFonts w:ascii='Arial'/><w:bCs/><w:szCs w:val='24'/></w:rPr>
    <w:t>Certificat médical</w:t>
   </w:r>
  </w:p>
  <w:sectPr>
   <w:headerReference w:type='default' r:id='rId1'/>
   <w:pgSz w:w='11906' w:h='16838'/>
   <w:pgMar w:top='1440' w:right='1440' w:bottom='1440' w:left='1440'/>
   <w:docGrid w:linePitch='360'/>
  </w:sectPr>
 </w:body>
</w:document>"""
    styles = """<w:styles xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>
 <w:style w:type='paragraph' w:styleId='Normal'>
  <w:name w:val='Normal'/>
  <w:pPr><w:keepNext/><w:textAlignment w:val='left'/></w:pPr>
  <w:rPr><w:rFonts w:ascii='Arial'/><w:szCs w:val='22'/></w:rPr>
 </w:style>
</w:styles>"""
    relationships = """<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>
 <Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/header' Target='header1.xml'/>
</Relationships>"""
    header = """<w:hdr xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'><w:p><w:r><w:t>En-tête</w:t></w:r></w:p></w:hdr>"""
    core = """<cp:coreProperties
 xmlns:cp='http://schemas.openxmlformats.org/package/2006/metadata/core-properties'
 xmlns:dc='http://purl.org/dc/elements/1.1/'
 xmlns:dcterms='http://purl.org/dc/terms/'>
 <dc:creator>Vysi Test</dc:creator>
 <dcterms:created>2026-06-20T00:00:00Z</dcterms:created>
</cp:coreProperties>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)
        archive.writestr("word/_rels/document.xml.rels", relationships)
        archive.writestr("word/header1.xml", header)
        archive.writestr("docProps/core.xml", core)


def _document_dir(workspace: Path) -> Path:
    return next(
        path
        for path in (workspace / "native").iterdir()
        if path.is_dir() and path.name.startswith("document_")
    )


def _all_properties(workspace: Path) -> list[dict[str, object]]:
    document_dir = _document_dir(workspace)
    profile = json.loads((document_dir / "profile.json").read_text(encoding="utf-8"))
    styles = json.loads((document_dir / "styles.json").read_text(encoding="utf-8"))
    properties: list[dict[str, object]] = []
    for section in profile["sections"]:
        properties.extend(section["properties"])
    for block in profile["blocks"]:
        properties.extend(block["properties"])
    for style in styles["styles"]:
        properties.extend(style["direct_properties"])
        properties.extend(style["resolved_properties"])
    return properties


def test_native_property_name_canonicalization_examples() -> None:
    assert canonical_property_name("paragraph.keepNext") == "paragraph.keep_next"
    assert canonical_property_name("run.rFonts") == "run.r_fonts"
    assert canonical_property_name("run.bCs") == "run.b_cs"
    assert canonical_property_name("run.szCs") == "run.sz_cs"
    assert canonical_property_name("section.headerReference") == "section.header_reference"
    assert canonical_property_name("section.pgSz") == "section.pg_sz"
    assert canonical_property_name(
        "cell_xf.{http://schemas.openxmlformats.org/spreadsheetml/2006/main}numFmtId"
    ) == "cell_xf.num_fmt_id"


def test_realistic_docx_camel_case_properties_reach_ds12_and_ds13(tmp_path: Path) -> None:
    source = tmp_path / "realistic.docx"
    _make_realistic_docx(source)

    mapping = run_mapping(request_for(source), tmp_path / "mapping")
    mapping_properties = _all_properties(mapping.workspace)
    mapping_names = [str(item["name"]) for item in mapping_properties]
    assert mapping_names
    assert all(PROPERTY_NAME_RE.fullmatch(name) for name in mapping_names)
    assert {
        "paragraph.keep_next",
        "paragraph.page_break_before",
        "paragraph.text_alignment",
        "run.r_fonts",
        "run.b_cs",
        "run.sz_cs",
        "section.header_reference",
        "section.pg_sz",
        "section.pg_mar",
        "section.doc_grid",
    } <= set(mapping_names)
    assert any(
        item["name"] == "paragraph.keep_next"
        and "/keepNext[" in str(item["source_address"])
        for item in mapping_properties
    )
    assert any(
        item["name"] == "run.r_fonts" and "/rFonts[" in str(item["source_address"])
        for item in mapping_properties
    )
    assert (mapping.workspace / "MAPPING_COMPLETE").is_file()

    quality = run_quality(request_for(source), tmp_path / "quality")
    assert (quality.workspace / "QUALITY_COMPLETE").is_file()
