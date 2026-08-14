import sqlite3
from pathlib import Path
import time
import asyncio
from typing import List, Tuple

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  key TEXT NOT NULL,
  ts INTEGER NOT NULL,
  value REAL
);
"""


class MetricsCache:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript(DB_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    async def insert(self, key: str, ts: int, value: float):
        await asyncio.to_thread(self._insert_sync, key, ts, value)

    def _insert_sync(self, key: str, ts: int, value: float):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("INSERT INTO metrics (key, ts, value) VALUES (?, ?, ?)", (key, ts, value))
            conn.commit()
            # prune older rows, keep last 200 per key
            conn.execute("DELETE FROM metrics WHERE id IN (SELECT id FROM metrics WHERE key = ? ORDER BY ts DESC LIMIT -1 OFFSET 200)", (key,))
            conn.commit()
        finally:
            conn.close()

    async def recent(self, key: str, limit: int = 30) -> List[Tuple[int, float]]:
        return await asyncio.to_thread(self._recent_sync, key, limit)

    def _recent_sync(self, key: str, limit: int):
        conn = sqlite3.connect(str(self.db_path))
        try:
            cur = conn.execute("SELECT ts, value FROM metrics WHERE key = ? ORDER BY ts DESC LIMIT ?", (key, limit))
            rows = cur.fetchall()
            # return in chronological order
            return [(r[0], r[1]) for r in reversed(rows)]
        finally:
            conn.close()
