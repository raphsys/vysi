from __future__ import annotations

import hashlib
import re
import unicodedata

_PROPERTY_NAME_RE = re.compile(r"^[a-z][a-z0-9_.:-]{1,200}$")
_XML_NAMESPACE_RE = re.compile(r"\{[^}]+\}")
_CAMEL_ACRONYM_RE = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_BOUNDARY_RE = re.compile(r"([a-z0-9])([A-Z])")
_INVALID_PROPERTY_CHAR_RE = re.compile(r"[^a-z0-9_.:-]+")


def canonical_property_name(name: str) -> str:
    """Return the portable contract identifier for a native property name.

    OOXML property names are case-sensitive and commonly use camelCase. Contract
    property bags deliberately use a closed lower-case ASCII namespace. The
    native spelling is not discarded: callers retain it in the source address.
    """
    if _PROPERTY_NAME_RE.fullmatch(name):
        return name

    normalized = unicodedata.normalize("NFKC", name)
    normalized = _XML_NAMESPACE_RE.sub("", normalized)
    normalized = _CAMEL_ACRONYM_RE.sub(r"\1_\2", normalized)
    normalized = _CAMEL_BOUNDARY_RE.sub(r"\1_\2", normalized)
    normalized = normalized.lower()
    normalized = _INVALID_PROPERTY_CHAR_RE.sub("_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_.:-")

    if not normalized or not normalized[0].isalpha():
        normalized = f"property_{normalized or 'unknown'}"
    if len(normalized) < 2:
        normalized = f"{normalized}_value"
    if len(normalized) > 201:
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
        normalized = f"{normalized[:188].rstrip('_.:-')}_{digest}"

    if not _PROPERTY_NAME_RE.fullmatch(normalized):
        raise ValueError(f"Unable to canonicalize native property name: {name!r}")
    return normalized
