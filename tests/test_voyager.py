from bot.auth import AuthExpiredError
from bot.rate_limit import RateLimitError
from bot.voyager import VoyagerClient


class FakeRuntime:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def fetch_json(self, path, params=None, method="GET", body=None, extra_headers=None):
        self.calls.append(
            {
                "path": path,
                "params": params,
                "method": method,
                "body": body,
                "extra_headers": extra_headers,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def build_reply_headers(self, *, page_instance_suffix=None):
        return {"x-li-page-instance": page_instance_suffix or "test"}

    def submit_comment_signal(self, thread_urn, *, page_instance_suffix=None):
        self.calls.append(
            {
                "path": "/graphql",
                "params": {"thread_urn": thread_urn},
                "method": "POST",
                "body": {"queryId": "signal"},
                "extra_headers": {"x-li-page-instance": page_instance_suffix or "test"},
            }
        )
        return {"data": {"ok": True}}


def test_get_reuses_runtime_fetch_json():
    runtime = FakeRuntime({"data": {"ok": True}})

    client = VoyagerClient(runtime)
    result = client.get("/feed/comments", params={"count": 100})

    assert result == {"data": {"ok": True}}
    assert runtime.calls == [
        {
            "path": "/feed/comments",
            "params": {"count": 100},
            "method": "GET",
            "body": None,
            "extra_headers": None,
        }
    ]


def test_post_reuses_runtime_fetch_json():
    runtime = FakeRuntime({"data": {"created": True}})

    client = VoyagerClient(runtime)
    result = client.post("/feed/comments", json_body={"message": {"text": "hi"}})

    assert result == {"data": {"created": True}}
    assert runtime.calls == [
        {
            "path": "/feed/comments",
            "params": None,
            "method": "POST",
            "body": {"message": {"text": "hi"}},
            "extra_headers": None,
        }
    ]


def test_runtime_errors_surface_unchanged():
    client = VoyagerClient(FakeRuntime(RateLimitError(3600)))

    try:
        client.get("/feed/comments")
    except RateLimitError as exc:
        assert exc.suggested_wait_seconds == 3600
    else:
        raise AssertionError("RateLimitError should propagate")

    client = VoyagerClient(FakeRuntime(AuthExpiredError("expired")))

    try:
        client.post("/feed/comments", json_body={})
    except AuthExpiredError as exc:
        assert str(exc) == "expired"
    else:
        raise AssertionError("AuthExpiredError should propagate")
