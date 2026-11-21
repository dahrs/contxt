from __future__ import annotations

import sqlite3

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
    interests: list[str],
    is_beginner_teacher: bool = False,
) -> Persona:
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO personas
                (target_lang, name, origin, age, background, physical_description,
                 psychological_profile, social_habits, explanation_style, teaching_philosophy,
                 correction_style, preferred_medium, vocabulary_strictness, cultural_depth,
                 is_beginner_teacher)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
