# pyright: reportMissingImports=false

from __future__ import annotations

import pytest

from bot.config_io import (
    ConfigIOError,
    dump_raw,
    get_by_path,
    load_raw,
    parse_value,
    set_by_path,
)


def test_parse_value_bool_true():
    assert parse_value("true") is True
    assert parse_value("True") is True
    assert parse_value("TRUE") is True


def test_parse_value_bool_false():
    assert parse_value("false") is False


def test_parse_value_int():
    assert parse_value("42") == 42
    assert parse_value("-7") == -7


def test_parse_value_float():
    assert parse_value("3.14") == 3.14


def test_parse_value_json_list():
    assert parse_value('["a","b"]') == ["a", "b"]


def test_parse_value_json_object():
    assert parse_value('{"key":1}') == {"key": 1}


def test_parse_value_invalid_json_raises():
    with pytest.raises(ConfigIOError):
        parse_value("[invalid")


def test_parse_value_plain_string():
    assert parse_value("hello world") == "hello world"


def test_parse_value_null():
    assert parse_value("null") is None
    assert parse_value("None") is None


def test_set_by_path_top_level():
    data: dict = {}
    set_by_path(data, "enabled", True)
    assert data == {"enabled": True}


def test_set_by_path_nested_creates_intermediates():
    data: dict = {}
    set_by_path(data, "dm.max_per_day", 50)
    assert data == {"dm": {"max_per_day": 50}}


def test_set_by_path_preserves_siblings():
    data = {"dm": {"enabled": True, "max_per_day": 10}}
    set_by_path(data, "dm.max_per_day", 99)
    assert data == {"dm": {"enabled": True, "max_per_day": 99}}


def test_set_by_path_empty_raises():
    with pytest.raises(ConfigIOError):
        set_by_path({}, "", True)


def test_set_by_path_overwrites_non_dict_intermediate():
    data = {"dm": "previously-a-string"}
    set_by_path(data, "dm.enabled", True)
    assert data == {"dm": {"enabled": True}}


def test_get_by_path_found():
    data = {"dm": {"max_per_day": 30}}
    assert get_by_path(data, "dm.max_per_day") == 30


def test_get_by_path_missing_returns_default():
    assert get_by_path({}, "dm.max_per_day", default=0) == 0


def test_load_and_dump_roundtrip(tmp_path):
    path = tmp_path / "cfg.yaml"
    original = {"enabled": True, "sentences": ["a", "b", "c"], "dm": {"max_per_day": 30}}
    dump_raw(original, path)
    loaded = load_raw(path)
    assert loaded == original


def test_load_missing_returns_empty(tmp_path):
    assert load_raw(tmp_path / "does-not-exist.yaml") == {}


def test_dump_preserves_unicode(tmp_path):
    path = tmp_path / "cfg.yaml"
    data = {"sentences": ["감사합니다 🙏"]}
    dump_raw(data, path)
    text = path.read_text(encoding="utf-8")
    assert "감사합니다" in text
    assert "\\u" not in text
