from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources

from app.config import settings


def init_db() -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    schema = resources.files("app.db").joinpath("schema.sql").read_text()
    with get_connection() as conn:
        conn.executescript(schema)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
