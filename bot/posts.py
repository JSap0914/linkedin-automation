from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from bot.models import Post
from bot.urn import parse_activity_urn, parse_person_urn
from bot.voyager import VoyagerClient

logger = logging.getLogger(__name__)


def _extract_profile_id(client: VoyagerClient, person_id: str) -> str:
    data = client.get(
        "/identity/dash/profiles",
        params={
            "q": "memberIdentity",
            "memberIdentity": person_id,
            "decorationId": "com.linkedin.voyager.dash.deco.identity.profile.TopCardSupplementary-175",
        },
    )
    elements = (data.get("data") or {}).get("*elements") or []
    if not elements:
        raise ValueError(f"Could not resolve LinkedIn profile ID for {person_id}")

    entity_urn = elements[0]
    if not isinstance(entity_urn, str) or not entity_urn.startswith("urn:li:fsd_profile:"):
        raise ValueError(f"Unexpected profile URN shape: {entity_urn!r}")

    return entity_urn.rsplit(":", 1)[-1]


def _activity_urn_to_created_at(activity_urn: str) -> datetime:
    activity_id = int(parse_activity_urn(activity_urn))
    created_ms = activity_id >> 22
    return datetime.fromtimestamp(created_ms / 1000, tz=timezone.utc)


def _extract_body_text(value: dict) -> str:
    if not isinstance(value, dict):
        return ""

    commentary = value.get("commentary") or {}
    if isinstance(commentary, dict):
        text_field = commentary.get("text")
        if isinstance(text_field, dict):
            inner = text_field.get("text")
            if isinstance(inner, str) and inner.strip():
                return inner
        if isinstance(text_field, str) and text_field.strip():
            return text_field

    content = value.get("content") or {}
    if isinstance(content, dict):
        description = content.get("description")
        if isinstance(description, dict):
            inner = description.get("text")
            if isinstance(inner, str) and inner.strip():
                return inner
        if isinstance(description, str) and description.strip():
            return description

    return ""


def discover_recent_posts(client: VoyagerClient, own_urn: str, lookback_days: int) -> list[Post]:
    person_id = parse_person_urn(own_urn)
    profile_id = _extract_profile_id(client, person_id)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    posts: list[Post] = []
    pagination_token = ""
    fetched = 0

    while fetched < 100:
        params = {
            "profileId": profile_id,
            "q": "memberShareFeed",
            "count": 20,
        }
        if pagination_token:
            params["paginationToken"] = pagination_token

        data = client.get("/feed/updates", params=params)
        payload = data.get("data") or {}
        elements = payload.get("*elements") or payload.get("elements") or []
        if not elements:
            break

        included_map = {
            item.get("entityUrn"): item
            for item in data.get("included") or []
            if isinstance(item, dict) and item.get("entityUrn")
        }

        for element_urn in elements:
            try:
                element = included_map.get(element_urn) or {}
                value = included_map.get(element.get("*value", "")) or {}
                urn_str = (
                    element.get("urn")
                    or (value.get("updateMetadata") or {}).get("urn")
                    or value.get("urn")
                    or ""
                )
                if not urn_str or "activity" not in urn_str:
                    continue

                created_at = _activity_urn_to_created_at(urn_str)
                update_metadata = value.get("updateMetadata") or {}
                object_urn = (
                    update_metadata.get("shareUrn")
                    or update_metadata.get("ugcUrn")
                    or (value.get("content") or {}).get("entityUrn")
                    or urn_str
                )
                body_text = _extract_body_text(value)

                if created_at >= cutoff:
                    activity_id = parse_activity_urn(urn_str)
                    posts.append(
                        Post(
                            activity_urn=urn_str,
                            activity_id=activity_id,
                            object_urn=object_urn,
                            created_at=created_at,
                            author_urn=own_urn,
                            body_text=body_text,
                        )
                    )
                    fetched += 1
            except Exception as exc:
                logger.debug("Skipping unparseable element: %s", exc)
                continue

        pagination_token = (payload.get("metadata") or {}).get("paginationToken", "")
        if not pagination_token:
            break

    logger.info("Discovered %d posts in last %d days", len(posts), lookback_days)
    return posts
