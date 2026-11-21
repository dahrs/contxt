from __future__ import annotations

import sqlite3

from app.db.connection import get_connection
from app.db.models import UserItemState


def _row_to_state(row: sqlite3.Row) -> UserItemState:
    return UserItemState(
        user_id=row["user_id"],
        item_id=row["item_id"],
        fsrs_card_json=row["fsrs_card_json"],
        reps=row["reps"],
        lapses=row["lapses"],
        last_reviewed_at=row["last_reviewed_at"],
        due_at=row["due_at"],
    )


def get_state(user_id: int, item_id: int) -> UserItemState | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM user_item_state WHERE user_id = ? AND item_id = ?", (user_id, item_id)
        ).fetchone()
    return _row_to_state(row) if row is not None else None


def upsert_state(state: UserItemState) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO user_item_state
                (user_id, item_id, fsrs_card_json, reps, lapses, last_reviewed_at, due_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (user_id, item_id) DO UPDATE SET
                fsrs_card_json = excluded.fsrs_card_json,
                reps = excluded.reps,
                lapses = excluded.lapses,
                last_reviewed_at = excluded.last_reviewed_at,
                due_at = excluded.due_at
            """,
            (
                state.user_id,
                state.item_id,
                state.fsrs_card_json,
                state.reps,
                state.lapses,
                state.last_reviewed_at,
                state.due_at,
            ),
        )


def get_due_items(user_id: int, as_of_iso: str) -> list[UserItemState]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM user_item_state WHERE user_id = ? AND due_at <= ? ORDER BY due_at ASC",
            (user_id, as_of_iso),
        ).fetchall()
    return [_row_to_state(row) for row in rows]


def get_introduced_item_ids(user_id: int) -> set[int]:
    with get_connection() as conn:
        rows = conn.execute("SELECT item_id FROM user_item_state WHERE user_id = ?", (user_id,)).fetchall()
    return {row["item_id"] for row in rows}


def get_mastered_states(user_id: int, as_of_iso: str) -> list[UserItemState]:
    """Items already introduced and not currently due for review."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM user_item_state WHERE user_id = ? AND due_at > ? ORDER BY due_at ASC",
            (user_id, as_of_iso),
        ).fetchall()
    return [_row_to_state(row) for row in rows]


def get_chronic_issue_states(user_id: int, lapse_threshold: int = 2) -> list[UserItemState]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM user_item_state WHERE user_id = ? AND lapses >= ? ORDER BY lapses DESC",
            (user_id, lapse_threshold),
        ).fetchall()
    return [_row_to_state(row) for row in rows]
