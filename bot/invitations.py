from __future__ import annotations

import logging
from typing import Any

from bot.voyager import VoyagerClient

logger = logging.getLogger(__name__)

INVITATION_VIEWS_PATH = "/relationships/invitationViews"
INVITATION_ACTION_PATH = "/relationships/invitations"


class InvitationAcceptError(RuntimeError):
    pass


def list_received_invitations(client: VoyagerClient, *, limit: int = 50) -> list[dict[str, Any]]:
    data = client.get(
        INVITATION_VIEWS_PATH,
        params={"q": "receivedInvitation", "start": 0, "count": limit},
    )

    if not isinstance(data, dict):
        return []

    invitations: list[dict[str, Any]] = []

    elements = data.get("elements")
    if isinstance(elements, list):
        for element in elements:
            invitation = _extract_invitation(element)
            if invitation is not None:
                invitations.append(invitation)
        if invitations:
            return invitations

    inner = data.get("data") or {}
    inner_elements = inner.get("*elements") if isinstance(inner, dict) else None
    included = data.get("included") or []
    if isinstance(inner_elements, list) and isinstance(included, list):
        included_map = {
            item.get("entityUrn"): item
            for item in included
            if isinstance(item, dict) and item.get("entityUrn")
        }
        for element_urn in inner_elements:
            if not isinstance(element_urn, str):
                continue
            view = included_map.get(element_urn) or {}
            invitation_ref = view.get("*invitation") or view.get("invitation")
            candidate: dict[str, Any] | None = None
            if isinstance(invitation_ref, str):
                candidate = included_map.get(invitation_ref)
            elif isinstance(invitation_ref, dict):
                candidate = invitation_ref
            invitation = _extract_invitation(candidate) if candidate else None
            if invitation is not None:
                invitations.append(invitation)

    return invitations


def _extract_invitation(container: Any) -> dict[str, Any] | None:
    if not isinstance(container, dict):
        return None
    if "sharedSecret" in container and container.get("entityUrn", "").startswith("urn:li:invitation:"):
        return container
    invitation = container.get("invitation")
    if isinstance(invitation, dict) and invitation.get("entityUrn", "").startswith("urn:li:invitation:"):
        return invitation
    return None


def find_invitation_from(
    invitations: list[dict[str, Any]],
    sender_person_urn: str,
) -> dict[str, Any] | None:
    sender_id = sender_person_urn.rsplit(":", 1)[-1].lower() if sender_person_urn else ""
    if not sender_id:
        return None

    for invitation in invitations:
        from_candidates = (
            invitation.get("*fromMember"),
            invitation.get("fromMemberUrn"),
            invitation.get("fromMember"),
        )
        for candidate in from_candidates:
            if isinstance(candidate, str) and sender_id in candidate.lower():
                return invitation
    return None


def accept_invitation(client: VoyagerClient, invitation: dict[str, Any]) -> bool:
    entity_urn = invitation.get("entityUrn", "")
    shared_secret = invitation.get("sharedSecret", "")

    is_valid_urn = entity_urn.startswith("urn:li:invitation:") or entity_urn.startswith(
        "urn:li:fsd_invitation:"
    )
    if not is_valid_urn or not shared_secret:
        logger.warning(
            "Refusing to accept invitation with missing fields: entityUrn=%r has_secret=%s",
            entity_urn,
            bool(shared_secret),
        )
        return False

    invitation_id = invitation.get("invitationId") or entity_urn.rsplit(":", 1)[-1]
    payload = {
        "invitationId": str(invitation_id),
        "invitationSharedSecret": shared_secret,
        "isGenericInvitation": False,
    }

    logger.info("Accepting invitation %s", entity_urn)
    response = client.post(
        f"{INVITATION_ACTION_PATH}/{invitation_id}?action=accept",
        json_body=payload,
    )

    if isinstance(response, dict) and response.get("__error"):
        logger.error(
            "Invitation accept rejected: status=%s statusText=%s",
            response.get("status"),
            response.get("statusText"),
        )
        return False

    logger.info("Invitation %s accepted", entity_urn)
    return True
