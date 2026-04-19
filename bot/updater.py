from __future__ import annotations

import hashlib
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class UpdateResult:
    pre_sha: str = ""
    post_sha: str = ""
    pulled: bool = False
    changed_files: list[str] = field(default_factory=list)
    pip_installed: bool = False
    config_migrated_added: list[str] = field(default_factory=list)
    config_migrated_removed: list[str] = field(default_factory=list)
    scheduler_reinstalled: bool = False
    tests_passed: bool | None = None
    dry_run: bool = False


class UpdateError(RuntimeError):
    pass


def _run(args: list[str], *, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args, check=check, capture_output=True, text=True, cwd=str(cwd) if cwd else None
    )


def is_dirty(cwd: Path | None = None) -> str:
    result = _run(["git", "status", "--porcelain"], cwd=cwd, check=False)
    return result.stdout.strip()


def current_sha(cwd: Path | None = None) -> str:
    result = _run(["git", "rev-parse", "HEAD"], cwd=cwd)
    return result.stdout.strip()


def changed_paths_between(old_sha: str, new_sha: str, cwd: Path | None = None) -> list[str]:
    if old_sha == new_sha:
        return []
    result = _run(
        ["git", "diff", "--name-only", old_sha, new_sha],
        cwd=cwd,
        check=False,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def pull_ff_only(cwd: Path | None = None) -> None:
    result = _run(
        ["git", "pull", "--ff-only", "origin", "main"],
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        raise UpdateError(
            f"git pull --ff-only failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


def pip_install_editable(cwd: Path | None = None) -> None:
    result = _run(
        [sys.executable, "-m", "pip", "install", "-e", ".[dev]"],
        cwd=cwd,
        check=False,
    )
    if result.returncode != 0:
        raise UpdateError(
            f"pip install failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


def run_pytest_smoke(cwd: Path | None = None) -> bool:
    result = _run(
        [sys.executable, "-m", "pytest", "-q", "-x", "tests/"],
        cwd=cwd,
        check=False,
    )
    return result.returncode == 0


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_PYPROJECT = "pyproject.toml"
_CONFIG_PY = "bot/config.py"
_CONFIG_DEFAULTS = "bot/config_defaults.py"
_SCHEDULER_TEMPLATES_PREFIX = "bot/scheduler/templates/"


def detect_drift(changed: list[str]) -> dict[str, bool]:
    return {
        "pyproject": _PYPROJECT in changed,
        "config_schema": _CONFIG_PY in changed or _CONFIG_DEFAULTS in changed,
        "scheduler_templates": any(p.startswith(_SCHEDULER_TEMPLATES_PREFIX) for p in changed),
    }
