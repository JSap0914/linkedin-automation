from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator


class Author(BaseModel):
    model_config = ConfigDict(frozen=True)

    urn: str
    name: str
    is_self: bool = False

    @field_validator("urn")
    @classmethod
    def urn_must_be_person(cls, v: str) -> str:
        if not v.startswith("urn:li:person:"):
            raise ValueError(f"author.urn must start with urn:li:person:, got: {v}")
        return v


class Comment(BaseModel):
    model_config = ConfigDict(frozen=True)

    comment_urn: str
    comment_id: str
    activity_urn: str
    activity_id: str
    parent_comment_urn: Optional[str] = None
    author: Author
    text: str
    created_at: datetime

    @field_validator("comment_urn")
    @classmethod
    def comment_urn_must_be_comment(cls, v: str) -> str:
        if not (
            v.startswith("urn:li:comment:(activity:")
            or v.startswith("urn:li:comment:(urn:li:activity:")
        ):
            raise ValueError(
                f"comment_urn must start with urn:li:comment:(activity: or urn:li:comment:(urn:li:activity:, got: {v}"
            )
        return v

    @field_validator("parent_comment_urn")
    @classmethod
    def parent_comment_urn_must_be_comment_or_none(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not (
            v.startswith("urn:li:comment:(activity:")
            or v.startswith("urn:li:comment:(urn:li:activity:")
        ):
            raise ValueError(
                f"parent_comment_urn must start with urn:li:comment:(activity: or urn:li:comment:(urn:li:activity:, got: {v}"
            )
        return v

    @field_validator("activity_urn")
    @classmethod
    def activity_urn_must_be_activity(cls, v: str) -> str:
        if not v.startswith("urn:li:activity:"):
            raise ValueError(f"activity_urn must start with urn:li:activity:, got: {v}")
        return v

    @property
    def is_top_level(self) -> bool:
        return self.parent_comment_urn is None


class Post(BaseModel):
    model_config = ConfigDict(frozen=True)

    activity_urn: str
    activity_id: str
    object_urn: str
    created_at: datetime
    author_urn: str
    body_text: str = ""

    @field_validator("activity_urn")
    @classmethod
    def activity_urn_must_be_activity(cls, v: str) -> str:
        if not v.startswith("urn:li:activity:"):
            raise ValueError(f"activity_urn must start with urn:li:activity:, got: {v}")
        return v

    @field_validator("object_urn")
    @classmethod
    def object_urn_must_be_supported_content_urn(cls, v: str) -> str:
        if not (v.startswith("urn:li:share:") or v.startswith("urn:li:ugcPost:") or v.startswith("urn:li:activity:")):
            raise ValueError(
                f"object_urn must start with urn:li:share:, urn:li:ugcPost:, or urn:li:activity:, got: {v}"
            )
        return v

    @field_validator("author_urn")
    @classmethod
    def author_urn_must_be_person(cls, v: str) -> str:
        if not v.startswith("urn:li:person:"):
            raise ValueError(f"author_urn must start with urn:li:person:, got: {v}")
        return v


Comment.model_rebuild()
