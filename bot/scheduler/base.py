from __future__ import annotations

import abc
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


LABEL = "com.user.linkedin-autoreply"
INTERVAL_SECONDS = 60


@dataclass
class SchedulerStatus:
    installed: bool
    enabled: bool
    last_run: datetime | None
    label: str
    interval_seconds: int
    raw: str


class Scheduler(abc.ABC):
    LABEL = LABEL
    INTERVAL_SECONDS = INTERVAL_SECONDS

    @abc.abstractmethod
    def install(self, *, project_root: Path, python_path: Path) -> None: ...

    @abc.abstractmethod
    def uninstall(self) -> None: ...

    @abc.abstractmethod
    def enable(self) -> None: ...

    @abc.abstractmethod
    def disable(self) -> None: ...

    @abc.abstractmethod
    def status(self) -> SchedulerStatus: ...

    @abc.abstractmethod
    def template_hash(self) -> str: ...


class UnsupportedPlatformError(RuntimeError):
    pass


class UnsupportedPlatformScheduler(Scheduler):
    _MSG = (
        "Scheduled runs are not supported on this platform yet. "
        "Run `linkedin-autoreply run` from cron/systemd manually."
    )

    def install(self, *, project_root: Path, python_path: Path) -> None:
        raise UnsupportedPlatformError(self._MSG)

    def uninstall(self) -> None:
        raise UnsupportedPlatformError(self._MSG)

    def enable(self) -> None:
        raise UnsupportedPlatformError(self._MSG)

    def disable(self) -> None:
        raise UnsupportedPlatformError(self._MSG)

    def status(self) -> SchedulerStatus:
        return SchedulerStatus(
            installed=False,
            enabled=False,
            last_run=None,
            label=self.LABEL,
            interval_seconds=self.INTERVAL_SECONDS,
            raw="unsupported-platform",
        )

    def template_hash(self) -> str:
        return "unsupported"
