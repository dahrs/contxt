from __future__ import annotations

import sqlite3

from app.db.connection import get_connection
from app.db.memory import get_introduced_item_ids
from app.db.models import Milestone
from app.db.skills import list_skill_items


def _row_to_milestone(row: sqlite3.Row, prerequisite_ids: list[int]) -> Milestone:
    return Milestone(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        cefr_level=row["cefr_level"],
        prerequisite_ids=prerequisite_ids,
    )


def _prerequisite_ids(conn: sqlite3.Connection, milestone_id: int) -> list[int]:
    rows = conn.execute(
        "SELECT prerequisite_id FROM milestone_prerequisites WHERE milestone_id = ?", (milestone_id,)
    ).fetchall()
    return [row["prerequisite_id"] for row in rows]


def create_milestone(
    name: str, description: str, cefr_level: str, prerequisite_ids: list[int] | None = None
) -> Milestone:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO milestones (name, description, cefr_level) VALUES (?, ?, ?)",
            (name, description, cefr_level),
        )
        milestone_id = cur.lastrowid
        if milestone_id is None:
            raise RuntimeError("insert into milestones did not return a row id")
        conn.executemany(
            "INSERT INTO milestone_prerequisites (milestone_id, prerequisite_id) VALUES (?, ?)",
            [(milestone_id, prereq_id) for prereq_id in (prerequisite_ids or [])],
        )
    milestone = get_milestone(milestone_id)
    if milestone is None:
        raise RuntimeError(f"failed to read back newly created milestone {milestone_id}")
    return milestone


def get_milestone(milestone_id: int) -> Milestone | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM milestones WHERE id = ?", (milestone_id,)).fetchone()
        if row is None:
            return None
        return _row_to_milestone(row, _prerequisite_ids(conn, milestone_id))


def list_milestones() -> list[Milestone]:
    """Language-independent - the milestone sequence itself doesn't vary by target_lang, only
    the skill_items that deliver each one do."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM milestones").fetchall()
        return [_row_to_milestone(row, _prerequisite_ids(conn, row["id"])) for row in rows]


def get_milestone_item_counts(native_lang: str, target_lang: str) -> dict[int, int]:
    """Total skill_items per milestone, for this (native_lang, target_lang) pair - content is
    pair-specific (see app/curriculum/language_comparison.py), not just target-language-specific -
    the denominator of an introduced-ratio used to decide whether a milestone's prerequisites are
    sufficiently covered."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT milestone_id, COUNT(*) AS n FROM skill_items WHERE native_lang = ? AND target_lang = ? "
            "GROUP BY milestone_id",
            (native_lang, target_lang),
        ).fetchall()
    return {row["milestone_id"]: row["n"] for row in rows}


def get_introduced_counts_by_milestone(user_id: int, native_lang: str, target_lang: str) -> dict[int, int]:
    """Same shape as get_milestone_item_counts, but only this user's introduced items - the
    numerator of the introduced-ratio. Built in Python from get_introduced_item_ids, same
    approach already used for persona engagement-token counting."""
    introduced_ids = get_introduced_item_ids(user_id)
    counts: dict[int, int] = {}
    for item in list_skill_items(native_lang, target_lang):
        if item.id in introduced_ids:
            counts[item.milestone_id] = counts.get(item.milestone_id, 0) + 1
    return counts
