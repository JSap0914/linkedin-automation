# pyright: reportMissingImports=false

from __future__ import annotations

from bot.config import RepliesConfig
from bot.config_defaults import default_config_dict


def test_default_config_dict_is_pydantic_valid():
    data = default_config_dict()
    RepliesConfig(**data)


def test_default_config_dict_has_exactly_three_sentences():
    data = default_config_dict()
    assert len(data["sentences"]) == 3


def test_default_config_dict_dm_disabled_by_default():
    data = default_config_dict()
    assert data["dm"]["enabled"] is False


def test_default_config_dict_is_idempotent():
    a = default_config_dict()
    b = default_config_dict()
    assert a == b
    a["sentences"][0] = "MUTATED"
    c = default_config_dict()
    assert c["sentences"][0] != "MUTATED"


def test_default_config_dict_enabled_top_level():
    assert default_config_dict()["enabled"] is True


def test_default_config_dict_has_three_dm_messages():
    assert len(default_config_dict()["dm"]["messages"]) == 3


def test_default_config_dict_post_lookback_days_in_schema_range():
    v = default_config_dict()["post_lookback_days"]
    assert 1 <= v <= 3650


def test_default_config_dict_polling_min_interval_at_least_60():
    assert default_config_dict()["polling_min_interval_seconds"] >= 60
