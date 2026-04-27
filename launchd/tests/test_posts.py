from typing import cast

from bot.posts import discover_recent_posts
from bot.voyager import VoyagerClient

OWN_URN = "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
PROFILE_ID = "ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
ACTIVITY_URN = "urn:li:activity:7429135022256791552"


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return self.responses.pop(0) if self.responses else {}


def _profile_resolution_response():
    return {
        "data": {
            "*elements": [f"urn:li:fsd_profile:{PROFILE_ID}"],
        }
    }


def _feed_updates_response(body_text_shape):
    feed_update_urn = "urn:li:fs_feedUpdate:(V2&MEMBER_SHARES," + ACTIVITY_URN + ")"
    update_v2_urn = "urn:li:fs_updateV2:(" + ACTIVITY_URN + ",MEMBER_SHARES,DEFAULT,DEFAULT,false)"
    return {
        "data": {
            "*elements": [feed_update_urn],
            "metadata": {"paginationToken": ""},
        },
        "included": [
            {
                "entityUrn": feed_update_urn,
                "*value": update_v2_urn,
                "urn": ACTIVITY_URN,
            },
            {
                "entityUrn": update_v2_urn,
                "commentary": body_text_shape["commentary"],
                "updateMetadata": {
                    "urn": ACTIVITY_URN,
                    "shareUrn": "urn:li:share:9999",
                },
            },
        ],
    }


def test_post_body_text_extracted_from_commentary_text_text():
    client = FakeClient(
        [
            _profile_resolution_response(),
            _feed_updates_response({"commentary": {"text": {"text": "런칭 소식 공유합니다"}}}),
        ]
    )
    posts = discover_recent_posts(cast(VoyagerClient, client), OWN_URN, lookback_days=3650)
    assert len(posts) == 1
    assert posts[0].body_text == "런칭 소식 공유합니다"


def test_post_body_text_defaults_to_empty_when_missing():
    client = FakeClient(
        [
            _profile_resolution_response(),
            _feed_updates_response({"commentary": {}}),
        ]
    )
    posts = discover_recent_posts(cast(VoyagerClient, client), OWN_URN, lookback_days=3650)
    assert len(posts) == 1
    assert posts[0].body_text == ""
