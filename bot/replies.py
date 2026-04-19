from __future__ import annotations

import logging
import random
import secrets
import sqlite3
import time
import unicodedata

from bot.auth import _normalize_person_urn
from bot.comments import fetch_comments
from bot.config import RepliesConfig
from bot.db import mark_seen
from bot.models import Comment
from bot.personalization import render_template
from bot.templates import select_template
from bot.voyager import VoyagerClient

logger = logging.getLogger(__name__)

CONFIRMATION_ATTEMPTS = 10
CONFIRMATION_WAIT_SECONDS = 3.0
INITIAL_CONFIRMATION_WAIT_SECONDS = 4.0


class ReplyConfirmationError(RuntimeError):
    pass


def _normalize_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).strip()


def _same_author_urn(left: str, right: str) -> bool:
    left_normalized = (_normalize_person_urn(left) or left).lower()
    right_normalized = (_normalize_person_urn(right) or right).lower()
    return left_normalized == right_normalized


def confirm_reply_created(
    client: VoyagerClient,
    comment: Comment,
    own_urn: str,
    reply_text: str,
) -> Comment:
    logger.info(
        "Waiting %.1fs before confirmation polling for parent comment %s",
        INITIAL_CONFIRMATION_WAIT_SECONDS,
        comment.comment_id,
    )
    time.sleep(INITIAL_CONFIRMATION_WAIT_SECONDS)

    expected_text = _normalize_text(reply_text)
    for attempt in range(1, CONFIRMATION_ATTEMPTS + 1):
        logger.info(
            "Confirmation attempt %d/%d for parent comment %s (actor=%s, activity=%s)",
            attempt,
            CONFIRMATION_ATTEMPTS,
            comment.comment_id,
            own_urn,
            comment.activity_id,
        )
        comments = fetch_comments(client, comment.activity_id)
        if not comments:
            logger.warning(
                "Confirmation attempt %d/%d found no comments for activity %s",
                attempt,
                CONFIRMATION_ATTEMPTS,
                comment.activity_id,
            )
        for candidate in comments:
            if (
                candidate.parent_comment_urn == comment.comment_urn
                and _same_author_urn(candidate.author.urn, own_urn)
                and _normalize_text(candidate.text) == expected_text
            ):
                logger.info(
                    "Confirmed reply %s to comment %s on attempt %d",
                    candidate.comment_id,
                    comment.comment_id,
                    attempt,
                )
                return candidate

        if attempt < CONFIRMATION_ATTEMPTS:
            logger.warning(
                "Reply not yet visible for comment %s (attempt %d/%d)",
                comment.comment_id,
                attempt,
                CONFIRMATION_ATTEMPTS,
            )
            time.sleep(CONFIRMATION_WAIT_SECONDS)

    raise ReplyConfirmationError(f"Reply creation could not be confirmed for comment {comment.comment_id}")


def post_reply(
    client: VoyagerClient,
    comment: Comment,
    own_urn: str,
    object_urn: str,
    config: RepliesConfig,
    conn: sqlite3.Connection,
    *,
    post_body_text: str = "",
) -> None:
    sentences, _ = select_template(config, comment.activity_urn, post_body_text)
    sentence_template = random.choice(sentences)
    reply_text = render_template(sentence_template, comment.author.name)
    delay = random.uniform(config.reply_delay_seconds_min, config.reply_delay_seconds_max)
    logger.info("Waiting %.1fs before replying to comment %s", delay, comment.comment_id)
    time.sleep(delay)

    payload = {
        "actor": own_urn,
        "object": object_urn,
        "message": {"text": reply_text},
        "parentComment": comment.comment_urn,
    }
    dash_payload = {
        "commentary": {
            "text": reply_text,
            "attributesV2": [],
            "$type": "com.linkedin.voyager.dash.common.text.TextViewModel",
        },
        "threadUrn": f"urn:li:comment:(activity:{comment.activity_id},{comment.comment_id})",
    }
    page_instance_suffix = secrets.token_hex(8)
    extra_headers = None
    if hasattr(client, "_runtime"):
        runtime = client._runtime
        if hasattr(runtime, "submit_comment_signal"):
            signal_response = runtime.submit_comment_signal(object_urn, page_instance_suffix=page_instance_suffix)
            logger.info(
                "Reply preflight signal response for comment %s: keys=%s",
                comment.comment_id,
                sorted(signal_response.keys()) if isinstance(signal_response, dict) else type(signal_response).__name__,
            )
        if hasattr(runtime, "build_reply_headers"):
            extra_headers = runtime.build_reply_headers(page_instance_suffix=page_instance_suffix)
    logger.info(
        "Posting reply to comment %s (actor URN=%s, object=%s, activity=%s, parent comment=%s): %r",
        comment.comment_id,
        own_urn,
        object_urn,
        comment.activity_id,
        comment.comment_urn,
        reply_text,
    )
    logger.info("Attempting legacy /feed/comments reply contract for comment %s", comment.comment_id)
    response_data = client.post("/feed/comments", json_body=payload, extra_headers=extra_headers)
    logger.info(
        "POST status envelope for comment %s: keys=%s restli_id=%s",
        comment.comment_id,
        sorted(response_data.keys()) if isinstance(response_data, dict) else type(response_data).__name__,
        response_data.get("restliId", "") if isinstance(response_data, dict) else "",
    )
    if isinstance(response_data, dict) and response_data.get("__error"):
        logger.error(
            "Legacy reply POST failed for comment %s: status=%s statusText=%s restli_id=%s body=%r data_keys=%s",
            comment.comment_id,
            response_data.get("status"),
            response_data.get("statusText"),
            response_data.get("restliId", ""),
            response_data.get("body", ""),
            sorted((response_data.get("data") or {}).keys()) if isinstance(response_data.get("data"), dict) else [],
        )
        logger.info("Escalating to Dash reply contract for comment %s", comment.comment_id)
        if hasattr(client, "_runtime") and hasattr(client._runtime, "submit_pre_submit_friction"):
            friction_response = client._runtime.submit_pre_submit_friction(
                object_urn,
                page_instance_suffix=page_instance_suffix,
            )
            logger.info(
                "Reply preSubmitFriction response for comment %s: keys=%s",
                comment.comment_id,
                sorted(friction_response.keys()) if isinstance(friction_response, dict) else type(friction_response).__name__,
            )
        response_data = client._runtime.fetch_json(
            "/voyagerSocialDashNormComments",
            params={"decorationId": "com.linkedin.voyager.dash.deco.social.NormComment-43"},
            method="POST",
            body=dash_payload,
            extra_headers=extra_headers,
        ) if hasattr(client, "_runtime") else client.post(
            "/voyagerSocialDashNormComments",
            json_body=dash_payload,
            extra_headers=extra_headers,
        )
        logger.info(
            "Dash POST status envelope for comment %s: keys=%s restli_id=%s",
            comment.comment_id,
            sorted(response_data.keys()) if isinstance(response_data, dict) else type(response_data).__name__,
            response_data.get("restliId", "") if isinstance(response_data, dict) else "",
        )
        if isinstance(response_data, dict) and response_data.get("__error"):
            logger.error(
                "Dash reply POST failed for comment %s: status=%s statusText=%s restli_id=%s body=%r data_keys=%s",
                comment.comment_id,
                response_data.get("status"),
                response_data.get("statusText"),
                response_data.get("restliId", ""),
                response_data.get("body", ""),
                sorted((response_data.get("data") or {}).keys()) if isinstance(response_data.get("data"), dict) else [],
            )
            raise RuntimeError(
                f"Reply POST rejected for comment {comment.comment_id}: status={response_data.get('status')} statusText={response_data.get('statusText')}"
            )

    restli_id = response_data.get("restliId", "") if isinstance(response_data, dict) else ""
    if restli_id:
        logger.info(
            "Reply confirmed via restliId for comment %s: %s",
            comment.comment_id,
            restli_id,
        )
        mark_seen(conn, comment.comment_id, comment.activity_id, comment.author.urn, "voyager_http")
        logger.info("Reply %s posted and comment %s marked seen", restli_id, comment.comment_id)
        return

    if isinstance(response_data, dict) and not response_data.get("__error"):
        dash_created = bool(response_data.get("data")) or bool(response_data.get("included"))
        if dash_created:
            logger.info(
                "Reply confirmed via Dash 2xx envelope for comment %s (keys=%s)",
                comment.comment_id,
                sorted(response_data.keys()),
            )
            mark_seen(conn, comment.comment_id, comment.activity_id, comment.author.urn, "voyager_http")
            logger.info(
                "Reply posted via Dash contract and comment %s marked seen",
                comment.comment_id,
            )
            return

    logger.info(
        "No restliId and no Dash envelope evidence in POST response for comment %s; falling back to re-fetch confirmation",
        comment.comment_id,
    )
    reply = confirm_reply_created(client, comment, own_urn, reply_text)
    mark_seen(conn, comment.comment_id, comment.activity_id, comment.author.urn, "voyager_http")
    logger.info("Reply %s posted and comment %s marked seen", reply.comment_id, comment.comment_id)
