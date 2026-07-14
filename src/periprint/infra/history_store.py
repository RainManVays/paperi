from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from periprint.utils.paths import config_dir

_SCHEMA = """
CREATE TABLE IF NOT EXISTS history (
    id TEXT PRIMARY KEY,
    source_path TEXT NOT NULL,
    printer_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    error_message TEXT
)
"""


@dataclass
class HistoryEntry:
    id: str
    source_path: str
    printer_name: str
    status: str
    created_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None


class HistoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (config_dir() / "history.sqlite")
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)

    def record(self, entry: HistoryEntry) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO history
                    (id, source_path, printer_name, status, created_at, finished_at, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.source_path,
                    entry.printer_name,
                    entry.status,
                    entry.created_at.isoformat(),
                    entry.finished_at.isoformat() if entry.finished_at else None,
                    entry.error_message,
                ),
            )

    def list_recent(self, limit: int = 50) -> list[HistoryEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, source_path, printer_name, status, created_at, finished_at, error_message
                FROM history
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            HistoryEntry(
                id=row[0],
                source_path=row[1],
                printer_name=row[2],
                status=row[3],
                created_at=datetime.fromisoformat(row[4]),
                finished_at=datetime.fromisoformat(row[5]) if row[5] else None,
                error_message=row[6],
            )
            for row in rows
        ]
