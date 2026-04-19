from datetime import datetime, timezone
from typing import cast

from bot.comments import _normalize_comment_urn, fetch_comments, filter_to_reply_targets
from bot.db import init_db, mark_seen
from bot.models import Author, Comment
from bot.voyager import VoyagerClient

SAMPLE_AUTHOR = Author(urn="urn:li:person:OTHER123", name="Other Person")
OWN_URN = "urn:li:person:OWN456"


def make_comment(comment_id: str, parent_urn=None, author=None):
    return Comment(
        comment_urn=f"urn:li:comment:(urn:li:activity:111,{comment_id})",
        comment_id=comment_id,
        activity_urn="urn:li:activity:111",
        activity_id="111",
        parent_comment_urn=parent_urn,
        author=author or SAMPLE_AUTHOR,
        text="test",
        created_at=datetime.now(timezone.utc),
    )


def test_filter_excludes_nested():
    conn = init_db(":memory:")
    nested = make_comment("1", parent_urn="urn:li:comment:(urn:li:activity:111,0)")
    result = filter_to_reply_targets([nested], OWN_URN, conn)
    assert result == []


def test_filter_excludes_own_author():
    conn = init_db(":memory:")
    own_comment = make_comment("2", author=Author(urn=OWN_URN, name="Me"))
    result = filter_to_reply_targets([own_comment], OWN_URN, conn)
    assert result == []


def test_filter_excludes_already_seen():
    conn = init_db(":memory:")
    mark_seen(conn, "3", "111", SAMPLE_AUTHOR.urn, "voyager_http")
    seen = make_comment("3")
    result = filter_to_reply_targets([seen], OWN_URN, conn)
    assert result == []


class FakeVoyagerClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params or {}))
        return self.response


def test_fetch_comments_parses_normalized_included_response():
    response = {
        "data": {
            "metadata": {"paginationToken": ""},
            "*elements": [
                "urn:li:fs_objectComment:(7451570843438186496,activity:7429135022256791552)"
            ],
        },
        "included": [
            {
                "$type": "com.linkedin.voyager.feed.Comment",
                "entityUrn": "urn:li:fs_objectComment:(7451570843438186496,activity:7429135022256791552)",
                "dashEntityUrn": "urn:li:fsd_comment:(7451570843438186496,urn:li:activity:7429135022256791552)",
                "commenterProfileId": "ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE",
                "commentV2": {"text": "test"},
                "comment": {"values": [{"value": "test"}]},
                "createdTime": 1_776_594_280_351,
                "parentCommentUrn": None,
                "commenterForDashConversion": {
                    "actorUnion": {
                        "profileUrn": "urn:li:person:ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE"
                    },
                    "image": {
                        "attributes": [
                            {
                                "*miniProfile": "urn:li:fs_miniProfile:ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE"
                            }
                        ]
                    },
                    "title": {"text": "slit slit"},
                },
            },
            {
                "$type": "com.linkedin.voyager.identity.shared.MiniProfile",
                "entityUrn": "urn:li:fs_miniProfile:ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE",
                "firstName": "slit",
                "lastName": "slit",
                "publicIdentifier": "slit-slit",
            },
        ],
    }
    client = FakeVoyagerClient(response)

    comments = fetch_comments(cast(VoyagerClient, client), "7429135022256791552")

    assert client.calls == [
        (
            "/feed/comments",
            {
                "count": 100,
                "start": 0,
                "q": "comments",
                "sortOrder": "RELEVANCE",
                "updateId": "urn:li:activity:7429135022256791552",
            },
        )
    ]
    assert len(comments) == 1
    assert comments[0].comment_urn == "urn:li:comment:(urn:li:activity:7429135022256791552,7451570843438186496)"
    assert comments[0].comment_id == "7451570843438186496"
    assert comments[0].activity_id == "7429135022256791552"
    assert comments[0].author.urn == "urn:li:person:ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE"
    assert comments[0].author.name == "slit slit"
    assert comments[0].text == "test"
    assert comments[0].parent_comment_urn is None


def test_fetch_comments_parses_legacy_elements_response():
    response = {
        "elements": [
            {
                "commentUrn": "urn:li:comment:(activity:111,999)",
                "commenter": {
                    "miniProfile": {
                        "entityUrn": "urn:li:person:OTHER123",
                        "firstName": "Other",
                        "lastName": "Person",
                        "publicIdentifier": "other-person",
                    }
                },
                "commentV2": {"text": "legacy"},
                "createdAt": 1_700_000_000_000,
            }
        ]
    }
    client = FakeVoyagerClient(response)

    comments = fetch_comments(cast(VoyagerClient, client), "111")

    assert len(comments) == 1
    assert comments[0].comment_id == "999"
    assert comments[0].activity_id == "111"
    assert comments[0].author.urn == "urn:li:person:OTHER123"
    assert comments[0].author.name == "Other Person"
    assert comments[0].text == "legacy"


def test_normalize_comment_urn_to_full_activity_form():
    assert _normalize_comment_urn(
        "urn:li:fs_objectComment:(7451570843438186496,activity:7429135022256791552)"
    ) == "urn:li:comment:(urn:li:activity:7429135022256791552,7451570843438186496)"

    assert _normalize_comment_urn(
        "urn:li:comment:(activity:7429135022256791552,7451570843438186496)"
    ) == "urn:li:comment:(urn:li:activity:7429135022256791552,7451570843438186496)"
