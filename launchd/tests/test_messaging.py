from typing import cast
from unittest.mock import MagicMock

import pytest

from bot.messaging import DMSendError, send_direct_message
from bot.voyager import VoyagerClient


class FakeRuntime:
    def __init__(self, response):
        self.response = response
        self.fetch_calls = []

    def fetch_json(self, path, params=None, method="GET", body=None, extra_headers=None):
        self.fetch_calls.append(
            {
                "path": path,
                "params": params,
                "method": method,
                "body": body,
                "extra_headers": extra_headers,
            }
        )
        return self.response

    def build_messaging_headers(self, *, page_instance_suffix=None):
        return {
            "accept": "application/json",
            "content-type": "text/plain;charset=UTF-8",
            "x-li-lang": "en_US",
            "x-li-page-instance": f"urn:li:page:d_flagship3_profile_view_base;{page_instance_suffix or 'test'}",
        }


INTERNAL_OWN = "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
INTERNAL_RECIPIENT = "urn:li:person:ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE"


def test_send_direct_message_posts_expected_payload():
    runtime = FakeRuntime({"restliId": "urn:li:msg_message:abc123"})
    client = VoyagerClient(runtime)

    result = send_direct_message(client, INTERNAL_RECIPIENT, INTERNAL_OWN, "안녕하세요")

    assert result == "urn:li:msg_message:abc123"
    assert len(runtime.fetch_calls) == 1
    call = runtime.fetch_calls[0]
    assert call["path"] == "/voyagerMessagingDashMessengerMessages"
    assert call["params"] == {"action": "createMessage"}
    assert call["method"] == "POST"
    body = call["body"]
    assert body["dedupeByClientGeneratedToken"] is False
    assert body["hostRecipientUrns"] == [
        "urn:li:fsd_profile:ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE"
    ]
    assert body["mailboxUrn"] == "urn:li:fsd_profile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
    assert body["message"]["body"]["text"] == "안녕하세요"
    assert body["message"]["body"]["attributes"] == []
    assert body["message"]["renderContentUnions"] == []
    assert isinstance(body["message"]["originToken"], str)
    assert len(body["message"]["originToken"]) >= 32
    assert isinstance(body["trackingId"], str)
    assert len(body["trackingId"]) == 16


def test_origin_token_is_unique_each_call():
    runtime = FakeRuntime({"restliId": "urn:li:msg_message:abc"})
    client = VoyagerClient(runtime)
    send_direct_message(client, INTERNAL_RECIPIENT, INTERNAL_OWN, "hi")
    send_direct_message(client, INTERNAL_RECIPIENT, INTERNAL_OWN, "hi2")
    tokens = {call["body"]["message"]["originToken"] for call in runtime.fetch_calls}
    assert len(tokens) == 2


def test_messaging_headers_applied():
    runtime = FakeRuntime({"restliId": "urn:li:msg_message:x"})
    client = VoyagerClient(runtime)
    send_direct_message(client, INTERNAL_RECIPIENT, INTERNAL_OWN, "hi")
    headers = runtime.fetch_calls[0]["extra_headers"]
    assert headers is not None
    assert headers["content-type"] == "text/plain;charset=UTF-8"
    assert headers["accept"] == "application/json"


def test_error_envelope_raises_dm_send_error():
    runtime = FakeRuntime({"__error": True, "status": 400, "statusText": "Bad Request", "data": {}})
    client = VoyagerClient(runtime)
    with pytest.raises(DMSendError):
        send_direct_message(client, INTERNAL_RECIPIENT, INTERNAL_OWN, "hi")


def test_rejects_vanity_slug_recipient():
    runtime = FakeRuntime({"restliId": ""})
    client = VoyagerClient(runtime)
    with pytest.raises(ValueError):
        send_direct_message(client, "urn:li:person:jisang-han-229681372", INTERNAL_OWN, "hi")
