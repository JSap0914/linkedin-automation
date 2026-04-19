from __future__ import annotations

import logging
import secrets
import uuid

from bot.urn import person_to_fsd_profile_urn
from bot.voyager import VoyagerClient

logger = logging.getLogger(__name__)


class DMSendError(RuntimeError):
    pass


def send_direct_message(
    client: VoyagerClient,
    recipient_person_urn: str,
    own_urn: str,
    text: str,
) -> str:
    recipient_fsd = person_to_fsd_profile_urn(recipient_person_urn)
    mailbox_fsd = person_to_fsd_profile_urn(own_urn)

    origin_token = str(uuid.uuid4())
    tracking_id = secrets.token_bytes(16).decode("latin-1")

    payload = {
        "dedupeByClientGeneratedToken": False,
        "hostRecipientUrns": [recipient_fsd],
        "mailboxUrn": mailbox_fsd,
        "message": {
            "body": {
                "attributes": [],
                "text": text,
            },
            "originToken": origin_token,
            "renderContentUnions": [],
        },
        "trackingId": tracking_id,
    }

    extra_headers = None
    if hasattr(client, "_runtime") and hasattr(client._runtime, "build_messaging_headers"):
        extra_headers = client._runtime.build_messaging_headers()

    logger.info(
        "Sending DM to %s (mailbox=%s, origin=%s)",
        recipient_fsd,
        mailbox_fsd,
        origin_token,
    )

    if hasattr(client, "_runtime"):
        response_data = client._runtime.fetch_json(
            "/voyagerMessagingDashMessengerMessages",
            params={"action": "createMessage"},
            method="POST",
            body=payload,
            extra_headers=extra_headers,
        )
    else:
        response_data = client.post(
            "/voyagerMessagingDashMessengerMessages?action=createMessage",
            json_body=payload,
            extra_headers=extra_headers,
        )

    restli_id = response_data.get("restliId", "") if isinstance(response_data, dict) else ""

    if isinstance(response_data, dict) and response_data.get("__error"):
        logger.error(
            "DM send failed: status=%s statusText=%s restli_id=%s data_keys=%s",
            response_data.get("status"),
            response_data.get("statusText"),
            restli_id,
            sorted((response_data.get("data") or {}).keys()) if isinstance(response_data.get("data"), dict) else [],
        )
        raise DMSendError(
            f"DM send rejected: status={response_data.get('status')} statusText={response_data.get('statusText')}"
        )

    logger.info("DM sent successfully (restliId=%s, origin=%s)", restli_id, origin_token)
    return restli_id or origin_token
