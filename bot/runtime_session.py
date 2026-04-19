from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from bot.auth import AuthExpiredError
from bot.rate_limit import RateLimitError

FEED_URL = "https://www.linkedin.com/feed"
VOYAGER_BASE_PATH = "/voyager/api"


class LinkedInRuntimeSession:
    def __init__(
        self,
        profile_dir: str | Path = ".profile/",
        *,
        headless: bool = True,
        network_idle: bool = True,
        timeout: int = 60_000,
    ) -> None:
        self.profile_dir = Path(profile_dir)
        self.headless = headless
        self.network_idle = network_idle
        self.timeout = timeout
        self._session = None
        self.context = None
        self.page = None

    def __enter__(self) -> LinkedInRuntimeSession:
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def start(self) -> None:
        if self._session is not None:
            raise RuntimeError("Runtime session already started")

        from scrapling.fetchers import StealthySession  # type: ignore[reportMissingImports]

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._session = StealthySession(
            headless=self.headless,
            user_data_dir=str(self.profile_dir),
            network_idle=self.network_idle,
            timeout=self.timeout,
        )
        self._session.start()
        self.context = self._session.context
        if self.context is None:
            self.close()
            raise RuntimeError("StealthySession did not expose a browser context")

        self.page = self.context.new_page()
        self.page.goto(FEED_URL, wait_until="domcontentloaded", timeout=self.timeout)
        self.page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
        self._check_auth_redirect(self.page.url)

    def close(self) -> None:
        if self.page is not None:
            try:
                if not self.page.is_closed():
                    self.page.close()
            except Exception:
                pass
            self.page = None

        if self._session is not None:
            self._session.close()
            self._session = None

        self.context = None

    def fetch_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        page = self._require_page()
        self._check_auth_redirect(page.url)

        envelope = page.evaluate(
            """
            async (args) => {
                const cookies = document.cookie.split(';').map(cookie => cookie.trim()).filter(Boolean);
                let csrfToken = args.csrfToken || '';
                if (!csrfToken) {
                    for (const cookie of cookies) {
                        if (cookie.startsWith('JSESSIONID=')) {
                            csrfToken = cookie.substring('JSESSIONID='.length).replace(/"/g, '');
                            break;
                        }
                    }
                }

                const url = new URL(args.basePath + args.path, window.location.origin);
                for (const [key, value] of Object.entries(args.params || {})) {
                    if (value !== null && value !== undefined) {
                        url.searchParams.set(key, String(value));
                    }
                }

                const headers = {
                    'accept': 'application/vnd.linkedin.normalized+json+2.1',
                    'x-restli-protocol-version': '2.0.0',
                    'csrf-token': csrfToken,
                };
                const options = {
                    method: args.method,
                    headers,
                };

                if (args.body !== null && args.body !== undefined) {
                    headers['content-type'] = 'application/json';
                    options.body = JSON.stringify(args.body);
                }

                for (const [key, value] of Object.entries(args.extraHeaders || {})) {
                    headers[key.toLowerCase()] = value;
                }

                try {
                    const resp = await fetch(url.toString(), options);
                    const contentType = resp.headers.get('content-type') || '';
                    const restliId = resp.headers.get('x-restli-id') || '';
                    const text = await resp.text();
                    let data = null;

                    if (text) {
                        try {
                            data = JSON.parse(text);
                        } catch (error) {
                            data = null;
                        }
                    }

                    return {
                        ok: resp.ok,
                        status: resp.status,
                        statusText: resp.statusText,
                        responseUrl: resp.url,
                        pageUrl: window.location.href,
                        contentType,
                        restliId,
                        text,
                        data,
                    };
                } catch (error) {
                    return {
                        ok: false,
                        status: 0,
                        statusText: String(error),
                        responseUrl: window.location.href,
                        pageUrl: window.location.href,
                        contentType: '',
                        restliId: '',
                        text: '',
                        data: null,
                        transportError: String(error),
                    };
                }
            }
            """,
            {
                "basePath": VOYAGER_BASE_PATH,
                "path": path,
                "params": params or {},
                "method": method.upper(),
                "body": body,
                "csrfToken": self._csrf_token_from_context(),
                "extraHeaders": extra_headers or {},
            },
        )
        return self._handle_fetch_envelope(envelope)

    def build_reply_headers(self, *, page_instance_suffix: str | None = None) -> dict[str, str]:
        suffix = page_instance_suffix or secrets.token_hex(8)
        li_track = {
            "clientVersion": "1.13.43630",
            "mpVersion": "1.13.43630",
            "osName": "web",
            "timezoneOffset": 9,
            "timezone": "Asia/Seoul",
            "deviceFormFactor": "DESKTOP",
            "mpName": "voyager-web",
            "displayDensity": 2,
            "displayWidth": 3024,
            "displayHeight": 1964,
        }
        return {
            "x-li-lang": "ko_KR",
            "x-li-deco-include-micro-schema": "true",
            "x-li-pem-metadata": "Voyager - Feed - Comments=create-a-comment-reply",
            "x-li-page-instance": f"urn:li:page:d_flagship3_detail_base;{suffix}",
            "x-li-track": json.dumps(li_track, separators=(",", ":")),
        }

    def submit_comment_signal(self, thread_urn: str, *, page_instance_suffix: str | None = None) -> dict[str, Any]:
        query_id = "inSessionRelevanceVoyagerFeedDashClientSignal.c1c9c08097afa4e02954945e9df54091"
        payload = {
            "variables": {
                "backendUpdateUrn": thread_urn,
                "actionType": "submitComment",
            },
            "queryId": query_id,
            "includeWebMetadata": True,
        }
        return self.fetch_json(
            "/graphql",
            params={"action": "execute", "queryId": query_id},
            method="POST",
            body=payload,
            extra_headers=self.build_reply_headers(page_instance_suffix=page_instance_suffix),
        )

    def submit_pre_submit_friction(self, thread_urn: str, *, page_instance_suffix: str | None = None) -> dict[str, Any]:
        query_id = "preSubmitFriction.b31c213182bef51fe7dd771542efa5e2"
        return self.fetch_json(
            "/graphql",
            params={
                "includeWebMetadata": "true",
                "variables": "()",
                "queryId": query_id,
            },
            method="GET",
            extra_headers=self.build_reply_headers(page_instance_suffix=page_instance_suffix),
        )

    def build_messaging_headers(self, *, page_instance_suffix: str | None = None) -> dict[str, str]:
        suffix = page_instance_suffix or secrets.token_hex(8)
        li_track = {
            "clientVersion": "1.13.43630",
            "mpVersion": "1.13.43630",
            "osName": "web",
            "timezoneOffset": 9,
            "timezone": "Asia/Seoul",
            "deviceFormFactor": "DESKTOP",
            "mpName": "voyager-web",
            "displayDensity": 2,
            "displayWidth": 3024,
            "displayHeight": 1964,
        }
        return {
            "accept": "application/json",
            "content-type": "text/plain;charset=UTF-8",
            "x-li-lang": "en_US",
            "x-li-page-instance": f"urn:li:page:d_flagship3_profile_view_base;{suffix}",
            "x-li-track": json.dumps(li_track, separators=(",", ":")),
        }

    def _require_page(self):
        if self.page is None:
            raise RuntimeError("Runtime session has not been started")
        return self.page

    def _csrf_token_from_context(self) -> str:
        if self.context is None:
            return ""

        for cookie in self.context.cookies():
            if cookie.get("name") == "JSESSIONID":
                return cookie.get("value", "").strip('"')
        return ""

    def _check_auth_redirect(self, url: str) -> None:
        if "/login" in url or "/authwall" in url:
            raise AuthExpiredError("Redirected to login/authwall")

    def _handle_fetch_envelope(self, envelope: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(envelope, dict):
            raise RuntimeError("Voyager fetch returned no response envelope")

        response_url = str(envelope.get("responseUrl") or "")
        page_url = str(envelope.get("pageUrl") or getattr(self.page, "url", ""))
        if response_url:
            self._check_auth_redirect(response_url)
        if page_url:
            self._check_auth_redirect(page_url)

        status = int(envelope.get("status") or 0)
        if status in {429, 999, 410}:
            raise RateLimitError(suggested_wait_seconds=3600)
        if status == 403:
            raise RateLimitError(suggested_wait_seconds=1800)
        if status == 401:
            raise AuthExpiredError(f"Session expired (HTTP {status})")

        if envelope.get("transportError"):
            raise RuntimeError(f"Voyager fetch failed: {envelope['transportError']}")

        data = envelope.get("data")
        if envelope.get("ok"):
            if data is None:
                return {}
            if not isinstance(data, dict):
                raise RuntimeError(f"Unexpected Voyager payload type: {type(data).__name__}")
            return data

        error_envelope: dict[str, Any] = {
            "__error": True,
            "status": status,
            "statusText": envelope.get("statusText", ""),
            "restliId": envelope.get("restliId", ""),
        }
        if isinstance(data, dict):
            error_envelope["data"] = data
        elif envelope.get("text"):
            error_envelope["body"] = envelope["text"]
        return error_envelope
