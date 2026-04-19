from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    only_first_degree_connections: bool = True
    auto_accept_pending_invitations: bool = True
    messages: list[str] = Field(default_factory=list)
    max_per_day: int = 0
    delay_seconds_min: int = Field(default=60, ge=0)
    delay_seconds_max: int = Field(default=300, ge=0)

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, messages: list[str]) -> list[str]:
        if any(not isinstance(message, str) or not message.strip() for message in messages):
            raise ValueError("dm.messages must contain only non-empty strings")
        return messages

    @model_validator(mode="after")
    def validate_state(self) -> "DMConfig":
        if self.enabled and not self.messages:
            raise ValueError("dm.messages must contain at least 1 message when dm.enabled is true")
        if self.delay_seconds_max < self.delay_seconds_min:
            raise ValueError("dm.delay_seconds_max must be >= dm.delay_seconds_min")
        return self


class TemplateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: list[str] = Field(default_factory=list)
    sentences: list[str] = Field(default_factory=list)
    dm_messages: list[str] = Field(default_factory=list)

    @field_validator("sentences", "dm_messages")
    @classmethod
    def validate_non_empty_strings(cls, values: list[str]) -> list[str]:
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("template string lists must contain only non-empty strings")
        return values

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, keywords: list[str]) -> list[str]:
        if any(not isinstance(keyword, str) or not keyword.strip() for keyword in keywords):
            raise ValueError("template keywords must contain only non-empty strings")
        return keywords


class RepliesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    sentences: list[str]
    reply_delay_seconds_min: int = Field(ge=0, le=600)
    reply_delay_seconds_max: int = Field(ge=0, le=600)
    post_lookback_days: int = Field(ge=1, le=3650)
    polling_min_interval_seconds: int = Field(ge=60)
    dm: DMConfig = Field(default_factory=DMConfig)
    templates: dict[str, TemplateConfig] = Field(default_factory=dict)
    post_bindings: dict[str, str] = Field(default_factory=dict)

    @field_validator("sentences")
    @classmethod
    def validate_sentences(cls, sentences: list[str]) -> list[str]:
        if len(sentences) != 3:
            raise ValueError("sentences must contain exactly 3 items")
        if any(not isinstance(sentence, str) or not sentence.strip() for sentence in sentences):
            raise ValueError("sentences must be non-empty strings")
        return sentences

    @model_validator(mode="after")
    def validate_delay_order(self) -> "RepliesConfig":
        if self.reply_delay_seconds_min > self.reply_delay_seconds_max:
            raise ValueError("reply_delay_seconds_min must be <= reply_delay_seconds_max")
        return self

    @model_validator(mode="after")
    def validate_post_bindings_reference_existing_templates(self) -> "RepliesConfig":
        for urn, template_name in self.post_bindings.items():
            if template_name not in self.templates and template_name != "default":
                raise ValueError(
                    f"post_bindings[{urn!r}] references unknown template {template_name!r}"
                )
        return self


def load_config(path: Path = Path("replies.yaml")) -> RepliesConfig:
    config_path = Path("replies.yaml.local") if Path("replies.yaml.local").exists() else Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        loaded_data = yaml.safe_load(handle) or {}
    return RepliesConfig(**loaded_data)
