from __future__ import annotations

import json
import sqlite3

from app.db.connection import get_connection
from app.db.models import Conversation, ItemOutcome, Message, MessageRole


def _row_to_conversation(row: sqlite3.Row) -> Conversation:
    return Conversation(
        id=row["id"],
        user_id=row["user_id"],
        persona_id=row["persona_id"],
        topic=row["topic"],
        claude_session_id=row["claude_session_id"],
        target_item_ids=json.loads(row["target_item_ids_json"]),
        started_at=row["started_at"],
    )


def _row_to_message(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        text=row["text"],
        created_at=row["created_at"],
    )


def create_conversation(user_id: int, persona_id: int, topic: str, target_item_ids: list[int]) -> Conversation:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO conversations (user_id, persona_id, topic, target_item_ids_json) VALUES (?, ?, ?, ?)",
            (user_id, persona_id, topic, json.dumps(target_item_ids)),
        )
        conversation_id = cur.lastrowid
        if conversation_id is None:
            raise RuntimeError("insert into conversations did not return a row id")
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return _row_to_conversation(row)


def get_conversation(conversation_id: int) -> Conversation | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return _row_to_conversation(row) if row is not None else None


def add_message(conversation_id: int, role: MessageRole, text: str) -> Message:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO messages (conversation_id, role, text) VALUES (?, ?, ?)",
            (conversation_id, role, text),
        )
        message_id = cur.lastrowid
        if message_id is None:
            raise RuntimeError("insert into messages did not return a row id")
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    return _row_to_message(row)


def get_messages(conversation_id: int) -> list[Message]:
    # created_at has only millisecond precision - id is the tiebreaker that actually guarantees
    # insertion order when two messages land in the same millisecond.
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id ASC",
            (conversation_id,),
        ).fetchall()
    return [_row_to_message(row) for row in rows]


def set_claude_session_id(conversation_id: int, claude_session_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE conversations SET claude_session_id = ? WHERE id = ?",
            (claude_session_id, conversation_id),
        )


def get_judged_item_ids(conversation_id: int) -> set[int]:
    """Item ids that already got an outcome recorded earlier in this conversation - once an item
    has a definitive outcome, later unrelated messages shouldn't re-judge it (and risk marking it
    "avoided" just because that message happened to be about something else)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT e.item_id
            FROM message_item_events e
            JOIN messages m ON m.id = e.message_id
            WHERE m.conversation_id = ?
            """,
            (conversation_id,),
        ).fetchall()
    return {row["item_id"] for row in rows}


def list_conversations(user_id: int) -> list[Conversation]:
    # started_at has only millisecond precision - id is the tiebreaker that actually guarantees
    # insertion order when two conversations land in the same millisecond.
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? ORDER BY started_at DESC, id DESC", (user_id,)
        ).fetchall()
    return [_row_to_conversation(row) for row in rows]


def get_recent_topics(user_id: int, limit: int = 5) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT topic FROM conversations WHERE user_id = ? ORDER BY started_at DESC, id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [row["topic"] for row in rows]


def add_item_event(message_id: int, item_id: int, outcome: ItemOutcome) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO message_item_events (message_id, item_id, outcome) VALUES (?, ?, ?)",
            (message_id, item_id, outcome),
        )


def get_most_recent_persona_id(user_id: int) -> int | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT persona_id FROM conversations WHERE user_id = ? ORDER BY started_at DESC, id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
    return row["persona_id"] if row is not None else None


def get_messages_with_persona_after(user_id: int, persona_id: int, after_message_id: int) -> list[Message]:
    """Every message from any of this user's conversations with this persona, newer than
    `after_message_id` - used to catch up a persona's relationship memory across conversations."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT m.*
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE c.user_id = ? AND c.persona_id = ? AND m.id > ?
            ORDER BY m.id ASC
            """,
            (user_id, persona_id, after_message_id),
        ).fetchall()
    return [_row_to_message(row) for row in rows]
