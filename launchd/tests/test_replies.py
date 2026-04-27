import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from bot.config import RepliesConfig, TemplateConfig
from bot.db import init_db, is_seen
from bot.models import Author, Comment
from bot.rate_limit import RateLimitError
from bot.replies import ReplyConfirmationError, _same_author_urn, post_reply

SENTENCES = ["댓글 감사합니다! 🙏", "관심 가져주셔서 감사해요 😊", "좋은 말씀 감사드립니다!"]


def make_config():
    return RepliesConfig(
        enabled=True,
        sentences=SENTENCES,
        reply_delay_seconds_min=0,
        reply_delay_seconds_max=1,
        post_lookback_days=30,
        polling_min_interval_seconds=900,
    )


def make_comment():
    return Comment(
        comment_urn="urn:li:comment:(activity:111,999)",
        comment_id="999",
        activity_urn="urn:li:activity:111",
        activity_id="111",
        parent_comment_urn=None,
        author=Author(urn="urn:li:person:OTHER", name="Other"),
        text="hi",
        created_at=datetime.now(timezone.utc),
    )


def test_successful_reply_marks_seen_via_restli_id():
    client = MagicMock()
    client.post.return_value = {"restliId": "urn:li:fsd_comment:(1000,urn:li:activity:111)"}
    conn = init_db(":memory:")
    fetch_mock = MagicMock()
    with patch("bot.replies.time.sleep"), patch("bot.replies.random.choice", return_value=SENTENCES[0]), patch(
        "bot.replies.fetch_comments", fetch_mock
    ):
        post_reply(client, make_comment(), "urn:li:person:OWN", "urn:li:share:111", make_config(), conn)
    assert is_seen(conn, "999")
    assert client.post.called
    fetch_mock.assert_not_called()


def test_successful_reply_falls_back_to_refetch_when_no_restli_id():
    client = MagicMock()
    client.post.return_value = {}
    conn = init_db(":memory:")
    confirmed_reply = Comment(
        comment_urn="urn:li:comment:(activity:111,1000)",
        comment_id="1000",
        activity_urn="urn:li:activity:111",
        activity_id="111",
        parent_comment_urn="urn:li:comment:(activity:111,999)",
        author=Author(urn="urn:li:person:OWN", name="Me"),
        text=SENTENCES[0],
        created_at=datetime.now(timezone.utc),
    )
    with patch("bot.replies.time.sleep"), patch("bot.replies.random.choice", return_value=SENTENCES[0]), patch(
        "bot.replies.fetch_comments", return_value=[confirmed_reply]
    ):
        post_reply(client, make_comment(), "urn:li:person:OWN", "urn:li:share:111", make_config(), conn)
    assert is_seen(conn, "999")
    assert client.post.called


def test_post_reply_applies_name_personalization():
    client = MagicMock()
    client.post.return_value = {"restliId": "urn:li:fsd_comment:(1000,urn:li:activity:111)"}
    conn = init_db(":memory:")
    template = "{name}님 감사합니다"
    commenter = Comment(
        comment_urn="urn:li:comment:(activity:111,999)",
        comment_id="999",
        activity_urn="urn:li:activity:111",
        activity_id="111",
        parent_comment_urn=None,
        author=Author(urn="urn:li:person:OTHER", name="Jisang Han"),
        text="hi",
        created_at=datetime.now(timezone.utc),
    )
    config = RepliesConfig(
        enabled=True,
        sentences=[template, template, template],
        reply_delay_seconds_min=0,
        reply_delay_seconds_max=1,
        post_lookback_days=30,
        polling_min_interval_seconds=900,
    )
    with patch("bot.replies.time.sleep"), patch("bot.replies.random.choice", side_effect=lambda seq: seq[0]):
        post_reply(client, commenter, "urn:li:person:OWN", "urn:li:share:111", config, conn)

    posted_payload = client.post.call_args.kwargs["json_body"]
    assert posted_payload["message"]["text"] == "Jisang Han님 감사합니다"


def test_rate_limit_error_not_marked_seen():
    client = MagicMock()
    client.post.side_effect = RateLimitError(3600)
    conn = init_db(":memory:")
    with patch("bot.replies.time.sleep"):
        with pytest.raises(RateLimitError):
            post_reply(client, make_comment(), "urn:li:person:OWN", "urn:li:share:111", make_config(), conn)
    assert not is_seen(conn, "999")


def test_unconfirmed_reply_not_marked_seen():
    client = MagicMock()
    client.post.return_value = {}
    conn = init_db(":memory:")
    with patch("bot.replies.time.sleep"), patch("bot.replies.fetch_comments", return_value=[]):
        with pytest.raises(ReplyConfirmationError, match="could not be confirmed"):
            post_reply(client, make_comment(), "urn:li:person:OWN", "urn:li:share:111", make_config(), conn)
    assert not is_seen(conn, "999")


def test_delayed_confirmation_still_marks_seen():
    client = MagicMock()
    client.post.return_value = {}
    conn = init_db(":memory:")
    confirmed_reply = Comment(
        comment_urn="urn:li:comment:(activity:111,1001)",
        comment_id="1001",
        activity_urn="urn:li:activity:111",
        activity_id="111",
        parent_comment_urn="urn:li:comment:(activity:111,999)",
        author=Author(urn="urn:li:person:OWN", name="Me"),
        text=SENTENCES[1],
        created_at=datetime.now(timezone.utc),
    )
    with patch("bot.replies.time.sleep"), patch("bot.replies.random.choice", return_value=SENTENCES[1]), patch(
        "bot.replies.fetch_comments", side_effect=[[], [], [confirmed_reply]]
    ):
        post_reply(client, make_comment(), "urn:li:person:OWN", "urn:li:share:111", make_config(), conn)
    assert is_seen(conn, "999")


def test_same_author_urn_normalizes_equivalent_forms():
    assert _same_author_urn(
        "urn:li:fsd_profile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg",
        "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg",
    )


def test_post_reply_uses_per_post_template_when_urn_bound():
    client = MagicMock()
    client.post.return_value = {"restliId": "urn:li:fsd_comment:(1000,urn:li:activity:111)"}
    conn = init_db(":memory:")
    config = RepliesConfig(
        enabled=True,
        sentences=SENTENCES,
        reply_delay_seconds_min=0,
        reply_delay_seconds_max=1,
        post_lookback_days=30,
        polling_min_interval_seconds=900,
        templates={
            "launch": TemplateConfig(
                keywords=[],
                sentences=["{name}님 런칭 전용 답글입니다!"],
                dm_messages=[],
            )
        },
        post_bindings={"urn:li:activity:111": "launch"},
    )
    with patch("bot.replies.time.sleep"):
        post_reply(
            client,
            make_comment(),
            "urn:li:person:OWN",
            "urn:li:share:111",
            config,
            conn,
        )
    posted_payload = client.post.call_args.kwargs["json_body"]
    assert posted_payload["message"]["text"] == "Other님 런칭 전용 답글입니다!"
