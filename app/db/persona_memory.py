from __future__ import annotations

import sqlite3

from app.db.connection import get_connection
from app.db.models import PersonaMemory


def _row_to_memory(row: sqlite3.Row) -> PersonaMemory:
    return PersonaMemory(
        user_id=row["user_id"],
        persona_id=row["persona_id"],
        summary=row["summary"],
        last_summarized_message_id=row["last_summarized_message_id"],
        updated_at=row["updated_at"],
    )


def get_memory(user_id: int, persona_id: int) -> PersonaMemory:
    """Always returns a value - an unmet persona has an empty-summary, zero-watermark memory."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM persona_user_memory WHERE user_id = ? AND persona_id = ?",
            (user_id, persona_id),
        ).fetchone()
    if row is not None:
        return _row_to_memory(row)
    return PersonaMemory(
        user_id=user_id, persona_id=persona_id, summary="", last_summarized_message_id=None, updated_at=""
    )


def upsert_memory(user_id: int, persona_id: int, summary: str, last_summarized_message_id: int) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO persona_user_memory (user_id, persona_id, summary, last_summarized_message_id, updated_at)
            VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
            ON CONFLICT (user_id, persona_id) DO UPDATE SET
                summary = excluded.summary,
                last_summarized_message_id = excluded.last_summarized_message_id,
                updated_at = excluded.updated_at
            """,
            (user_id, persona_id, summary, last_summarized_message_id),
        )
