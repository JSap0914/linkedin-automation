from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

from bot.scheduler.base import Scheduler, SchedulerStatus

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent / "templates" / "linkedin_autoreply.plist.tmpl"


def _launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _plist_dest() -> Path:
    return _launch_agents_dir() / f"{Scheduler.LABEL}.plist"


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    logger.debug("Running: %s", " ".join(args))
    return subprocess.run(args, check=check, capture_output=True, text=True)


class MacOSScheduler(Scheduler):
    def _render(self, *, project_root: Path, python_path: Path) -> str:
        template = TEMPLATE_PATH.read_text()
        rendered = template.replace("{{PROJECT_ROOT}}", str(project_root))
        rendered = rendered.replace(
            f"{project_root}/.venv/bin/python", str(python_path)
        )
        return rendered

    def install(self, *, project_root: Path, python_path: Path) -> None:
        dest = _plist_dest()
        dest.parent.mkdir(parents=True, exist_ok=True)
        (project_root / "logs").mkdir(parents=True, exist_ok=True)
        dest.write_text(self._render(project_root=project_root, python_path=python_path))
        self.enable()

    def uninstall(self) -> None:
        dest = _plist_dest()
        if dest.exists():
            self.disable()
            dest.unlink(missing_ok=True)

    def enable(self) -> None:
        dest = _plist_dest()
        if not dest.exists():
            raise FileNotFoundError(
                f"Plist not installed at {dest}. Run install() first."
            )
        _run(["launchctl", "unload", str(dest)], check=False)
        _run(["launchctl", "load", str(dest)])

    def disable(self) -> None:
        dest = _plist_dest()
        if dest.exists():
            _run(["launchctl", "unload", str(dest)], check=False)

    def status(self) -> SchedulerStatus:
        dest = _plist_dest()
        installed = dest.exists()
        result = _run(["launchctl", "list"], check=False)
        raw = result.stdout
        label_re = re.compile(rf"^\S+\s+\S+\s+{re.escape(Scheduler.LABEL)}\s*$", re.MULTILINE)
        enabled = bool(label_re.search(raw))
        last_run = self._last_run_from_logs()
        return SchedulerStatus(
            installed=installed,
            enabled=enabled,
            last_run=last_run,
            label=Scheduler.LABEL,
            interval_seconds=Scheduler.INTERVAL_SECONDS,
            raw=raw,
        )

    def _last_run_from_logs(self) -> datetime | None:
        log = Path("logs/bot.log")
        if not log.exists():
            return None
        try:
            mtime = log.stat().st_mtime
            return datetime.fromtimestamp(mtime)
        except OSError:
            return None

    def template_hash(self) -> str:
        return hashlib.sha256(TEMPLATE_PATH.read_bytes()).hexdigest()
