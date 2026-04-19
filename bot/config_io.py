from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_PATH = Path("replies.yaml")


class ConfigIOError(ValueError):
    pass


def load_raw(path: Path = DEFAULT_PATH) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump_raw(data: dict, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            data,
            handle,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        )


_INT_RE = re.compile(r"^-?\d+$")
_FLOAT_RE = re.compile(r"^-?\d+\.\d+$")


def parse_value(raw: str) -> Any:
    stripped = raw.strip()
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    if stripped.lower() == "null" or stripped.lower() == "none":
        return None
    if _INT_RE.match(stripped):
        return int(stripped)
    if _FLOAT_RE.match(stripped):
        return float(stripped)
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ConfigIOError(f"Invalid JSON value: {raw!r}: {exc}") from exc
    return raw


def set_by_path(data: dict, dotted_path: str, value: Any) -> dict:
    if not dotted_path:
        raise ConfigIOError("Empty path")
    parts = dotted_path.split(".")
    cursor: Any = data
    for part in parts[:-1]:
        if not isinstance(cursor, dict):
            raise ConfigIOError(f"Path traverses non-dict at {part!r}")
        if part not in cursor or not isinstance(cursor[part], dict):
            cursor[part] = {}
        cursor = cursor[part]
    if not isinstance(cursor, dict):
        raise ConfigIOError(f"Cannot set on non-dict at {dotted_path!r}")
    cursor[parts[-1]] = value
    return data


def get_by_path(data: dict, dotted_path: str, default: Any = None) -> Any:
    cursor: Any = data
    for part in dotted_path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return default
        cursor = cursor[part]
    return cursor
