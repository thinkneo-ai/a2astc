"""
A2ASTC JSON Schemas (Section 15).

Validation schemas for team manifests, audit events, gate verdicts,
policy bindings, and agent records.
"""

import json
from pathlib import Path
from typing import Any, Dict

_SCHEMA_DIR = Path(__file__).parent


def load_schema(name: str) -> Dict[str, Any]:
    """Load a JSON schema by name.

    Args:
        name: Schema name without extension (e.g., "team-manifest").

    Returns:
        Parsed JSON schema as a dictionary.
    """
    path = _SCHEMA_DIR / f"{name}.schema.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_available_schemas() -> list[str]:
    """List all available schema names."""
    return [
        p.stem.replace(".schema", "")
        for p in _SCHEMA_DIR.glob("*.schema.json")
    ]
