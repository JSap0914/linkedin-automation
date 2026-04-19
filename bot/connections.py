from __future__ import annotations

import logging
from typing import Any

from bot.rate_limit import RateLimitError
from bot.urn import parse_person_urn
from bot.voyager import VoyagerClient

logger = logging.getLogger(__name__)

DASH_PROFILES_PATH = "/identity/dash/profiles"
PRIMARY_DECORATION_ID = (
    "com.linkedin.voyager.dash.deco.identity.profile.TopCardSupplementary-175"
)

_first_degree_cache: dict[str, bool] = {}
_profile_response_cache: dict[str, dict] = {}


def clear_cache() -> None:
    _first_degree_cache.clear()
    _profile_response_cache.clear()


def fetch_profile_data(client: VoyagerClient, person_urn: str) -> dict | None:
    cached = _profile_response_cache.get(person_urn)
    if cached is not None:
        return cached

    try:
        person_id = parse_person_urn(person_urn)
    except ValueError:
        return None

    try:
        data = client.get(
            DASH_PROFILES_PATH,
            params={
                "q": "memberIdentity",
                "memberIdentity": person_id,
                "decorationId": PRIMARY_DECORATION_ID,
            },
        )
    except RateLimitError:
        raise
    except Exception as exc:
        logger.warning("Dash profile fetch failed for %s: %s", person_urn, exc)
        return None

    if not isinstance(data, dict):
        return None

    _profile_response_cache[person_urn] = data
    return data


def extract_pending_invitation(profile_data: dict) -> dict | None:
    if not isinstance(profile_data, dict):
        return None

    included = profile_data.get("included") or []
    if not isinstance(included, list):
        return None

    invitation_urn: str | None = None

    for item in included:
        if not isinstance(item, dict):
            continue
        if item.get("$type") != "com.linkedin.voyager.dash.relationships.MemberRelationship":
            continue
        union = item.get("memberRelationshipUnion") or item.get("memberRelationshipData") or {}
        if not isinstance(union, dict):
            continue
        no_connection = union.get("noConnection") or union.get("*noConnection")
        if isinstance(no_connection, dict):
            invitation_union = no_connection.get("invitationUnion") or {}
            if isinstance(invitation_union, dict):
                ref = invitation_union.get("*invitation") or invitation_union.get("invitation")
                if isinstance(ref, str):
                    invitation_urn = ref
                    break
                if isinstance(ref, dict):
                    return _normalize_invitation(ref)

    if invitation_urn is None:
        return None

    for item in included:
        if not isinstance(item, dict):
            continue
        if item.get("$type") != "com.linkedin.voyager.dash.relationships.invitation.Invitation":
            continue
        if item.get("entityUrn") == invitation_urn:
            return _normalize_invitation(item)

    return None


def _normalize_invitation(raw: dict) -> dict | None:
    entity_urn = raw.get("entityUrn", "")
    shared_secret = raw.get("sharedSecret", "")
    invitation_type = raw.get("invitationType", "")

    if not entity_urn or not shared_secret:
        return None
    if invitation_type and invitation_type != "RECEIVED":
        return None

    invitation_id = entity_urn.rsplit(":", 1)[-1]

    return {
        "entityUrn": entity_urn,
        "sharedSecret": shared_secret,
        "invitationId": invitation_id,
    }


def is_first_degree_connection(client: VoyagerClient, person_urn: str) -> bool:
    cached = _first_degree_cache.get(person_urn)
    if cached is not None:
        return cached

    data = fetch_profile_data(client, person_urn)
    if data is None:
        _first_degree_cache[person_urn] = False
        return False

    distance_value = _extract_distance_value(data)
    if distance_value is None:
        logger.warning("Could not parse memberDistance for %s", person_urn)
        _first_degree_cache[person_urn] = False
        return False

    is_first = distance_value == "DISTANCE_1"
    _first_degree_cache[person_urn] = is_first
    logger.info(
        "Connection degree for %s: distance=%s first_degree=%s",
        person_urn,
        distance_value,
        is_first,
    )
    return is_first


def get_pending_invitation(client: VoyagerClient, person_urn: str) -> dict | None:
    data = fetch_profile_data(client, person_urn)
    if data is None:
        return None
    return extract_pending_invitation(data)


def invalidate_profile_cache(person_urn: str) -> None:
    _first_degree_cache.pop(person_urn, None)
    _profile_response_cache.pop(person_urn, None)


def _extract_distance_value(data: Any) -> str | None:
    if not isinstance(data, dict):
        return None

    for source in (data, data.get("data") or {}):
        if isinstance(source, dict):
            value = _distance_from_container(source)
            if value:
                return value

    included = data.get("included") or []

    for item in included:
        if isinstance(item, dict):
            value = _distance_from_container(item)
            if value:
                return value

    for item in included:
        if not isinstance(item, dict):
            continue
        item_type = item.get("$type", "")
        if item_type == "com.linkedin.voyager.dash.relationships.MemberRelationship":
            union = item.get("memberRelationshipUnion") or item.get("memberRelationshipData") or {}
            if not isinstance(union, dict):
                continue

            if "*connection" in union or "connection" in union:
                return "DISTANCE_1"

            no_connection = union.get("noConnection") or union.get("*noConnection")
            if isinstance(no_connection, dict):
                nested_distance = no_connection.get("memberDistance")
                if isinstance(nested_distance, str):
                    return nested_distance
                if isinstance(nested_distance, dict):
                    value = nested_distance.get("value")
                    if isinstance(value, str):
                        return value
                return "OUT_OF_NETWORK"

            if any(key in union for key in ("*invitedMember", "*invitationPending", "invitationPending")):
                return "DISTANCE_2"

    for item in included:
        if not isinstance(item, dict):
            continue
        item_type = item.get("$type", "")
        if item_type == "com.linkedin.voyager.dash.relationships.Connection":
            if item.get("connectedMember") or item.get("*connectedMemberResolutionResult"):
                return "DISTANCE_1"

    return None


def _distance_from_container(container: dict) -> str | None:
    member_distance = container.get("memberDistance")
    if isinstance(member_distance, dict):
        value = member_distance.get("value")
        if isinstance(value, str):
            return value
    if isinstance(member_distance, str):
        return member_distance

    distance = container.get("distance")
    if isinstance(distance, dict):
        value = distance.get("value")
        if isinstance(value, str):
            return value
    if isinstance(distance, str):
        return distance

    return None
