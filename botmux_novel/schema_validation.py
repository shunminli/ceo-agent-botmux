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


def validate_schema(name: str, payload: Dict[str, Any]) -> None:
    errors = schema_validation_errors(name, payload)
    if errors:
        joined = ", ".join(errors)
        raise ValueError(f"{name} schema validation failed: {joined}")


def schema_validation_errors(name: str, payload: Dict[str, Any]) -> List[str]:
    schema = load_schema(name)
    return collect_schema_errors(schema=schema, value=payload, path="")


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


def collect_schema_errors(*, schema: Dict[str, Any], value: Any, path: str) -> List[str]:
    errors: List[str] = []
    expected_type = schema.get("type")
    if expected_type is not None and not value_matches_type(value, expected_type):
        errors.append(f"{path or '$'} expected {format_expected_type(expected_type)}")
        return errors

    if isinstance(value, dict):
        errors.extend(
            f"Missing required field: {field}"
            for field in collect_missing_required(schema=schema, value=value, path=path)
        )
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            for field_name, field_schema in properties.items():
                if field_name in value and isinstance(field_schema, dict):
                    field_path = f"{path}.{field_name}" if path else field_name
                    errors.extend(collect_schema_errors(schema=field_schema, value=value[field_name], path=field_path))
    return errors


def value_matches_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(value_matches_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def format_expected_type(expected_type: Any) -> str:
    if isinstance(expected_type, list):
        return "|".join(str(item) for item in expected_type)
    return str(expected_type)
