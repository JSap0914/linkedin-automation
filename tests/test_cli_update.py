# pyright: reportMissingImports=false

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from bot.cli import app

runner = CliRunner()


def test_update_aborts_on_dirty_working_tree():
    with patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value="M bot/x.py"):
        result = runner.invoke(app, ["update"])
        assert result.exit_code == 1


def test_update_dry_run_does_no_pull():
    with (
        patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value=""),
        patch("bot.cli_commands.update_cmd.updater.current_sha", return_value="abc123"),
        patch("bot.cli_commands.update_cmd.updater.pull_ff_only") as mock_pull,
    ):
        result = runner.invoke(app, ["update", "--dry-run"])
        assert result.exit_code == 0
        mock_pull.assert_not_called()


def test_update_already_up_to_date_exits_zero():
    with (
        patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value=""),
        patch("bot.cli_commands.update_cmd.updater.current_sha", return_value="abc123"),
        patch("bot.cli_commands.update_cmd.updater.pull_ff_only"),
        patch("bot.cli_commands.update_cmd.updater.changed_paths_between", return_value=[]),
    ):
        result = runner.invoke(app, ["update"])
        assert result.exit_code == 0
        assert "Already up to date" in result.stdout


def test_update_runs_pip_on_pyproject_change():
    with (
        patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value=""),
        patch(
            "bot.cli_commands.update_cmd.updater.current_sha",
            side_effect=["abc", "def"],
        ),
        patch("bot.cli_commands.update_cmd.updater.pull_ff_only"),
        patch(
            "bot.cli_commands.update_cmd.updater.changed_paths_between",
            return_value=["pyproject.toml"],
        ),
        patch("bot.cli_commands.update_cmd.updater.pip_install_editable") as mock_pip,
        patch("bot.cli_commands.update_cmd.updater.run_pytest_smoke", return_value=True),
    ):
        result = runner.invoke(app, ["update", "--skip-tests"])
        assert result.exit_code == 0, result.stdout
        mock_pip.assert_called_once()


def test_update_skips_pip_when_pyproject_unchanged():
    with (
        patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value=""),
        patch(
            "bot.cli_commands.update_cmd.updater.current_sha",
            side_effect=["abc", "def"],
        ),
        patch("bot.cli_commands.update_cmd.updater.pull_ff_only"),
        patch(
            "bot.cli_commands.update_cmd.updater.changed_paths_between",
            return_value=["README.md"],
        ),
        patch("bot.cli_commands.update_cmd.updater.pip_install_editable") as mock_pip,
    ):
        result = runner.invoke(app, ["update", "--skip-tests"])
        assert result.exit_code == 0
        mock_pip.assert_not_called()


def test_update_reinstalls_scheduler_on_template_change(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with (
        patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value=""),
        patch(
            "bot.cli_commands.update_cmd.updater.current_sha",
            side_effect=["abc", "def"],
        ),
        patch("bot.cli_commands.update_cmd.updater.pull_ff_only"),
        patch(
            "bot.cli_commands.update_cmd.updater.changed_paths_between",
            return_value=["bot/scheduler/templates/linkedin_autoreply.plist.tmpl"],
        ),
        patch("bot.cli_commands.update_cmd._reinstall_scheduler", return_value=True) as mock_reinstall,
    ):
        result = runner.invoke(app, ["update", "--skip-tests"])
        assert result.exit_code == 0
        mock_reinstall.assert_called_once()


def test_update_skip_tests_skips_pytest():
    with (
        patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value=""),
        patch(
            "bot.cli_commands.update_cmd.updater.current_sha",
            side_effect=["abc", "def"],
        ),
        patch("bot.cli_commands.update_cmd.updater.pull_ff_only"),
        patch(
            "bot.cli_commands.update_cmd.updater.changed_paths_between",
            return_value=["README.md"],
        ),
        patch("bot.cli_commands.update_cmd.updater.run_pytest_smoke") as mock_test,
    ):
        result = runner.invoke(app, ["update", "--skip-tests"])
        assert result.exit_code == 0
        mock_test.assert_not_called()


def test_update_test_failure_exits_one():
    with (
        patch("bot.cli_commands.update_cmd.updater.is_dirty", return_value=""),
        patch(
            "bot.cli_commands.update_cmd.updater.current_sha",
            side_effect=["abc", "def"],
        ),
        patch("bot.cli_commands.update_cmd.updater.pull_ff_only"),
        patch(
            "bot.cli_commands.update_cmd.updater.changed_paths_between",
            return_value=["README.md"],
        ),
        patch("bot.cli_commands.update_cmd.updater.run_pytest_smoke", return_value=False),
    ):
        result = runner.invoke(app, ["update"])
        assert result.exit_code == 1
