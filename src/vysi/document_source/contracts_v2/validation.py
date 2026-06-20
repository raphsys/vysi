from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource


@dataclass(frozen=True)
class ContractValidationError(Exception):
    schema_key: str
    messages: tuple[str, ...]

    def __str__(self) -> str:
        return f"{self.schema_key}: " + "; ".join(self.messages)


class SchemaStore:
    def __init__(self, schema_dir: Path) -> None:
        self.schema_dir = schema_dir
        registry_path = schema_dir / "SCHEMA_REGISTRY.json"
        registry_data = json.loads(registry_path.read_text(encoding="utf-8"))
        schemas: dict[str, dict[str, Any]] = {}
        registry = Registry()
        for key, meta in registry_data["schemas"].items():
            path = schema_dir / str(meta["path"])
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[key] = schema
            registry = registry.with_resource(str(schema["$id"]), Resource.from_contents(schema))
        self._schemas = schemas
        self._registry = registry

    @property
    def schema_keys(self) -> frozenset[str]:
        return frozenset(self._schemas)

    def validate(self, schema_key: str, instance: Any) -> None:
        schema = self._schemas[schema_key]
        validator = Draft202012Validator(
            schema, registry=self._registry, format_checker=FormatChecker()
        )
        errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.absolute_path))
        if errors:
            messages = tuple(
                f"/{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errors
            )
            raise ContractValidationError(schema_key, messages)

    def load_and_validate(self, schema_key: str, path: Path) -> Any:
        instance = json.loads(path.read_text(encoding="utf-8"))
        self.validate(schema_key, instance)
        return instance
