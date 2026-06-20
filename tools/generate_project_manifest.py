from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

EXCLUDED_DIR_NAMES = {
    ".git",
    ".vysi",
    ".vysi_test",
    ".auditvenv",
    ".venv",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
}
EXCLUDED_FILE_NAMES = {
    "PROJECT_MANIFEST.json",
    "ESSENTIAL_SNAPSHOT_INFO.txt",
    "ESSENTIAL_SNAPSHOT_SHA256SUMS.txt",
    ".coverage",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
    ".log",
    ".tmp",
    ".temp",
    ".swp",
    ".swo",
    ".zip",
    ".tgz",
    ".gz",
    ".tar",
    ".7z",
    ".rar",
}


def _is_runtime_generated(relative: Path) -> bool:
    parts = relative.parts
    if not parts or parts[0] != "runtime":
        return False
    return relative.name != ".gitkeep"


def iter_project_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_DIR_NAMES or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.name in EXCLUDED_FILE_NAMES:
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        if _is_runtime_generated(relative):
            continue
        yield path


def build_manifest(root: Path, version: str, revision: str) -> dict[str, object]:
    files: list[dict[str, object]] = []
    for path in iter_project_files(root):
        payload = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    return {
        "schema": "vysi.project_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "project_name": "vysi",
        "project_version": version,
        "delivery_revision": revision,
        "file_count": len(files),
        "files": files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the immutable Vysi project manifest")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--version", required=True)
    parser.add_argument("--revision", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    manifest = build_manifest(root, args.version, args.revision)
    target = root / "PROJECT_MANIFEST.json"
    target.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest régénéré : {manifest['file_count']} fichiers déclarés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
