from __future__ import annotations

from pathlib import Path

from ds00_ds06.helpers import request_for

from vysi.document_source.execution.coordinator import run_rendering


def test_empty_text_preview_keeps_document_provenance(tmp_path: Path) -> None:
    source = tmp_path / "empty.txt"
    source.write_text("", encoding="utf-8")
    request = request_for(
        source,
        rendering_policy={"mode": "on_demand", "profiles": ["source_reference"]},
    )
    result = run_rendering(request, tmp_path / "out")
    rendered = next((result.workspace / "rendered").glob("document_*"))
    assert next((rendered / "assets").glob("*.svg")).is_file()
