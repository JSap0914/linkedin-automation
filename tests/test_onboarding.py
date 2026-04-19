# pyright: reportMissingImports=false

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bot.onboarding.steps import (
    BaseStep,
    BootstrapStep,
    DmConfigStep,
    FinalStep,
    GitHubStarStep,
    ReplyConfigStep,
    SchedulerInstallStep,
    TosStep,
    WriteConfigStep,
)
from bot.onboarding.wizard import OnboardingWizard


class _OkStep(BaseStep):
    name = "ok"
    calls = 0

    def run(self, state):
        _OkStep.calls += 1
        state["ok"] = True
        return True


class _FailStep(BaseStep):
    name = "fail"

    def run(self, state):
        return False


class _NeverStep(BaseStep):
    name = "never"
    ran = False

    def run(self, state):
        _NeverStep.ran = True
        return True


def test_wizard_runs_all_steps_when_all_ok():
    _OkStep.calls = 0
    w = OnboardingWizard(steps=[_OkStep, _OkStep])
    assert w.run() is True
    assert _OkStep.calls == 2


def test_wizard_short_circuits_on_fail():
    _NeverStep.ran = False
    w = OnboardingWizard(steps=[_FailStep, _NeverStep])
    assert w.run() is False
    assert _NeverStep.ran is False


def test_wizard_config_only_steps_excludes_login():
    assert len(OnboardingWizard.CONFIG_ONLY_STEPS) == 3
    assert ReplyConfigStep in OnboardingWizard.CONFIG_ONLY_STEPS
    assert DmConfigStep in OnboardingWizard.CONFIG_ONLY_STEPS
    assert WriteConfigStep in OnboardingWizard.CONFIG_ONLY_STEPS


def test_tos_step_returns_false_when_user_declines():
    step = TosStep()
    with patch("bot.onboarding.steps._confirm", return_value=False):
        assert step.run({}) is False


def test_tos_step_returns_true_when_user_accepts():
    step = TosStep()
    state: dict = {}
    with patch("bot.onboarding.steps._confirm", return_value=True):
        assert step.run(state) is True
    assert state["tos_accepted"] is True


def test_reply_config_step_uses_defaults_on_happy_path():
    step = ReplyConfigStep()
    state: dict = {}
    with (
        patch("bot.onboarding.steps._confirm", return_value=True),
        patch("bot.onboarding.steps._text", side_effect=["0", "60", "30"]),
    ):
        assert step.run(state) is True
    assert state["config"]["enabled"] is True
    assert len(state["config"]["sentences"]) == 3
    assert state["config"]["reply_delay_seconds_min"] == 0
    assert state["config"]["polling_min_interval_seconds"] == 60
    assert state["config"]["post_lookback_days"] == 30


def test_reply_config_step_can_override_post_lookback_days():
    step = ReplyConfigStep()
    state: dict = {}
    with (
        patch("bot.onboarding.steps._confirm", return_value=True),
        patch("bot.onboarding.steps._text", side_effect=["0", "60", "7"]),
    ):
        assert step.run(state) is True
    assert state["config"]["post_lookback_days"] == 7


def test_dm_config_step_skips_detail_when_disabled():
    step = DmConfigStep()
    state: dict = {}
    with patch("bot.onboarding.steps._confirm", return_value=False):
        assert step.run(state) is True
    assert state["config"]["dm"]["enabled"] is False


def test_dm_config_step_fills_all_fields_when_enabled():
    step = DmConfigStep()
    state: dict = {}
    confirm_answers = iter([True, True, True, True])
    text_answers = iter(["50", "0"])
    with (
        patch("bot.onboarding.steps._confirm", lambda *a, **kw: next(confirm_answers)),
        patch("bot.onboarding.steps._text", lambda *a, **kw: next(text_answers)),
    ):
        assert step.run(state) is True
    dm = state["config"]["dm"]
    assert dm["enabled"] is True
    assert dm["only_first_degree_connections"] is True
    assert dm["auto_accept_pending_invitations"] is True
    assert dm["max_per_day"] == 50


def test_write_config_step_writes_and_validates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from bot.config_defaults import default_config_dict
    step = WriteConfigStep()
    state = {"config": default_config_dict()}
    assert step.run(state) is True
    assert (tmp_path / "replies.yaml").exists()


def test_write_config_step_aborts_on_invalid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    step = WriteConfigStep()
    state = {"config": {"enabled": "not-a-bool"}}
    assert step.run(state) is False
    assert not (tmp_path / "replies.yaml").exists()


def test_write_config_step_aborts_when_no_config_in_state():
    step = WriteConfigStep()
    assert step.run({}) is False


def test_bootstrap_step_can_be_skipped():
    step = BootstrapStep()
    with patch("bot.onboarding.steps._confirm", return_value=False):
        with patch("bot.orchestrator.run") as mock_run:
            assert step.run({}) is True
            mock_run.assert_not_called()


def test_final_step_always_true():
    assert FinalStep().run({}) is True


def test_scheduler_install_step_skipped_if_declined():
    step = SchedulerInstallStep()
    with patch("bot.onboarding.steps._confirm", return_value=False):
        with patch("bot.onboarding.steps.get_scheduler") as mock_get:
            assert step.run({}) is True
            mock_get.assert_not_called()


def test_github_star_step_is_in_full_steps():
    assert GitHubStarStep in OnboardingWizard.FULL_STEPS
    full = OnboardingWizard.FULL_STEPS
    assert full.index(GitHubStarStep) > full.index(SchedulerInstallStep)
    assert full.index(GitHubStarStep) < full.index(FinalStep)


def test_github_star_step_skips_in_non_tty():
    step = GitHubStarStep()
    with (
        patch.object(step, "_is_interactive", return_value=False),
        patch.object(step, "_gh_available") as mock_gh,
        patch("bot.onboarding.steps._confirm") as mock_confirm,
    ):
        assert step.run({}) is True
        mock_gh.assert_not_called()
        mock_confirm.assert_not_called()


def test_github_star_step_already_starred_skips_prompt():
    step = GitHubStarStep()
    with (
        patch.object(step, "_is_interactive", return_value=True),
        patch.object(step, "_gh_available", return_value=True),
        patch.object(step, "_already_starred", return_value=True),
        patch.object(step, "_star_via_gh") as mock_star,
        patch("bot.onboarding.steps._confirm") as mock_confirm,
    ):
        assert step.run({}) is True
        mock_star.assert_not_called()
        mock_confirm.assert_not_called()


def test_github_star_step_stars_when_user_accepts():
    step = GitHubStarStep()
    with (
        patch.object(step, "_is_interactive", return_value=True),
        patch.object(step, "_gh_available", return_value=True),
        patch.object(step, "_already_starred", return_value=False),
        patch.object(step, "_star_via_gh", return_value=True) as mock_star,
        patch("bot.onboarding.steps._confirm", return_value=True),
    ):
        assert step.run({}) is True
        mock_star.assert_called_once()


def test_github_star_step_respects_user_decline():
    step = GitHubStarStep()
    with (
        patch.object(step, "_is_interactive", return_value=True),
        patch.object(step, "_gh_available", return_value=True),
        patch.object(step, "_already_starred", return_value=False),
        patch.object(step, "_star_via_gh") as mock_star,
        patch("bot.onboarding.steps._confirm", return_value=False),
    ):
        assert step.run({}) is True
        mock_star.assert_not_called()


def test_github_star_step_no_gh_falls_back_to_webbrowser():
    step = GitHubStarStep()
    with (
        patch.object(step, "_is_interactive", return_value=True),
        patch.object(step, "_gh_available", return_value=False),
        patch("bot.onboarding.steps._confirm", return_value=True),
        patch("bot.onboarding.steps.webbrowser.open") as mock_open,
    ):
        assert step.run({}) is True
        mock_open.assert_called_once()
        assert "github.com" in mock_open.call_args[0][0]


def test_github_star_step_no_gh_declines_opens_nothing():
    step = GitHubStarStep()
    with (
        patch.object(step, "_is_interactive", return_value=True),
        patch.object(step, "_gh_available", return_value=False),
        patch("bot.onboarding.steps._confirm", return_value=False),
        patch("bot.onboarding.steps.webbrowser.open") as mock_open,
    ):
        assert step.run({}) is True
        mock_open.assert_not_called()


def test_github_star_step_gh_put_fails_falls_back_to_browser():
    step = GitHubStarStep()
    with (
        patch.object(step, "_is_interactive", return_value=True),
        patch.object(step, "_gh_available", return_value=True),
        patch.object(step, "_already_starred", return_value=False),
        patch.object(step, "_star_via_gh", return_value=False),
        patch("bot.onboarding.steps._confirm", return_value=True),
        patch("bot.onboarding.steps.webbrowser.open") as mock_open,
    ):
        assert step.run({}) is True
        mock_open.assert_called_once()


def test_github_star_step_uses_omo_exact_command():
    step = GitHubStarStep()
    with patch("bot.onboarding.steps.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        step._star_via_gh()
        args = mock_run.call_args[0][0]
        assert args == [
            "gh", "api", "--silent", "--method", "PUT",
            f"/user/starred/{GitHubStarStep.REPO}",
        ]
