"""
SQLite-backed persistent event store.

Replaces the in-memory event_log list. All inserts/queries go through this class.
The DB file is created next to config.yaml in the process working directory.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB_FILE = "events.db"

_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id          TEXT PRIMARY KEY,
    timestamp   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    ecgi        INTEGER,
    band        INTEGER,
    router_ctn  TEXT,
    message     TEXT NOT NULL,
    raw_json    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_timestamp  ON events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_event_type ON events (event_type);
CREATE INDEX IF NOT EXISTS idx_events_ecgi_band  ON events (ecgi, band);
CREATE INDEX IF NOT EXISTS idx_events_router_ctn ON events (router_ctn);
"""


class EventStore:

    def __init__(self, db_path: str = _DB_FILE):
        self._path = str(Path(db_path).resolve())
        self._conn: sqlite3.Connection = sqlite3.connect(
            self._path, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.executescript(_DDL)
        self._conn.commit()
        logger.info("EventStore opened: %s", self._path)

    # ── Write ──────────────────────────────────────────────────────────────────

    def insert(self, event: dict) -> None:
        gk = event.get("groupingKey")
        self._conn.execute(
            """
            INSERT OR IGNORE INTO events
                (id, timestamp, event_type, ecgi, band, router_ctn, message, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event["id"],
                event["timestamp"],
                event["eventType"],
                gk["ecgi"] if gk else None,
                gk["band"] if gk else None,
                event.get("routerCtn"),
                event.get("message", ""),
                json.dumps(event),
            ),
        )
        self._conn.commit()

    # ── Read ───────────────────────────────────────────────────────────────────

    def query_alerts(self, limit: int = 200) -> list[dict]:
        """AlertFeed용 — 최신순 limit건."""
        cur = self._conn.execute(
            "SELECT raw_json FROM events ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [json.loads(r[0]) for r in cur.fetchall()]

    def query_device_history(
        self,
        ctn: Optional[str] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict]:
        sql = "SELECT raw_json FROM events WHERE event_type NOT IN ('CELL_OVERLOAD','CELL_RECOVERY')"
        params: list = []
        if ctn:
            sql += " AND router_ctn = ?"
            params.append(ctn)
        if from_ts:
            sql += " AND timestamp >= ?"
            params.append(from_ts)
        if to_ts:
            sql += " AND timestamp <= ?"
            params.append(to_ts)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cur = self._conn.execute(sql, params)
        return [json.loads(r[0]) for r in cur.fetchall()]

    def query_cell_history(
        self,
        ecgi: Optional[int] = None,
        band: Optional[int] = None,
        from_ts: Optional[str] = None,
        to_ts: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict]:
        sql = "SELECT raw_json FROM events WHERE event_type IN ('CELL_OVERLOAD','CELL_RECOVERY')"
        params: list = []
        if ecgi is not None:
            sql += " AND ecgi = ?"
            params.append(ecgi)
        if band is not None:
            sql += " AND band = ?"
            params.append(band)
        if from_ts:
            sql += " AND timestamp >= ?"
            params.append(from_ts)
        if to_ts:
            sql += " AND timestamp <= ?"
            params.append(to_ts)
        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        cur = self._conn.execute(sql, params)
        return [json.loads(r[0]) for r in cur.fetchall()]

    # ── Admin ──────────────────────────────────────────────────────────────────

    def reset(self) -> int:
        """모든 이벤트 삭제. 삭제된 행 수 반환."""
        cur = self._conn.execute("DELETE FROM events")
        self._conn.commit()
        deleted = cur.rowcount
        self._conn.execute("VACUUM")
        logger.info("EventStore reset: %d rows deleted", deleted)
        return deleted

    def size(self) -> dict:
        """행 수와 파일 크기(bytes) 반환."""
        count = self._conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        try:
            file_bytes = Path(self._path).stat().st_size
        except OSError:
            file_bytes = 0
        return {"rows": count, "bytes": file_bytes}

    def close(self) -> None:
        self._conn.close()
