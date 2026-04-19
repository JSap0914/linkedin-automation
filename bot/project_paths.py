from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    override = os.environ.get("LINKEDIN_AUTOREPLY_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parent.parent


def venv_python(root: Path | None = None) -> Path:
    base = root or repo_root()
    if os.name == "nt":
        return base / ".venv" / "Scripts" / "python.exe"
    return base / ".venv" / "bin" / "python"
