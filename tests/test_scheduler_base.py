# pyright: reportMissingImports=false

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from bot.scheduler import (
    UnsupportedPlatformError,
    UnsupportedPlatformScheduler,
    get_scheduler,
)
from bot.scheduler.base import Scheduler


def test_scheduler_has_standard_label_and_interval():
    assert Scheduler.LABEL == "com.user.linkedin-autoreply"
    assert Scheduler.INTERVAL_SECONDS == 60


def test_get_scheduler_returns_macos_on_darwin(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    from bot.scheduler.macos import MacOSScheduler
    sched = get_scheduler()
    assert isinstance(sched, MacOSScheduler)


def test_get_scheduler_returns_windows_on_win32(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    from bot.scheduler.windows import WindowsScheduler
    sched = get_scheduler()
    assert isinstance(sched, WindowsScheduler)


def test_get_scheduler_returns_unsupported_on_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    sched = get_scheduler()
    assert isinstance(sched, UnsupportedPlatformScheduler)


def test_unsupported_install_raises():
    sched = UnsupportedPlatformScheduler()
    with pytest.raises(UnsupportedPlatformError):
        sched.install(project_root=Path("/tmp"), python_path=Path("/tmp/py"))


def test_unsupported_uninstall_raises():
    sched = UnsupportedPlatformScheduler()
    with pytest.raises(UnsupportedPlatformError):
        sched.uninstall()


def test_unsupported_enable_disable_raise():
    sched = UnsupportedPlatformScheduler()
    with pytest.raises(UnsupportedPlatformError):
        sched.enable()
    with pytest.raises(UnsupportedPlatformError):
        sched.disable()


def test_unsupported_status_returns_not_installed():
    sched = UnsupportedPlatformScheduler()
    status = sched.status()
    assert status.installed is False
    assert status.enabled is False
    assert status.last_run is None
    assert "unsupported" in status.raw


def test_unsupported_template_hash_is_sentinel():
    sched = UnsupportedPlatformScheduler()
    assert sched.template_hash() == "unsupported"
