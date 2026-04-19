# pyright: reportMissingImports=false

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from bot.cli import app
from bot.config_defaults import default_config_dict
from bot.config_io import load_raw

runner = CliRunner()


def test_config_reset_writes_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["config", "reset", "-y"])
    assert result.exit_code == 0, result.stdout
    data = load_raw(tmp_path / "replies.yaml")
    assert data == default_config_dict()


def test_config_reset_uses_config_defaults_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])
    written = load_raw(tmp_path / "replies.yaml")
    expected = default_config_dict()
    assert written == expected


def test_config_reset_refuses_non_tty_without_yes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "replies.yaml").write_text("enabled: true\n")
    result = runner.invoke(app, ["config", "reset"])
    assert result.exit_code == 1


def test_config_show_prints_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "enabled" in result.stdout
    assert "dm" in result.stdout


def test_config_show_errors_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 1


def test_config_set_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])

    result = runner.invoke(app, ["config", "set", "dm.max_per_day", "50"])
    assert result.exit_code == 0, result.stdout

    data = load_raw(tmp_path / "replies.yaml")
    assert data["dm"]["max_per_day"] == 50


def test_config_set_bool(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])

    result = runner.invoke(app, ["config", "set", "dm.enabled", "true"])
    assert result.exit_code == 0, result.stdout

    data = load_raw(tmp_path / "replies.yaml")
    assert data["dm"]["enabled"] is True


def test_config_set_invalid_value_exits_non_zero(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])

    result = runner.invoke(app, ["config", "set", "dm.max_per_day", "not-a-number"])
    assert result.exit_code == 1


def test_config_set_rejects_non_schema_field(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])
    original = load_raw(tmp_path / "replies.yaml")

    result = runner.invoke(app, ["config", "set", "random.garbage", "42"])
    assert result.exit_code == 1

    after = load_raw(tmp_path / "replies.yaml")
    assert after == original


def test_config_set_json_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])

    result = runner.invoke(
        app,
        ["config", "set", "sentences", '["one","two","three"]'],
    )
    assert result.exit_code == 0, result.stdout

    data = load_raw(tmp_path / "replies.yaml")
    assert data["sentences"] == ["one", "two", "three"]


def test_config_set_rejects_sentences_wrong_count(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])
    original = load_raw(tmp_path / "replies.yaml")

    result = runner.invoke(app, ["config", "set", "sentences", '["only-one"]'])
    assert result.exit_code == 1

    after = load_raw(tmp_path / "replies.yaml")
    assert after == original


def test_config_edit_opens_editor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["config", "reset", "-y"])
    monkeypatch.setenv("EDITOR", "true")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        result = runner.invoke(app, ["config", "edit"])
        assert result.exit_code == 0
        mock_run.assert_called_once()
        assert mock_run.call_args[0][0][0] == "true"


def test_config_edit_missing_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["config", "edit"])
    assert result.exit_code == 1
