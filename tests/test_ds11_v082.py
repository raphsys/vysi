from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ds00_ds06.helpers import request_for
from helpers import make_docx

from vysi.document_source.execution.coordinator import run_rendering
from vysi.document_source.rendering_v2 import (
    BuiltinReferenceRenderer,
    RendererCapability,
    select_renderer,
)
from vysi.document_source.rendering_v2.models import RenderOutput
