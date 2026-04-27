# pyright: reportMissingImports=false

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bot.scheduler import macos as macos_module
from bot.scheduler.macos import MacOSScheduler, TEMPLATE_PATH


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def fake_run(monkeypatch):
    calls: list[list[str]] = []

    def _run(args, *, check=True):
        calls.append(list(args))
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(macos_module, "_run", _run)
    return calls


def test_install_renders_plist_with_project_root_and_python_path(fake_home, fake_run, tmp_path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    python_path = project_root / ".venv" / "bin" / "python3"
    sched = MacOSScheduler()
    sched.install(project_root=project_root, python_path=python_path)

    dest = fake_home / "Library" / "LaunchAgents" / "com.user.linkedin-autoreply.plist"
    content = dest.read_text()
    assert str(project_root) in content
    assert str(python_path) in content
    assert "{{PROJECT_ROOT}}" not in content


def test_install_calls_launchctl_load(fake_home, fake_run, tmp_path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    python_path = project_root / ".venv" / "bin" / "python3"
    sched = MacOSScheduler()
    sched.install(project_root=project_root, python_path=python_path)

    load_calls = [c for c in fake_run if c[:2] == ["launchctl", "load"]]
    assert len(load_calls) == 1


def test_install_is_idempotent_unloads_before_load(fake_home, fake_run, tmp_path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    sched = MacOSScheduler()
    sched.install(project_root=project_root, python_path=project_root / "py")

    launchctl_calls = [c for c in fake_run if c[0] == "launchctl"]
    assert launchctl_calls[0][1] == "unload"
    assert launchctl_calls[1][1] == "load"


def test_uninstall_unloads_and_removes_plist(fake_home, fake_run, tmp_path):
    project_root = tmp_path / "proj"
    project_root.mkdir()
    sched = MacOSScheduler()
    sched.install(project_root=project_root, python_path=project_root / "py")

    dest = fake_home / "Library" / "LaunchAgents" / "com.user.linkedin-autoreply.plist"
    assert dest.exists()

    sched.uninstall()
    assert not dest.exists()


def test_status_parses_launchctl_list(fake_home, monkeypatch, tmp_path):
    project_root = tmp_path / "proj"
    project_root.mkdir()

    dest = fake_home / "Library" / "LaunchAgents" / "com.user.linkedin-autoreply.plist"
    dest.parent.mkdir(parents=True)
    dest.write_text("<stub/>")

    def _run(args, *, check=True):
        if args[:2] == ["launchctl", "list"]:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="12345\t0\tcom.user.linkedin-autoreply\n",
                stderr="",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(macos_module, "_run", _run)
    sched = MacOSScheduler()
    status = sched.status()
    assert status.installed is True
    assert status.enabled is True


def test_status_when_not_loaded(fake_home, monkeypatch, tmp_path):
    dest = fake_home / "Library" / "LaunchAgents" / "com.user.linkedin-autoreply.plist"
    dest.parent.mkdir(parents=True)
    dest.write_text("<stub/>")

    def _run(args, *, check=True):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(macos_module, "_run", _run)
    sched = MacOSScheduler()
    status = sched.status()
    assert status.installed is True
    assert status.enabled is False


def test_template_hash_is_stable():
    sched = MacOSScheduler()
    h1 = sched.template_hash()
    h2 = sched.template_hash()
    assert h1 == h2
    assert len(h1) == 64


def test_template_hash_reflects_template_file_content():
    sched = MacOSScheduler()
    import hashlib
    expected = hashlib.sha256(TEMPLATE_PATH.read_bytes()).hexdigest()
    assert sched.template_hash() == expected
