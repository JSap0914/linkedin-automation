from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from bot.auth import _normalize_person_urn
from bot.db import is_seen
from bot.models import Author, Comment
from bot.urn import parse_comment_urn
from bot.voyager import VoyagerClient

logger = logging.getLogger(__name__)

FS_COMMENT_URN_RE = re.compile(r"^urn:li:fs_objectComment:\((\d+),activity:(\d+)\)$")
SHORT_COMMENT_URN_RE = re.compile(r"^urn:li:comment:\(activity:(\d+),(\d+)\)$")
FULL_COMMENT_URN_RE = re.compile(r"^urn:li:comment:\(urn:li:activity:(\d+),(\d+)\)$")
FSD_COMMENT_URN_RE = re.compile(r"^urn:li:fsd_comment:\((\d+),urn:li:activity:(\d+)\)$")


def to_fsd_comment_urn(comment_urn: str) -> str:
    """Convert any supported comment URN form to the Dash ``fsd_comment`` form.

    Dash/FSD write endpoints expect ``urn:li:fsd_comment:(commentId,urn:li:activity:activityId)``
    with the comment id first and the activity URN second — the opposite field
    order of the legacy ``urn:li:comment:(urn:li:activity:X,Y)`` form.
    """
    if not comment_urn:
        return ""

    if FSD_COMMENT_URN_RE.match(comment_urn):
        return comment_urn

    full_match = FULL_COMMENT_URN_RE.match(comment_urn)
    if full_match:
        activity_id, comment_id = full_match.groups()
        return f"urn:li:fsd_comment:({comment_id},urn:li:activity:{activity_id})"

    short_match = SHORT_COMMENT_URN_RE.match(comment_urn)
    if short_match:
        activity_id, comment_id = short_match.groups()
        return f"urn:li:fsd_comment:({comment_id},urn:li:activity:{activity_id})"

    fs_match = FS_COMMENT_URN_RE.match(comment_urn)
    if fs_match:
        comment_id, activity_id = fs_match.groups()
        return f"urn:li:fsd_comment:({comment_id},urn:li:activity:{activity_id})"

    raise ValueError(f"Invalid comment URN format for Dash conversion: {comment_urn}")


def _normalize_comment_urn(value: str) -> str:
    if not value:
        return ""
    if FULL_COMMENT_URN_RE.match(value):
        return value

    short_match = SHORT_COMMENT_URN_RE.match(value)
    if short_match:
        activity_id, comment_id = short_match.groups()
        return f"urn:li:comment:(urn:li:activity:{activity_id},{comment_id})"

    match = FS_COMMENT_URN_RE.match(value)
    if match:
        comment_id, activity_id = match.groups()
        return f"urn:li:comment:(urn:li:activity:{activity_id},{comment_id})"

    return ""


def _extract_ids_from_comment_urn(comment_urn: str) -> tuple[str, str]:
    if comment_urn.startswith("urn:li:comment:(activity:") or comment_urn.startswith(
        "urn:li:comment:(urn:li:activity:"
    ):
        return parse_comment_urn(comment_urn)

    match = FS_COMMENT_URN_RE.match(comment_urn)
    if match:
        comment_id, activity_id = match.groups()
        return activity_id, comment_id

    raise ValueError(f"Invalid comment URN format: {comment_urn}")


def _extract_author(elem: dict[str, Any]) -> Author:
    commenter = elem.get("commenter") or {}
    commenter_dash = elem.get("commenterForDashConversion") or {}
    actor_union = commenter_dash.get("actorUnion") or {}

    mini = (
        commenter.get("miniProfile")
        or commenter.get("com.linkedin.voyager.identity.shared.MiniProfile")
        or {}
    )
    profile_id = elem.get("commenterProfileId") or commenter_dash.get("commenterProfileId") or "unknown"
    author_urn = actor_union.get("profileUrn") or mini.get("entityUrn") or ""
    if author_urn.startswith("urn:li:fsd_profile:"):
        author_urn = f"urn:li:person:{author_urn.rsplit(':', 1)[-1]}"
    elif author_urn.startswith("urn:li:fs_miniProfile:"):
        author_urn = f"urn:li:person:{author_urn.rsplit(':', 1)[-1]}"
    elif not author_urn.startswith("urn:li:person:"):
        author_urn = f"urn:li:person:{mini.get('publicIdentifier') or profile_id}"

    author_name = (
        ((commenter_dash.get("title") or {}).get("text"))
        or f"{mini.get('firstName', '')} {mini.get('lastName', '')}".strip()
        or "Unknown"
    )

    return Author(urn=author_urn, name=author_name, is_self=False)


def _extract_text(elem: dict[str, Any]) -> str:
    comment_v2 = elem.get("commentV2") or {}
    comment = elem.get("comment") or {}
    commentary = elem.get("commentaryText") or elem.get("commentary") or {}
    return (
        comment_v2.get("text", "")
        or ((comment.get("values") or [{}])[0].get("value", ""))
        or commentary.get("text", "")
        or ""
    )


def _extract_created_at(elem: dict[str, Any]) -> datetime:
    created_ms = elem.get("createdAt") or elem.get("createdTime") or (elem.get("created") or {}).get("time") or 0
    return (
        datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)
        if created_ms
        else datetime.now(timezone.utc)
    )


def fetch_comments(client: VoyagerClient, activity_id: str) -> list[Comment]:
    comments: list[Comment] = []
    start = 0
    pagination_token = ""
    fetched_total = 0

    while fetched_total < 500:
        params: dict = {
            "count": 100,
            "start": start,
            "q": "comments",
            "sortOrder": "RELEVANCE",
            "updateId": f"urn:li:activity:{activity_id}",
        }
        if pagination_token:
            params["paginationToken"] = pagination_token

        data = client.get("/feed/comments", params=params)
        collection = data.get("data") or {}
        element_urns = set(collection.get("*elements") or [])
        included = data.get("included") or []

        if element_urns and included:
            elements = [
                item
                for item in included
                if isinstance(item, dict) and item.get("entityUrn") in element_urns
            ]
        else:
            elements = data.get("elements") or collection.get("elements") or collection.get("*elements") or []

        if not elements:
            break

        for elem in elements:
            try:
                comment_urn = _normalize_comment_urn(
                    elem.get("commentUrn")
                    or elem.get("entityUrn")
                    or elem.get("dashEntityUrn")
                    or ""
                )
                if not comment_urn:
                    continue

                act_id, cmt_id = _extract_ids_from_comment_urn(comment_urn)

                parent_urn = _normalize_comment_urn(
                    elem.get("parentCommentUrn") or elem.get("parentCommentBackendUrn") or ""
                ) or None

                comment = Comment(
                    comment_urn=comment_urn,
                    comment_id=cmt_id,
                    activity_urn=f"urn:li:activity:{act_id}",
                    activity_id=act_id,
                    parent_comment_urn=parent_urn,
                    author=_extract_author(elem),
                    text=_extract_text(elem),
                    created_at=_extract_created_at(elem),
                )
                comments.append(comment)
                fetched_total += 1
            except Exception as exc:
                logger.debug("Skipping unparseable comment: %s", exc)
                continue

        pagination_token = ((collection.get("metadata") or {}).get("paginationToken", "")) or (
            (data.get("metadata") or {}).get("paginationToken", "")
        )
        if not pagination_token:
            break
        start += 100

    logger.info("Fetched %d comments for activity %s", len(comments), activity_id)
    return comments


def filter_to_reply_targets(
    comments: list[Comment],
    own_urn: str,
    conn: sqlite3.Connection,
) -> list[Comment]:
    targets = []
    normalized_own_urn = (_normalize_person_urn(own_urn) or own_urn).lower()
    for comment in comments:
        if not comment.is_top_level:
            continue
        normalized_author_urn = (_normalize_person_urn(comment.author.urn) or comment.author.urn).lower()
        if normalized_author_urn == normalized_own_urn:
            continue
        if is_seen(conn, comment.comment_id):
            continue
        targets.append(comment)
    logger.debug("Filter: %d/%d comments are reply targets", len(targets), len(comments))
    return targets
