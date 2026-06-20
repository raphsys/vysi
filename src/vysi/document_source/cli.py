from __future__ import annotations

import argparse
import json
from pathlib import Path

from vysi.document_source.contracts_v2.canonical import content_hash
from vysi.document_source.contracts_v2.identities import stable_id
from vysi.document_source.execution.contracts import make_contract
from vysi.document_source.execution.coordinator import (
    run_ir,
    run_mapping,
    run_native,
    run_preflight,
    run_quality,
)
from vysi.document_source.services.ingest import ingest


def _default_request(source: Path) -> dict[str, object]:
    resolved = source.expanduser().resolve(strict=False)
    locator_id = stable_id("locator", {"path": str(resolved)})
    body: dict[str, object] = {
        "request_id": stable_id("request", {"source": str(resolved)}),
        "sources": [
            {
                "locator_id": locator_id,
                "kind": "directory" if resolved.is_dir() else "local_file",
                "role": "primary",
                "uri": str(resolved),
                "display_name": resolved.name,
            }
        ],
        "selection": {"mode": "all", "selectors": []},
        "ingestion_policy": {"allow_partial": False, "resume": True, "cache": "read_write"},
        "security_policy": {
            "network": "deny",
            "active_content": "inventory_only",
            "embedded_documents": "inventory_only",
            "external_references": "inventory_only",
            "encryption": "allow_with_secret_ref",
        },
        "resource_budget": {
            "max_source_bytes": 2_147_483_648,
            "max_decompressed_bytes": 8_589_934_592,
            "max_parts": 100_000,
            "max_memory_bytes": 2_147_483_648,
            "max_cpu_seconds": 300,
            "max_wall_seconds": 1800,
            "max_temp_bytes": 8_589_934_592,
            "max_child_depth": 4,
        },
        "rendering_policy": {"mode": "none", "profiles": []},
        "preservation_policy": {
            "preserve_original": True,
            "preserve_unknown_parts": True,
            "extract_native_resources": True,
        },
        "strictness_policy": {
            "mode": "balanced",
            "major_loss_action": "review",
            "minor_loss_action": "allow",
        },
        "correlation": {},
    }
    return make_contract(
        "source_ingestion_request",
        body,
        producer_version="0.6.1",
        contract_seed={"source": str(resolved)},
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vysi")
    sub = parser.add_subparsers(dest="command", required=True)
    ingest_parser = sub.add_parser("ingest", help="Prototype 0.1 compatibility pipeline")
    ingest_parser.add_argument("source", type=Path)
    ingest_parser.add_argument(
        "--output", type=Path, default=Path("runtime/results/document_source")
    )

    preflight = sub.add_parser("preflight", help="Run DOCUMENT_SOURCE DS00-DS06")
    source_group = preflight.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", type=Path)
    source_group.add_argument("--request", type=Path)
    preflight.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    preflight.add_argument("--cancel-file", type=Path)
    preflight.add_argument("--resume-from", type=Path)

    native = sub.add_parser("native", help="Run DOCUMENT_SOURCE DS00-DS09")
    native_source_group = native.add_mutually_exclusive_group(required=True)
    native_source_group.add_argument("--source", type=Path)
    native_source_group.add_argument("--request", type=Path)
    native.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    native.add_argument("--cancel-file", type=Path)
    native.add_argument("--resume-from", type=Path)

    ir = sub.add_parser("ir", help="Run DOCUMENT_SOURCE DS00-DS10")
    ir_source_group = ir.add_mutually_exclusive_group(required=True)
    ir_source_group.add_argument("--source", type=Path)
    ir_source_group.add_argument("--request", type=Path)
    ir.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    ir.add_argument("--cancel-file", type=Path)
    ir.add_argument("--resume-from", type=Path)

    mapping = sub.add_parser("mapping", help="Run DOCUMENT_SOURCE DS00-DS10 and DS12")
    mapping_source_group = mapping.add_mutually_exclusive_group(required=True)
    mapping_source_group.add_argument("--source", type=Path)
    mapping_source_group.add_argument("--request", type=Path)
    mapping.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    mapping.add_argument("--cancel-file", type=Path)
    mapping.add_argument("--resume-from", type=Path)

    quality = sub.add_parser("quality", help="Run DOCUMENT_SOURCE DS00-DS10, DS12-DS13")
    quality_source_group = quality.add_mutually_exclusive_group(required=True)
    quality_source_group.add_argument("--source", type=Path)
    quality_source_group.add_argument("--request", type=Path)
    quality.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    quality.add_argument("--cancel-file", type=Path)
    quality.add_argument("--resume-from", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "ingest":
        package = ingest(args.source, args.output)
        print(package)
        return 0
    if args.command in {"preflight", "native", "ir", "mapping", "quality"}:
        if args.request is not None:
            request = json.loads(args.request.read_text(encoding="utf-8"))
        else:
            request = _default_request(args.source)
        # Recompute in case a caller edited a generated request without updating its identity.
        request["header"]["content_hash"] = content_hash(request)
        runner = {
            "preflight": run_preflight,
            "native": run_native,
            "ir": run_ir,
            "mapping": run_mapping,
            "quality": run_quality,
        }[args.command]
        result = runner(
            request, args.output, cancel_file=args.cancel_file, resume_from=args.resume_from
        )
        print(result.workspace)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
