from __future__ import annotations

import logging
from pathlib import Path

from bot.models import Comment

logger = logging.getLogger(__name__)


class BrowserFallbackError(Exception):
    pass


def post_reply_via_browser(profile_dir: Path, comment: Comment, reply_text: str) -> None:
    """Post a reply via browser automation (fallback when Voyager HTTP fails)."""
    import urllib.parse

    from scrapling.fetchers import StealthySession  # type: ignore[reportMissingImports]

    profile_dir = Path(profile_dir)
    post_url = f"https://www.linkedin.com/feed/update/urn:li:activity:{comment.activity_id}"
    comment_urn_encoded = urllib.parse.quote(comment.comment_urn)
    url = f"{post_url}?commentUrn={comment_urn_encoded}"

    success = False

    def perform_reply(page):
        nonlocal success
        try:
            page.wait_for_load_state("networkidle", timeout=30_000)

            reply_btn = None
            for selector in [
                f'[data-id="{comment.comment_urn}"] button[aria-label*="Reply"]',
                'button[aria-label*="Reply"]',
                'button:has-text("Reply")',
            ]:
                try:
                    candidate = page.locator(selector).first
                    if candidate.count():
                        reply_btn = candidate
                        break
                except Exception:
                    continue

            if not reply_btn or not reply_btn.count():
                logger.error("Could not find Reply button on post page")
                return

            if not reply_btn.is_visible():
                logger.error("Reply button found but is not visible")
                return

            reply_btn.click()
            page.wait_for_timeout(1500)

            reply_box = page.locator(
                '.comments-comment-texteditor__contenteditable, .editor-content[contenteditable="true"]'
            ).first
            if not reply_box.count() or not reply_box.is_visible():
                logger.error("Reply editor was not visible after clicking Reply")
                return
            reply_box.click()
            reply_box.type(reply_text, delay=80)
            page.wait_for_timeout(500)

            submit_btn = page.locator(
                'button.comments-comment-box__submit-button, button[aria-label*="Submit"], button:has-text("Post")'
            ).first
            if not submit_btn.count() or not submit_btn.is_visible():
                logger.error("Submit button was not visible for browser fallback")
                return
            submit_btn.click()
            page.wait_for_timeout(3000)
            success = True
            logger.info("Browser fallback entered submit phase for comment %s", comment.comment_id)
        except Exception as exc:
            logger.error("Browser fallback action failed: %s", exc)

    with StealthySession(
        headless=True,
        user_data_dir=str(profile_dir),
        network_idle=True,
        timeout=90_000,
    ) as session:
        final_url = getattr(session.fetch(url, page_action=perform_reply), "url", "")

    if "/login" in final_url or "/authwall" in final_url:
        from bot.auth import AuthExpiredError

        raise AuthExpiredError("Browser session expired during fallback")

    if not success:
        raise BrowserFallbackError(
            f"Failed to post reply via browser for comment {comment.comment_id}"
        )
