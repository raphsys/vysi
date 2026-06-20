from __future__ import annotations

import json
from pathlib import Path

from vysi.document_source.services.ingest import ingest


def test_text_ingestion(tmp_path: Path) -> None:
    source = tmp_path / "note.txt"
    source.write_text("Ligne 1\nLigne 2\n", encoding="utf-8")
    package = ingest(source, tmp_path / "out")
    assert (package / "COMMITTED").is_file()
    native = json.loads((package / "contracts/native_document.json").read_text())
    assert native["profile"] == "plain_text.v1"
    assert native["profile_data"]["line_count"] == 2
    envelope = json.loads((package / "document_envelope.json").read_text())
    assert envelope["final_status"] == "ok"
