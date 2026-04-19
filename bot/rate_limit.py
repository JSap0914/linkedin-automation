from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    def __init__(self, suggested_wait_seconds: int = 3600):
        self.suggested_wait_seconds = suggested_wait_seconds
        super().__init__(f"Rate limited. Suggested wait: {suggested_wait_seconds}s")


def check(response) -> None:
    """Raises RateLimitError if any rate-limit signal detected. Call before returning from VoyagerClient."""
    url = getattr(response, "url", "") or ""
    status = getattr(response, "status", 200) or 200
    body = ""
    try:
        body = (getattr(response, "text", "") or "").lower()
    except Exception:
        pass

    # 1. URL redirect patterns (highest priority)
    # Covers: security challenge, auth wall, game-based captcha, re-auth page, login redirect
    for pattern in ("/checkpoint/", "/authwall", "/challenge/", "/reauthentication", "/login"):
        if pattern in url:
            logger.warning("Rate-limit URL pattern detected: %s", pattern)
            raise RateLimitError(suggested_wait_seconds=3600)

    # 2. HTTP status codes
    if status in {429, 999, 410}:
        logger.warning("Rate-limit HTTP status: %s", status)
        raise RateLimitError(suggested_wait_seconds=3600)

    # 3. HTTP 403 with rate-limit body
    if status == 403 and ("rate" in body or "limit" in body):
        logger.warning("HTTP 403 with rate-limit body")
        raise RateLimitError(suggested_wait_seconds=1800)

    # 4. Body text phrases (only for non-2xx or ambiguous)
    for phrase in ("too many requests", "rate limit", "slow down", "try again later"):
        if phrase in body:
            logger.warning("Rate-limit body phrase: %s", phrase)
            raise RateLimitError(suggested_wait_seconds=1800)
