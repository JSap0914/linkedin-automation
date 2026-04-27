from typing import cast

from bot.connections import (
    DASH_PROFILES_PATH,
    PRIMARY_DECORATION_ID,
    clear_cache,
    is_first_degree_connection,
)
from bot.rate_limit import RateLimitError
from bot.voyager import VoyagerClient


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def setup_function():
    clear_cache()


def _distance_response(distance_value: str) -> dict:
    return {
        "data": {
            "data": {
                "identityDashProfilesByMemberIdentity": {
                    "*elements": ["urn:li:fsd_profile:ACoAAx"],
                }
            }
        },
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.identity.profile.Profile",
                "entityUrn": "urn:li:fsd_profile:ACoAAx",
                "memberDistance": {"value": distance_value},
            }
        ],
    }


INTERNAL_PERSON = "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"


def test_first_degree_detected_from_member_distance():
    client = FakeClient(_distance_response("DISTANCE_1"))
    assert is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)
    path, params = client.calls[0]
    assert path == DASH_PROFILES_PATH
    assert params["q"] == "memberIdentity"
    assert params["decorationId"] == PRIMARY_DECORATION_ID
    assert params["memberIdentity"] == "ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"


def test_second_degree_returns_false():
    client = FakeClient(_distance_response("DISTANCE_2"))
    assert not is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)


def test_out_of_network_returns_false():
    client = FakeClient(_distance_response("OUT_OF_NETWORK"))
    assert not is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)


def test_distance_as_bare_string_supported():
    client = FakeClient(
        {
            "included": [
                {"memberDistance": "DISTANCE_1"},
            ]
        }
    )
    assert is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)


def test_network_error_returns_false():
    client = FakeClient(RuntimeError("boom"))
    assert not is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)


def test_rate_limit_propagates():
    client = FakeClient(RateLimitError(3600))
    try:
        is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)
    except RateLimitError:
        pass
    else:
        raise AssertionError("Expected RateLimitError to propagate")


def test_missing_distance_field_returns_false():
    client = FakeClient({"data": {"unrelated": "value"}, "included": []})
    assert not is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)


def test_invalid_urn_returns_false():
    client = FakeClient(_distance_response("DISTANCE_1"))
    assert not is_first_degree_connection(cast(VoyagerClient, client), "not-a-urn")


def test_cache_returns_same_result_without_re_calling():
    client = FakeClient(_distance_response("DISTANCE_1"))
    first = is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)
    second = is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)
    assert first and second
    assert len(client.calls) == 1


def test_member_relationship_with_connection_is_first_degree():
    response = {
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.relationships.MemberRelationship",
                "memberRelationshipUnion": {
                    "*connection": "urn:li:fsd_connection:ACoAAxYz"
                },
                "memberRelationshipData": {
                    "*connection": "urn:li:fsd_connection:ACoAAxYz"
                },
            }
        ]
    }
    client = FakeClient(response)
    assert is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)


def test_connection_entry_with_connected_member_is_first_degree():
    response = {
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.relationships.Connection",
                "connectedMember": "urn:li:fsd_profile:ACoAAxYz",
                "entityUrn": "urn:li:fsd_connection:ACoAAxYz",
            }
        ]
    }
    client = FakeClient(response)
    assert is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)


def test_member_relationship_no_connection_is_not_first_degree():
    response = {
        "included": [
            {
                "$type": "com.linkedin.voyager.dash.relationships.MemberRelationship",
                "memberRelationshipUnion": {
                    "*noConnection": "urn:li:fsd_noConnection:ACoAAxYz"
                },
            }
        ]
    }
    client = FakeClient(response)
    assert not is_first_degree_connection(cast(VoyagerClient, client), INTERNAL_PERSON)
