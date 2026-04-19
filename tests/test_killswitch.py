# pyright: reportMissingImports=false

from __future__ import annotations

import pytest

from bot.config import RepliesConfig
from bot.killswitch import check_kill_switch


def make_config(enabled: bool) -> RepliesConfig:
    return RepliesConfig(
        enabled=enabled,
        sentences=["a", "b", "c"],
        reply_delay_seconds_min=30,
        reply_delay_seconds_max=120,
        post_lookback_days=30,
        polling_min_interval_seconds=900,
    )


def test_enabled_true_returns_none():
    assert check_kill_switch(make_config(True)) is None


def test_enabled_false_exits_zero():
    with pytest.raises(SystemExit) as exc:
        check_kill_switch(make_config(False))
    assert exc.value.code == 0


def test_enabled_false_logs_message(caplog):
    caplog.set_level("INFO")
    with pytest.raises(SystemExit):
        check_kill_switch(make_config(False))
    assert any("Kill switch active" in record.message for record in caplog.records)
