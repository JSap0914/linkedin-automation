from __future__ import annotations

import logging
import importlib.util
import random
import sqlite3
import sys
import time
from collections.abc import Callable
from pathlib import Path

from bot.auth import AuthExpiredError, extract_cookies_from_page, get_or_discover_own_urn_from_runtime
from bot.comments import fetch_comments, filter_to_reply_targets
from bot.config import RepliesConfig, load_config
from bot.connections import get_pending_invitation, invalidate_profile_cache, is_first_degree_connection
from bot.db import bulk_mark_seen, count_dms_sent_today, has_dm_been_sent, init_db, mark_dm_sent, mark_seen
from bot.invitations import accept_invitation, find_invitation_from, list_received_invitations
from bot.killswitch import check_kill_switch
from bot.lockfile import AlreadyRunningError, acquire_lock
from bot.logging_config import configure_logging
from bot.messaging import DMSendError, send_direct_message
from bot.models import Comment
from bot.personalization import render_template
from bot.posts import discover_recent_posts
from bot.rate_limit import RateLimitError
from bot.replies import ReplyConfirmationError, confirm_reply_created, post_reply
from bot.runtime_session import LinkedInRuntimeSession
from bot.templates import select_template
from bot.urn import person_to_fsd_profile_urn
from bot.voyager import VoyagerClient

logger = logging.getLogger(__name__)

EXIT_RATE_LIMITED = 3
EXIT_AUTH_EXPIRED = 4


def _load_browser_fallback() -> Callable[..., None]:
    fallback_path = Path(__file__).with_name("browser_fallback.py")
    spec = importlib.util.spec_from_file_location("linkedin_autoreply_browser_fallback", fallback_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load browser fallback from {fallback_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.post_reply_via_browser


_cached_invitations: list[dict] | None = None


def _reset_invitation_cache() -> None:
    global _cached_invitations
    _cached_invitations = None


def _try_accept_pending_invitation(
    *,
    client: VoyagerClient,
    comment: Comment,
) -> bool:
    invitation = get_pending_invitation(client, comment.author.urn)

    if invitation is None:
        logger.info(
            "No pending invitation embedded in profile for %s (comment %s)",
            comment.author.urn,
            comment.comment_id,
        )
        return False

    logger.info(
        "Pending invitation %s from %s found in profile response; accepting before DM retry",
        invitation.get("entityUrn"),
        comment.author.urn,
    )
    try:
        accepted = accept_invitation(client, invitation)
    except Exception as exc:
        logger.warning("Exception while accepting invitation: %s", exc)
        return False

    if not accepted:
        logger.warning(
            "Invitation accept did not succeed for %s",
            comment.author.urn,
        )
        return False

    invalidate_profile_cache(comment.author.urn)

    time.sleep(5)

    if not is_first_degree_connection(client, comment.author.urn):
        logger.warning(
            "After accepting invitation from %s, 1st-degree check still returned False",
            comment.author.urn,
        )
        return False

    return True


def _maybe_send_dm(
    *,
    client: VoyagerClient,
    comment: Comment,
    own_urn: str,
    config: RepliesConfig,
    conn: sqlite3.Connection,
    post_body_text: str = "",
) -> None:
    dm_config = config.dm
    if not dm_config.enabled:
        logger.info("DM skipped for comment %s: dm.enabled=false", comment.comment_id)
        return

    _, dm_messages = select_template(config, comment.activity_urn, post_body_text)
    if not dm_messages:
        logger.info("DM skipped for comment %s: no DM messages configured", comment.comment_id)
        return

    try:
        recipient_fsd = person_to_fsd_profile_urn(comment.author.urn)
    except ValueError:
        logger.info(
            "DM skipped for comment %s: commenter URN is not postable (%s)",
            comment.comment_id,
            comment.author.urn,
        )
        return

    if has_dm_been_sent(conn, recipient_fsd):
        logger.info(
            "DM skipped for comment %s: recipient %s already has a DM record",
            comment.comment_id,
            recipient_fsd,
        )
        return

    if dm_config.max_per_day > 0:
        sent_today = count_dms_sent_today(conn)
        if sent_today >= dm_config.max_per_day:
            logger.info(
                "DM skipped for comment %s: daily cap reached (%d / %d)",
                comment.comment_id,
                sent_today,
                dm_config.max_per_day,
            )
            return

    if dm_config.only_first_degree_connections:
        if not is_first_degree_connection(client, comment.author.urn):
            accepted = False
            if dm_config.auto_accept_pending_invitations:
                accepted = _try_accept_pending_invitation(
                    client=client,
                    comment=comment,
                )
            if not accepted:
                logger.info(
                    "DM skipped for comment %s: %s is not a 1st-degree connection and no pending invitation auto-accepted",
                    comment.comment_id,
                    comment.author.urn,
                )
                mark_dm_sent(conn, recipient_fsd, trigger_comment_id=comment.comment_id)
                return

    message_template = random.choice(dm_messages)
    message_text = render_template(message_template, comment.author.name)

    delay = random.uniform(dm_config.delay_seconds_min, dm_config.delay_seconds_max)
    logger.info("Waiting %.1fs before sending DM to %s", delay, recipient_fsd)
    time.sleep(delay)

    try:
        send_direct_message(client, comment.author.urn, own_urn, message_text)
    except DMSendError as exc:
        logger.error("DM send failed for comment %s: %s", comment.comment_id, exc)
        return
    except Exception as exc:
        logger.error("Unexpected DM error for comment %s: %s", comment.comment_id, exc)
        return

    mark_dm_sent(conn, recipient_fsd, trigger_comment_id=comment.comment_id)
    logger.info("DM sent and marked for recipient %s (comment %s)", recipient_fsd, comment.comment_id)


def run(dry_run: bool = False, bootstrap: bool = False) -> None:
    configure_logging(Path("logs/bot.log"))
    config = load_config()
    check_kill_switch(config)

    try:
        with acquire_lock(Path("logs/bot.lock")):
            _run_inner(config, dry_run=dry_run, bootstrap=bootstrap)
    except AlreadyRunningError as exc:
        logger.error("Bot already running: %s", exc)
        sys.exit(1)
    except RateLimitError as exc:
        logger.warning("Rate limited. Wait %ds before next run.", exc.suggested_wait_seconds)
        sys.exit(EXIT_RATE_LIMITED)
    except AuthExpiredError as exc:
        logger.error("Auth expired: %s. Run setup.py again.", exc)
        sys.exit(EXIT_AUTH_EXPIRED)
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        sys.exit(1)


def _run_inner(config: RepliesConfig, dry_run: bool, bootstrap: bool) -> None:
    _reset_invitation_cache()
    conn = init_db(Path("seen_comments.db"))

    try:
        with LinkedInRuntimeSession(profile_dir=Path(".profile/")) as runtime:
            extract_cookies_from_page(runtime.page)
            own_urn = get_or_discover_own_urn_from_runtime(runtime)
            client = VoyagerClient(runtime)

            posts = discover_recent_posts(client, own_urn, config.post_lookback_days)
            logger.info("Found %d recent posts to check", len(posts))

            total_replied = 0
            for post in posts:
                comments = fetch_comments(client, post.activity_id)
                targets = filter_to_reply_targets(comments, own_urn, conn)

                if bootstrap:
                    rows = [
                        (comment.comment_id, comment.activity_id, comment.author.urn, "bootstrap_skipped")
                        for comment in targets
                    ]
                    if rows:
                        bulk_mark_seen(conn, rows)
                        logger.info(
                            "Bootstrap: marked %d comments seen on post %s",
                            len(rows),
                            post.activity_id,
                        )
                    continue

                for comment in targets:
                    if dry_run:
                        reply_text = random.choice(config.sentences)
                        logger.info(
                            "Dry run: would reply to %s with %r",
                            comment.comment_id,
                            reply_text,
                        )
                        continue

                    reply_succeeded = False
                    post_body_text = getattr(post, "body_text", "")
                    try:
                        object_urn = getattr(post, "object_urn", post.activity_urn)
                        post_reply(
                            client,
                            comment,
                            own_urn,
                            object_urn,
                            config,
                            conn,
                            post_body_text=post_body_text,
                        )
                        total_replied += 1
                        reply_succeeded = True
                    except RateLimitError:
                        raise
                    except ReplyConfirmationError as exc:
                        logger.error(
                            "Reply confirmation failed for %s (POST likely succeeded but could not verify): %s",
                            comment.comment_id,
                            exc,
                        )
                    except Exception as exc:
                        logger.error("Failed to post reply to %s: %s", comment.comment_id, exc)

                    if reply_succeeded:
                        try:
                            _maybe_send_dm(
                                client=client,
                                comment=comment,
                                own_urn=own_urn,
                                config=config,
                                conn=conn,
                                post_body_text=post_body_text,
                            )
                        except RateLimitError:
                            raise
                        except Exception as dm_exc:
                            logger.error(
                                "DM step raised unexpectedly for comment %s: %s",
                                comment.comment_id,
                                dm_exc,
                            )

        if bootstrap:
            logger.info("Bootstrap complete")
        elif dry_run:
            logger.info("Dry run complete")
        else:
            logger.info("Replied to %d comments across %d posts", total_replied, len(posts))
    finally:
        conn.close()
