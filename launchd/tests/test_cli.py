# pyright: reportMissingImports=false

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from bot.cli import app

runner = CliRunner()


def test_cli_help_lists_all_subcommands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("init", "run", "setup", "update", "start", "stop", "uninstall", "status", "logs", "config"):
        assert cmd in result.stdout, f"Missing subcommand in help: {cmd}"


def test_cli_no_args_prints_help_and_exits_zero():
    result = runner.invoke(app, [])
    assert result.exit_code in (0, 2)
    assert "Usage" in result.stdout or "Usage" in (result.stderr or "")


def test_cli_unknown_subcommand_exits_non_zero():
    result = runner.invoke(app, ["nonexistent-command"])
    assert result.exit_code != 0


def test_cli_run_dry_run_routes_to_orchestrator():
    with patch("bot.orchestrator.run") as mock_run:
        result = runner.invoke(app, ["run", "--dry-run"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(dry_run=True, bootstrap=False)


def test_cli_run_bootstrap_routes_to_orchestrator():
    with patch("bot.orchestrator.run") as mock_run:
        result = runner.invoke(app, ["run", "--bootstrap"])
        assert result.exit_code == 0
        mock_run.assert_called_once_with(dry_run=False, bootstrap=True)


def test_cli_setup_routes_to_wizard():
    with patch("bot.cli_commands.setup_cmd.main") as mock_main:
        result = runner.invoke(app, ["setup"])
        assert result.exit_code == 0
        mock_main.assert_called_once()


def test_cli_config_subgroup_has_all_subcommands():
    result = runner.invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    for sub in ("show", "set", "edit", "wizard", "reset", "migrate"):
        assert sub in result.stdout


def test_cli_config_show_is_placeholder():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0


def test_cli_update_accepts_flags():
    with (
        patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value=""),
        patch("bot.cli_commands.update_cmd.updater.current_sha", return_value="abc"),
    ):
        result = runner.invoke(app, ["update", "--dry-run", "--skip-tests", "-y"])
        assert result.exit_code == 0


def test_cli_start_stop_uninstall_are_placeholders():
    for cmd in ("start", "stop", "uninstall"):
        result = runner.invoke(app, [cmd])
        assert result.exit_code == 0, f"{cmd} failed: {result.stdout}"


def test_cli_status_is_placeholder():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0


def test_cli_logs_accepts_n_flag():
    result = runner.invoke(app, ["logs", "-n", "10"])
    assert result.exit_code == 0
