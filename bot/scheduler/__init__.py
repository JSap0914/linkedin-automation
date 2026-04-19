from __future__ import annotations

import sys

from bot.scheduler.base import (
    Scheduler,
    SchedulerStatus,
    UnsupportedPlatformError,
    UnsupportedPlatformScheduler,
)

__all__ = [
    "Scheduler",
    "SchedulerStatus",
    "UnsupportedPlatformError",
    "UnsupportedPlatformScheduler",
    "get_scheduler",
]


def get_scheduler() -> Scheduler:
    if sys.platform == "darwin":
        from bot.scheduler.macos import MacOSScheduler
        return MacOSScheduler()
    if sys.platform.startswith("win"):
        from bot.scheduler.windows import WindowsScheduler
        return WindowsScheduler()
    return UnsupportedPlatformScheduler()
