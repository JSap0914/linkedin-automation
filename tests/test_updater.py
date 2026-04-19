# pyright: reportMissingImports=false

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bot import updater


@pytest.fixture
def fake_run(monkeypatch):
    calls: list[list[str]] = []
    outputs: list[dict] = []

    def _run(args, *, check=True, cwd=None):
        calls.append(list(args))
        if outputs:
            spec = outputs.pop(0)
            result = subprocess.CompletedProcess(
                args=args,
                returncode=spec.get("rc", 0),
                stdout=spec.get("stdout", ""),
                stderr=spec.get("stderr", ""),
            )
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(result.returncode, args, result.stdout, result.stderr)
            return result
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(updater, "_run", _run)
    return calls, outputs


def test_is_dirty_returns_porcelain_output(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 0, "stdout": " M bot/config.py\n"})
    assert updater.is_dirty() == "M bot/config.py"


def test_is_dirty_empty_on_clean(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 0, "stdout": ""})
    assert updater.is_dirty() == ""


def test_current_sha(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 0, "stdout": "deadbeef1234\n"})
    assert updater.current_sha() == "deadbeef1234"


def test_changed_paths_between(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 0, "stdout": "bot/config.py\npyproject.toml\n"})
    assert updater.changed_paths_between("old", "new") == ["bot/config.py", "pyproject.toml"]


def test_changed_paths_same_sha_returns_empty():
    assert updater.changed_paths_between("abc", "abc") == []


def test_pull_ff_only_raises_on_failure(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 1, "stdout": "", "stderr": "non-ff"})
    with pytest.raises(updater.UpdateError):
        updater.pull_ff_only()


def test_pull_ff_only_uses_ff_only_flag(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 0, "stdout": ""})
    updater.pull_ff_only()
    assert "--ff-only" in calls[0]
    assert "origin" in calls[0]
    assert "main" in calls[0]


def test_pip_install_editable(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 0, "stdout": ""})
    updater.pip_install_editable()
    args = calls[0]
    assert "-m" in args
    assert "pip" in args
    assert "install" in args
    assert "-e" in args
    assert ".[dev]" in args


def test_pip_install_raises_on_failure(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 1, "stdout": "", "stderr": "deps conflict"})
    with pytest.raises(updater.UpdateError):
        updater.pip_install_editable()


def test_run_pytest_smoke_success(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 0, "stdout": ""})
    assert updater.run_pytest_smoke() is True
    assert "pytest" in calls[0]
    assert "-x" in calls[0]


def test_run_pytest_smoke_failure(fake_run):
    calls, outputs = fake_run
    outputs.append({"rc": 1, "stdout": ""})
    assert updater.run_pytest_smoke() is False


def test_detect_drift_pyproject():
    drift = updater.detect_drift(["pyproject.toml"])
    assert drift["pyproject"] is True
    assert drift["config_schema"] is False
    assert drift["scheduler_templates"] is False


def test_detect_drift_config_schema_via_config_py():
    drift = updater.detect_drift(["bot/config.py"])
    assert drift["config_schema"] is True


def test_detect_drift_config_schema_via_defaults():
    drift = updater.detect_drift(["bot/config_defaults.py"])
    assert drift["config_schema"] is True


def test_detect_drift_scheduler_templates():
    drift = updater.detect_drift(["bot/scheduler/templates/linkedin_autoreply.plist.tmpl"])
    assert drift["scheduler_templates"] is True


def test_detect_drift_irrelevant_files():
    drift = updater.detect_drift(["README.md", "docs/foo.md"])
    assert all(v is False for v in drift.values())


def test_updater_uses_repo_root_when_cwd_not_passed(monkeypatch):
    seen: dict[str, object] = {}

    def _subprocess_run(args, *, check=True, capture_output=True, text=True, cwd=None):
        seen["cwd"] = cwd
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    fake_root = Path("/tmp/fake-repo")

    monkeypatch.setattr(updater, "repo_root", lambda: fake_root)
    monkeypatch.setattr(subprocess, "run", _subprocess_run)
    updater.is_dirty()
    assert seen["cwd"] == str(fake_root)


def test_updater_respects_explicit_cwd(monkeypatch):
    seen: dict[str, object] = {}

    def _run(args, *, check=True, cwd=None):
        seen["cwd"] = cwd
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="abc\n", stderr="")

    explicit = Path("/tmp/explicit")

    monkeypatch.setattr(updater, "_run", _run)
    assert updater.current_sha(cwd=explicit) == "abc"
    assert seen["cwd"] == explicit
