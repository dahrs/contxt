from __future__ import annotations

import sqlite3

from app.db.connection import get_connection
from app.db.models import EngagementTopic, EngagementValence


def _row_to_topic(row: sqlite3.Row) -> EngagementTopic:
    return EngagementTopic(
        id=row["id"],
        user_id=row["user_id"],
        topic=row["topic"],
        valence=row["valence"],
        follow_up_note=row["follow_up_note"],
        surfaced_at=row["surfaced_at"],
        created_at=row["created_at"],
    )


def add_engagement_topic(user_id: int, topic: str, valence: EngagementValence, follow_up_note: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO engagement_topics (user_id, topic, valence, follow_up_note) VALUES (?, ?, ?, ?)",
            (user_id, topic, valence, follow_up_note),
        )


def get_unsurfaced_engagement_topics(user_id: int, limit: int) -> list[EngagementTopic]:
    """Most recently observed first - a fresh engagement signal is more worth following up on than
    one from months ago, and `limit` keeps a single session prompt from being handed a growing
    backlog of everything ever noticed."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM engagement_topics WHERE user_id = ? AND surfaced_at IS NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [_row_to_topic(row) for row in rows]


def mark_engagement_topics_surfaced(topic_ids: list[int]) -> None:
    if not topic_ids:
        return
    with get_connection() as conn:
        conn.executemany(
            "UPDATE engagement_topics SET surfaced_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = ?",
            [(topic_id,) for topic_id in topic_ids],
        )
