from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class SupportsVoyagerRuntime(Protocol):
    def fetch_json(
        self,
        path: str,
        params: dict | None = None,
        method: str = "GET",
        body: dict | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> Any: ...

    def build_reply_headers(self, *, page_instance_suffix: str | None = None) -> dict[str, str]: ...

    def submit_comment_signal(self, thread_urn: str, *, page_instance_suffix: str | None = None) -> Any: ...

    def submit_pre_submit_friction(self, thread_urn: str, *, page_instance_suffix: str | None = None) -> Any: ...

    def build_messaging_headers(self, *, page_instance_suffix: str | None = None) -> dict[str, str]: ...


class VoyagerClient:
    def __init__(self, runtime: SupportsVoyagerRuntime) -> None:
        self._runtime = runtime

    def get(self, path: str, params: dict | None = None, extra_headers: dict[str, str] | None = None) -> dict:
        logger.debug("GET %s", path)
        return self._runtime.fetch_json(path, params=params, method="GET", extra_headers=extra_headers)

    def post(self, path: str, json_body: dict, extra_headers: dict[str, str] | None = None) -> dict:
        logger.debug("POST %s", path)
        return self._runtime.fetch_json(path, method="POST", body=json_body, extra_headers=extra_headers)
