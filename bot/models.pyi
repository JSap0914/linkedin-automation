from datetime import datetime
from typing import Optional

from pydantic import BaseModel

class Author(BaseModel):
    urn: str
    name: str
    is_self: bool = ...

class Comment(BaseModel):
    comment_urn: str
    comment_id: str
    activity_urn: str
    activity_id: str
    parent_comment_urn: Optional[str]
    author: Author
    text: str
    created_at: datetime
    @property
    def is_top_level(self) -> bool: ...

class Post(BaseModel):
    activity_urn: str
    activity_id: str
    created_at: datetime
    author_urn: str
