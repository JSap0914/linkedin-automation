from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path

from bot.scheduler.base import Scheduler, SchedulerStatus

logger = logging.getLogger(__name__)

TASK_NAME = "LinkedInAutoReply"
SCHTASKS = "schtasks.exe"


def _run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    logger.debug("Running: %s", " ".join(args))
    return subprocess.run(args, check=check, capture_output=True, text=True)


def _query_raw() -> tuple[bool, str]:
    result = _run(
        [SCHTASKS, "/Query", "/TN", TASK_NAME, "/FO", "LIST", "/V"],
        check=False,
    )
    return result.returncode == 0, result.stdout


class WindowsScheduler(Scheduler):
    TASK_NAME = TASK_NAME

    def install(self, *, project_root: Path, python_path: Path) -> None:
        bot_py = project_root / "bot.py"
        cmd = f'"{python_path}" "{bot_py}"'
        (project_root / "logs").mkdir(parents=True, exist_ok=True)
        _run(
            [
                SCHTASKS,
                "/Create",
                "/SC", "MINUTE",
                "/MO", "1",
                "/TN", TASK_NAME,
                "/TR", cmd,
                "/RL", "LIMITED",
                "/F",
            ],
        )

    def uninstall(self) -> None:
        installed, _ = _query_raw()
        if installed:
            _run([SCHTASKS, "/Delete", "/TN", TASK_NAME, "/F"], check=False)

    def enable(self) -> None:
        _run([SCHTASKS, "/Change", "/TN", TASK_NAME, "/ENABLE"])

    def disable(self) -> None:
        _run([SCHTASKS, "/Change", "/TN", TASK_NAME, "/DISABLE"], check=False)

    def status(self) -> SchedulerStatus:
        installed, raw = _query_raw()
        enabled = False
        last_run: datetime | None = None
        if installed:
            scheduled_task_state = self._field(raw, "Scheduled Task State")
            status_text = self._field(raw, "Status")
            enabled = (scheduled_task_state or "").strip().lower() == "enabled"
            if status_text and status_text.strip().lower() == "disabled":
                enabled = False
            last_run = self._parse_last_run(raw)
        return SchedulerStatus(
            installed=installed,
            enabled=enabled,
            last_run=last_run,
            label=Scheduler.LABEL,
            interval_seconds=Scheduler.INTERVAL_SECONDS,
            raw=raw,
        )

    def _field(self, raw: str, key: str) -> str | None:
        pattern = re.compile(rf"^{re.escape(key)}:\s*(.+?)\s*$", re.MULTILINE)
        match = pattern.search(raw)
        return match.group(1) if match else None

    def _parse_last_run(self, raw: str) -> datetime | None:
        value = self._field(raw, "Last Run Time")
        if not value or value.strip().lower() in {"n/a", "never"}:
            return None
        for fmt in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value.strip(), fmt)
            except ValueError:
                continue
        return None

    def template_hash(self) -> str:
        key = f"{Scheduler.LABEL}|{Scheduler.INTERVAL_SECONDS}|schtasks|MINUTE|1|LIMITED"
        return hashlib.sha256(key.encode()).hexdigest()
