# pyright: reportMissingImports=false

from __future__ import annotations

import pytest

from bot.config_defaults import default_config_dict
from bot.config_migrate import MigrationError, detect_drift, migrate


def test_migrate_fills_missing_fields_with_defaults():
    current = {
        "enabled": True,
        "sentences": ["a", "b", "c"],
        "reply_delay_seconds_min": 0,
        "reply_delay_seconds_max": 0,
        "post_lookback_days": 7,
        "polling_min_interval_seconds": 60,
    }
    merged, added, removed = migrate(current)
    assert "dm" in merged
    assert removed == []
    assert any("dm" in a for a in added)


def test_migrate_never_overwrites_existing_user_values():
    current = default_config_dict()
    current["dm"]["max_per_day"] = 999
    current["sentences"] = ["custom1", "custom2", "custom3"]
    merged, added, removed = migrate(current)
    assert merged["dm"]["max_per_day"] == 999
    assert merged["sentences"] == ["custom1", "custom2", "custom3"]


def test_migrate_drops_unknown_fields_and_warns():
    current = default_config_dict()
    current["dm"]["legacy_field"] = "to-be-dropped"
    current["removed_top_level"] = "gone"

    merged, added, removed = migrate(current)

    assert "legacy_field" not in merged["dm"]
    assert "removed_top_level" not in merged
    assert "dm.legacy_field" in removed
    assert "removed_top_level" in removed


def test_migrate_errors_on_type_mismatch():
    current = default_config_dict()
    current["post_lookback_days"] = "not-an-int"
    with pytest.raises(MigrationError):
        migrate(current)


def test_migrate_noop_when_already_valid():
    current = default_config_dict()
    merged, added, removed = migrate(current)
    assert merged == current
    assert added == []
    assert removed == []


def test_detect_drift_added_and_removed():
    current = {"enabled": True, "random_extra": 42}
    drift = detect_drift(current)
    assert "random_extra" in drift["removed"]
    assert any("dm" in p for p in drift["added"])


def test_migrate_returns_deepcopy_not_reference():
    current = default_config_dict()
    merged, _, _ = migrate(current)
    merged["enabled"] = False
    assert current["enabled"] is True
