from __future__ import annotations

import sqlite3

from app.db.connection import get_connection
from app.db.models import SkillItem, SkillItemType


def _row_to_skill_item(row: sqlite3.Row, prerequisite_ids: list[int]) -> SkillItem:
    return SkillItem(
        id=row["id"],
        type=row["type"],
        target_lang=row["target_lang"],
        content=row["content"],
        level=row["level"],
        category=row["category"],
        prerequisite_ids=prerequisite_ids,
    )


def _prerequisite_ids(conn: sqlite3.Connection, item_id: int) -> list[int]:
    rows = conn.execute("SELECT prerequisite_id FROM skill_item_prerequisites WHERE item_id = ?", (item_id,)).fetchall()
    return [row["prerequisite_id"] for row in rows]


def create_skill_item(
    item_type: SkillItemType,
    target_lang: str,
    content: str,
    level: str,
    category: str | None = None,
    prerequisite_ids: list[int] | None = None,
) -> SkillItem:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO skill_items (type, target_lang, content, level, category) VALUES (?, ?, ?, ?, ?)",
            (item_type, target_lang, content, level, category),
        )
        item_id = cur.lastrowid
        if item_id is None:
            raise RuntimeError("insert into skill_items did not return a row id")
        conn.executemany(
            "INSERT INTO skill_item_prerequisites (item_id, prerequisite_id) VALUES (?, ?)",
            [(item_id, prereq_id) for prereq_id in (prerequisite_ids or [])],
        )
    item = get_skill_item(item_id)
    if item is None:
        raise RuntimeError(f"failed to read back newly created skill item {item_id}")
    return item


def get_skill_item(item_id: int) -> SkillItem | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM skill_items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            return None
        return _row_to_skill_item(row, _prerequisite_ids(conn, item_id))


def list_skill_items(target_lang: str) -> list[SkillItem]:
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM skill_items WHERE target_lang = ?", (target_lang,)).fetchall()
        return [_row_to_skill_item(row, _prerequisite_ids(conn, row["id"])) for row in rows]
