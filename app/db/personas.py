from __future__ import annotations

import json
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.db.connection import get_connection
from app.db.models import Persona


def _row_to_persona(row: sqlite3.Row, interests: list[str]) -> Persona:
    return Persona(
        id=row["id"],
        target_lang=row["target_lang"],
        name=row["name"],
        origin=row["origin"],
        age=row["age"],
        background=row["background"],
        physical_description=row["physical_description"],
        psychological_profile=row["psychological_profile"],
        social_habits=row["social_habits"],
        explanation_style=row["explanation_style"],
        teaching_philosophy=row["teaching_philosophy"],
        correction_style=row["correction_style"],
        preferred_medium=row["preferred_medium"],
        vocabulary_strictness=row["vocabulary_strictness"],
        cultural_depth=row["cultural_depth"],
        timezone=row["timezone"],
        daily_routine=row["daily_routine"],
        free_hours=json.loads(row["free_hours_json"]),
        is_beginner_teacher=bool(row["is_beginner_teacher"]),
        interests=interests,
    )


def _interests_for(conn: sqlite3.Connection, persona_id: int) -> list[str]:
    rows = conn.execute("SELECT topic FROM persona_interests WHERE persona_id = ?", (persona_id,)).fetchall()
    return [row["topic"] for row in rows]


def create_persona(
    target_lang: str,
    name: str,
    origin: str,
    age: int,
    background: str,
    physical_description: str,
    psychological_profile: str,
    social_habits: str,
    explanation_style: str,
    teaching_philosophy: str,
    correction_style: str,
    preferred_medium: str,
    vocabulary_strictness: str,
    cultural_depth: str,
    timezone: str,
    daily_routine: str,
    free_hours: list[int],
    interests: list[str],
    is_beginner_teacher: bool = False,
) -> Persona:
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"not a valid IANA timezone: {timezone!r}") from exc
    if any(hour < 0 or hour > 23 for hour in free_hours):
        raise ValueError(f"free_hours must be in 0-23: {free_hours!r}")

    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO personas
                (target_lang, name, origin, age, background, physical_description,
                 psychological_profile, social_habits, explanation_style, teaching_philosophy,
                 correction_style, preferred_medium, vocabulary_strictness, cultural_depth,
                 timezone, daily_routine, free_hours_json, is_beginner_teacher)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_lang,
                name,
                origin,
                age,
                background,
                physical_description,
                psychological_profile,
                social_habits,
                explanation_style,
                teaching_philosophy,
                correction_style,
                preferred_medium,
                vocabulary_strictness,
                cultural_depth,
                timezone,
                daily_routine,
                json.dumps(free_hours),
                is_beginner_teacher,
            ),
        )
        persona_id = cur.lastrowid
        if persona_id is None:
            raise RuntimeError("insert into personas did not return a row id")
        conn.executemany(
            "INSERT INTO persona_interests (persona_id, topic) VALUES (?, ?)",
            [(persona_id, topic) for topic in interests],
        )
    persona = get_persona(persona_id)
    if persona is None:
        raise RuntimeError(f"failed to read back newly created persona {persona_id}")
    return persona


def get_persona(persona_id: int) -> Persona | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM personas WHERE id = ?", (persona_id,)).fetchone()
        if row is None:
            return None
        return _row_to_persona(row, _interests_for(conn, persona_id))


def list_personas(target_lang: str) -> list[Persona]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM personas WHERE target_lang = ? AND is_beginner_teacher = 0", (target_lang,)
        ).fetchall()
        return [_row_to_persona(row, _interests_for(conn, row["id"])) for row in rows]


def get_beginner_teacher_persona(target_lang: str) -> Persona | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM personas WHERE target_lang = ? AND is_beginner_teacher = 1", (target_lang,)
        ).fetchone()
        if row is None:
            return None
        return _row_to_persona(row, _interests_for(conn, row["id"]))


def delete_persona(persona_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM personas WHERE id = ?", (persona_id,))


def add_persona_interest(persona_id: int, topic: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO persona_interests (persona_id, topic) VALUES (?, ?) ON CONFLICT DO NOTHING",
            (persona_id, topic),
        )


def remove_persona_interest(persona_id: int, topic: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM persona_interests WHERE persona_id = ? AND topic = ?",
            (persona_id, topic),
        )


def update_persona_character(persona_id: int, daily_routine: str | None = None, background: str | None = None) -> None:
    """Updates the persona's own canonical character sheet - this is global (shared across every
    user talking to this persona), not scoped to one user's relationship with them. Only the
    fields actually passed get changed; `None` means "no change to this field"."""
    if daily_routine is None and background is None:
        return
    with get_connection() as conn:
        if daily_routine is not None:
            conn.execute("UPDATE personas SET daily_routine = ? WHERE id = ?", (daily_routine, persona_id))
        if background is not None:
            conn.execute("UPDATE personas SET background = ? WHERE id = ?", (background, persona_id))
