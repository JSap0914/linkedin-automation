from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from bot.config import DMConfig, RepliesConfig, TemplateConfig
from bot.db import count_dms_sent_today, has_dm_been_sent, init_db, mark_dm_sent
from bot.models import Author, Comment
from bot.orchestrator import _maybe_send_dm
from bot.voyager import VoyagerClient


SENTENCES = ["댓글 감사합니다! 🙏", "관심 가져주셔서 감사해요 😊", "좋은 말씀 감사드립니다!"]
INTERNAL_OWN = "urn:li:person:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
INTERNAL_RECIPIENT = "urn:li:person:ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE"
RECIPIENT_FSD = "urn:li:fsd_profile:ACoAAGAlgWYBxxou3MGXNossEt9eI_MdZ788rLE"


def _make_config(dm_kwargs=None):
    base = dict(
        enabled=True,
        sentences=SENTENCES,
        reply_delay_seconds_min=0,
        reply_delay_seconds_max=1,
        post_lookback_days=30,
        polling_min_interval_seconds=900,
    )
    if dm_kwargs is not None:
        base["dm"] = DMConfig(**dm_kwargs)
    return RepliesConfig(**base)


def _make_comment(author_urn=INTERNAL_RECIPIENT, name="Jisang Han"):
    return Comment(
        comment_urn="urn:li:comment:(activity:111,999)",
        comment_id="999",
        activity_urn="urn:li:activity:111",
        activity_id="111",
        parent_comment_urn=None,
        author=Author(urn=author_urn, name=name),
        text="hi",
        created_at=datetime.now(timezone.utc),
    )


def test_dm_disabled_skips():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = _make_config({"enabled": False, "messages": []})
    with patch("bot.orchestrator.send_direct_message") as send:
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    send.assert_not_called()
    assert not has_dm_been_sent(conn, RECIPIENT_FSD)


def test_dm_enabled_first_degree_sends_and_marks():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": True,
            "messages": ["{name}님 감사합니다"],
            "max_per_day": 0,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    with patch("bot.orchestrator.is_first_degree_connection", return_value=True), patch(
        "bot.orchestrator.send_direct_message", return_value="urn:li:msg_message:ok"
    ) as send, patch("bot.orchestrator.time.sleep"):
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    send.assert_called_once()
    sent_text = send.call_args[0][3]
    assert sent_text == "Jisang Han님 감사합니다"
    assert has_dm_been_sent(conn, RECIPIENT_FSD)


def test_dm_skipped_when_not_first_degree():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": True,
            "messages": ["hi"],
            "max_per_day": 0,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    with patch("bot.orchestrator.is_first_degree_connection", return_value=False), patch(
        "bot.orchestrator.get_pending_invitation", return_value=None
    ), patch(
        "bot.orchestrator.send_direct_message"
    ) as send, patch("bot.orchestrator.time.sleep"):
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    send.assert_not_called()
    assert has_dm_been_sent(conn, RECIPIENT_FSD)


def test_dm_dedup_skips_already_sent():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    mark_dm_sent(conn, RECIPIENT_FSD, trigger_comment_id="earlier")
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": False,
            "messages": ["hi"],
            "max_per_day": 0,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    with patch("bot.orchestrator.send_direct_message") as send:
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    send.assert_not_called()


def test_dm_max_per_day_blocks_further_sends():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    conn.execute(
        "INSERT INTO dm_sent (recipient_urn, sent_at) VALUES (?, datetime('now'))",
        ("urn:li:fsd_profile:OtherTodayUser1234567",),
    )
    conn.commit()
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": False,
            "messages": ["hi"],
            "max_per_day": 1,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    with patch("bot.orchestrator.send_direct_message") as send:
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    send.assert_not_called()


def test_dm_skips_invalid_person_urn():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": False,
            "messages": ["hi"],
            "max_per_day": 0,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    comment = _make_comment(author_urn="urn:li:person:jisang-han-229681372")
    with patch("bot.orchestrator.send_direct_message") as send:
        _maybe_send_dm(client=client, comment=comment, own_urn=INTERNAL_OWN, config=config, conn=conn)
    send.assert_not_called()


def test_non_first_degree_with_pending_invitation_accepts_and_dms():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": True,
            "auto_accept_pending_invitations": True,
            "messages": ["hi"],
            "max_per_day": 0,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    pending_invitation = {
        "entityUrn": "urn:li:fsd_invitation:7451670452932059136",
        "sharedSecret": "ro1sHSxA",
        "invitationId": "7451670452932059136",
    }
    with patch("bot.orchestrator.is_first_degree_connection", side_effect=[False, True]), patch(
        "bot.orchestrator.get_pending_invitation", return_value=pending_invitation
    ), patch("bot.orchestrator.accept_invitation", return_value=True), patch(
        "bot.orchestrator.invalidate_profile_cache"
    ), patch(
        "bot.orchestrator.send_direct_message", return_value="msg-ok"
    ) as send, patch("bot.orchestrator.time.sleep"):
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    send.assert_called_once()
    assert has_dm_been_sent(conn, RECIPIENT_FSD)


def test_non_first_degree_without_pending_invitation_skips_and_marks():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": True,
            "auto_accept_pending_invitations": True,
            "messages": ["hi"],
            "max_per_day": 0,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    with patch("bot.orchestrator.is_first_degree_connection", return_value=False), patch(
        "bot.orchestrator.get_pending_invitation", return_value=None
    ), patch("bot.orchestrator.send_direct_message") as send, patch("bot.orchestrator.time.sleep"):
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    send.assert_not_called()
    assert has_dm_been_sent(conn, RECIPIENT_FSD)


def test_first_degree_does_not_fetch_invitation_list():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": True,
            "auto_accept_pending_invitations": True,
            "messages": ["hi"],
            "max_per_day": 0,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    with patch("bot.orchestrator.is_first_degree_connection", return_value=True), patch(
        "bot.orchestrator.get_pending_invitation"
    ) as invite_mock, patch("bot.orchestrator.send_direct_message", return_value="ok"), patch(
        "bot.orchestrator.time.sleep"
    ):
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    invite_mock.assert_not_called()


def test_auto_accept_flag_disabled_skips_invitation_logic():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = _make_config(
        {
            "enabled": True,
            "only_first_degree_connections": True,
            "auto_accept_pending_invitations": False,
            "messages": ["hi"],
            "max_per_day": 0,
            "delay_seconds_min": 0,
            "delay_seconds_max": 1,
        }
    )
    with patch("bot.orchestrator.is_first_degree_connection", return_value=False), patch(
        "bot.orchestrator.get_pending_invitation"
    ) as invite_mock, patch("bot.orchestrator.send_direct_message") as send, patch(
        "bot.orchestrator.time.sleep"
    ):
        _maybe_send_dm(client=client, comment=_make_comment(), own_urn=INTERNAL_OWN, config=config, conn=conn)
    invite_mock.assert_not_called()
    send.assert_not_called()


def test_maybe_send_dm_uses_per_post_template_when_keyword_matches():
    client = MagicMock(spec=VoyagerClient)
    conn = init_db(":memory:")
    config = RepliesConfig(
        enabled=True,
        sentences=SENTENCES,
        reply_delay_seconds_min=0,
        reply_delay_seconds_max=1,
        post_lookback_days=30,
        polling_min_interval_seconds=900,
        dm=DMConfig(
            enabled=True,
            only_first_degree_connections=False,
            messages=["root-dm"],
            max_per_day=0,
            delay_seconds_min=0,
            delay_seconds_max=1,
        ),
        templates={
            "launch": TemplateConfig(
                keywords=["launch"],
                sentences=[],
                dm_messages=["{name}님 런칭 관련 자료 보내드릴게요"],
            )
        },
    )
    with patch("bot.orchestrator.send_direct_message", return_value="msg-ok") as send, patch(
        "bot.orchestrator.time.sleep"
    ):
        _maybe_send_dm(
            client=client,
            comment=_make_comment(),
            own_urn=INTERNAL_OWN,
            config=config,
            conn=conn,
            post_body_text="Product launch today!",
        )
    send.assert_called_once()
    sent_text = send.call_args[0][3]
    assert sent_text == "Jisang Han님 런칭 관련 자료 보내드릴게요"
