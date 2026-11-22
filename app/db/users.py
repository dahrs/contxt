from __future__ import annotations

import sqlite3

from app.db.connection import get_connection
from app.db.models import User


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        username=row["username"],
        password_hash=row["password_hash"],
        display_name=row["display_name"],
        native_lang=row["native_lang"],
        target_lang=row["target_lang"],
        is_absolute_beginner=bool(row["is_absolute_beginner"]),
        email=row["email"],
        last_proactive_sent_at=row["last_proactive_sent_at"],
        created_at=row["created_at"],
    )


def create_user(
    username: str,
    password_hash: str,
    display_name: str,
    native_lang: str,
    target_lang: str,
    is_absolute_beginner: bool = False,
    email: str | None = None,
) -> User:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, display_name, native_lang, target_lang, "
            "is_absolute_beginner, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (username, password_hash, display_name, native_lang, target_lang, is_absolute_beginner, email),
        )
        user_id = cur.lastrowid
    if user_id is None:
        raise RuntimeError("insert into users did not return a row id")
    user = get_user_by_id(user_id)
    if user is None:
        raise RuntimeError(f"failed to read back newly created user {user_id}")
    return user


def get_user_by_username(username: str) -> User | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return _row_to_user(row) if row is not None else None


def get_user_by_id(user_id: int) -> User | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row is not None else None


def set_interests(user_id: int, topics_with_weight: dict[str, float]) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM interests WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO interests (user_id, topic, weight) VALUES (?, ?, ?)",
            [(user_id, topic, weight) for topic, weight in topics_with_weight.items()],
        )


def get_interests(user_id: int) -> dict[str, float]:
    with get_connection() as conn:
        rows = conn.execute("SELECT topic, weight FROM interests WHERE user_id = ?", (user_id,)).fetchall()
    return {row["topic"]: row["weight"] for row in rows}


def list_all_users() -> list[User]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM users").fetchall()
    return [_row_to_user(row) for row in rows]


def set_last_proactive_sent_at(user_id: int, timestamp: str) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE users SET last_proactive_sent_at = ? WHERE id = ?", (timestamp, user_id))
