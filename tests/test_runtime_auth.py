from pathlib import Path
from typing import Optional

from bot.auth import get_or_discover_own_urn_from_runtime


class FakePageContext:
    def cookies(self):
        return []


class FakePage:
    def __init__(self, href: Optional[str] = None):
        self.url = "https://www.linkedin.com/feed"
        self.context = FakePageContext()
        self._href = href

    def evaluate(self, script):
        return self._href


class FakeRuntime:
    def __init__(self, response, href: Optional[str] = None):
        self.page = FakePage(href=href)
        self.response = response
        self.calls = []

    def fetch_json(self, path, params=None, method="GET", body=None):
        self.calls.append((path, params, method, body))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_get_or_discover_own_urn_from_runtime_uses_voyager_and_caches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runtime = FakeRuntime(
        {
            "data": {
                "*miniProfile": "urn:li:fs_miniProfile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
            }
        }
    )

    own_urn = get_or_discover_own_urn_from_runtime(runtime)

    assert own_urn == "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
    assert runtime.calls == [("/me", None, "GET", None)]
    assert Path(".cache/own_urn").read_text() == own_urn


def test_get_or_discover_own_urn_from_runtime_falls_back_to_dom(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cached_urn = "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
    Path(".cache").mkdir()
    Path(".cache/own_urn").write_text(cached_urn)
    runtime = FakeRuntime(RuntimeError("no voyager"), href="/in/jisang-han-229681372")

    own_urn = get_or_discover_own_urn_from_runtime(runtime)

    assert own_urn == cached_urn
    assert runtime.calls == []
