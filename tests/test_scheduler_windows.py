# pyright: reportMissingImports=false

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bot.scheduler import windows as windows_module
from bot.scheduler.windows import WindowsScheduler


@pytest.fixture
def fake_run(monkeypatch):
    calls: list[list[str]] = []
    queries: list[dict] = []

    def _run(args, *, check=True):
        calls.append(list(args))
        if args[:3] == ["schtasks.exe", "/Query", "/TN"]:
            preset = queries[0] if queries else {"rc": 1, "stdout": ""}
            return subprocess.CompletedProcess(
                args=args,
                returncode=preset["rc"],
                stdout=preset["stdout"],
                stderr="",
            )
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(windows_module, "_run", _run)
    return calls, queries


def test_install_invokes_schtasks_create_with_limited_run_level(fake_run, tmp_path):
    calls, _ = fake_run
    project_root = tmp_path / "proj"
    project_root.mkdir()
    python_path = project_root / ".venv" / "Scripts" / "python.exe"
    sched = WindowsScheduler()
    sched.install(project_root=project_root, python_path=python_path)

    create = [c for c in calls if c[:2] == ["schtasks.exe", "/Create"]]
    assert len(create) == 1
    assert "/RL" in create[0]
    rl_idx = create[0].index("/RL")
    assert create[0][rl_idx + 1] == "LIMITED"


def test_install_uses_per_minute_schedule(fake_run, tmp_path):
    calls, _ = fake_run
    project_root = tmp_path / "proj"
    project_root.mkdir()
    sched = WindowsScheduler()
    sched.install(project_root=project_root, python_path=project_root / "py")

    create = [c for c in calls if c[:2] == ["schtasks.exe", "/Create"]][0]
    sc_idx = create.index("/SC")
    assert create[sc_idx + 1] == "MINUTE"
    mo_idx = create.index("/MO")
    assert create[mo_idx + 1] == "1"


def test_install_embeds_python_and_bot_py_in_action(fake_run, tmp_path):
    calls, _ = fake_run
    project_root = tmp_path / "proj"
    project_root.mkdir()
    python_path = project_root / ".venv" / "Scripts" / "python.exe"
    sched = WindowsScheduler()
    sched.install(project_root=project_root, python_path=python_path)

    create = [c for c in calls if c[:2] == ["schtasks.exe", "/Create"]][0]
    tr_idx = create.index("/TR")
    action = create[tr_idx + 1]
    assert str(python_path) in action
    assert "bot.py" in action
    assert "cmd.exe /d /c" in action
    assert "cd /d" in action


def test_install_forces_overwrite(fake_run, tmp_path):
    calls, _ = fake_run
    project_root = tmp_path / "proj"
    project_root.mkdir()
    sched = WindowsScheduler()
    sched.install(project_root=project_root, python_path=project_root / "py")

    create = [c for c in calls if c[:2] == ["schtasks.exe", "/Create"]][0]
    assert "/F" in create


def test_uninstall_invokes_schtasks_delete_only_if_installed(fake_run):
    calls, queries = fake_run
    queries.append({
        "rc": 0,
        "stdout": (
            "HostName: PC\nTaskName: \\LinkedInAutoReply\n"
            "Scheduled Task State: Enabled\nLast Run Time: N/A\nStatus: Ready\n"
        ),
    })
    sched = WindowsScheduler()
    sched.uninstall()

    delete = [c for c in calls if c[:2] == ["schtasks.exe", "/Delete"]]
    assert len(delete) == 1


def test_uninstall_noop_when_task_missing(fake_run):
    calls, queries = fake_run
    queries.append({"rc": 1, "stdout": ""})
    sched = WindowsScheduler()
    sched.uninstall()

    delete = [c for c in calls if c[:2] == ["schtasks.exe", "/Delete"]]
    assert len(delete) == 0


def test_enable_invokes_schtasks_change_enable(fake_run):
    calls, _ = fake_run
    sched = WindowsScheduler()
    sched.enable()

    change = [c for c in calls if c[:2] == ["schtasks.exe", "/Change"]][0]
    assert "/ENABLE" in change


def test_disable_invokes_schtasks_change_disable(fake_run):
    calls, _ = fake_run
    sched = WindowsScheduler()
    sched.disable()

    change = [c for c in calls if c[:2] == ["schtasks.exe", "/Change"]][0]
    assert "/DISABLE" in change


def test_status_parses_schtasks_query_list_format(fake_run):
    _, queries = fake_run
    queries.append({
        "rc": 0,
        "stdout": (
            "HostName: PC\n"
            "TaskName: \\LinkedInAutoReply\n"
            "Scheduled Task State: Enabled\n"
            "Last Run Time: 4/20/2026 2:15:00 AM\n"
            "Status: Ready\n"
        ),
    })
    sched = WindowsScheduler()
    status = sched.status()
    assert status.installed is True
    assert status.enabled is True
    assert status.last_run is not None
    assert status.last_run.year == 2026


def test_status_when_disabled(fake_run):
    _, queries = fake_run
    queries.append({
        "rc": 0,
        "stdout": (
            "TaskName: \\LinkedInAutoReply\n"
            "Scheduled Task State: Disabled\n"
            "Last Run Time: N/A\n"
            "Status: Ready\n"
        ),
    })
    sched = WindowsScheduler()
    status = sched.status()
    assert status.installed is True
    assert status.enabled is False
    assert status.last_run is None


def test_status_when_not_installed(fake_run):
    _, queries = fake_run
    queries.append({"rc": 1, "stdout": ""})
    sched = WindowsScheduler()
    status = sched.status()
    assert status.installed is False
    assert status.enabled is False


def test_template_hash_is_stable():
    sched = WindowsScheduler()
    assert sched.template_hash() == sched.template_hash()
    assert len(sched.template_hash()) == 64
