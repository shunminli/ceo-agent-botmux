from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


SCHEMA_ROOT = Path(__file__).resolve().parent.parent / "schemas"


@lru_cache(maxsize=None)
def load_schema(name: str) -> Dict[str, Any]:
    path = SCHEMA_ROOT / f"{name}.schema.json"
    if not path.exists():
        raise ValueError(f"unknown schema: {name}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate_required(name: str, payload: Dict[str, Any]) -> None:
    schema = load_schema(name)
    missing = [field for field in schema.get("required", []) if field not in payload]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{name} is missing required fields: {joined}")
