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
    run_rendering,
    run_validation,
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
        producer_version="0.8.1",
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

    rendering = sub.add_parser("render", help="Run DOCUMENT_SOURCE DS00-DS11")
    rendering_source_group = rendering.add_mutually_exclusive_group(required=True)
    rendering_source_group.add_argument("--source", type=Path)
    rendering_source_group.add_argument("--request", type=Path)
    rendering.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    rendering.add_argument("--cancel-file", type=Path)
    rendering.add_argument("--resume-from", type=Path)
    rendering.add_argument("--render-mode", choices=("on_demand", "required"), default="on_demand")
    rendering.add_argument(
        "--render-profile",
        action="append",
        choices=("source_reference", "technical_preview", "native_passthrough"),
        dest="render_profiles",
    )

    mapping = sub.add_parser(
        "mapping", help="Run DOCUMENT_SOURCE DS00-DS12 (DS11 evaluated by policy)"
    )
    mapping_source_group = mapping.add_mutually_exclusive_group(required=True)
    mapping_source_group.add_argument("--source", type=Path)
    mapping_source_group.add_argument("--request", type=Path)
    mapping.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    mapping.add_argument("--cancel-file", type=Path)
    mapping.add_argument("--resume-from", type=Path)
    mapping.add_argument("--render-mode", choices=("none", "on_demand", "required"), default="none")
    mapping.add_argument(
        "--render-profile",
        action="append",
        choices=("source_reference", "technical_preview", "native_passthrough"),
        dest="render_profiles",
    )

    quality = sub.add_parser(
        "quality", help="Run DOCUMENT_SOURCE DS00-DS13 (DS11 evaluated by policy)"
    )
    quality_source_group = quality.add_mutually_exclusive_group(required=True)
    quality_source_group.add_argument("--source", type=Path)
    quality_source_group.add_argument("--request", type=Path)
    quality.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    quality.add_argument("--cancel-file", type=Path)
    quality.add_argument("--resume-from", type=Path)
    quality.add_argument("--render-mode", choices=("none", "on_demand", "required"), default="none")
    quality.add_argument(
        "--render-profile",
        action="append",
        choices=("source_reference", "technical_preview", "native_passthrough"),
        dest="render_profiles",
    )

    validation = sub.add_parser(
        "validate", help="Run DOCUMENT_SOURCE DS00-DS12 (DS11 evaluated by policy)-DS14"
    )
    validation_source_group = validation.add_mutually_exclusive_group(required=True)
    validation_source_group.add_argument("--source", type=Path)
    validation_source_group.add_argument("--request", type=Path)
    validation.add_argument("--output", type=Path, default=Path("runtime/results/document_source"))
    validation.add_argument("--cancel-file", type=Path)
    validation.add_argument("--resume-from", type=Path)
    validation.add_argument(
        "--render-mode", choices=("none", "on_demand", "required"), default="none"
    )
    validation.add_argument(
        "--render-profile",
        action="append",
        choices=("source_reference", "technical_preview", "native_passthrough"),
        dest="render_profiles",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "ingest":
        package = ingest(args.source, args.output)
        print(package)
        return 0
    if args.command in {"preflight", "native", "ir", "render", "mapping", "quality", "validate"}:
        if args.request is not None:
            request = json.loads(args.request.read_text(encoding="utf-8"))
        else:
            request = _default_request(args.source)
        if args.command in {"render", "mapping", "quality", "validate"} and args.request is None:
            mode = args.render_mode
            profiles = [] if mode == "none" else (args.render_profiles or ["source_reference"])
            request["rendering_policy"] = {"mode": mode, "profiles": profiles}
        # Recompute in case a caller edited a generated request without updating its identity.
        request["header"]["content_hash"] = content_hash(request)
        runner = {
            "preflight": run_preflight,
            "native": run_native,
            "ir": run_ir,
            "render": run_rendering,
            "mapping": run_mapping,
            "quality": run_quality,
            "validate": run_validation,
        }[args.command]
        result = runner(
            request, args.output, cancel_file=args.cancel_file, resume_from=args.resume_from
        )
        print(result.workspace)
        if args.command == "validate" and result.state not in {"succeeded", "partial"}:
            return 2
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
