from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Union


def init_db(path: Union[Path, str]) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS seen_comments (
            comment_id TEXT PRIMARY KEY,
            activity_id TEXT NOT NULL,
            author_urn TEXT NOT NULL,
            replied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            reply_mode TEXT NOT NULL CHECK(reply_mode IN ('voyager_http', 'browser_fallback', 'bootstrap_skipped'))
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_activity ON seen_comments(activity_id)")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dm_sent (
            recipient_urn TEXT PRIMARY KEY,
            sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            trigger_comment_id TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_dm_sent_at ON dm_sent(sent_at)")
    conn.commit()
    return conn


def mark_seen(conn: sqlite3.Connection, comment_id: str, activity_id: str, author_urn: str, reply_mode: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO seen_comments (comment_id, activity_id, author_urn, reply_mode) VALUES (?,?,?,?)",
        (comment_id, activity_id, author_urn, reply_mode),
    )
    conn.commit()


def is_seen(conn: sqlite3.Connection, comment_id: str) -> bool:
    row = conn.execute("SELECT 1 FROM seen_comments WHERE comment_id=?", (comment_id,)).fetchone()
    return row is not None


def bulk_mark_seen(conn: sqlite3.Connection, rows: list[tuple[str, str, str, str]]) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO seen_comments (comment_id, activity_id, author_urn, reply_mode) VALUES (?,?,?,?)",
        rows,
    )
    conn.commit()


def mark_dm_sent(
    conn: sqlite3.Connection,
    recipient_urn: str,
    trigger_comment_id: str | None = None,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO dm_sent (recipient_urn, trigger_comment_id) VALUES (?, ?)",
        (recipient_urn, trigger_comment_id),
    )
    conn.commit()


def has_dm_been_sent(conn: sqlite3.Connection, recipient_urn: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM dm_sent WHERE recipient_urn=?", (recipient_urn,)
    ).fetchone()
    return row is not None


def count_dms_sent_today(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) FROM dm_sent
        WHERE date(sent_at) = date('now')
        """
    ).fetchone()
    return int(row[0]) if row else 0
