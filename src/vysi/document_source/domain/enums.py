from __future__ import annotations

from enum import Enum


class DocumentFamily(str, Enum):
    PLAIN_TEXT = "plain_text"
    WORDPROCESSING = "wordprocessing"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    FIXED_LAYOUT = "fixed_layout"
    RASTER = "raster"
    LEGACY_OLE = "legacy_ole"
    UNKNOWN = "unknown"


class LayoutNature(str, Enum):
    LINEAR = "linear"
    FLOW = "flow"
    GRID = "grid"
    SLIDE = "slide"
    FIXED = "fixed"
    RASTER = "raster"
    UNKNOWN = "unknown"


class FinalStatus(str, Enum):
    OK = "ok"
    REVIEW = "review"
    REJECTED = "rejected"
    ERROR = "error"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"
