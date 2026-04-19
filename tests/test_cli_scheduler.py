# pyright: reportMissingImports=false

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from bot.cli import app
from bot.scheduler.base import SchedulerStatus, UnsupportedPlatformError

runner = CliRunner()


def _fake_status(
    *, installed: bool = True, enabled: bool = True, last_run: datetime | None = None
) -> SchedulerStatus:
    return SchedulerStatus(
        installed=installed,
        enabled=enabled,
        last_run=last_run,
        label="com.user.linkedin-autoreply",
        interval_seconds=60,
        raw="ok",
    )


@pytest.fixture
def fake_sched():
    sched = MagicMock()
    sched.status.return_value = _fake_status()
    with patch("bot.cli_commands.scheduler_cmd.get_scheduler", return_value=sched):
        yield sched


@pytest.fixture
def fake_status_sched():
    sched = MagicMock()
    sched.status.return_value = _fake_status()
    with patch("bot.cli_commands.status_cmd.get_scheduler", return_value=sched):
        yield sched


def test_start_installs_scheduler(fake_sched):
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0, result.stdout
    fake_sched.install.assert_called_once()


def test_start_on_unsupported_platform_exits_zero(fake_sched):
    fake_sched.install.side_effect = UnsupportedPlatformError("no scheduler here")
    result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    assert "no scheduler here" in result.stdout


def test_stop_calls_scheduler_disable_only(fake_sched):
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    fake_sched.disable.assert_called_once()
    fake_sched.uninstall.assert_not_called()


def test_stop_on_unsupported_platform(fake_sched):
    fake_sched.disable.side_effect = UnsupportedPlatformError("unsupported")
    result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0


def test_uninstall_calls_scheduler_uninstall(fake_sched):
    result = runner.invoke(app, ["uninstall"])
    assert result.exit_code == 0
    fake_sched.uninstall.assert_called_once()


def test_status_shows_scheduler_state(fake_status_sched, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "com.user.linkedin-autoreply" in result.stdout


def test_status_shows_log_tail_when_present(fake_status_sched, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "bot.log").write_text("line1\nline2\nline3\n")
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "line3" in result.stdout


def test_status_when_no_logs(fake_status_sched, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "No logs yet" in result.stdout


def test_logs_tail_respects_n(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logs = tmp_path / "logs"
    logs.mkdir()
    lines = "\n".join(f"line{i}" for i in range(1, 21)) + "\n"
    (logs / "bot.log").write_text(lines)

    result = runner.invoke(app, ["logs", "-n", "3"])
    assert result.exit_code == 0
    assert "line20" in result.stdout
    assert "line18" in result.stdout
    assert "line17" not in result.stdout


def test_logs_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["logs"])
    assert result.exit_code == 0
    assert "No logs yet" in result.stdout


def test_scheduler_cmd_does_not_import_subprocess_directly():
    import ast
    from pathlib import Path

    source = Path("bot/cli_commands/scheduler_cmd.py").read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name == "subprocess" for alias in node.names), (
                "scheduler_cmd must not import subprocess directly; route via bot.scheduler"
            )
        if isinstance(node, ast.ImportFrom):
            assert node.module != "subprocess", (
                "scheduler_cmd must not import from subprocess directly"
            )
