from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

INTERNAL_PERSON_ID_RE = re.compile(r"^[A-Z][A-Za-z0-9_-]{10,}$")


class LoginTimeoutError(Exception):
    pass


class AuthExpiredError(Exception):
    pass


def _check_auth_redirect(url: str) -> None:
    if "/login" in url or "/authwall" in url:
        raise AuthExpiredError("Session expired or redirected to login")


def first_login(profile_dir: Path) -> None:
    """Open a visible browser and wait for the user to log into LinkedIn.

    The Patchright browser profile is persisted to profile_dir automatically.
    On success, the session cookies (li_at, JSESSIONID) are stored in the profile.
    """
    from scrapling.fetchers import StealthySession  # type: ignore[reportMissingImports]
    import time

    profile_dir = Path(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Opening browser for LinkedIn login. Please log in within 5 minutes.")

    login_succeeded = False

    def wait_for_login(page):
        nonlocal login_succeeded
        deadline = time.time() + 300
        while time.time() < deadline:
            current_url = page.url
            if "/feed" in current_url or "/in/" in current_url:
                login_succeeded = True
                logger.info("Login detected at URL: %s", current_url)
                return
            page.wait_for_timeout(2000)
        logger.error("Login timeout: user did not log in within 5 minutes")

    with StealthySession(
        headless=False,
        user_data_dir=str(profile_dir),
        network_idle=True,
        timeout=120_000,
    ) as session:
        session.fetch("https://www.linkedin.com/login", page_action=wait_for_login)

    if not login_succeeded:
        raise LoginTimeoutError("User did not complete LinkedIn login within 5 minutes")

    logger.info("Login complete. Profile saved to %s", profile_dir)


def extract_cookies(profile_dir: Path) -> dict:
    """Extract li_at and JSESSIONID from the persisted browser profile.

    Returns: {"li_at": "...", "JSESSIONID": "ajax:...", "csrf_token": "ajax:..."}
    Raises: AuthExpiredError if li_at is missing or session redirected to login.
    """
    from scrapling.fetchers import StealthySession  # type: ignore[reportMissingImports]

    profile_dir = Path(profile_dir)

    result_holder: list[dict[str, str]] = []

    def page_action(page):
        result_holder.append(extract_cookies_from_page(page))

    with StealthySession(
        headless=True,
        user_data_dir=str(profile_dir),
        network_idle=True,
        timeout=30_000,
    ) as session:
        session.fetch("https://www.linkedin.com/feed", page_action=page_action)

    logger.info("Cookies extracted successfully")
    if not result_holder:
        raise AuthExpiredError("Could not extract cookies from browser session")
    return result_holder[0]


def extract_cookies_from_page(page: Any) -> dict[str, str]:
    _check_auth_redirect(page.url)

    cookies_found: dict[str, str] = {}
    for cookie in page.context.cookies():
        name = cookie.get("name")
        if name == "li_at":
            cookies_found["li_at"] = cookie.get("value", "")
        elif name == "JSESSIONID":
            cookies_found["JSESSIONID"] = cookie.get("value", "")

    li_at = cookies_found.get("li_at")
    jsessionid = cookies_found.get("JSESSIONID", "")
    if not li_at:
        raise AuthExpiredError("Session expired or redirected to login")

    cookies_found["csrf_token"] = jsessionid.strip('"')
    return cookies_found


def get_or_discover_own_urn(cookies: dict) -> str:
    """Return own profile URN, reading from .cache/own_urn if available.

    Uses StealthySession to call the Voyager /me endpoint from inside the browser
    where cookies are valid (HTTP-only requests get redirected to /login).
    Raises: AuthExpiredError if cookies are invalid.
    """
    _ = cookies
    from scrapling.fetchers import StealthySession  # type: ignore[reportMissingImports]
    result_holder: list[str] = []

    with StealthySession(
        headless=True,
        user_data_dir=".profile/",
        network_idle=True,
        timeout=60_000,
    ) as session:
        def page_action(page):
            def fetch_json(path: str) -> dict:
                csrf_token = ""
                for cookie in page.context.cookies():
                    if cookie.get("name") == "JSESSIONID":
                        csrf_token = cookie.get("value", "").strip('"')
                        break

                return page.evaluate(
                    """
                    async (args) => {
                        const resp = await fetch('/voyager/api' + args.path, {
                            headers: {
                                'accept': 'application/vnd.linkedin.normalized+json+2.1',
                                'x-restli-protocol-version': '2.0.0',
                                'csrf-token': args.csrfToken,
                            }
                        });
                        return await resp.json();
                    }
                    """,
                    {"path": path, "csrfToken": csrf_token},
                )

            result_holder.append(_discover_own_urn(page=page, fetch_json=fetch_json))

        session.fetch("https://www.linkedin.com/feed", page_action=page_action)

    if not result_holder:
        raise AuthExpiredError("Could not extract own URN: no result from browser")
    return result_holder[0]


def get_or_discover_own_urn_from_runtime(runtime: Any) -> str:
    cache_path = Path(".cache/own_urn")
    if cache_path.exists():
        cached_urn = cache_path.read_text().strip()
        if _looks_internal_person_urn(cached_urn):
            logger.info("Own URN loaded from cache: %s", cached_urn)
            return cached_urn

    page = runtime.page
    if page is None:
        raise AuthExpiredError("Could not extract own URN: runtime page is unavailable")
    return _discover_own_urn(page=page, fetch_json=lambda path: runtime.fetch_json(path), cache_path=cache_path)


def _discover_own_urn(
    page: Any,
    fetch_json: Any,
    cache_path: Path | None = None,
) -> str:
    cache_path = cache_path or Path(".cache/own_urn")
    _check_auth_redirect(page.url)

    person_urn: str | None = None
    try:
        data = fetch_json("/me")
        person_urn = _extract_internal_person_urn_from_me_response(data)
    except Exception as exc:
        logger.warning("Voyager /me fetch failed: %s; trying DOM fallback", exc)

    if not person_urn:
        try:
            href = page.evaluate(
                """
                () => {
                    const el = document.querySelector('a[href*="/in/"]');
                    return el ? el.getAttribute('href') : null;
                }
                """
            )
        except Exception as exc:
            logger.error("DOM fallback also failed: %s", exc)
            href = None

        match = re.search(r"/in/([^/?#]+)", href or "")
        if match:
            person_urn = f"urn:li:person:{match.group(1)}"

    person_urn = _coerce_person_urn(person_urn)
    if not person_urn or not _looks_internal_person_urn(person_urn):
        raise AuthExpiredError(
            f"Resolved own URN is not an internal person URN and is unsafe for posting: {person_urn}"
        )

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(person_urn)

    logger.info("Own URN discovered and cached: %s", person_urn)
    return person_urn


def _coerce_person_urn(person_urn: str | None) -> str | None:
    if not person_urn:
        return None
    if person_urn.startswith("urn:li:fsd_profile:"):
        person_id = person_urn.split(":")[-1]
        return f"urn:li:person:{person_id}"
    if not person_urn.startswith("urn:li:person:"):
        parts = person_urn.rsplit(":", 1)
        if len(parts) == 2:
            return f"urn:li:person:{parts[1]}"
    return person_urn


def _extract_internal_person_urn_from_me_response(data: dict) -> str | None:
    candidates: list[str] = []

    me_data = data.get("data") or {}
    for key in ("*miniProfile", "miniProfile", "entityUrn", "dashEntityUrn", "objectUrn"):
        value = me_data.get(key)
        if isinstance(value, str):
            candidates.append(value)

    for item in data.get("included") or []:
        if not isinstance(item, dict):
            continue
        for key in ("dashEntityUrn", "entityUrn", "objectUrn"):
            value = item.get(key)
            if isinstance(value, str):
                candidates.append(value)
        mini = item.get("miniProfile") or {}
        if isinstance(mini, dict):
            for key in ("dashEntityUrn", "entityUrn", "objectUrn"):
                value = mini.get(key)
                if isinstance(value, str):
                    candidates.append(value)

    plain_id = me_data.get("plainId") or me_data.get("id")
    if plain_id:
        candidates.append(f"urn:li:member:{plain_id}")

    for candidate in candidates:
        normalized = _normalize_person_urn(candidate)
        if normalized and _looks_internal_person_urn(normalized):
            return normalized

    return None


def _normalize_person_urn(candidate: str) -> str | None:
    if candidate.startswith("urn:li:person:"):
        return candidate
    if candidate.startswith(("urn:li:fsd_profile:", "urn:li:fs_miniProfile:", "urn:li:member:")):
        return f"urn:li:person:{candidate.rsplit(':', 1)[-1]}"
    return None


def _looks_internal_person_urn(person_urn: str) -> bool:
    normalized = _normalize_person_urn(person_urn)
    if not normalized:
        return False
    person_id = normalized.rsplit(":", 1)[-1]
    return bool(INTERNAL_PERSON_ID_RE.match(person_id))
