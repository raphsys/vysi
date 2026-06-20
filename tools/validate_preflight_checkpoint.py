from __future__ import annotations

import argparse
from pathlib import Path

from vysi.document_source.execution.preflight_validation import validate_preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()
    findings = validate_preflight(args.checkpoint.resolve())
    if findings:
        for finding in findings:
            print(f"{finding.code}: {finding.message} [{finding.path or '-'}]")
        return 1
    scope = (
        "DS00–DS14"
        if (args.checkpoint / "VALIDATION_COMPLETE").is_file()
        else "DS00–DS13"
        if (args.checkpoint / "QUALITY_COMPLETE").is_file()
        else "DS00–DS12"
        if (args.checkpoint / "MAPPING_COMPLETE").is_file()
        else "DS00–DS11"
        if (args.checkpoint / "RENDERING_COMPLETE").is_file()
        else "DS00–DS10"
        if (args.checkpoint / "IR_COMPLETE").is_file()
        else "DS00–DS09"
        if (args.checkpoint / "NATIVE_COMPLETE").is_file()
        else "DS00–DS06"
    )
    print(f"Checkpoint {scope} valide")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
