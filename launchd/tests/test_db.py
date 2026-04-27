
from bot.db import (
    bulk_mark_seen,
    count_dms_sent_today,
    has_dm_been_sent,
    init_db,
    is_seen,
    mark_dm_sent,
    mark_seen,
)


def test_init_creates_table(tmp_path):
    conn = init_db(tmp_path / "db.sqlite")
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='seen_comments'"
    ).fetchone()
    assert tables is not None


def test_mark_and_is_seen(tmp_path):
    conn = init_db(tmp_path / "db.sqlite")
    assert not is_seen(conn, "c1")
    mark_seen(conn, "c1", "a1", "urn:li:person:U1", "voyager_http")
    assert is_seen(conn, "c1")


def test_duplicate_mark_seen_idempotent(tmp_path):
    conn = init_db(tmp_path / "db.sqlite")
    mark_seen(conn, "c1", "a1", "urn:li:person:U1", "voyager_http")
    mark_seen(conn, "c1", "a2", "urn:li:person:U2", "browser_fallback")
    count = conn.execute("SELECT COUNT(*) FROM seen_comments WHERE comment_id='c1'").fetchone()[0]
    assert count == 1


def test_bulk_mark_seen_inserts_rows(tmp_path):
    conn = init_db(tmp_path / "db.sqlite")
    bulk_mark_seen(
        conn,
        [
            ("c1", "a1", "urn:li:person:U1", "voyager_http"),
            ("c2", "a1", "urn:li:person:U2", "browser_fallback"),
        ],
    )
    assert is_seen(conn, "c1")
    assert is_seen(conn, "c2")


def test_init_creates_dm_sent_table(tmp_path):
    conn = init_db(tmp_path / "db.sqlite")
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='dm_sent'"
    ).fetchone()
    assert row is not None


def test_mark_and_has_dm_been_sent(tmp_path):
    conn = init_db(tmp_path / "db.sqlite")
    recipient = "urn:li:fsd_profile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
    assert not has_dm_been_sent(conn, recipient)
    mark_dm_sent(conn, recipient, trigger_comment_id="c1")
    assert has_dm_been_sent(conn, recipient)


def test_mark_dm_sent_is_idempotent(tmp_path):
    conn = init_db(tmp_path / "db.sqlite")
    recipient = "urn:li:fsd_profile:ACoAAFxKuAEB2uYSY5bKNUovRFAO8QRcvS4wXzg"
    mark_dm_sent(conn, recipient, trigger_comment_id="c1")
    mark_dm_sent(conn, recipient, trigger_comment_id="c2")
    count = conn.execute(
        "SELECT COUNT(*) FROM dm_sent WHERE recipient_urn=?", (recipient,)
    ).fetchone()[0]
    assert count == 1


def test_count_dms_sent_today_excludes_older_entries(tmp_path):
    conn = init_db(tmp_path / "db.sqlite")
    conn.execute(
        "INSERT INTO dm_sent (recipient_urn, sent_at) VALUES (?, datetime('now'))",
        ("urn:li:fsd_profile:TodayOne1234567",),
    )
    conn.execute(
        "INSERT INTO dm_sent (recipient_urn, sent_at) VALUES (?, datetime('now', '-2 days'))",
        ("urn:li:fsd_profile:OldTwo123456789",),
    )
    conn.commit()
    assert count_dms_sent_today(conn) == 1
