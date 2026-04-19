from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from bot.config import RepliesConfig
from bot.config_defaults import default_config_dict


def _walk(d: Any, prefix: str = "") -> list[str]:
    out: list[str] = []
    if not isinstance(d, dict):
        return out
    for key, val in d.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(val, dict):
            sub = _walk(val, path)
            if sub:
                out.extend(sub)
            else:
                out.append(path)
        else:
            out.append(path)
    return out


def detect_drift(current: dict) -> dict[str, list[str]]:
    defaults = default_config_dict()
    defaults_paths = set(_walk(defaults))
    current_paths = set(_walk(current))
    return {
        "added": sorted(defaults_paths - current_paths),
        "removed": sorted(current_paths - defaults_paths),
    }


class MigrationError(ValueError):
    pass


def _get(d: dict, path: str, default: Any = None) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _set(d: dict, path: str, value: Any) -> None:
    cur: Any = d
    parts = path.split(".")
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def _del(d: dict, path: str) -> None:
    cur: Any = d
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return
        cur = cur[part]
    if isinstance(cur, dict):
        cur.pop(parts[-1], None)


def migrate(current: dict) -> tuple[dict, list[str], list[str]]:
    defaults = default_config_dict()
    drift = detect_drift(current)
    added = drift["added"]
    removed = drift["removed"]

    merged = deepcopy(current)

    for path in added:
        _set(merged, path, _get(defaults, path))

    for path in removed:
        _del(merged, path)

    try:
        RepliesConfig(**merged)
    except ValidationError as exc:
        raise MigrationError(f"Post-migration config is invalid:\n{exc}") from exc

    return merged, added, removed
