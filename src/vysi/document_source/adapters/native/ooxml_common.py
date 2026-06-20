from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from vysi.common.ids import stable_id

REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def attr_local(element: ET.Element, name: str) -> str | None:
    for key, value in element.attrib.items():
        if local(key) == name:
            return value
    return None


def attr_ns(element: ET.Element, namespace: str, name: str) -> str | None:
    return element.attrib.get(f"{{{namespace}}}{name}")


def read_xml(archive: zipfile.ZipFile, name: str) -> ET.Element:
    return ET.fromstring(archive.read(name))


def relationship_map(archive: zipfile.ZipFile, source_part: str) -> dict[str, str]:
    directory = posixpath.dirname(source_part)
    basename = posixpath.basename(source_part)
    rels = posixpath.join(directory, "_rels", basename + ".rels")
    if rels not in archive.namelist():
        return {}
    root = read_xml(archive, rels)
    result: dict[str, str] = {}
    for item in root.findall(f"{{{REL_NS}}}Relationship"):
        rid = item.attrib.get("Id")
        target = item.attrib.get("Target")
        if rid and target and item.attrib.get("TargetMode", "Internal") != "External":
            result[rid] = posixpath.normpath(posixpath.join(directory, target)).lstrip("/")
    return result


def unit_id(path: Path, *parts: object) -> str:
    return stable_id("native", path.name, *parts)
