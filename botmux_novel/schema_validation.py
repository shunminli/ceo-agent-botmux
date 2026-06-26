from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "schemas"


@lru_cache(maxsize=None)
def load_schema(name: str) -> Dict[str, Any]:
    path = SCHEMA_ROOT / f"{name}.schema.json"
    if not path.exists():
        raise ValueError(f"unknown schema: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_required(name: str, payload: Dict[str, Any]) -> None:
    missing = missing_required_fields(name, payload)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{name} is missing required fields: {joined}")


def missing_required_fields(name: str, payload: Dict[str, Any]) -> List[str]:
    schema = load_schema(name)
    return collect_missing_required(schema=schema, value=payload, path="")


def collect_missing_required(*, schema: Dict[str, Any], value: Any, path: str) -> List[str]:
    if not isinstance(value, dict):
        return []
    missing: List[str] = []
    required = schema.get("required", [])
    properties = schema.get("properties", {})
    if not isinstance(required, list) or not isinstance(properties, dict):
        return missing

    for field in required:
        field_name = str(field)
        field_path = f"{path}.{field_name}" if path else field_name
        if field_name not in value:
            missing.append(field_path)
            continue
        field_schema = properties.get(field_name)
        if isinstance(field_schema, dict):
            missing.extend(collect_missing_required(schema=field_schema, value=value[field_name], path=field_path))
    return missing
