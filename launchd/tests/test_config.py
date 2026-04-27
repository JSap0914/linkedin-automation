from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from bot.config import DMConfig, RepliesConfig, TemplateConfig, load_config

BASE_REPLIES_YAML = {
    "enabled": True,
    "sentences": [
        "댓글 감사합니다! 🙏",
        "관심 가져주셔서 감사해요 😊",
        "좋은 말씀 감사드립니다!",
    ],
    "reply_delay_seconds_min": 30,
    "reply_delay_seconds_max": 120,
    "post_lookback_days": 30,
    "polling_min_interval_seconds": 900,
}


def _write_yaml(tmp_path, data):
    config_path = tmp_path / "replies.yaml"
    config_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return config_path


def test_config_loads_without_dm_block_defaults_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    path = _write_yaml(tmp_path, BASE_REPLIES_YAML)
    config = load_config(path)
    assert config.dm.enabled is False
    assert config.dm.messages == []
    assert config.dm.max_per_day == 0


def test_config_loads_with_dm_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = dict(BASE_REPLIES_YAML)
    data["dm"] = {
        "enabled": True,
        "only_first_degree_connections": True,
        "messages": ["{name}님 감사합니다"],
        "max_per_day": 5,
        "delay_seconds_min": 60,
        "delay_seconds_max": 120,
    }
    path = _write_yaml(tmp_path, data)
    config = load_config(path)
    assert config.dm.enabled is True
    assert config.dm.only_first_degree_connections is True
    assert config.dm.messages == ["{name}님 감사합니다"]
    assert config.dm.max_per_day == 5


def test_dm_enabled_requires_at_least_one_message():
    with pytest.raises(ValidationError):
        DMConfig(enabled=True, messages=[])


def test_dm_empty_message_rejected():
    with pytest.raises(ValidationError):
        DMConfig(enabled=True, messages=["valid", ""])


def test_dm_negative_or_zero_max_per_day_means_unlimited():
    cfg = DMConfig(enabled=True, messages=["hi"], max_per_day=0)
    assert cfg.max_per_day == 0
    cfg_negative = DMConfig(enabled=True, messages=["hi"], max_per_day=-1)
    assert cfg_negative.max_per_day == -1


def test_dm_delay_max_less_than_min_rejected():
    with pytest.raises(ValidationError):
        DMConfig(
            enabled=True,
            messages=["hi"],
            delay_seconds_min=100,
            delay_seconds_max=50,
        )


def test_replies_config_accepts_dm_default():
    config = RepliesConfig(**BASE_REPLIES_YAML)
    assert isinstance(config.dm, DMConfig)
    assert config.dm.enabled is False


def test_legacy_config_without_templates_loads():
    config = RepliesConfig(**BASE_REPLIES_YAML)
    assert config.templates == {}
    assert config.post_bindings == {}


def test_config_with_templates_and_post_bindings_loads():
    data = dict(BASE_REPLIES_YAML)
    data["templates"] = {
        "product_launch": {
            "keywords": ["런칭", "출시"],
            "sentences": ["{name}님 런칭 감사합니다"],
            "dm_messages": ["{name}님, 자료 공유드릴게요"],
        }
    }
    data["post_bindings"] = {"urn:li:activity:123": "product_launch"}
    config = RepliesConfig(**data)
    assert "product_launch" in config.templates
    assert config.post_bindings == {"urn:li:activity:123": "product_launch"}
    assert config.templates["product_launch"].keywords == ["런칭", "출시"]


def test_invalid_binding_raises_validation_error():
    data = dict(BASE_REPLIES_YAML)
    data["templates"] = {
        "product_launch": {
            "sentences": ["hi"],
        }
    }
    data["post_bindings"] = {"urn:li:activity:123": "does_not_exist"}
    with pytest.raises(ValidationError):
        RepliesConfig(**data)


def test_empty_template_sentences_allowed():
    template = TemplateConfig(keywords=["x"], sentences=[], dm_messages=[])
    assert template.sentences == []
    assert template.dm_messages == []


def test_template_config_standalone():
    template = TemplateConfig(
        keywords=["런칭"],
        sentences=["{name}님 감사합니다"],
        dm_messages=["{name}님 DM"],
    )
    assert template.keywords == ["런칭"]
    assert template.sentences == ["{name}님 감사합니다"]
    assert template.dm_messages == ["{name}님 DM"]


def test_auto_accept_pending_invitations_default_true():
    dm = DMConfig(enabled=True, messages=["hi"])
    assert dm.auto_accept_pending_invitations is True
