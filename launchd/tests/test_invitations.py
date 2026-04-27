from typing import cast

from bot.invitations import (
    accept_invitation,
    find_invitation_from,
    list_received_invitations,
)
from bot.voyager import VoyagerClient


class FakeClient:
    def __init__(self, get_response=None, post_response=None):
        self.get_response = get_response
        self.post_response = post_response
        self.get_calls = []
        self.post_calls = []

    def get(self, path, params=None):
        self.get_calls.append((path, params))
        return self.get_response

    def post(self, path, json_body=None, extra_headers=None):
        self.post_calls.append({"path": path, "json_body": json_body, "extra_headers": extra_headers})
        return self.post_response


INVITATION_A = {
    "entityUrn": "urn:li:invitation:6227164820370661376",
    "sharedSecret": "viUrSCUs",
    "*fromMember": "urn:li:fs_miniProfile:ACoAAxyzSenderA1234567890",
}

INVITATION_B = {
    "entityUrn": "urn:li:invitation:7000000000000000000",
    "sharedSecret": "otherSec",
    "*fromMember": "urn:li:fs_miniProfile:ACoAAotherSenderXYZ123",
}


def test_list_received_invitations_parses_flat_elements():
    client = FakeClient(
        get_response={
            "elements": [{"invitation": INVITATION_A}, {"invitation": INVITATION_B}]
        }
    )
    invitations = list_received_invitations(cast(VoyagerClient, client), limit=10)
    assert len(invitations) == 2
    assert invitations[0]["entityUrn"] == INVITATION_A["entityUrn"]


def test_list_received_invitations_parses_normalized_elements():
    client = FakeClient(
        get_response={
            "data": {
                "*elements": ["urn:li:fs_invitationView:view-1"],
            },
            "included": [
                {
                    "entityUrn": "urn:li:fs_invitationView:view-1",
                    "*invitation": "urn:li:invitation:6227164820370661376",
                },
                {
                    "entityUrn": "urn:li:invitation:6227164820370661376",
                    "sharedSecret": "viUrSCUs",
                    "*fromMember": "urn:li:fs_miniProfile:ACoAAxyzSenderA1234567890",
                },
            ],
        }
    )
    invitations = list_received_invitations(cast(VoyagerClient, client), limit=10)
    assert len(invitations) == 1
    assert invitations[0]["sharedSecret"] == "viUrSCUs"


def test_find_invitation_from_matches_by_from_member_urn():
    invitations = [INVITATION_A, INVITATION_B]
    match = find_invitation_from(invitations, "urn:li:person:ACoAAxyzSenderA1234567890")
    assert match is not None
    assert match["entityUrn"] == INVITATION_A["entityUrn"]


def test_find_invitation_from_returns_none_when_no_match():
    invitations = [INVITATION_A, INVITATION_B]
    match = find_invitation_from(invitations, "urn:li:person:ACoAAnonExistentUser999")
    assert match is None


def test_accept_invitation_builds_correct_payload_and_returns_true_on_2xx():
    client = FakeClient(post_response={"status": 200})
    result = accept_invitation(cast(VoyagerClient, client), INVITATION_A)
    assert result is True
    assert len(client.post_calls) == 1
    call = client.post_calls[0]
    assert call["path"] == "/relationships/invitations/6227164820370661376?action=accept"
    body = call["json_body"]
    assert body == {
        "invitationId": "6227164820370661376",
        "invitationSharedSecret": "viUrSCUs",
        "isGenericInvitation": False,
    }


def test_accept_invitation_returns_false_on_error_envelope():
    client = FakeClient(post_response={"__error": True, "status": 400, "statusText": "Bad"})
    assert accept_invitation(cast(VoyagerClient, client), INVITATION_A) is False


def test_accept_invitation_rejects_missing_fields():
    client = FakeClient(post_response={"status": 200})
    assert accept_invitation(cast(VoyagerClient, client), {"entityUrn": "", "sharedSecret": ""}) is False
    assert len(client.post_calls) == 0
